"""
AI Enhancement Prompts Management

This file contains all the prompts used for AI enhancement of CodeBundles and tasks.
Centralizing prompts here makes them easier to manage, version, and improve.
"""

from typing import Dict, Any


class AIPrompts:
    """Centralized management of AI enhancement prompts"""
    
    # System prompts for different enhancement types
    SYSTEM_PROMPTS = {
        "codebundle_enhancement": """You are an expert in cloud infrastructure, DevOps automation, and security compliance. 
Analyze CodeBundles (automation runbooks) to provide detailed, actionable descriptions and classify their specific access requirements.

Your response must be valid JSON with these exact keys:
- enhanced_description: A detailed, comprehensive description (3-4 sentences) explaining what this does, when to use it, and what problems it solves
- access_level: Either "read-only", "read-write", or "unknown"
- iam_requirements: Array of SPECIFIC IAM permissions, policies, or roles needed (be very detailed and platform-specific)

Focus on providing actionable information that helps users understand exactly what permissions they need and when to use this automation.""",

        "task_enhancement": """You are an expert in cloud infrastructure, DevOps automation, and security compliance. 
Analyze individual automation tasks to provide detailed, actionable descriptions with specific use cases and authorization requirements.

Return your response as JSON with keys:
- purpose: Detailed explanation of why this task exists and what problem it solves (2-3 sentences)
- function: Comprehensive explanation of what this task does, how it works, and when you would use it (3-4 sentences)
- requirements: List of SPECIFIC prerequisites, permissions, tools, and conditions needed (be very detailed about authorization requirements)""",

        "chat_query": """You are a RunWhen CodeBundle recommendation assistant. Help users find automation scripts for infrastructure troubleshooting.

CRITICAL RULES:
1. **BE STRICT ABOUT RELEVANCE** - Only recommend codebundles that DIRECTLY address the user's specific question
2. **DON'T PAD RESULTS** - Quality over quantity. 1-2 good matches is better than 5 tangential ones
3. **USE EXACT NAMES** - Reference codebundles exactly as they appear in the provided data
4. **BE HONEST** - If nothing truly matches, say so instead of suggesting loosely related options

When relevant codebundles exist:
- Explain what each does and why it matches the query
- Mention collection and platform
- Be conversational and helpful

When NO relevant codebundles exist:
- Be upfront: "I couldn't find a codebundle specifically for [user's need]"
- Suggest creating a GitHub issue to request new automation
- Don't include loosely-related results just to have something to show"""
    }
    
    # Template prompts for different enhancement scenarios
    CODEBUNDLE_ENHANCEMENT_TEMPLATE = """
Analyze this automation CodeBundle and provide detailed, actionable metadata:

CodeBundle Information:
- Name: {name}
- Current Description: {description}
- Platform: {platform}
- Resource Types: {resource_types}
- Tasks: {tasks}
- Support Tags: {support_tags}
- Author: {author}
- Collection: {codecollection_name}

{robot_content_section}

Provide detailed analysis:

1. Enhanced Description: 
   - Explain EXACTLY what this CodeBundle does (be specific about the operations)
   - Describe WHEN and WHY someone would use this (specific scenarios and use cases)
   - Explain what problems it solves and what value it provides
   - Include any important limitations or considerations
   - Make it actionable for both technical teams and management

2. Access Level Classification:
   - "read-only": Only reads/queries resources (monitoring, health checks, information gathering)
   - "read-write": Modifies, creates, deletes, or changes resources (deployments, scaling, configuration changes)
   - "unknown": Cannot determine from available information

3. IAM Requirements - BE VERY SPECIFIC:
   For AWS: List exact IAM actions (e.g., "ec2:DescribeInstances", "eks:DescribeCluster", "iam:ListRoles")
   For Kubernetes: List exact RBAC permissions (e.g., "pods:get", "deployments:list", "secrets:create")
   For Azure: List exact role assignments (e.g., "Virtual Machine Contributor", "Reader", "Network Contributor")
   For GCP: List exact IAM roles (e.g., "roles/compute.instanceAdmin", "roles/container.developer")
   
   Include:
   - Service-specific permissions
   - Resource-level permissions where applicable
   - Any cross-service permissions needed
   - Minimum viable permission sets
   - Any elevated permissions and why they're needed

Platform Context: {platform}
Resource Types: {resource_types}

Be extremely detailed about authorization requirements - this is critical for security and compliance.
"""

    TASK_ENHANCEMENT_TEMPLATE = """
Analyze this automation task and provide comprehensive, actionable details:

CodeBundle Context: {codebundle_name}
Platform: {platform}
Resource Types: {resource_types}

Task Details:
- Name: {task_name}
- Description: {task_description}
- Documentation: {task_documentation}
- Tags: {task_tags}
- Steps: {task_steps}

Provide detailed analysis:

1. Purpose (2-3 sentences):
   - WHY does this task exist? What specific problem does it solve?
   - What business or operational value does it provide?
   - When would you typically need to run this task?
   - What happens if this task is NOT performed?

2. Function (3-4 sentences):
   - EXACTLY what does this task do? Be specific about the operations performed.
   - HOW does it work? Describe the process and methodology.
   - What are the expected inputs and outputs?
   - What systems, services, or resources does it interact with?
   - What are the success criteria and how do you know it worked?

3. Requirements - BE EXTREMELY SPECIFIC:
   Authorization Requirements:
   - List EXACT permissions needed (e.g., "ec2:DescribeInstances", "pods:get", "roles/viewer")
   - Specify service accounts, roles, or user permissions required
   - Include any elevated privileges and WHY they're needed
   - Note any cross-service or cross-resource permissions
   
   Prerequisites:
   - Required tools, CLI access, or software installed
   - Network connectivity requirements
   - Required configuration files or environment variables
   - Dependencies on other tasks or systems
   - Minimum resource requirements (CPU, memory, etc.)
   
   Conditions:
   - When this task should/shouldn't be run
   - Required system states or conditions
   - Time-sensitive considerations
   - Risk factors or safety considerations

Platform: {platform} | Resource Types: {resource_types}

Focus on providing actionable, security-conscious information that helps users understand exactly what they need and when to use this task.
"""

    CHAT_QUERY_TEMPLATE = """
User Question: "{user_question}"

Available CodeBundles and Their Tasks:
{context_codebundles}

STRICT REQUIREMENTS:
- ONLY recommend tasks that appear in the above codebundles
- Use EXACT task names from the "tasks" arrays (in quotes)
- If no relevant tasks exist, say so and suggest adding them to the registry

IF RELEVANT TASKS EXIST, format as:

**Tasks Available in Registry for: {user_question}**

1. **"Exact Task Name"** (from Codebundle Name)
   - What it does: [Based on codebundle description]
   - When to use: [Specific scenario]

IF NO RELEVANT TASKS EXIST, respond with:

**No Matching Tasks Found**

I couldn't find any tasks in the CodeCollection registry that match your request for "{user_question}".

**Would you like these tasks added to the registry?**

[Briefly describe what types of tasks would be helpful for their use case]

You can create a GitHub issue to request these tasks be added to the registry.

NEVER invent or suggest tasks that don't exist in the provided data.
"""

    # Prompt variations for different scenarios
    ENHANCEMENT_VARIATIONS = {
        "aws": {
            "context_suffix": "\nAWS PLATFORM - Be extremely specific about IAM permissions. Include service-specific actions, resource ARNs where applicable, and consider cross-service dependencies. Mention AWS CLI requirements and any required AWS service configurations.",
            "iam_examples": [
                "ec2:DescribeInstances", "ec2:StartInstances", "ec2:StopInstances",
                "eks:DescribeCluster", "eks:ListClusters", "eks:UpdateClusterConfig",
                "iam:ListRoles", "iam:PassRole", "iam:GetRole",
                "s3:GetObject", "s3:PutObject", "s3:ListBucket",
                "cloudwatch:GetMetricStatistics", "cloudwatch:PutMetricData",
                "logs:CreateLogGroup", "logs:DescribeLogGroups"
            ]
        },
        "kubernetes": {
            "context_suffix": "\nKUBERNETES PLATFORM - Be extremely specific about RBAC permissions. Include exact resource types, verbs, and namespaces. Consider cluster-level vs namespace-level permissions and any required service accounts.",
            "iam_examples": [
                "pods:get", "pods:list", "pods:create", "pods:delete",
                "deployments:get", "deployments:list", "deployments:create", "deployments:update",
                "services:get", "services:list", "services:create",
                "configmaps:get", "configmaps:create", "secrets:get", "secrets:create",
                "nodes:get", "nodes:list", "persistentvolumes:get"
            ]
        },
        "gcp": {
            "context_suffix": "\nGCP PLATFORM - Be extremely specific about IAM roles and permissions. Include predefined roles, custom role requirements, and service account permissions. Mention gcloud CLI requirements and any required API enablements.",
            "iam_examples": [
                "roles/compute.instanceAdmin", "roles/compute.viewer",
                "roles/container.developer", "roles/container.clusterViewer",
                "roles/storage.objectViewer", "roles/storage.objectAdmin",
                "roles/monitoring.viewer", "roles/logging.viewer",
                "roles/iam.serviceAccountUser", "roles/resourcemanager.projectViewer"
            ]
        },
        "azure": {
            "context_suffix": "\nAZURE PLATFORM - Be extremely specific about RBAC roles and permissions. Include built-in roles, custom role requirements, and resource-level permissions. Mention Azure CLI requirements and any required resource provider registrations.",
            "iam_examples": [
                "Virtual Machine Contributor", "Virtual Machine Reader",
                "Network Contributor", "Storage Account Contributor",
                "Kubernetes Service Cluster Admin Role", "Azure Kubernetes Service Cluster User Role",
                "Monitoring Reader", "Log Analytics Reader",
                "Resource Group Reader", "Subscription Reader"
            ]
        }
    }

    @classmethod
    def get_codebundle_prompt(cls, codebundle_context: Dict[str, Any]) -> str:
        """
        Generate a complete prompt for CodeBundle enhancement
        
        Args:
            codebundle_context: Dictionary containing CodeBundle information
            
        Returns:
            Complete prompt string ready for AI model
        """
        # Prepare robot content section
        robot_content_section = ""
        if codebundle_context.get('robot_content'):
            robot_content_section = f"""
Robot Framework Content (first 1000 characters):
```
{codebundle_context.get('robot_content', '')}
```

This gives you actual implementation details to analyze for more accurate enhancement."""
        else:
            robot_content_section = "Robot Framework content not available - analyze based on available metadata."

        base_prompt = cls.CODEBUNDLE_ENHANCEMENT_TEMPLATE.format(
            name=codebundle_context.get('name', 'Unknown'),
            description=codebundle_context.get('description', 'No description available'),
            platform=codebundle_context.get('platform', 'Unknown'),
            resource_types=', '.join(codebundle_context.get('resource_types', [])),
            tasks=', '.join(codebundle_context.get('tasks', [])),
            support_tags=', '.join(codebundle_context.get('support_tags', [])),
            author=codebundle_context.get('author', 'Unknown'),
            codecollection_name=codebundle_context.get('codecollection_name', 'Unknown'),
            robot_content_section=robot_content_section
        )
        
        # Add platform-specific context if available
        platform = codebundle_context.get('platform', '') or ''
        platform = platform.lower() if platform else ''
        if platform and platform in cls.ENHANCEMENT_VARIATIONS:
            variation = cls.ENHANCEMENT_VARIATIONS[platform]
            base_prompt += variation['context_suffix']
            base_prompt += f"\n\nExample IAM requirements for {platform.upper()}: {', '.join(variation['iam_examples'])}"
        
        return base_prompt

    @classmethod
    def get_task_prompt(cls, task_context: Dict[str, Any], codebundle_context: Dict[str, Any]) -> str:
        """
        Generate a complete prompt for individual task enhancement
        
        Args:
            task_context: Dictionary containing task information
            codebundle_context: Dictionary containing parent CodeBundle information
            
        Returns:
            Complete prompt string ready for AI model
        """
        base_prompt = cls.TASK_ENHANCEMENT_TEMPLATE.format(
            codebundle_name=codebundle_context.get('name', 'Unknown'),
            platform=codebundle_context.get('platform', 'Unknown'),
            resource_types=', '.join(codebundle_context.get('resource_types', [])),
            task_name=task_context.get('name', 'Unknown'),
            task_description=task_context.get('description', 'No description available'),
            task_documentation=task_context.get('documentation', 'No documentation available'),
            task_tags=', '.join(task_context.get('tags', [])),
            task_steps=', '.join(task_context.get('steps', []))
        )
        
        # Add platform-specific context if available
        platform = codebundle_context.get('platform', '') or ''
        platform = platform.lower() if platform else ''
        if platform and platform in cls.ENHANCEMENT_VARIATIONS:
            variation = cls.ENHANCEMENT_VARIATIONS[platform]
            base_prompt += variation['context_suffix']
        
        return base_prompt

    @classmethod
    def get_chat_query_prompt(cls, user_question: str, context_codebundles: str) -> str:
        """
        Generate a complete prompt for chat queries about codebundles
        
        Args:
            user_question: The user's question
            context_codebundles: Formatted string of relevant codebundles
            
        Returns:
            Complete prompt string ready for AI model
        """
        return cls.CHAT_QUERY_TEMPLATE.format(
            user_question=user_question,
            context_codebundles=context_codebundles
        )

    @classmethod
    def get_system_prompt(cls, enhancement_type: str) -> str:
        """
        Get the system prompt for a specific enhancement type
        
        Args:
            enhancement_type: Type of enhancement ('codebundle_enhancement' or 'task_enhancement')
            
        Returns:
            System prompt string
        """
        return cls.SYSTEM_PROMPTS.get(enhancement_type, cls.SYSTEM_PROMPTS['codebundle_enhancement'])

    @classmethod
    def validate_response_format(cls, response: Dict[str, Any], enhancement_type: str) -> bool:
        """
        Validate that AI response has the expected format
        
        Args:
            response: AI response dictionary
            enhancement_type: Type of enhancement being validated
            
        Returns:
            True if response format is valid, False otherwise
        """
        if enhancement_type == 'codebundle_enhancement':
            required_keys = ['enhanced_description', 'access_level', 'iam_requirements']
            valid_access_levels = ['read-only', 'read-write', 'unknown']
            
            # Check required keys exist
            if not all(key in response for key in required_keys):
                return False
            
            # Check access_level is valid
            if response['access_level'] not in valid_access_levels:
                return False
            
            # Check iam_requirements is a list
            if not isinstance(response['iam_requirements'], list):
                return False
                
        elif enhancement_type == 'task_enhancement':
            required_keys = ['purpose', 'function', 'requirements']
            
            # Check required keys exist
            if not all(key in response for key in required_keys):
                return False
            
            # Check requirements is a list
            if not isinstance(response['requirements'], list):
                return False
        
        return True

    @classmethod
    def get_fallback_response(cls, enhancement_type: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate a fallback response when AI enhancement fails
        
        Args:
            enhancement_type: Type of enhancement
            context: Context information for generating fallback
            
        Returns:
            Fallback response dictionary
        """
        if enhancement_type == 'codebundle_enhancement':
            return {
                'enhanced_description': f"Automation runbook for {context.get('name', 'unknown')} operations. Please review and enhance this description.",
                'access_level': 'unknown',
                'iam_requirements': []
            }
        elif enhancement_type == 'task_enhancement':
            return {
                'purpose': f"Performs {context.get('name', 'unknown')} operation.",
                'function': "Please review this task and provide detailed function description.",
                'requirements': []
            }
        
        return {}


# Convenience functions for backward compatibility
def get_codebundle_enhancement_prompt(codebundle_context: Dict[str, Any]) -> str:
    """Get CodeBundle enhancement prompt - convenience function"""
    return AIPrompts.get_codebundle_prompt(codebundle_context)


def get_task_enhancement_prompt(task_context: Dict[str, Any], codebundle_context: Dict[str, Any]) -> str:
    """Get task enhancement prompt - convenience function"""
    return AIPrompts.get_task_prompt(task_context, codebundle_context)


def get_system_prompt(enhancement_type: str = 'codebundle_enhancement') -> str:
    """Get system prompt - convenience function"""
    return AIPrompts.get_system_prompt(enhancement_type)
