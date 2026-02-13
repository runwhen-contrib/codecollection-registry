"""
GitHub Issue Creation for Missing Tasks
"""
import logging
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
import requests

from app.core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/github", tags=["github"])


class TaskRequestIssue(BaseModel):
    user_query: str
    task_description: str
    use_case: str
    platform: str = "Generic"
    priority: str = "medium"  # low, medium, high
    user_email: str = None


class IssueResponse(BaseModel):
    issue_url: str
    issue_number: int
    message: str


@router.post("/create-task-request", response_model=IssueResponse)
async def create_task_request_issue(request: TaskRequestIssue):
    """Create a GitHub issue requesting new tasks for the registry"""
    
    if settings.GITHUB_TOKEN == "your_github_token_here":
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="GitHub integration not configured. Please set GITHUB_TOKEN in environment variables."
        )
    
    try:
        # Create issue title
        title = f"Task Request: {request.user_query}"
        
        # Create issue body
        body_parts = [
            "## 🚀 New Task Request",
            "",
            f"**User Query:** {request.user_query}",
            "",
            "### Task Description",
            request.task_description,
            "",
            "### Use Case",
            request.use_case,
            "",
            "### Details",
            f"- **Platform:** {request.platform}",
            f"- **Priority:** {request.priority}",
        ]
        
        if request.user_email:
            body_parts.extend([
                f"- **Requested by:** {request.user_email}",
            ])
        
        body_parts.extend([
            "",
            "### Acceptance Criteria",
            "- [ ] Create codebundle that addresses the user query",
            "- [ ] Add appropriate tasks for the described use case",
            "- [ ] Include proper documentation and examples",
            "- [ ] Test the codebundle functionality",
            "",
            "---",
            "*This issue was automatically created from the CodeCollection Registry chat interface.*"
        ])
        
        body = "\n".join(body_parts)
        
        # Create GitHub issue
        github_api_url = f"https://api.github.com/repos/{settings.GITHUB_OWNER}/{settings.GITHUB_REPO}/issues"
        
        headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json",
            "Content-Type": "application/json"
        }
        
        issue_data = {
            "title": title,
            "body": body,
            "labels": ["enhancement", "task-request", f"platform:{request.platform.lower()}", f"priority:{request.priority}"]
        }
        
        response = requests.post(github_api_url, json=issue_data, headers=headers)
        
        if response.status_code == 201:
            issue_info = response.json()
            return IssueResponse(
                issue_url=issue_info["html_url"],
                issue_number=issue_info["number"],
                message=f"Successfully created GitHub issue #{issue_info['number']}"
            )
        else:
            logger.error(f"GitHub API error: {response.status_code} - {response.text}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create GitHub issue: {response.text}"
            )
            
    except requests.RequestException as e:
        logger.error(f"Error creating GitHub issue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error communicating with GitHub: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Unexpected error creating GitHub issue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error: {str(e)}"
        )


@router.get("/issue-template")
async def get_issue_template(user_query: str):
    """Get a pre-filled issue template for a user query"""
    
    # Generate suggested task description and use case based on the query
    task_description = f"Create automation tasks that can handle: {user_query}"
    
    # Try to infer platform from query
    platform = "Generic"
    query_lower = user_query.lower()
    if any(word in query_lower for word in ["aws", "amazon"]):
        platform = "AWS"
    elif any(word in query_lower for word in ["azure", "microsoft"]):
        platform = "Azure"
    elif any(word in query_lower for word in ["gcp", "google", "cloud platform"]):
        platform = "GCP"
    elif any(word in query_lower for word in ["kubernetes", "k8s"]):
        platform = "Kubernetes"
    elif any(word in query_lower for word in ["docker", "container"]):
        platform = "Docker"
    elif any(word in query_lower for word in ["terraform"]):
        platform = "Terraform"
    
    # Generate use case suggestions
    use_case_suggestions = []
    if any(word in query_lower for word in ["cost", "spend", "billing", "budget"]):
        use_case_suggestions.append("Cost optimization and monitoring")
    if any(word in query_lower for word in ["deploy", "deployment"]):
        use_case_suggestions.append("Automated deployment and infrastructure management")
    if any(word in query_lower for word in ["monitor", "alert", "health"]):
        use_case_suggestions.append("Monitoring and alerting")
    if any(word in query_lower for word in ["security", "compliance"]):
        use_case_suggestions.append("Security and compliance automation")
    if any(word in query_lower for word in ["backup", "restore"]):
        use_case_suggestions.append("Backup and disaster recovery")
    
    if not use_case_suggestions:
        use_case_suggestions.append("General automation and operational tasks")
    
    use_case = "; ".join(use_case_suggestions)
    
    return {
        "user_query": user_query,
        "task_description": task_description,
        "use_case": use_case,
        "platform": platform,
        "priority": "medium"
    }






