"""
CodeBundle Intake Wizard Router

Guides users through a conversational flow to define CodeBundle requirements,
searches existing coverage via the MCP server, and files structured issues
to the codebundle-farm repository.
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import requests

from app.core.config import settings
from app.services.github_auth import get_github_auth
from app.services.mcp_client import get_mcp_client, MCPError

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/intake", tags=["intake"])

CODEBUNDLE_FARM_REPO = settings.GITHUB_INTAKE_REPO

PLATFORMS = [
    "Kubernetes", "AWS", "Azure", "GCP", "Linux",
    "Database", "Terraform", "Docker", "GitHub", "Other",
]


# =============================================================================
# Request/Response Models
# =============================================================================

class SearchRequest(BaseModel):
    """Step 1–2: User describes their need and we search for existing coverage."""
    description: str
    platform: Optional[str] = None


class SearchMatch(BaseModel):
    display_name: str
    slug: str
    collection_slug: str
    platform: str
    description: str
    tasks: List[str] = []
    tags: List[str] = []
    relevance_score: float = 0.0
    source_url: str = ""


class ExistingRequest(BaseModel):
    number: int
    title: str
    url: str
    created_at: str


class SearchResponse(BaseModel):
    matches: List[SearchMatch]
    existing_requests: List[ExistingRequest]
    suggested_platform: str
    query_used: str


class DesignSpecDraft(BaseModel):
    """Legacy: structured Design Spec. Kept for backwards compat; minimal intake uses SubmitRequest."""
    codebundle_name: str
    target_collection: str = "rw-cli-codecollection"
    platform: str = ""
    purpose: str
    tasks: List[Dict[str, str]] = []
    resource_types: List[str] = []
    env_vars: List[Dict[str, str]] = []
    secrets: List[Dict[str, str]] = []
    tools_required: List[str] = []
    related_bundles: List[str] = []
    user_description: str
    coverage_notes: str = ""


class SubmitRequest(BaseModel):
    """Minimal intake: title + description required. Search results included for the designer."""
    title: str
    description: str
    extra_context: Optional[str] = None
    contact_email: Optional[str] = None
    contact_ok: Optional[bool] = False
    matches: List[SearchMatch] = []
    existing_requests: List[ExistingRequest] = []


class SubmitResponse(BaseModel):
    issue_url: str
    issue_number: int
    message: str


# =============================================================================
# Endpoints
# =============================================================================

@router.get("/platforms")
async def get_platforms():
    """Return the list of supported platforms for the wizard."""
    return {"platforms": PLATFORMS}


@router.post("/search", response_model=SearchResponse)
async def search_existing_coverage(req: SearchRequest):
    """
    Search for existing CodeBundles and open requests that match the
    user's description. Called during wizard steps 1–3.
    """
    mcp = get_mcp_client()
    matches: List[SearchMatch] = []
    existing_requests: List[ExistingRequest] = []
    suggested_platform = req.platform or ""

    # Search existing CodeBundles via MCP
    try:
        if await mcp.is_available():
            args: Dict[str, Any] = {"query": req.description, "max_results": 8}
            if req.platform:
                args["platform"] = req.platform

            result = await mcp.call_tool("find_codebundle", args)
            if result and result.get("success"):
                parsed = _parse_codebundle_results(result.get("result", ""))
                matches = parsed

            # Check for open requests
            search_term = req.platform or req.description.split()[0] if req.description else ""
            if search_term:
                req_result = await mcp.call_tool("check_existing_requests", {"search_term": search_term})
                if req_result and req_result.get("success"):
                    existing_requests = _parse_existing_requests(req_result.get("result", ""))
    except MCPError as e:
        logger.warning(f"MCP search failed, continuing without results: {e}")
    except Exception as e:
        logger.warning(f"Unexpected error during MCP search: {e}")

    # Infer platform from description if not provided
    if not suggested_platform:
        suggested_platform = _infer_platform(req.description)

    return SearchResponse(
        matches=matches,
        existing_requests=existing_requests,
        suggested_platform=suggested_platform,
        query_used=req.description,
    )


@router.post("/generate-spec", response_model=DesignSpecDraft)
async def generate_design_spec(
    description: str,
    platform: str,
    tasks_description: str,
    resource_types: str = "",
    tools: str = "",
):
    """
    Generate a draft Design Spec from user-provided information.
    This is a helper that pre-fills the spec structure; the frontend
    lets the user refine it before submission.
    """
    task_list = [t.strip() for t in tasks_description.split("\n") if t.strip()]
    tasks = [{"name": _slugify_task(t), "checks": t} for t in task_list]
    resources = [r.strip() for r in resource_types.split(",") if r.strip()]
    tool_list = [t.strip() for t in tools.split(",") if t.strip()]

    name = _generate_bundle_name(platform, description)

    return DesignSpecDraft(
        codebundle_name=name,
        platform=platform,
        purpose=description,
        tasks=tasks,
        resource_types=resources,
        tools_required=tool_list,
        user_description=description,
    )


@router.post("/submit", response_model=SubmitResponse)
async def submit_intake(req: SubmitRequest):
    """
    Create a GitHub Issue in codebundle-farm. Requires only title + description.
    Search results (matches, existing_requests) are included in the issue body
    so the designer can see existing coverage and avoid duplication.
    """
    gh = get_github_auth()
    if not gh.is_configured:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub integration not configured. Set GITHUB_APP_ID/GITHUB_APP_PRIVATE_KEY or GITHUB_TOKEN.",
        )

    title = f"[intake] {req.title[:100]}"
    body = _build_minimal_issue_body(req)
    platform = _infer_platform(req.description)
    labels = ["intake", "needs-architect"]
    if platform:
        labels.append(f"platform:{platform.lower()}")

    try:
        api_url = f"https://api.github.com/repos/{CODEBUNDLE_FARM_REPO}/issues"
        headers = {
            **gh.auth_header(),
            "Accept": "application/vnd.github.v3+json",
        }
        issue_data = {"title": title, "body": body, "labels": labels}

        response = requests.post(api_url, json=issue_data, headers=headers)

        if response.status_code == 201:
            info = response.json()
            return SubmitResponse(
                issue_url=info["html_url"],
                issue_number=info["number"],
                message=f"Created issue #{info['number']} in {CODEBUNDLE_FARM_REPO}",
            )
        else:
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"GitHub API error: {response.text}",
            )
    except HTTPException:
        raise
    except requests.RequestException as e:
        logger.error(f"Error creating GitHub issue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error communicating with GitHub: {e}",
        )
    except Exception as e:
        logger.error(f"Unexpected error in submit_intake: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {e}",
        )


# =============================================================================
# Helpers
# =============================================================================


def _build_minimal_issue_body(req: SubmitRequest) -> str:
    """Build issue body with original request + full existing coverage details for the designer."""
    parts = [
        "## Request",
        "",
        f"**Title:** {req.title}",
        "",
        "**Description:**",
        "",
        "\n".join(f"> {line}" for line in req.description.splitlines()),
        "",
    ]

    if req.extra_context:
        parts.extend([
            "**Additional context:**",
            "",
            req.extra_context,
            "",
        ])

    # Existing CodeBundles found by search — full details for the designer
    if req.matches:
        parts.extend([
            "---",
            "## Existing Coverage (from registry search)",
            "",
            "The following CodeBundles may overlap with this request. Designer: consider reusing, extending, or differentiating.",
            "",
        ])
        for i, m in enumerate(req.matches, 1):
            score_str = f" ({int(m.relevance_score * 100)}% match)" if m.relevance_score > 0 else ""
            parts.append(f"### {i}. {m.display_name}{score_str}")
            parts.append("")
            parts.append(f"- **Collection:** `{m.collection_slug}`")
            parts.append(f"- **Platform:** {m.platform or '—'}")
            parts.append(f"- **Description:** {m.description[:500]}{'…' if len(m.description) > 500 else ''}")
            if m.tasks:
                parts.append(f"- **Tasks:** {', '.join(m.tasks[:8])}{'…' if len(m.tasks) > 8 else ''}")
            if m.tags:
                parts.append(f"- **Tags:** {', '.join(m.tags[:10])}")
            if m.source_url:
                parts.append(f"- **Link:** {m.source_url}")
            parts.append("")

    # Existing open requests — designer can consolidate
    if req.existing_requests:
        parts.extend([
            "---",
            "## Open Requests (may overlap)",
            "",
            "Consider commenting on an existing issue instead of duplicating work.",
            "",
        ])
        for r in req.existing_requests:
            parts.append(f"- [#{r.number} {r.title}]({r.url})")
        parts.append("")

    if req.contact_email:
        parts.append(f"**Contact:** {req.contact_email}")
        parts.append("")
    if req.contact_ok:
        parts.append("**Contact OK:** Yes, please reach out.")
        parts.append("")

    parts.extend([
        "---",
        f"*Created via CodeCollection Registry intake at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}.*",
    ])
    return "\n".join(parts)


def _infer_platform(description: str) -> str:
    """Best-effort platform detection from free text."""
    d = description.lower()
    mapping = [
        (["kubernetes", "k8s", "kubectl", "pod", "deployment", "namespace", "helm"], "Kubernetes"),
        (["aws", "amazon", "s3", "ec2", "lambda", "cloudwatch", "iam"], "AWS"),
        (["azure", "az ", "aks", "app service", "resource group"], "Azure"),
        (["gcp", "google cloud", "gke", "bigquery", "pubsub"], "GCP"),
        (["terraform", "tfstate", "hcl"], "Terraform"),
        (["docker", "container", "dockerfile"], "Docker"),
        (["github", "gh ", "actions", "repository"], "GitHub"),
        (["postgres", "mysql", "redis", "database", "sql"], "Database"),
        (["linux", "ssh", "systemd", "cron"], "Linux"),
    ]
    for keywords, platform in mapping:
        if any(kw in d for kw in keywords):
            return platform
    return ""


def _generate_bundle_name(platform: str, description: str) -> str:
    """Generate a bundle name slug from platform and description."""
    prefix = platform.lower().replace(" ", "-") if platform else "generic"
    words = description.lower().split()[:4]
    slug = "-".join(w for w in words if len(w) > 2 and w.isalnum())
    if not slug:
        slug = "healthcheck"
    return f"{prefix}-{slug}"


def _slugify_task(description: str) -> str:
    """Turn a task description into a Robot Framework task name."""
    words = description.strip().split()[:8]
    return " ".join(w.capitalize() for w in words)


def _parse_codebundle_results(markdown: str) -> List[SearchMatch]:
    """Parse the markdown output from MCP find_codebundle into structured matches."""
    matches = []
    current: Dict[str, Any] = {}

    for line in markdown.split("\n"):
        line = line.strip()
        if line.startswith("## ") and "**" in line:
            if current.get("display_name"):
                matches.append(SearchMatch(**current))
            name = line.split("**")[1] if "**" in line else line[3:]
            current = {
                "display_name": name.strip(),
                "slug": "",
                "collection_slug": "",
                "platform": "",
                "description": "",
                "tasks": [],
                "tags": [],
                "relevance_score": 0.0,
                "source_url": "",
            }
        elif line.startswith("**Collection:**"):
            current["collection_slug"] = line.split("**Collection:**")[1].strip()
        elif line.startswith("**Platform:**"):
            current["platform"] = line.split("**Platform:**")[1].strip()
        elif line.startswith("**Description:**"):
            current["description"] = line.split("**Description:**")[1].strip()
        elif line.startswith("**Relevance:**"):
            try:
                score_str = line.split("**Relevance:**")[1].strip().rstrip("%")
                current["relevance_score"] = float(score_str) / 100
            except (ValueError, IndexError):
                pass
        elif line.startswith("**Tags:**"):
            tags_str = line.split("**Tags:**")[1].strip()
            current["tags"] = [t.strip() for t in tags_str.split(",") if t.strip()]
        elif line.startswith("**Source:**"):
            # Extract slug from source link
            if "/codebundles/" in line:
                slug_part = line.split("/codebundles/")[-1].rstrip(")")
                current["slug"] = slug_part
                current["source_url"] = line.split("(")[-1].rstrip(")") if "(" in line else ""
        elif line.startswith("- ") and current.get("display_name"):
            task = line[2:].strip()
            if task and "tasks" in current:
                current["tasks"].append(task)

    if current.get("display_name"):
        matches.append(SearchMatch(**current))

    return matches


def _parse_existing_requests(markdown: str) -> List[ExistingRequest]:
    """Parse the markdown output from MCP check_existing_requests."""
    requests_list = []
    for line in markdown.split("\n"):
        line = line.strip()
        if line.startswith("- **#"):
            try:
                number = int(line.split("**#")[1].split("**")[0])
                title = line.split("[")[1].split("]")[0] if "[" in line else ""
                url = line.split("(")[1].split(")")[0] if "(" in line else ""
                created = ""
                if "Created:" in line:
                    created = line.split("Created:")[1].strip()
                requests_list.append(ExistingRequest(
                    number=number, title=title, url=url, created_at=created,
                ))
            except (IndexError, ValueError):
                continue
    return requests_list
