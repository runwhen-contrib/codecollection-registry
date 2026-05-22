"""
GitHub Issue Tools

Creates Skill Template request issues on GitHub when semantic search
fails to find matching Skill Templates (internally still called
``CodeBundle`` for backward compatibility -- see Phase 1 cosmetic
rename notes in ``mcp-server/utils/terminology.py``).

Uses the codebundle-wanted.yaml template format from:
https://github.com/runwhen-contrib/codecollection-registry/blob/main/.github/ISSUE_TEMPLATE/codebundle-wanted.yaml

Requires GitHub App or PAT credentials -- see cc-registry-v2/README.md
"GitHub App (Issue Creation)" section for env var details.
"""

import base64
import os
import time
import threading
import httpx
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

from .base import BaseTool, ToolDefinition, ToolParameter

logger = logging.getLogger(__name__)

REPO_OWNER = "runwhen-contrib"
REPO_NAME = "codecollection-registry"
GITHUB_API_BASE = "https://api.github.com"


@dataclass
class CodeBundleRequest:
    """Data for a new Skill Template (formerly "CodeBundle") request issue.

    Class name is preserved for backward compatibility with existing
    callers; the user-facing vocabulary is "Skill Template".
    """
    platform: str                    # What cloud platform(s) should this support?
    tasks: List[str]                 # Key Tools that should be performed
    original_query: Optional[str] = None  # The user's original search query
    context: Optional[str] = None    # Any other helpful context
    contact_ok: bool = False         # Willing to be contacted?


class _AppTokenManager:
    """Manages GitHub App JWT -> installation token lifecycle.

    Parallel implementation to backend's GitHubAuth (different service,
    different JWT library).  Keep changes in sync.
    """

    def __init__(self, app_id: str, private_key_raw: str, installation_id: Optional[int] = None):
        self._app_id = app_id
        self._installation_id = installation_id
        self._private_key = self._decode_key(private_key_raw)
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return bool(self._private_key)

    @staticmethod
    def _decode_key(raw: str) -> Optional[str]:
        if raw.startswith("-----BEGIN"):
            return raw
        try:
            decoded = base64.b64decode(raw).decode("utf-8")
            if "-----BEGIN" in decoded:
                return decoded
        except Exception:
            pass
        logger.error("GITHUB_APP_PRIVATE_KEY is not a valid PEM or base64-encoded PEM")
        return None

    def _make_jwt(self) -> str:
        import jwt as pyjwt
        now = int(time.time())
        payload = {"iat": now - 60, "exp": now + 600, "iss": self._app_id}
        return pyjwt.encode(payload, self._private_key, algorithm="RS256")

    def _discover_installation(self, app_jwt: str) -> Optional[int]:
        try:
            resp = httpx.get(
                f"{GITHUB_API_BASE}/app/installations",
                headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"},
                timeout=15,
            )
            if resp.status_code != 200:
                logger.error("Failed to list installations: %s %s", resp.status_code, resp.text)
                return None
            installs = resp.json()
            if not installs:
                logger.error("No installations for GitHub App %s", self._app_id)
                return None
            return installs[0]["id"]
        except Exception as exc:
            logger.error("Error discovering installation: %s", exc)
            return None

    def get_token(self) -> str:
        if self._token and time.time() < self._expires_at:
            return self._token
        with self._lock:
            if self._token and time.time() < self._expires_at:
                return self._token
            app_jwt = self._make_jwt()
            if not self._installation_id:
                self._installation_id = self._discover_installation(app_jwt)
                if not self._installation_id:
                    raise RuntimeError("Cannot discover GitHub App installation")
            resp = httpx.post(
                f"{GITHUB_API_BASE}/app/installations/{self._installation_id}/access_tokens",
                headers={"Authorization": f"Bearer {app_jwt}", "Accept": "application/vnd.github+json"},
                timeout=15,
            )
            if resp.status_code != 201:
                raise RuntimeError(f"Failed to get installation token: {resp.status_code} {resp.text}")
            self._token = resp.json()["token"]
            self._expires_at = time.time() + 3500
            return self._token


class GitHubIssueClient:
    """
    Low-level client for GitHub issue operations.

    Authenticates via GitHub App (GITHUB_APP_ID + GITHUB_APP_PRIVATE_KEY)
    or falls back to GITHUB_TOKEN PAT.
    """

    def __init__(self):
        self._app_mgr: Optional[_AppTokenManager] = None
        self.token = os.getenv("GITHUB_TOKEN")

        app_id = os.getenv("GITHUB_APP_ID")
        app_key = os.getenv("GITHUB_APP_PRIVATE_KEY")
        inst_id = os.getenv("GITHUB_APP_INSTALLATION_ID")
        if app_id and app_key:
            mgr = _AppTokenManager(app_id, app_key, int(inst_id) if inst_id else None)
            if mgr.available:
                self._app_mgr = mgr
                logger.info("GitHub App authentication configured (app_id=%s)", app_id)

        self.client = httpx.Client(
            base_url=GITHUB_API_BASE,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0,
        )
        self._refresh_auth()

    def _refresh_auth(self):
        """Set the Authorization header using the best available credential."""
        if self._app_mgr:
            try:
                token = self._app_mgr.get_token()
                self.client.headers["Authorization"] = f"Bearer {token}"
                return
            except Exception as exc:
                logger.warning("App token refresh failed, falling back to PAT: %s", exc)
        if self.token:
            self.client.headers["Authorization"] = f"Bearer {self.token}"

    def is_configured(self) -> bool:
        """Check if any GitHub credential is available."""
        return bool(self._app_mgr and self._app_mgr.available) or bool(self.token)
    
    def _format_tasks(self, tasks: List[str]) -> str:
        """Format Tools as a numbered list."""
        if not tasks:
            return "No specific Tools provided"
        return "\n".join(f"{i+1}. {task}" for i, task in enumerate(tasks))
    
    def _build_issue_body(self, request: CodeBundleRequest) -> str:
        """Build the issue body matching the template format."""
        sections = []
        
        # Original query section (not in template but helpful)
        if request.original_query:
            sections.append(f"## Original Search Query\n> {request.original_query}")
        
        # Cloud platform(s)
        sections.append(f"## What cloud platform(s) should this support?\n{request.platform}")
        
        # Key Tools (Runbooks/Monitors)
        sections.append(f"## What are some key Tools that should be performed?\n{self._format_tasks(request.tasks)}")
        
        # Additional context
        if request.context:
            sections.append(f"## Any other helpful context?\n{request.context}")
        
        # Contact preference
        contact = "Yes, please" if request.contact_ok else "No, thanks"
        sections.append(f"## Contact\n{contact}")
        
        # Footer
        sections.append("---\n*This issue was automatically created via the CodeCollection Registry chat interface.*")
        
        return "\n\n".join(sections)
    
    def _generate_title(self, request: CodeBundleRequest) -> str:
        """Generate issue title from platform."""
        # Clean up platform for title
        platform = request.platform.strip()
        if len(platform) > 50:
            platform = platform[:47] + "..."
        return f"[new-codebundle-request] - {platform}"
    
    def create_issue(self, request: CodeBundleRequest) -> Dict[str, Any]:
        """
        Create a new CodeBundle request issue on GitHub.
        
        Returns:
            Dict with 'success', 'issue_url', 'issue_number', or 'error'
        """
        if not self.is_configured():
            return {
                "success": False,
                "error": "GitHub not configured. Set GITHUB_APP_ID/GITHUB_APP_PRIVATE_KEY or GITHUB_TOKEN."
            }
        
        self._refresh_auth()
        title = self._generate_title(request)
        body = self._build_issue_body(request)
        
        try:
            response = self.client.post(
                f"/repos/{REPO_OWNER}/{REPO_NAME}/issues",
                json={
                    "title": title,
                    "body": body,
                    "labels": ["new-codebundle-request"]
                }
            )
            
            if response.status_code == 201:
                data = response.json()
                logger.info(f"Created GitHub issue #{data['number']}: {data['html_url']}")
                return {
                    "success": True,
                    "issue_url": data["html_url"],
                    "issue_number": data["number"],
                    "title": title
                }
            else:
                error_msg = response.json().get("message", response.text)
                logger.error(f"GitHub API error: {response.status_code} - {error_msg}")
                return {
                    "success": False,
                    "error": f"GitHub API error: {error_msg}"
                }
                
        except httpx.HTTPError as e:
            logger.error(f"HTTP error creating issue: {e}")
            return {
                "success": False,
                "error": f"HTTP error: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Error creating issue: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def check_existing_issues(self, search_term: str) -> List[Dict[str, Any]]:
        """
        Check for existing issues that might match the request.
        
        Returns list of potentially related open issues.
        """
        self._refresh_auth()
        try:
            query = f"repo:{REPO_OWNER}/{REPO_NAME} is:issue is:open {search_term}"
            response = self.client.get(
                "/search/issues",
                params={"q": query, "per_page": 5}
            )
            
            if response.status_code == 200:
                data = response.json()
                return [
                    {
                        "number": issue["number"],
                        "title": issue["title"],
                        "url": issue["html_url"],
                        "created_at": issue["created_at"]
                    }
                    for issue in data.get("items", [])
                ]
            return []
            
        except Exception as e:
            logger.error(f"Error searching issues: {e}")
            return []


# Singleton instance
_github_client: Optional[GitHubIssueClient] = None


def get_github_client() -> GitHubIssueClient:
    """Get or create the GitHub client singleton."""
    global _github_client
    if _github_client is None:
        _github_client = GitHubIssueClient()
    return _github_client


# Legacy alias for backward compatibility
def get_github_tool() -> GitHubIssueClient:
    """Legacy alias for get_github_client"""
    return get_github_client()


# =============================================================================
# MCP Tool Classes
# =============================================================================

class RequestCodeBundleTool(BaseTool):
    """
    Request a new Skill Template (formerly "CodeBundle") by creating a
    GitHub issue. Use this when no existing Skill Template matches the
    user's needs.
    """
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="request_codebundle",
            description="Request a new Skill Template (formerly 'CodeBundle') from the community by creating a GitHub issue. Use this when no existing Skill Template matches the user's needs.",
            category="action",
            parameters=[
                ToolParameter(
                    name="platform",
                    type="string",
                    description="Cloud platform(s) this should support (e.g., 'ServiceNow', 'Kubernetes on AWS', 'Azure')",
                    required=True
                ),
                ToolParameter(
                    name="tasks",
                    type="array",
                    description="List of key Tools (Runbooks or Monitors) that should be performed",
                    required=True,
                    items="string"
                ),
                ToolParameter(
                    name="original_query",
                    type="string",
                    description="The user's original search query",
                    required=False
                ),
                ToolParameter(
                    name="context",
                    type="string",
                    description="Additional context about the use case",
                    required=False
                ),
                ToolParameter(
                    name="contact_ok",
                    type="boolean",
                    description="Whether the user is willing to be contacted for follow-up",
                    required=False,
                    default=False
                )
            ]
        )
    
    async def execute(
        self,
        platform: str,
        tasks: List[str],
        original_query: Optional[str] = None,
        context: Optional[str] = None,
        contact_ok: bool = False
    ) -> str:
        """Create a GitHub issue for a new Skill Template request"""
        client = get_github_client()
        
        if not client.is_configured():
            return "**GitHub integration not configured.**\n\nPlease set GITHUB_TOKEN in environment variables to enable issue creation."
        
        request = CodeBundleRequest(
            platform=platform,
            tasks=tasks,
            original_query=original_query,
            context=context,
            contact_ok=contact_ok
        )
        
        result = client.create_issue(request)
        
        if result["success"]:
            return f"""# Skill Template Request Created!

Your request has been submitted successfully.

**Issue:** #{result['issue_number']}
**URL:** [{result['issue_url']}]({result['issue_url']})

The RunWhen community will review your request and may reach out if additional information is needed.

Thank you for helping improve the CodeCollection!"""
        else:
            return f"""# Failed to Create Request

An error occurred while creating the GitHub issue:

**Error:** {result['error']}

You can manually create an issue at:
https://github.com/{REPO_OWNER}/{REPO_NAME}/issues/new?template=codebundle-wanted.yaml"""


class CheckExistingRequestsTool(BaseTool):
    """Check if there are existing Skill Template (formerly "CodeBundle") requests similar to what the user needs."""
    
    @property
    def definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="check_existing_requests",
            description="Check if there are existing Skill Template (formerly 'CodeBundle') requests similar to what the user needs",
            category="info",
            parameters=[
                ToolParameter(
                    name="search_term",
                    type="string",
                    description="Term to search for in existing issues",
                    required=True
                )
            ]
        )
    
    async def execute(self, search_term: str) -> str:
        """Check for existing Skill Template requests"""
        client = get_github_client()
        
        existing = client.check_existing_issues(search_term)
        
        if existing:
            output = f"# Existing Skill Template Requests for: {search_term}\n\n"
            output += f"Found {len(existing)} related open issue(s):\n\n"
            
            for issue in existing:
                output += f"- **#{issue['number']}** - [{issue['title']}]({issue['url']})\n"
                output += f"  Created: {issue['created_at'][:10]}\n\n"
            
            output += "\nConsider commenting on an existing issue if it matches your needs, or create a new request if yours is different."
            return output
        else:
            return f"No existing open requests found for '{search_term}'.\n\nYou can create a new Skill Template request using the request_codebundle tool."
