"""
Registry Task System - Sync and Parse Collections/Codebundles

This is the CANONICAL code path for syncing and parsing codebundles.
All tasks here use the shared Celery app from celery_app.py.
"""
import os
import yaml
import tempfile
import logging
import subprocess
from typing import Dict, Any, List, Optional
from datetime import datetime
from git import Repo
import requests

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import CodeCollection, Codebundle, RawRepositoryData
from app.models.version import CodeCollectionVersion

logger = logging.getLogger(__name__)

# Use the shared Celery app (single instance for the entire application)
from app.tasks.celery_app import celery_app

def _create_display_name(name: str) -> str:
    """Create a display name from a codebundle name"""
    import re
    display_words = []
    words = re.split(r'[-_]', name)
    
    for word in words:
        if word:
            camel_words = re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)', word)
            if camel_words:
                display_words.extend([w.capitalize() for w in camel_words])
            else:
                display_words.append(word.capitalize())
    
    return ' '.join(display_words)

def _parse_robot_file_content(content: str, file_path: str, collection_slug: str = None) -> Optional[Dict[str, Any]]:
    """Parse Robot Framework file content using the WORKING parser from generate_registry.py"""
    from app.tasks.fixed_parser import parse_robot_file_content
    return parse_robot_file_content(content, file_path, collection_slug)


def _validate_git_url(git_url: str, collection_slug: str) -> Optional[str]:
    """Sanity-check a CC's git_url at YAML ingestion time.

    Returns None if the URL resolves (HTTP 200/301/302), or an
    error string if it doesn't. The check is intentionally lenient:

      - HEAD before GET (cheap; GitHub returns the same status codes).
      - Short timeout (5s) — sync_all_collections_task runs ~30 CCs and
        we don't want one DNS hang to stall the whole sync.
      - Network errors are reported but never fatal: a transient outage
        shouldn't make a sync fail. We log + collect the error and let
        the rest of the task continue.

    This is the guard that would have caught the stewartshea typo
    (`rw-cli-codecollectionn`) at ingestion time, before image-sync
    started silently skipping the bad entry.
    """
    if not git_url:
        return "missing git_url"
    if not git_url.startswith(("http://", "https://")):
        return f"git_url {git_url!r} is not an http(s) URL"
    try:
        resp = requests.head(git_url, allow_redirects=True, timeout=5)
        if resp.status_code in (200, 301, 302):
            return None
        if resp.status_code == 404:
            return (
                f"git_url returned 404 — repository does not exist or is "
                f"private without auth (got {git_url})"
            )
        return f"git_url returned HTTP {resp.status_code} for {git_url}"
    except requests.RequestException as e:
        return f"git_url request failed: {type(e).__name__}: {e}"

@celery_app.task(bind=True)
def sync_all_collections_task(self):
    """
    Sync all collections from YAML file:
    - Load codecollections.yaml
    - Create/update CodeCollection records in DB
    - Clone repositories to temp directory for parsing

    NOT updated here: `image_registry`. That field is not a column on
    CodeCollection; image refs are stored per-version on
    CodeCollectionVersion by `sync_image_tags_task`. That task reads
    `image_registry` directly from codecollections.yaml on every run, so
    edits to the YAML's `image_registry` field take effect the next time
    `sync_image_tags_task` runs — no `CodeCollection` row update is
    needed (or possible) here. See docs/CCV.md for the image-catalog
    pipeline.
    """
    try:
        logger.info(f"Starting sync_all_collections_task {self.request.id}")

        # Load YAML. Missing config is a hard failure — raise so the task
        # is recorded as FAILURE in Celery + task_executions, rather than
        # silently returning SUCCESS with an error payload that nobody
        # checks. See AGENTS.md "task error handling".
        yaml_path = settings.CODECOLLECTIONS_FILE
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"codecollections.yaml not found at {yaml_path}")

        with open(yaml_path, 'r') as file:
            yaml_data = yaml.safe_load(file)
        
        collections_data = yaml_data.get('codecollections', [])
        logger.info(f"Loaded {len(collections_data)} collections from YAML")

        collections_synced = 0
        # Collect per-CC ingestion warnings so the task result surfaces
        # them in one place (task_executions.result), instead of forcing
        # operators to scrape worker logs. Non-fatal: a single CC with a
        # bad git_url shouldn't block the rest of the sync.
        ingestion_warnings: List[Dict[str, str]] = []
        db = SessionLocal()

        try:
            for collection_data in collections_data:
                collection_slug = collection_data.get('slug')
                git_url = collection_data.get('git_url')

                if not collection_slug or not git_url:
                    logger.warning(f"Skipping collection with missing slug or git_url")
                    ingestion_warnings.append({
                        "slug": collection_slug or "<unknown>",
                        "error": "missing slug or git_url in codecollections.yaml",
                    })
                    continue

                # Validate git_url is reachable. This catches typos in
                # codecollections.yaml (e.g. `rw-cli-codecollectionn`)
                # at the earliest possible point, instead of letting
                # them silently break image-sync and other downstream
                # consumers. Non-fatal — we still write the row so the
                # admin UI surfaces the CC alongside its error.
                url_err = _validate_git_url(git_url, collection_slug)
                if url_err:
                    logger.warning(f"[{collection_slug}] git_url validation failed: {url_err}")
                    ingestion_warnings.append({
                        "slug": collection_slug,
                        "git_url": git_url,
                        "error": url_err,
                    })

                # Create/update collection in DB
                collection = db.query(CodeCollection).filter(
                    CodeCollection.slug == collection_slug
                ).first()
                
                # Visibility defaults to 'public' if omitted; only ever
                # take on the values declared in YAML so a CC can be
                # toggled hidden/public by re-deploying config alone.
                visibility = collection_data.get('visibility', 'public')
                if visibility not in ('public', 'hidden'):
                    logger.warning(
                        f"Unknown visibility {visibility!r} for {collection_slug}, defaulting to 'public'"
                    )
                    visibility = 'public'

                # `last_synced` is OWNED by this task. It means
                # "when was this CC last (re-)ingested from
                # codecollections.yaml". Per-version image refreshes
                # (sync_image_tags_task, every 5 min) and stats reads
                # do NOT bump it — only an actual YAML→DB sync does.
                now = datetime.utcnow()

                if not collection:
                    collection = CodeCollection(
                        name=collection_data.get('name', collection_slug),
                        slug=collection_slug,
                        git_url=git_url,
                        description=collection_data.get('description', ''),
                        owner=collection_data.get('owner', ''),
                        owner_email=collection_data.get('owner_email', ''),
                        owner_icon=collection_data.get('owner_icon', ''),
                        git_ref=collection_data.get('git_ref', 'main'),
                        visibility=visibility,
                        is_active=True,
                        last_synced=now,
                    )
                    db.add(collection)
                    logger.info(f"Created collection: {collection_slug} (visibility={visibility})")
                else:
                    collection.name = collection_data.get('name', collection_slug)
                    collection.git_url = git_url
                    collection.description = collection_data.get('description', '')
                    collection.visibility = visibility
                    collection.is_active = True
                    collection.last_synced = now
                    logger.info(f"Updated collection: {collection_slug} (visibility={visibility})")
                
                db.commit()
                collections_synced += 1
            
            logger.info(
                f"Synced {collections_synced} collections "
                f"({len(ingestion_warnings)} ingestion warning(s))"
            )
            return {
                "status": "success",
                "collections_synced": collections_synced,
                "ingestion_warnings": ingestion_warnings,
            }

        finally:
            db.close()

    except Exception:
        # logger.exception captures the full traceback into the log.
        # The bare `raise` re-throws the original exception so Celery
        # marks the task FAILURE (which task_failure_handler in
        # celery_app.py persists to task_executions.error_message +
        # task_executions.traceback via task_monitor.update_task_status).
        logger.exception("sync_all_collections_task failed")
        raise

@celery_app.task(bind=True)
def parse_all_codebundles_task(self):
    """
    Parse all codebundles from collections:
    - Clone each collection repository
    - Parse robot files and create/update Codebundle records
    - Extract tasks, metadata, discovery config
    """
    try:
        logger.info(f"Starting parse_all_codebundles_task {self.request.id}")
        
        db = SessionLocal()
        codebundles_created = 0
        codebundles_updated = 0
        
        try:
            collections = db.query(CodeCollection).filter(CodeCollection.is_active == True).all()
            logger.info(f"Found {len(collections)} active collections to parse")
            
            with tempfile.TemporaryDirectory() as tmp_dir:
                for collection in collections:
                    try:
                        # Clone repository
                        repo_path = os.path.join(tmp_dir, collection.slug)
                        logger.info(f"Cloning {collection.git_url} to {repo_path}")
                        
                        try:
                            Repo.clone_from(collection.git_url, repo_path)
                        except Exception as clone_err:
                            logger.error(f"Failed to clone {collection.git_url}: {clone_err}")
                            continue
                        
                        # Find and parse codebundles
                        codebundles_dir = os.path.join(repo_path, 'codebundles')
                        if not os.path.exists(codebundles_dir):
                            logger.warning(f"No codebundles directory in {collection.slug}")
                            continue
                        
                        for bundle_name in os.listdir(codebundles_dir):
                            bundle_path = os.path.join(codebundles_dir, bundle_name)
                            if not os.path.isdir(bundle_path):
                                continue
                            
                            runbook_path = os.path.join(bundle_path, 'runbook.robot')
                            sli_path = os.path.join(bundle_path, 'sli.robot')
                            
                            has_runbook = os.path.exists(runbook_path)
                            has_sli = os.path.exists(sli_path)
                            
                            if not has_runbook and not has_sli:
                                continue
                            
                            # Parse robot files
                            runbook_parsed = None
                            if has_runbook:
                                with open(runbook_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                relative_path = f"codebundles/{bundle_name}/runbook.robot"
                                runbook_parsed = _parse_robot_file_content(content, relative_path, collection.slug)
                            
                            sli_parsed = None
                            if has_sli:
                                with open(sli_path, 'r', encoding='utf-8') as f:
                                    content = f.read()
                                relative_path = f"codebundles/{bundle_name}/sli.robot"
                                sli_parsed = _parse_robot_file_content(content, relative_path, collection.slug)
                            
                            primary_parsed = runbook_parsed or sli_parsed
                            if not primary_parsed:
                                continue
                            
                            # Extract tasks
                            taskset_tasks = runbook_parsed.get('tasks', []) if runbook_parsed else []
                            sli_tasks = sli_parsed.get('tasks', []) if sli_parsed else []
                            
                            support_tags = list(set(
                                (runbook_parsed.get('support_tags', []) if runbook_parsed else []) +
                                (sli_parsed.get('support_tags', []) if sli_parsed else [])
                            ))
                            
                            # Read README
                            readme_content = ""
                            readme_path_file = os.path.join(bundle_path, "README.md")
                            if os.path.exists(readme_path_file):
                                with open(readme_path_file, 'r', encoding='utf-8') as f:
                                    readme_content = f.read()
                            
                            # Create/update codebundle
                            existing = db.query(Codebundle).filter(
                                Codebundle.slug == primary_parsed['slug'],
                                Codebundle.codecollection_id == collection.id
                            ).first()
                            
                            runbook_source_url = f"{collection.git_url.rstrip('.git')}/tree/main/codebundles/{bundle_name}"
                            
                            # Get git date
                            git_date = _get_git_last_commit_date(repo_path, f"codebundles/{bundle_name}")
                            
                            if existing:
                                existing.name = primary_parsed.get('name', bundle_name)
                                existing.display_name = primary_parsed.get('display_name', bundle_name)
                                existing.description = primary_parsed.get('description', '')
                                existing.doc = primary_parsed.get('doc', '')
                                existing.readme = readme_content
                                existing.author = primary_parsed.get('author', '')
                                existing.support_tags = support_tags
                                existing.tasks = taskset_tasks
                                existing.slis = sli_tasks
                                existing.task_count = len(taskset_tasks)
                                existing.sli_count = len(sli_tasks)
                                existing.runbook_source_url = runbook_source_url
                                existing.user_variables = primary_parsed.get('user_variables', [])
                                existing.data_classifications = (
                                    runbook_parsed.get('data_classifications', {}) if runbook_parsed else {}
                                )  # Extract user variables
                                if git_date:
                                    existing.git_updated_at = git_date
                                codebundles_updated += 1
                            else:
                                codebundle = Codebundle(
                                    name=primary_parsed.get('name', bundle_name),
                                    slug=primary_parsed['slug'],
                                    display_name=primary_parsed.get('display_name', bundle_name),
                                    description=primary_parsed.get('description', ''),
                                    doc=primary_parsed.get('doc', ''),
                                    readme=readme_content,
                                    author=primary_parsed.get('author', ''),
                                    support_tags=support_tags,
                                    tasks=taskset_tasks,
                                    slis=sli_tasks,
                                    task_count=len(taskset_tasks),
                                    sli_count=len(sli_tasks),
                                    codecollection_id=collection.id,
                                    runbook_source_url=runbook_source_url,
                                    user_variables=primary_parsed.get('user_variables', []),
                                    data_classifications=(
                                        runbook_parsed.get('data_classifications', {}) if runbook_parsed else {}
                                    ),
                                    is_active=True,
                                    git_updated_at=git_date
                                )
                                db.add(codebundle)
                                codebundles_created += 1
                            
                            db.commit()
                            
                    except Exception as e:
                        logger.error(f"Error processing collection {collection.slug}: {e}")
                        continue
            
            logger.info(f"Parsed codebundles: {codebundles_created} created, {codebundles_updated} updated")
            return {
                "status": "success",
                "codebundles_created": codebundles_created,
                "codebundles_updated": codebundles_updated
            }

        finally:
            db.close()

    except Exception:
        logger.exception("parse_all_codebundles_task failed")
        raise

def _get_git_last_commit_date(repo_path: str, folder_path: str) -> Optional[datetime]:
    """Get the last commit date for files in a folder, excluding meta.yml"""
    import subprocess
    try:
        result = subprocess.run(
            ['git', 'log', '-1', '--format=%ct', '--', folder_path,
             f':(exclude){folder_path}/meta.yml',
             f':(exclude){folder_path}/meta.yaml'],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            timestamp = int(result.stdout.strip())
            return datetime.fromtimestamp(timestamp)
    except Exception as e:
        logger.warning(f"Could not get git date for {folder_path}: {e}")
    return None

def _parse_runwhen_discovery(db, collection_slug: str, codebundle_name: str) -> Dict[str, Any]:
    """Parse .runwhen directory for discovery configuration"""
    return {}
