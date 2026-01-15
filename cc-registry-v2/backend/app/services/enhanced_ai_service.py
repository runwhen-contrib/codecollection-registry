"""
Enhanced AI Service with Full Logging and Manual Control
Provides complete visibility into AI enhancement process
"""
import json
import logging
import time
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass

from openai import OpenAI, AzureOpenAI
from sqlalchemy.orm import Session
import requests

from app.core.config import settings
from app.models import AIConfiguration, Codebundle, RawRepositoryData
from app.models.ai_enhancement_log import AIEnhancementLog
from app.services.ai_prompts import AIPrompts

logger = logging.getLogger(__name__)


@dataclass
class AIConfig:
    """Simple configuration object for AI service"""
    service_provider: str
    api_key: str
    model_name: str
    enhancement_enabled: bool
    is_active: bool
    azure_endpoint: Optional[str] = None
    azure_deployment_name: Optional[str] = None
    api_version: Optional[str] = None


class EnhancedAIService:
    """Enhanced AI service with full logging and manual control"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.config = self._get_active_config()
        
    def _get_active_config(self) -> Optional[AIConfig]:
        """Get AI configuration from environment variables"""
        if settings.AI_SERVICE_PROVIDER == "azure-openai":
            if not (settings.AZURE_OPENAI_API_KEY and 
                   settings.AZURE_OPENAI_ENDPOINT and 
                   settings.AZURE_OPENAI_DEPLOYMENT_NAME):
                return None
            return AIConfig(
                service_provider="azure-openai",
                api_key=settings.AZURE_OPENAI_API_KEY,
                model_name=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                azure_endpoint=settings.AZURE_OPENAI_ENDPOINT,
                azure_deployment_name=settings.AZURE_OPENAI_DEPLOYMENT_NAME,
                api_version=settings.AZURE_OPENAI_API_VERSION,
                enhancement_enabled=settings.AI_ENHANCEMENT_ENABLED,
                is_active=True
            )
        else:
            if not settings.OPENAI_API_KEY:
                return None
            return AIConfig(
                service_provider="openai",
                api_key=settings.OPENAI_API_KEY,
                model_name=settings.AI_MODEL,
                enhancement_enabled=settings.AI_ENHANCEMENT_ENABLED,
                is_active=True
            )
    
    def is_enabled(self) -> bool:
        """Check if AI enhancement is enabled and configured"""
        return (
            self.config is not None and 
            self.config.api_key is not None and
            self.config.enhancement_enabled
        )
    
    def enhance_codebundle_with_logging(self, codebundle: Codebundle) -> Dict[str, any]:
        """
        Enhance a CodeBundle with full logging for debugging and manual editing
        """
        start_time = time.time()
        
        # Create log entry
        log_entry = AIEnhancementLog(
            codebundle_id=codebundle.id,
            codebundle_slug=codebundle.slug,
            status='pending',
            model_used=self.config.model_name if self.config else 'unknown',
            service_provider=self.config.service_provider if self.config else 'unknown'
        )
        self.db.add(log_entry)
        self.db.commit()
        
        try:
            if not self.is_enabled():
                log_entry.status = 'failed'
                log_entry.error_message = "AI enhancement is not enabled or configured"
                self.db.commit()
                raise ValueError("AI enhancement is not enabled or configured")
            
            # Prepare comprehensive context with actual robot code
            context = self._prepare_comprehensive_context(codebundle)
            
            # Generate prompts
            system_prompt = AIPrompts.get_system_prompt('codebundle_enhancement')
            user_prompt = self._generate_comprehensive_prompt(context)
            
            # Log the prompts being sent
            log_entry.system_prompt = system_prompt
            log_entry.prompt_sent = user_prompt
            self.db.commit()
            
            # Set up AI client
            client = self._get_ai_client()
            
            # Make AI API call
            try:
                response = client.chat.completions.create(
                    model=self._get_model_name(),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    max_tokens=1500,
                    temperature=0.3
                )
                
                # Log raw response
                raw_response = response.choices[0].message.content.strip()
                log_entry.ai_response_raw = raw_response
                
                # Parse response
                try:
                    parsed_response = json.loads(raw_response)
                    log_entry.ai_response_parsed = parsed_response
                    
                    # Extract enhancement data
                    enhanced_description = parsed_response.get('enhanced_description', '')
                    access_level = parsed_response.get('access_level', 'unknown')
                    iam_requirements = parsed_response.get('iam_requirements', [])
                    
                    log_entry.enhanced_description = enhanced_description
                    log_entry.access_level = access_level
                    log_entry.iam_requirements = iam_requirements
                    log_entry.status = 'success'
                    
                except json.JSONDecodeError as e:
                    log_entry.status = 'failed'
                    log_entry.error_message = f"Failed to parse AI response as JSON: {e}"
                    # Use fallback
                    enhanced_description = f"AI-generated description for {codebundle.name}. Raw response: {raw_response[:200]}..."
                    access_level = 'unknown'
                    iam_requirements = []
                
            except Exception as api_error:
                log_entry.status = 'failed'
                log_entry.error_message = f"AI API call failed: {str(api_error)}"
                
                # Use intelligent fallback based on actual data
                enhanced_description = self._generate_intelligent_fallback(context)
                access_level = self._classify_access_from_content(context)
                iam_requirements = self._extract_iam_from_content(context)
                
                log_entry.enhanced_description = enhanced_description
                log_entry.access_level = access_level
                log_entry.iam_requirements = iam_requirements
            
            # Calculate processing time
            processing_time = int((time.time() - start_time) * 1000)
            log_entry.processing_time_ms = processing_time
            
            self.db.commit()
            
            return {
                "enhanced_description": enhanced_description,
                "access_level": access_level,
                "iam_requirements": iam_requirements,
                "enhancement_metadata": {
                    "model_used": self.config.model_name,
                    "enhanced_at": datetime.utcnow().isoformat(),
                    "service_provider": self.config.service_provider,
                    "log_id": log_entry.id,
                    "processing_time_ms": processing_time
                }
            }
            
        except Exception as e:
            log_entry.status = 'failed'
            log_entry.error_message = str(e)
            log_entry.processing_time_ms = int((time.time() - start_time) * 1000)
            self.db.commit()
            raise
    
    def _prepare_comprehensive_context(self, codebundle: Codebundle) -> Dict[str, any]:
        """Prepare comprehensive context with actual robot code and scripts"""
        
        # Get robot file content
        robot_content = self._get_robot_file_content(codebundle)
        
        # Get all related files (scripts, configs, etc.)
        related_files = self._get_related_files(codebundle)
        
        # Extract actual task information
        actual_tasks = self._extract_tasks_from_robot(robot_content) if robot_content else []
        
        return {
            "name": codebundle.name,
            "slug": codebundle.slug,
            "display_name": codebundle.display_name,
            "description": codebundle.description,
            "doc": codebundle.doc,
            "author": codebundle.author,
            "support_tags": codebundle.support_tags or [],
            "platform": codebundle.discovery_platform or "Generic",
            "resource_types": codebundle.discovery_resource_types or [],
            "codecollection_name": getattr(codebundle.codecollection, 'name', 'Unknown') if codebundle.codecollection else "Unknown",
            
            # Actual code content
            "robot_content": robot_content,
            "related_files": related_files,
            "actual_tasks": actual_tasks,
            "runbook_path": codebundle.runbook_path,
            
            # Analysis hints
            "has_robot_content": bool(robot_content),
            "file_count": len(related_files),
            "task_count": len(actual_tasks)
        }
    
    def _get_robot_file_content(self, codebundle: Codebundle) -> Optional[str]:
        """Get the actual robot file content"""
        try:
            # Check if codecollection is loaded
            if not codebundle.codecollection:
                logger.warning(f"CodeBundle {codebundle.slug} has no codecollection relationship loaded")
                return None
            
            # Get collection slug safely
            collection_slug = getattr(codebundle.codecollection, 'slug', None)
            if not collection_slug:
                logger.warning(f"CodeBundle {codebundle.slug} codecollection has no slug attribute")
                return None
            
            # Look for robot file by slug
            robot_file = self.db.query(RawRepositoryData).filter(
                RawRepositoryData.collection_slug == collection_slug,
                RawRepositoryData.file_path.like(f'%{codebundle.slug}%'),
                RawRepositoryData.file_type == 'robot'
            ).first()
            
            if robot_file:
                return robot_file.file_content
            
            # Fallback: try by runbook path
            if codebundle.runbook_path:
                robot_file = self.db.query(RawRepositoryData).filter(
                    RawRepositoryData.collection_slug == collection_slug,
                    RawRepositoryData.file_path == codebundle.runbook_path
                ).first()
                
                if robot_file:
                    return robot_file.file_content
                    
        except Exception as e:
            logger.warning(f"Could not retrieve robot file content for {codebundle.slug}: {e}")
            
        return None
    
    def _get_related_files(self, codebundle: Codebundle) -> List[Dict[str, str]]:
        """Get all files related to this codebundle"""
        try:
            # Check if codecollection is loaded
            if not codebundle.codecollection:
                logger.warning(f"CodeBundle {codebundle.slug} has no codecollection relationship loaded")
                return []
            
            # Get collection slug safely
            collection_slug = getattr(codebundle.codecollection, 'slug', None)
            if not collection_slug:
                logger.warning(f"CodeBundle {codebundle.slug} codecollection has no slug attribute")
                return []
            
            files = self.db.query(RawRepositoryData).filter(
                RawRepositoryData.collection_slug == collection_slug,
                RawRepositoryData.file_path.like(f'%{codebundle.slug}%')
            ).all()
            
            return [
                {
                    "path": f.file_path or "",
                    "type": f.file_type or "",
                    "content": f.file_content[:500] if f.file_content else ""  # First 500 chars
                }
                for f in files if f  # Filter out any None values
            ]
        except Exception as e:
            logger.warning(f"Could not retrieve related files for {codebundle.slug}: {e}")
            return []
    
    def _extract_tasks_from_robot(self, robot_content: str) -> List[str]:
        """Extract actual task names from robot file"""
        if not robot_content:
            return []
            
        tasks = []
        try:
            lines = robot_content.split('\n')
            in_test_cases = False
            
            for line in lines:
                line = line.strip()
                
                if line.lower().startswith('*** test cases ***'):
                    in_test_cases = True
                    continue
                elif line.startswith('***') and in_test_cases:
                    in_test_cases = False
                    continue
                
                # Extract test case names
                if in_test_cases and line and not line.startswith('[') and not line.startswith('#'):
                    if not line.startswith(' ') and not line.startswith('\t'):
                        tasks.append(line)
                        
        except Exception as e:
            logger.warning(f"Error extracting tasks from robot content: {e}")
            
        return tasks
    
    def _generate_comprehensive_prompt(self, context: Dict[str, any]) -> str:
        """Generate a comprehensive prompt with all available data"""
        
        prompt = f"""
ANALYZE THIS AUTOMATION CODEBUNDLE FOR DETAILED ENHANCEMENT

CodeBundle Information:
- Name: {context.get('name', 'Unknown')}
- Slug: {context.get('slug', 'unknown')}
- Description: {context.get('description', 'No description available')}
- Platform: {context.get('platform', 'Generic')}
- Collection: {context.get('codecollection_name', 'Unknown')}
- Author: {context.get('author', 'Unknown')}

Actual Tasks Found:
{chr(10).join(f"- {task}" for task in context.get('actual_tasks', []))}

Robot Framework Content:
```robot
{context.get('robot_content', 'No robot content available')[:2000]}
```

Related Files:
{chr(10).join(f"- {f['path']} ({f['type']}): {f['content'][:100]}..." for f in context.get('related_files', [])[:5])}

PROVIDE DETAILED ANALYSIS:

1. Enhanced Description (3-4 sentences):
   - Explain EXACTLY what this automation does based on the actual code
   - Describe specific use cases and scenarios
   - Explain what problems it solves and business value
   - Include any important limitations or prerequisites

2. Access Level Classification:
   - "read-only": Only reads/queries resources
   - "read-write": Modifies, creates, deletes resources
   - "unknown": Cannot determine from available information

3. IAM Requirements (be EXTREMELY specific):
   - List exact permissions needed based on the actual code
   - Include service-specific permissions
   - Note any elevated privileges required
   - Provide minimum viable permission sets

Return response as JSON with keys: enhanced_description, access_level, iam_requirements
"""
        
        return prompt
    
    def _generate_intelligent_fallback(self, context: Dict[str, any]) -> str:
        """Generate intelligent fallback based on actual content analysis"""
        name = context.get('name', 'Unknown')
        platform = context.get('platform', 'Generic')
        actual_tasks = context.get('actual_tasks', [])
        robot_content = context.get('robot_content', '')
        collection = context.get('codecollection_name', 'Unknown')
        
        # Analyze content for detailed keywords and patterns
        content_lower = f"{name} {robot_content} {' '.join(actual_tasks)}".lower()
        
        # Azure-specific analysis
        if 'azure' in content_lower:
            if 'storage' in content_lower:
                if 'health' in content_lower:
                    return f"Azure Storage health monitoring automation that checks storage account availability, identifies unused disks and snapshots, detects public access containers, and validates storage configurations. Provides comprehensive health scoring for Azure storage resources in specified resource groups. Essential for maintaining storage security and cost optimization in Azure environments."
                else:
                    return f"Azure Storage management automation for {name}. Handles storage account operations, disk management, and container configurations on Azure platform. Provides automated storage lifecycle management and compliance monitoring."
            elif 'vm' in content_lower or 'virtual machine' in content_lower:
                return f"Azure Virtual Machine automation for {name}. Manages VM lifecycle, monitoring, and configuration on Azure platform. Provides automated VM operations with health checks and performance optimization."
            else:
                return f"Azure cloud automation for {name}. Manages Azure resources and services with automated monitoring and configuration. Provides cloud-native operations with Azure-specific optimizations."
        
        # Kubernetes-specific analysis
        elif 'k8s' in content_lower or 'kubernetes' in content_lower:
            if 'health' in content_lower:
                return f"Kubernetes health monitoring automation that validates cluster components, checks pod status, and monitors service availability. Provides comprehensive health assessment for Kubernetes workloads and infrastructure components."
            else:
                return f"Kubernetes automation for {name}. Manages cluster operations, workload deployment, and resource monitoring on Kubernetes platform. Provides cloud-native orchestration and scaling capabilities."
        
        # AWS-specific analysis
        elif 'aws' in content_lower or 'ec2' in content_lower or 's3' in content_lower:
            return f"AWS cloud automation for {name}. Manages AWS resources and services with automated monitoring, configuration, and optimization. Provides cloud-native operations with AWS-specific integrations."
        
        # Generic analysis based on operations
        elif 'health' in content_lower or 'check' in content_lower or 'monitor' in content_lower:
            operations = []
            if 'count' in content_lower: operations.append('resource counting')
            if 'status' in content_lower: operations.append('status monitoring') 
            if 'available' in content_lower: operations.append('availability checking')
            if 'unused' in content_lower: operations.append('unused resource detection')
            if 'public' in content_lower: operations.append('security validation')
            
            ops_desc = f" including {', '.join(operations)}" if operations else ""
            return f"Health monitoring and validation automation for {name}{ops_desc}. Provides comprehensive system health assessment, resource utilization analysis, and security compliance checking. Essential for maintaining operational excellence and cost optimization."
        
        elif 'deploy' in content_lower or 'install' in content_lower:
            return f"Deployment automation for {name}. Handles installation, configuration, and setup processes with automated validation and rollback capabilities. Ensures consistent and reliable deployment workflows."
        
        elif 'backup' in content_lower or 'restore' in content_lower:
            return f"Backup and recovery automation for {name}. Manages data protection, restoration processes, and disaster recovery procedures. Ensures data integrity and business continuity."
        
        else:
            # Use actual task names if available
            if actual_tasks:
                task_summary = f"Includes operations: {', '.join(actual_tasks[:2])}"
                if len(actual_tasks) > 2:
                    task_summary += f" and {len(actual_tasks) - 2} more tasks"
            else:
                task_summary = "Provides automated operational procedures"
            
            return f"Automation runbook for {name} operations. {task_summary}. Delivers standardized, repeatable processes with monitoring and validation capabilities."
    
    def _classify_access_from_content(self, context: Dict[str, any]) -> str:
        """Classify access level based on content analysis"""
        content = f"{context.get('name', '')} {context.get('robot_content', '')}".lower()
        
        write_keywords = ['create', 'delete', 'update', 'modify', 'deploy', 'install', 'configure', 'set', 'apply']
        read_keywords = ['get', 'list', 'describe', 'check', 'verify', 'monitor', 'health', 'status']
        
        write_score = sum(1 for keyword in write_keywords if keyword in content)
        read_score = sum(1 for keyword in read_keywords if keyword in content)
        
        if write_score > read_score:
            return 'read-write'
        elif read_score > 0:
            return 'read-only'
        else:
            return 'unknown'
    
    def _extract_iam_from_content(self, context: Dict[str, any]) -> List[str]:
        """Extract IAM requirements based on content analysis"""
        content = f"{context.get('name', '')} {context.get('robot_content', '')} {' '.join(context.get('actual_tasks', []))}".lower()
        platform = context.get('platform', '').lower()
        requirements = []
        
        # Azure-specific IAM extraction
        if 'azure' in content:
            if 'storage' in content:
                requirements.extend([
                    'Storage Account Contributor',
                    'Storage Blob Data Reader',
                    'Reader'
                ])
                if any(write_term in content for write_term in ['create', 'delete', 'modify', 'configure']):
                    requirements.extend([
                        'Storage Account Contributor',
                        'Storage Blob Data Contributor'
                    ])
            elif 'vm' in content or 'virtual machine' in content:
                requirements.extend([
                    'Virtual Machine Contributor',
                    'Reader'
                ])
            elif 'resource group' in content or 'resource_group' in content:
                requirements.extend([
                    'Reader',
                    'Resource Group Reader'
                ])
            else:
                requirements.extend(['Reader', 'Contributor'])
        
        # AWS-specific IAM extraction
        elif 'aws' in content or any(aws_term in content for aws_term in ['ec2', 's3', 'eks', 'rds']):
            if 'ec2' in content:
                requirements.extend(['ec2:DescribeInstances', 'ec2:DescribeInstanceStatus'])
            if 's3' in content:
                requirements.extend(['s3:GetObject', 's3:ListBucket'])
            if 'eks' in content:
                requirements.extend(['eks:DescribeCluster', 'eks:ListClusters'])
                
        # Kubernetes-specific RBAC extraction
        elif 'k8s' in content or 'kubernetes' in content:
            requirements.extend(['pods:get', 'pods:list', 'services:get'])
            if any(write_term in content for write_term in ['create', 'delete', 'update']):
                requirements.extend(['pods:create', 'pods:delete', 'deployments:patch'])
        
        # Remove duplicates and return
        return list(set(requirements))
    
    def _get_ai_client(self):
        """Get the appropriate AI client"""
        if self.config.service_provider == "azure-openai":
            if not self.config.azure_endpoint or not self.config.azure_deployment_name:
                raise ValueError("Azure OpenAI requires azure_endpoint and azure_deployment_name")
            
            return AzureOpenAI(
                api_key=self.config.api_key,
                api_version=self.config.api_version or "2024-02-15-preview",
                azure_endpoint=self.config.azure_endpoint
            )
        else:
            return OpenAI(api_key=self.config.api_key)
    
    def _get_model_name(self) -> str:
        """Get the model name to use"""
        if self.config.service_provider == "azure-openai":
            return self.config.azure_deployment_name or self.config.model_name
        else:
            return self.config.model_name


def get_enhanced_ai_service(db: Session) -> Optional[EnhancedAIService]:
    """Get enhanced AI service instance"""
    try:
        return EnhancedAIService(db)
    except Exception as e:
        logger.error(f"Failed to create enhanced AI service: {e}")
        return None
