"""
AI Service for CodeBundle Enhancement
Provides AI-powered description enhancement and access classification
"""
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from openai import OpenAI
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import AIConfiguration, Codebundle

logger = logging.getLogger(__name__)


class AIEnhancementService:
    """Service for AI-powered CodeBundle enhancement"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.config = self._get_active_config()
        
    def _get_active_config(self) -> Optional[AIConfiguration]:
        """Get the active AI configuration"""
        return self.db.query(AIConfiguration).filter(
            AIConfiguration.is_active == True,
            AIConfiguration.enhancement_enabled == True
        ).first()
    
    def is_enabled(self) -> bool:
        """Check if AI enhancement is enabled and configured"""
        return (
            self.config is not None and 
            self.config.api_key is not None and
            self.config.enhancement_enabled
        )
    
    def enhance_codebundle(self, codebundle: Codebundle) -> Dict[str, any]:
        """
        Enhance a CodeBundle with AI-generated description and access classification
        
        Returns:
            Dict containing enhanced_description, access_level, and iam_requirements
        """
        if not self.is_enabled():
            raise ValueError("AI enhancement is not enabled or configured")
        
        try:
            # Set up OpenAI client
            client = OpenAI(api_key=self.config.api_key)
            
            # Prepare context for AI
            context = self._prepare_codebundle_context(codebundle)
            
            # Generate enhanced description
            enhanced_description = self._generate_enhanced_description(context, client)
            
            # Classify access level and determine IAM requirements
            access_level, iam_requirements = self._classify_access_and_iam(context, client)
            
            return {
                "enhanced_description": enhanced_description,
                "access_level": access_level,
                "iam_requirements": iam_requirements,
                "enhancement_metadata": {
                    "model_used": self.config.model_name,
                    "enhanced_at": datetime.utcnow().isoformat(),
                    "service_provider": self.config.service_provider
                }
            }
            
        except Exception as e:
            logger.error(f"Error enhancing codebundle {codebundle.slug}: {e}")
            raise
    
    def _prepare_codebundle_context(self, codebundle: Codebundle) -> Dict[str, any]:
        """Prepare context information for AI processing"""
        return {
            "name": codebundle.name,
            "display_name": codebundle.display_name,
            "description": codebundle.description,
            "doc": codebundle.doc,
            "author": codebundle.author,
            "support_tags": codebundle.support_tags,
            "tasks": codebundle.tasks,
            "task_count": codebundle.task_count,
            "platform": codebundle.discovery_platform,
            "resource_types": codebundle.discovery_resource_types,
            "codecollection_name": codebundle.codecollection.name if codebundle.codecollection else None
        }
    
    def _generate_enhanced_description(self, context: Dict[str, any], client: OpenAI) -> str:
        """Generate an enhanced description using AI"""
        prompt = self._build_description_prompt(context)
        
        try:
            response = client.chat.completions.create(
                model=self.config.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in cloud infrastructure and DevOps automation. Your task is to create clear, comprehensive descriptions for automation scripts (CodeBundles) that help users understand what the script does, when to use it, and what value it provides."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating enhanced description: {e}")
            raise
    
    def _classify_access_and_iam(self, context: Dict[str, any], client: OpenAI) -> Tuple[str, List[str]]:
        """Classify access level and determine IAM requirements"""
        prompt = self._build_access_classification_prompt(context)
        
        try:
            response = client.chat.completions.create(
                model=self.config.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": """You are an expert in cloud security and IAM permissions. Analyze automation scripts to determine:
1. Access level: 'read-only' or 'read-write' based on the operations performed
2. Minimum IAM requirements: List specific permissions, roles, or policies needed

Return your response as JSON with keys: access_level, iam_requirements"""
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=300,
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content.strip())
            return result.get("access_level", "unknown"), result.get("iam_requirements", [])
            
        except Exception as e:
            logger.error(f"Error classifying access and IAM: {e}")
            return "unknown", []
    
    def _build_description_prompt(self, context: Dict[str, any]) -> str:
        """Build prompt for description enhancement"""
        return f"""
Please create an enhanced description for this CodeBundle:

Name: {context['name']}
Display Name: {context['display_name']}
Current Description: {context['description']}
Documentation: {context['doc']}
Author: {context['author']}
Platform: {context['platform']}
Resource Types: {context['resource_types']}
Support Tags: {context['support_tags']}
Tasks: {context['tasks']}
Collection: {context['codecollection_name']}

Create a clear, comprehensive description (2-3 sentences) that explains:
1. What this CodeBundle does
2. When/why someone would use it
3. What value or problem it solves

Make it accessible to both technical and non-technical users.
"""
    
    def _build_access_classification_prompt(self, context: Dict[str, any]) -> str:
        """Build prompt for access classification"""
        return f"""
Analyze this CodeBundle to determine access requirements:

Name: {context['name']}
Tasks: {context['tasks']}
Platform: {context['platform']}
Resource Types: {context['resource_types']}
Support Tags: {context['support_tags']}
Documentation: {context['doc']}

Based on the task names and operations, determine:

1. Access Level: 
   - "read-only" if it only reads/monitors/checks status
   - "read-write" if it modifies, creates, deletes, or changes resources

2. IAM Requirements: List the minimum permissions needed, such as:
   - AWS: Specific IAM policies or actions (e.g., "ec2:DescribeInstances", "s3:GetObject")
   - Kubernetes: RBAC permissions (e.g., "pods:get", "deployments:list")
   - Azure: Role assignments or permissions
   - GCP: IAM roles or permissions

Return as JSON format:
{{
  "access_level": "read-only" or "read-write",
  "iam_requirements": ["permission1", "permission2", ...]
}}
"""


def get_ai_service(db_session: Session) -> AIEnhancementService:
    """Factory function to get AI service instance"""
    return AIEnhancementService(db_session)

