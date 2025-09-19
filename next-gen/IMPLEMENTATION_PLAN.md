# Implementation Plan: Interactive CodeCollection Registry

## Phase 1: Foundation Setup

### 1.1 Backend API Structure
```python
# app/main.py
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from app.routers import issues, codebundles, registry, webhooks
from app.database import engine, Base
from app.core.config import settings

app = FastAPI(title="CodeCollection Registry API", version="1.0.0")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create database tables
Base.metadata.create_all(bind=engine)

# Include routers
app.include_router(issues.router, prefix="/api/issues", tags=["issues"])
app.include_router(codebundles.router, prefix="/api/codebundles", tags=["codebundles"])
app.include_router(registry.router, prefix="/api/registry", tags=["registry"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["webhooks"])
```

### 1.2 Database Models
```python
# app/models.py
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class Issue(Base):
    __tablename__ = "issues"
    
    id = Column(Integer, primary_key=True)
    github_issue_id = Column(Integer, unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    body = Column(Text)
    labels = Column(JSON)
    state = Column(String(50), default="open")  # open, processing, completed, failed
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    codebundle_requests = relationship("CodebundleRequest", back_populates="issue")

class CodebundleRequest(Base):
    __tablename__ = "codebundle_requests"
    
    id = Column(Integer, primary_key=True)
    issue_id = Column(Integer, ForeignKey("issues.id"))
    target_collection = Column(String(100))  # Which codecollection to add to
    platform = Column(String(50))  # Azure, AWS, etc.
    tasks = Column(JSON)  # List of tasks to implement
    status = Column(String(50), default="pending")  # pending, generating, completed, failed
    generated_code = Column(Text)  # Generated codebundle content
    pr_url = Column(String(255))  # Link to created PR
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    issue = relationship("Issue", back_populates="codebundle_requests")

class CodeCollection(Base):
    __tablename__ = "codecollections"
    
    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    git_url = Column(String(255), nullable=False)
    description = Column(Text)
    owner = Column(String(100))
    last_synced = Column(DateTime)
    is_active = Column(Boolean, default=True)
```

### 1.3 GitHub Integration Service
```python
# app/services/github_service.py
import httpx
from typing import List, Dict, Optional
from app.core.config import settings

class GitHubService:
    def __init__(self):
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {settings.GITHUB_TOKEN}",
            "Accept": "application/vnd.github.v3+json"
        }
    
    async def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict:
        """Get issue details from GitHub"""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}",
                headers=self.headers
            )
            return response.json()
    
    async def add_labels(self, owner: str, repo: str, issue_number: int, labels: List[str]):
        """Add labels to an issue"""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self.base_url}/repos/{owner}/{repo}/issues/{issue_number}/labels",
                headers=self.headers,
                json={"labels": labels}
            )
    
    async def create_pull_request(self, owner: str, repo: str, title: str, 
                                 head: str, base: str, body: str) -> Dict:
        """Create a pull request"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.base_url}/repos/{owner}/{repo}/pulls",
                headers=self.headers,
                json={
                    "title": title,
                    "head": head,
                    "base": base,
                    "body": body
                }
            )
            return response.json()
```

## Phase 2: AI Integration

### 2.1 Cursor AI Integration
```python
# app/services/ai_service.py
import subprocess
import json
import tempfile
from typing import Dict, List
from app.core.config import settings

class CursorAIService:
    def __init__(self):
        self.cursor_api_key = settings.CURSOR_API_KEY
    
    async def generate_codebundle(self, issue_context: Dict, target_collection: str) -> Dict:
        """
        Use Cursor AI to generate a codebundle based on issue requirements
        """
        # Prepare context for AI
        context = {
            "issue_title": issue_context["title"],
            "issue_body": issue_context["body"],
            "platform": issue_context.get("platform", "Azure"),
            "tasks": issue_context.get("tasks", []),
            "target_collection": target_collection,
            "existing_patterns": await self._get_existing_patterns(target_collection)
        }
        
        # Create temporary workspace
        with tempfile.TemporaryDirectory() as temp_dir:
            # Clone the target repository
            await self._clone_repository(target_collection, temp_dir)
            
            # Generate codebundle using Cursor
            codebundle = await self._generate_with_cursor(temp_dir, context)
            
            return {
                "codebundle": codebundle,
                "validation_results": await self._validate_codebundle(codebundle)
            }
    
    async def _generate_with_cursor(self, workspace_path: str, context: Dict) -> str:
        """Generate codebundle using Cursor AI"""
        prompt = f"""
        Based on the following issue requirements, generate a Robot Framework codebundle:
        
        Issue: {context['issue_title']}
        Description: {context['issue_body']}
        Platform: {context['platform']}
        Tasks: {context['tasks']}
        
        Please create a complete codebundle following the existing patterns in this repository.
        Include:
        1. A runbook.robot file with the main tasks
        2. A meta.yaml file with metadata
        3. Any necessary resource files
        4. Proper error handling and logging
        
        The codebundle should be production-ready and follow Robot Framework best practices.
        """
        
        # Use Cursor CLI or API to generate code
        result = subprocess.run([
            "cursor", "generate",
            "--prompt", prompt,
            "--workspace", workspace_path,
            "--output", "codebundle"
        ], capture_output=True, text=True)
        
        return result.stdout
    
    async def _validate_codebundle(self, codebundle: str) -> Dict:
        """Validate the generated codebundle"""
        # Run Robot Framework validation
        # Check syntax, imports, etc.
        return {"valid": True, "errors": []}
```

### 2.2 Issue Processing Workflow
```python
# app/services/workflow_service.py
from app.models import Issue, CodebundleRequest
from app.services.github_service import GitHubService
from app.services.ai_service import CursorAIService
from app.core.database import get_db
from sqlalchemy.orm import Session

class WorkflowService:
    def __init__(self):
        self.github_service = GitHubService()
        self.ai_service = CursorAIService()
    
    async def process_issue(self, issue_data: Dict, db: Session):
        """Process a GitHub issue and generate codebundle"""
        try:
            # Create issue record
            issue = Issue(
                github_issue_id=issue_data["number"],
                title=issue_data["title"],
                body=issue_data["body"],
                labels=issue_data.get("labels", []),
                state="processing"
            )
            db.add(issue)
            db.commit()
            
            # Add processing label
            await self.github_service.add_labels(
                "runwhen-contrib", "codecollection-registry", 
                issue_data["number"], ["ai-processing"]
            )
            
            # Determine target collection
            target_collection = self._determine_target_collection(issue_data)
            
            # Create codebundle request
            request = CodebundleRequest(
                issue_id=issue.id,
                target_collection=target_collection,
                platform=self._extract_platform(issue_data),
                tasks=self._extract_tasks(issue_data),
                status="generating"
            )
            db.add(request)
            db.commit()
            
            # Generate codebundle using AI
            result = await self.ai_service.generate_codebundle(issue_data, target_collection)
            
            # Update request with results
            request.generated_code = result["codebundle"]
            request.status = "completed" if result["validation_results"]["valid"] else "failed"
            db.commit()
            
            # Create PR if successful
            if request.status == "completed":
                pr = await self._create_pull_request(request, issue_data)
                request.pr_url = pr["html_url"]
                db.commit()
                
                # Update issue labels
                await self.github_service.add_labels(
                    "runwhen-contrib", "codecollection-registry",
                    issue_data["number"], ["ai-completed", "ready-for-review"]
                )
            
        except Exception as e:
            # Handle errors
            issue.state = "failed"
            request.status = "failed"
            db.commit()
            
            await self.github_service.add_labels(
                "runwhen-contrib", "codecollection-registry",
                issue_data["number"], ["ai-failed"]
            )
    
    def _determine_target_collection(self, issue_data: Dict) -> str:
        """Determine which codecollection to target based on issue content"""
        # Logic to determine target based on platform, labels, etc.
        if "azure" in issue_data["body"].lower():
            return "rw-public-codecollection"
        elif "aws" in issue_data["body"].lower():
            return "rw-cli-codecollection"
        else:
            return "rw-generic-codecollection"
```

## Phase 3: Frontend Interface

### 3.1 React Components
```typescript
// src/components/IssueDashboard.tsx
import React, { useState, useEffect } from 'react';
import { Card, CardContent, Typography, Chip, Button } from '@mui/material';

interface Issue {
  id: number;
  title: string;
  state: string;
  labels: string[];
  created_at: string;
  codebundle_requests: CodebundleRequest[];
}

interface CodebundleRequest {
  id: number;
  target_collection: string;
  status: string;
  pr_url?: string;
}

export const IssueDashboard: React.FC = () => {
  const [issues, setIssues] = useState<Issue[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchIssues();
  }, []);

  const fetchIssues = async () => {
    try {
      const response = await fetch('/api/issues');
      const data = await response.json();
      setIssues(data);
    } catch (error) {
      console.error('Error fetching issues:', error);
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'completed': return 'success';
      case 'processing': return 'warning';
      case 'failed': return 'error';
      default: return 'default';
    }
  };

  return (
    <div>
      <Typography variant="h4" gutterBottom>
        Issue Dashboard
      </Typography>
      {issues.map((issue) => (
        <Card key={issue.id} sx={{ mb: 2 }}>
          <CardContent>
            <Typography variant="h6">{issue.title}</Typography>
            <div style={{ marginTop: 8 }}>
              {issue.labels.map((label) => (
                <Chip key={label} label={label} size="small" sx={{ mr: 1 }} />
              ))}
            </div>
            {issue.codebundle_requests.map((request) => (
              <div key={request.id} style={{ marginTop: 16 }}>
                <Typography variant="body2">
                  Target: {request.target_collection}
                </Typography>
                <Chip 
                  label={request.status} 
                  color={getStatusColor(request.status)}
                  size="small"
                />
                {request.pr_url && (
                  <Button 
                    href={request.pr_url} 
                    target="_blank" 
                    size="small"
                    sx={{ ml: 1 }}
                  >
                    View PR
                  </Button>
                )}
              </div>
            ))}
          </CardContent>
        </Card>
      ))}
    </div>
  );
};
```

## Phase 4: Deployment & Monitoring

### 4.1 Docker Configuration
```dockerfile
# Dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port
EXPOSE 8000

# Start application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### 4.2 Docker Compose
```yaml
# docker-compose.yml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://user:password@db:5432/codecollection_registry
      - GITHUB_TOKEN=${GITHUB_TOKEN}
      - CURSOR_API_KEY=${CURSOR_API_KEY}
    depends_on:
      - db
      - redis
    volumes:
      - ./data:/app/data

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=codecollection_registry
      - POSTGRES_USER=user
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
    depends_on:
      - app

volumes:
  postgres_data:
  redis_data:
```

## Security Implementation

### Authentication & Authorization
```python
# app/auth.py
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from app.core.config import settings

security = HTTPBearer()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, settings.SECRET_KEY, algorithms=["HS256"])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(status_code=401, detail="Invalid authentication credentials")
        return user_id
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid authentication credentials")

async def require_admin(current_user: str = Depends(get_current_user)):
    # Check if user has admin role
    if not await is_admin(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user
```

This implementation plan provides a solid foundation for building an interactive CodeCollection Registry with automated codebundle generation capabilities. The architecture is designed to be scalable, secure, and maintainable while leveraging AI agents like Cursor for intelligent code generation.
