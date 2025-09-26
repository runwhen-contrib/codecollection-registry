"""
AI Service for CodeBundle Enhancement
Provides AI-powered description enhancement and access classification
"""
import json
import logging
from typing import Dict, List, Optional, Tuple
from datetime import datetime

from openai import OpenAI, AzureOpenAI
from sqlalchemy.orm import Session
import requests

from app.core.config import settings
from app.models import AIConfiguration, Codebundle
from app.services.ai_prompts import AIPrompts

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
    
    def _get_ai_client(self):
        """Get the appropriate AI client based on service provider"""
        if self.config.service_provider == "azure-openai":
            if not self.config.azure_endpoint or not self.config.azure_deployment_name:
                raise ValueError("Azure OpenAI requires azure_endpoint and azure_deployment_name")
            
            return AzureOpenAI(
                api_key=self.config.api_key,
                api_version=self.config.api_version or "2024-02-15-preview",
                azure_endpoint=self.config.azure_endpoint
            )
        else:
            # Default to OpenAI
            return OpenAI(api_key=self.config.api_key)
    
    def _get_model_name(self) -> str:
        """Get the model name to use for API calls"""
        if self.config.service_provider == "azure-openai":
            return self.config.azure_deployment_name or self.config.model_name
        else:
            return self.config.model_name
    
    def enhance_codebundle(self, codebundle: Codebundle) -> Dict[str, any]:
        """
        Enhance a CodeBundle with AI-generated description and access classification
        
        Returns:
            Dict containing enhanced_description, access_level, iam_requirements, and enhanced_tasks
        """
        if not self.is_enabled():
            raise ValueError("AI enhancement is not enabled or configured")
        
        try:
            # Set up AI client based on service provider
            client = self._get_ai_client()
            
            # Prepare context for AI
            context = self._prepare_codebundle_context(codebundle)
            
            # Generate enhanced description
            enhanced_description = self._generate_enhanced_description(context, client)
            
            # Classify access level and determine IAM requirements
            access_level, iam_requirements = self._classify_access_and_iam(context, client)
            
            # Enhance individual tasks if available in ai_enhanced_metadata
            enhanced_tasks = []
            detailed_tasks = codebundle.ai_enhanced_metadata.get("detailed_tasks", []) if codebundle.ai_enhanced_metadata else []
            if detailed_tasks:
                enhanced_tasks = self._enhance_individual_tasks(detailed_tasks, context, client)
            
            return {
                "enhanced_description": enhanced_description,
                "access_level": access_level,
                "iam_requirements": iam_requirements,
                "enhanced_tasks": enhanced_tasks,
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
        try:
            # Use the centralized prompt system
            prompt = AIPrompts.get_codebundle_prompt(context)
            system_prompt = AIPrompts.get_system_prompt('codebundle_enhancement')
            
            response = client.chat.completions.create(
                model=self._get_model_name(),
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            # Parse the JSON response to extract just the enhanced_description
            full_response = json.loads(response.choices[0].message.content.strip())
            if AIPrompts.validate_response_format(full_response, 'codebundle_enhancement'):
                return full_response.get('enhanced_description', context.get('description', 'Enhanced description not available'))
            else:
                logger.warning("AI response format validation failed for description enhancement")
                fallback = AIPrompts.get_fallback_response('codebundle_enhancement', context)
                return fallback['enhanced_description']
            
        except Exception as e:
            logger.error(f"Error generating enhanced description: {e}")
            fallback = AIPrompts.get_fallback_response('codebundle_enhancement', context)
            return fallback['enhanced_description']
    
    def _classify_access_and_iam(self, context: Dict[str, any], client: OpenAI) -> Tuple[str, List[str]]:
        """Classify access level and determine IAM requirements"""
        try:
            # Use the centralized prompt system
            prompt = AIPrompts.get_codebundle_prompt(context)
            system_prompt = AIPrompts.get_system_prompt('codebundle_enhancement')
            
            response = client.chat.completions.create(
                model=self._get_model_name(),
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=500,
                temperature=0.1
            )
            
            # Parse JSON response
            result = json.loads(response.choices[0].message.content.strip())
            if AIPrompts.validate_response_format(result, 'codebundle_enhancement'):
                access_level = result.get("access_level", "unknown")
                iam_requirements = result.get("iam_requirements", [])
                return access_level, iam_requirements
            else:
                logger.warning("AI response format validation failed for access classification")
                fallback = AIPrompts.get_fallback_response('codebundle_enhancement', context)
                return fallback['access_level'], fallback['iam_requirements']
            
        except Exception as e:
            logger.error(f"Error classifying access and IAM: {e}")
            fallback = AIPrompts.get_fallback_response('codebundle_enhancement', context)
            return fallback['access_level'], fallback['iam_requirements']
    


    def _enhance_individual_tasks(self, detailed_tasks: List[Dict], context: Dict[str, any], client: OpenAI) -> List[Dict]:
        """Enhance individual tasks with AI-generated purpose and function descriptions"""
        enhanced_tasks = []
        
        for task in detailed_tasks:
            try:
                # Use centralized prompt system
                task_prompt = AIPrompts.get_task_prompt(task, context)
                system_prompt = AIPrompts.get_system_prompt('task_enhancement')
                
                response = client.chat.completions.create(
                    model=self._get_model_name(),
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt
                        },
                        {
                            "role": "user",
                            "content": task_prompt
                        }
                    ],
                    max_tokens=600,
                    temperature=0.3
                )
                
                enhancement = json.loads(response.choices[0].message.content.strip())
                
                # Validate response format
                if AIPrompts.validate_response_format(enhancement, 'task_enhancement'):
                    enhanced_task = {
                        **task,  # Keep original task data
                        "ai_purpose": enhancement.get("purpose", ""),
                        "ai_function": enhancement.get("function", ""),
                        "ai_requirements": enhancement.get("requirements", [])
                    }
                else:
                    logger.warning(f"AI response format validation failed for task '{task.get('name', 'unknown')}'")
                    fallback = AIPrompts.get_fallback_response('task_enhancement', task)
                    enhanced_task = {
                        **task,  # Keep original task data
                        "ai_purpose": fallback.get("purpose", ""),
                        "ai_function": fallback.get("function", ""),
                        "ai_requirements": fallback.get("requirements", [])
                    }
                
                enhanced_tasks.append(enhanced_task)
                
            except Exception as e:
                logger.warning(f"Failed to enhance task '{task.get('name', 'unknown')}': {e}")
                # Use fallback response
                fallback = AIPrompts.get_fallback_response('task_enhancement', task)
                enhanced_task = {
                    **task,  # Keep original task data
                    "ai_purpose": fallback.get("purpose", ""),
                    "ai_function": fallback.get("function", ""),
                    "ai_requirements": fallback.get("requirements", [])
                }
                enhanced_tasks.append(enhanced_task)
        
        return enhanced_tasks
    


def get_ai_service(db_session: Session) -> AIEnhancementService:
    """Factory function to get AI service instance"""
    return AIEnhancementService(db_session)

