"""
Analytics computation tasks.

The Task Library Growth chart on the homepage is fed by the
`task_growth_metrics` table, which this module populates. The historical
data is reconstructed by walking the git history of each codebundle's
`runbook.robot` / `sli.robot` and recording the first commit where each
*currently-existing* task name appears.

Why per-task attribution (and not per-codebundle "directory created" date)?
-------------------------------------------------------------------------
The previous implementation timestamped every codebundle once — using the
commit that first added the bundle's directory — and then attributed the
codebundle's *current* `task_count + sli_count` to that single date. That
produced a smooth-but-wrong ramp: 100 tasks added to existing codebundles
last month were back-dated to those codebundles' original creation months
(sometimes years ago), so genuine bursts of growth were invisible on the
chart. We now bucket by per-task first-introduction date so recent
additions to long-lived bundles surface in the correct month.

Semantic note
-------------
"Cumulative at month M" = count of CURRENTLY-existing tasks/SLIs whose
first appearance in git history is on-or-before M. Tasks renamed in git
are counted from the rename commit (the new name didn't exist before
that). Tasks deleted from the codebase don't appear in this curve at all.
This keeps the chart monotonic over time and stable across re-runs.
"""
import logging
import tempfile
import os
import subprocess
import time
from datetime import datetime, timedelta
from collections import defaultdict
from typing import Dict, Set

from app.tasks.celery_app import celery_app
from app.core.database import SessionLocal
from app.core.visibility import PUBLIC_VISIBILITY
from app.models import CodeCollection, Codebundle, TaskGrowthMetric

logger = logging.getLogger(__name__)


# Robot Framework section headers that contain task definitions.
# (`*** Tasks ***` is the modern spelling, `*** Test Cases ***` is the
# legacy spelling; both are accepted by the runner.)
_TASK_SECTION_NAMES = frozenset({"tasks", "test cases"})


def _extract_task_names_from_robot(content: str) -> Set[str]:
    """
    Parse a Robot Framework file and return the set of task/test-case
    names defined in it.

    A task name in Robot Framework is any line inside a `*** Tasks ***`
    (or `*** Test Cases ***`) section that:
      - starts at column 0 (no leading whitespace),
      - is not a comment (`#`),
      - is not itself a section header.

    Lines belonging to the task body are indented and therefore ignored.
    """
    names: Set[str] = set()
    in_task_section = False
    for raw_line in content.splitlines():
        if not raw_line.strip():
            continue
        # Section headers can have leading spaces in some files; normalize.
        stripped = raw_line.lstrip()
        if stripped.startswith("***"):
            header = stripped.strip("* \t").lower()
            in_task_section = header in _TASK_SECTION_NAMES
            continue
        if not in_task_section:
            continue
        # Task body lines are indented; comments start with '#'.
        if raw_line[0] in (" ", "\t"):
            continue
        if stripped.startswith("#"):
            continue
        names.add(stripped.rstrip())
    return names


def _first_introduction_dates(
    repo_path: str,
    file_path: str,
    target_names: Set[str],
) -> Dict[str, datetime]:
    """
    For each name in `target_names` that exists in `file_path` at some
    point in git history, return the timestamp of the earliest commit
    where it appears.

    Walks commits oldest-first; stops as soon as every target name has
    been attributed. Names that never appear in any committed version
    are simply omitted from the result.
    """
    if not target_names:
        return {}

    log = subprocess.run(
        ["git", "log", "--reverse", "--format=%ct|%H", "--", file_path],
        cwd=repo_path,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if log.returncode != 0 or not log.stdout.strip():
        return {}

    seen: Dict[str, datetime] = {}
    remaining = set(target_names)
    for entry in log.stdout.strip().splitlines():
        if not remaining:
            break
        try:
            ts_str, sha = entry.split("|", 1)
            commit_time = datetime.fromtimestamp(int(ts_str))
        except (ValueError, OSError):
            continue

        show = subprocess.run(
            ["git", "show", f"{sha}:{file_path}"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if show.returncode != 0:
            continue

        names_at_commit = _extract_task_names_from_robot(show.stdout)
        newly_seen = remaining & names_at_commit
        if newly_seen:
            for name in newly_seen:
                seen[name] = commit_time
            remaining -= newly_seen
    return seen


@celery_app.task(bind=True)
def compute_task_growth_analytics(self):
    """
    Recompute monthly cumulative task-library growth and persist to
    `task_growth_metrics`.

    Algorithm:
      1. For every PUBLIC, active codecollection: clone the repo.
      2. For every active codebundle in that codecollection: union the
         current task names (`cb.tasks`) and SLI names (`cb.slis`).
      3. Walk the git history of the codebundle's `runbook.robot` and
         `sli.robot` and find the earliest commit containing each name.
      4. Bucket each (codebundle, name) introduction date by month.
      5. Generate a cumulative series for the last 18 months and the
         historical pre-window total. Store in `task_growth_metrics`.

    Excludes:
      - CodeCollections with `visibility = 'hidden'` (PAPI-only entries
        like internal/private codecollections — they must never feed any
        public-audience surface, including this chart).
      - Inactive codecollections / inactive codebundles.
    """
    db = SessionLocal()
    start_time = time.time()

    try:
        logger.info(
            f"Starting task growth analytics computation (task {self.request.id})"
        )

        eighteen_months_ago = datetime.now() - timedelta(days=18 * 30)

        # Only PUBLIC, active codecollections and their active codebundles.
        # Hidden codecollections exist for PAPI but must not skew public
        # registry analytics. See app.core.visibility for context.
        codebundles = (
            db.query(Codebundle)
            .join(CodeCollection)
            .filter(
                Codebundle.is_active.is_(True),
                CodeCollection.is_active.is_(True),
                CodeCollection.visibility == PUBLIC_VISIBILITY,
            )
            .all()
        )

        logger.info(
            f"Analyzing {len(codebundles)} codebundles "
            "(public + active) for per-task introduction dates"
        )

        # Group by collection so each repo is cloned exactly once.
        collections_map: Dict[int, Dict] = {}
        for cb in codebundles:
            entry = collections_map.setdefault(
                cb.codecollection_id,
                {"collection": cb.codecollection, "codebundles": []},
            )
            entry["codebundles"].append(cb)

        # `attribution_dates` is a flat list of (introduction_date) entries,
        # one per (codebundle, name). Each contributes exactly 1 to its
        # bucket month; the cumulative line is the running sum.
        attribution_dates = []
        per_name_attributed = 0
        per_name_fallback = 0

        with tempfile.TemporaryDirectory() as tmp_dir:
            for coll_id, data in collections_map.items():
                collection: CodeCollection = data["collection"]
                bundles = data["codebundles"]
                repo_path = os.path.join(tmp_dir, collection.slug)

                logger.info(
                    f"Cloning {collection.git_url} to attribute task introductions"
                )
                clone = subprocess.run(
                    [
                        "git",
                        "clone",
                        "--quiet",
                        "--no-checkout",
                        "--filter=blob:none",
                        collection.git_url,
                        repo_path,
                    ],
                    capture_output=True,
                    text=True,
                    timeout=120,
                )
                clone_ok = clone.returncode == 0

                if not clone_ok:
                    logger.warning(
                        f"Clone failed for {collection.slug}: "
                        f"{(clone.stderr or '').strip()[:200]}"
                    )

                for cb in bundles:
                    current_task_names = set(cb.tasks or [])
                    current_sli_names = set(cb.slis or [])
                    all_names = current_task_names | current_sli_names
                    if not all_names:
                        continue

                    # Map each name to the most likely file it lives in.
                    # We try runbook first for tasks, sli for SLIs, and
                    # fall back to "either file" to be tolerant of layout
                    # drift. Files are repo-relative because that's how
                    # git log expects them.
                    runbook_rel = (cb.runbook_path or "").lstrip("/") or None
                    sli_rel = (cb.sli_path or "").lstrip("/") or None

                    # Collect introduction dates per name, preferring the
                    # canonical file but falling back to the other if the
                    # name only shows up there.
                    found: Dict[str, datetime] = {}
                    if clone_ok:
                        if runbook_rel:
                            found.update(
                                _first_introduction_dates(
                                    repo_path, runbook_rel, current_task_names
                                )
                            )
                        if sli_rel:
                            found.update(
                                _first_introduction_dates(
                                    repo_path, sli_rel, current_sli_names
                                )
                            )
                        # Edge case: a name we didn't find in its canonical
                        # file might exist in the other one (some bundles
                        # mix tasks+slis in a single .robot historically).
                        missing = all_names - set(found.keys())
                        if missing and runbook_rel and sli_rel:
                            for fallback_path in (sli_rel, runbook_rel):
                                if not missing:
                                    break
                                extra = _first_introduction_dates(
                                    repo_path, fallback_path, missing
                                )
                                found.update(extra)
                                missing -= set(extra.keys())

                    for name in all_names:
                        if name in found:
                            attribution_dates.append(found[name])
                            per_name_attributed += 1
                        else:
                            # Couldn't attribute via git — fall back to the
                            # codebundle's database created_at, which is at
                            # worst as wrong as the old algorithm was.
                            fallback = cb.created_at or datetime.utcnow()
                            attribution_dates.append(fallback)
                            per_name_fallback += 1

        if not attribution_dates:
            logger.warning("No codebundle data found")
            return {"status": "no_data", "message": "No codebundles found"}

        attribution_dates.sort()

        # Bucket by calendar month.
        monthly_data: Dict[str, int] = defaultdict(int)
        for ts in attribution_dates:
            month_key = ts.strftime("%Y-%m-01")
            monthly_data[month_key] += 1

        months = []
        cumulative = []

        start_month = eighteen_months_ago.replace(day=1)
        latest = datetime.now().replace(day=1)

        # Pre-window cumulative (everything older than the visible range).
        running_total = 0
        earliest = attribution_dates[0].replace(day=1)
        cursor = earliest
        while cursor < start_month:
            running_total += monthly_data.get(cursor.strftime("%Y-%m-01"), 0)
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)

        cursor = start_month
        while cursor <= latest:
            month_key = cursor.strftime("%Y-%m-01")
            running_total += monthly_data.get(month_key, 0)
            months.append(month_key)
            cumulative.append(running_total)
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)

        result_data = {
            "months": months,
            "cumulative": cumulative,
            "total_tasks": running_total,
        }

        duration = int(time.time() - start_time)

        db.query(TaskGrowthMetric).filter(
            TaskGrowthMetric.metric_type == "monthly_growth",
            TaskGrowthMetric.time_period == "18_months",
        ).delete()

        attributed_pct = (
            int(100 * per_name_attributed / (per_name_attributed + per_name_fallback))
            if (per_name_attributed + per_name_fallback)
            else 0
        )

        metric = TaskGrowthMetric(
            metric_type="monthly_growth",
            time_period="18_months",
            data=result_data,
            computation_duration_seconds=duration,
            codebundles_analyzed=len(codebundles),
            notes=(
                f"Per-task git attribution across {len(codebundles)} codebundles "
                f"in {len(collections_map)} public codecollections; "
                f"{per_name_attributed} names dated from git, "
                f"{per_name_fallback} fell back to codebundle.created_at "
                f"({attributed_pct}% git-attributed)"
            ),
        )

        db.add(metric)
        db.commit()

        logger.info(
            f"Task growth analytics computed successfully in {duration}s: "
            f"{running_total} total tasks; {per_name_attributed} git-attributed, "
            f"{per_name_fallback} fallback"
        )

        return {
            "status": "success",
            "duration_seconds": duration,
            "codebundles_analyzed": len(codebundles),
            "names_git_attributed": per_name_attributed,
            "names_fallback_attributed": per_name_fallback,
            "total_tasks": running_total,
            "months_generated": len(months),
        }

    except Exception:
        # logger.exception captures the full traceback. Bare `raise`
        # re-throws so Celery marks the task FAILURE — task_executions
        # then records error_message + traceback via task_monitor (see
        # task_failure_handler in celery_app.py).
        logger.exception("Error computing task growth analytics")
        db.rollback()
        raise
    finally:
        db.close()
