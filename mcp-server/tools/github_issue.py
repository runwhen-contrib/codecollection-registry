"""
GitHub Issue Creation Tool

Creates CodeBundle request issues on GitHub when semantic search
fails to find matching codebundles.

Uses the codebundle-wanted.yaml template format from:
https://github.com/runwhen-contrib/codecollection-registry/blob/main/.github/ISSUE_TEMPLATE/codebundle-wanted.yaml
"""

import os
import httpx
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)

REPO_OWNER = "runwhen-contrib"
REPO_NAME = "codecollection-registry"
GITHUB_API_BASE = "https://api.github.com"


@dataclass
class CodeBundleRequest:
    """Data for a new CodeBundle request issue."""
    platform: str                    # What cloud platform(s) should this support?
    tasks: List[str]                 # Key tasks that should be performed
    original_query: Optional[str] = None  # The user's original search query
    context: Optional[str] = None    # Any other helpful context
    contact_ok: bool = False         # Willing to be contacted?


class GitHubIssueTool:
    """
    Creates CodeBundle request issues on GitHub.
    
    Requires GITHUB_TOKEN environment variable with repo scope.
    """
    
    def __init__(self):
        self.token = os.getenv("GITHUB_TOKEN")
        self.client = httpx.Client(
            base_url=GITHUB_API_BASE,
            headers={
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=30.0
        )
        if self.token:
            self.client.headers["Authorization"] = f"Bearer {self.token}"
    
    def is_configured(self) -> bool:
        """Check if GitHub token is configured."""
        return bool(self.token)
    
    def _format_tasks(self, tasks: List[str]) -> str:
        """Format tasks as a numbered list."""
        if not tasks:
            return "No specific tasks provided"
        return "\n".join(f"{i+1}. {task}" for i, task in enumerate(tasks))
    
    def _build_issue_body(self, request: CodeBundleRequest) -> str:
        """Build the issue body matching the template format."""
        sections = []
        
        # Original query section (not in template but helpful)
        if request.original_query:
            sections.append(f"## Original Search Query\n> {request.original_query}")
        
        # Cloud platform(s)
        sections.append(f"## What cloud platform(s) should this support?\n{request.platform}")
        
        # Key tasks
        sections.append(f"## What are some key tasks that should be performed?\n{self._format_tasks(request.tasks)}")
        
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
                "error": "GitHub token not configured. Set GITHUB_TOKEN environment variable."
            }
        
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
        try:
            # Search for open issues with the search term
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
_github_tool: Optional[GitHubIssueTool] = None


def get_github_tool() -> GitHubIssueTool:
    """Get or create the GitHub tool singleton."""
    global _github_tool
    if _github_tool is None:
        _github_tool = GitHubIssueTool()
    return _github_tool

