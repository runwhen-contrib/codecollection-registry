"""
Chat Service for CodeCollection Query System
Implements RAG (Retrieval-Augmented Generation) for answering questions about codecollection tasks
"""
import json
import logging
import re
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, Text, cast, String

from app.models import Codebundle, CodeCollection, AIConfiguration
from app.services.ai_service import AIEnhancementService
from app.services.ai_prompts import AIPrompts

logger = logging.getLogger(__name__)


class ChatService:
    """Service for AI-powered chat about codecollection tasks"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.ai_service = AIEnhancementService(db_session)
        
    def is_enabled(self) -> bool:
        """Check if chat service is enabled"""
        return self.ai_service.is_enabled()
    
    async def answer_query(
        self,
        question: str,
        context_limit: int = 10,
        include_enhanced_descriptions: bool = True
    ) -> Dict[str, Any]:
        """
        Answer a question about codecollection tasks using RAG
        
        Args:
            question: User's question
            context_limit: Maximum number of relevant tasks to include in context
            include_enhanced_descriptions: Whether to use AI-enhanced descriptions
            
        Returns:
            Dict containing answer, relevant tasks, and metadata
        """
        try:
            # Step 1: Find relevant tasks using semantic search
            relevant_tasks = self._find_relevant_tasks(
                question, 
                limit=context_limit,
                include_enhanced_descriptions=include_enhanced_descriptions
            )
            
            # Step 2: Build context for the AI
            context = self._build_context(question, relevant_tasks)
            
            # Step 3: Generate answer using AI (or fallback if AI not available)
            if self.is_enabled():
                answer = await self._generate_answer(question, context)
            else:
                answer = self._generate_fallback_answer(question, context)
            
            # Step 4: Extract sources and metadata
            sources_used = [task["codebundle_name"] for task in relevant_tasks]
            
            return {
                "answer": answer,
                "relevant_tasks": relevant_tasks,
                "sources_used": sources_used,
                "metadata": {
                    "query_processed_at": datetime.utcnow().isoformat(),
                    "context_tasks_count": len(relevant_tasks),
                    "ai_model": self.ai_service.config.model_name if self.ai_service.config else "fallback"
                }
            }
            
        except Exception as e:
            logger.error(f"Error answering query: {e}")
            raise
    
    def _find_relevant_tasks(
        self, 
        question: str, 
        limit: int = 5,
        include_enhanced_descriptions: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Find relevant tasks based on the user's question using multiple search strategies
        """
        try:
            # Extract keywords from the question
            keywords = self._extract_keywords(question)
            
            # Build search query
            query = self.db.query(Codebundle).filter(Codebundle.is_active == True)
            
            # Search conditions
            search_conditions = []
            
            # 1. Search in names and descriptions
            for keyword in keywords:
                keyword_pattern = f"%{keyword}%"
                search_conditions.extend([
                    Codebundle.name.ilike(keyword_pattern),
                    Codebundle.display_name.ilike(keyword_pattern),
                    Codebundle.description.ilike(keyword_pattern),
                ])
                
                # Include AI-enhanced descriptions if available
                if include_enhanced_descriptions:
                    search_conditions.append(
                        Codebundle.ai_enhanced_description.ilike(keyword_pattern)
                    )
            
            # 2. Search in support tags (JSON array)
            for keyword in keywords:
                # Convert JSON array to text for searching
                search_conditions.append(
                    func.cast(Codebundle.support_tags, Text).ilike(f"%{keyword}%")
                )
            
            # 3. Search in task names (JSON array)
            for keyword in keywords:
                search_conditions.append(
                    func.cast(Codebundle.tasks, Text).ilike(f"%{keyword}%")
                )
            
            # Combine all search conditions with OR
            if search_conditions:
                query = query.filter(or_(*search_conditions))
            
            # Join with CodeCollection for additional context
            query = query.join(CodeCollection)
            
            # Execute query and get results
            codebundles = query.limit(limit * 2).all()  # Get more than needed for ranking
            
            # Rank and filter results
            ranked_tasks = self._rank_tasks_by_relevance(question, codebundles, keywords)
            
            # Convert to response format
            result_tasks = []
            for codebundle, score in ranked_tasks[:limit]:
                # Get collection info
                collection = codebundle.codecollection
                
                # Prepare task data
                task_data = {
                    "id": codebundle.id,
                    "codebundle_name": codebundle.display_name or codebundle.name,
                    "codebundle_slug": codebundle.slug,
                    "collection_name": collection.name,
                    "collection_slug": collection.slug,
                    "description": codebundle.ai_enhanced_description if (include_enhanced_descriptions and codebundle.ai_enhanced_description) else codebundle.description,
                    "support_tags": codebundle.support_tags or [],
                    "tasks": codebundle.tasks or [],
                    "slis": codebundle.slis or [],
                    "author": codebundle.author,
                    "access_level": codebundle.access_level or "unknown",
                    "minimum_iam_requirements": codebundle.minimum_iam_requirements or [],
                    "runbook_source_url": codebundle.runbook_source_url,
                    "relevance_score": score,
                    "platform": codebundle.discovery_platform,
                    "resource_types": codebundle.discovery_resource_types or []
                }
                
                result_tasks.append(task_data)
            
            return result_tasks
            
        except Exception as e:
            logger.error(f"Error finding relevant tasks: {e}")
            return []
    
    def _extract_keywords(self, question: str) -> List[str]:
        """Extract relevant keywords from the user's question"""
        # Convert to lowercase
        question = question.lower()
        
        # Remove common stop words and question words
        stop_words = {
            'what', 'how', 'when', 'where', 'why', 'which', 'who', 'do', 'does', 'did',
            'is', 'are', 'was', 'were', 'be', 'been', 'being', 'have', 'has', 'had',
            'will', 'would', 'could', 'should', 'can', 'may', 'might', 'must',
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'up', 'about', 'into', 'through', 'during',
            'before', 'after', 'above', 'below', 'between', 'among', 'i', 'me', 'my',
            'you', 'your', 'he', 'him', 'his', 'she', 'her', 'it', 'its', 'we', 'us',
            'our', 'they', 'them', 'their'
        }
        
        # Extract words (alphanumeric + hyphens)
        words = re.findall(r'\b[a-zA-Z0-9-]+\b', question)
        
        # Filter out stop words and short words
        keywords = [word for word in words if word not in stop_words and len(word) > 2]
        
        # Add some domain-specific keyword mapping
        keyword_expansions = {
            'pod': ['kubernetes', 'k8s', 'container'],
            'pods': ['kubernetes', 'k8s', 'container'],
            'k8s': ['kubernetes'],
            'cli': ['command', 'terminal', 'bash'],
            'failing': ['error', 'fail', 'issue', 'problem', 'debug'],
            'debug': ['troubleshoot', 'diagnose', 'error'],
            'azure': ['microsoft', 'cloud'],
            'aws': ['amazon', 'cloud'],
            'gcp': ['google', 'cloud'],
        }
        
        # Expand keywords
        expanded_keywords = set(keywords)
        for keyword in keywords:
            if keyword in keyword_expansions:
                expanded_keywords.update(keyword_expansions[keyword])
        
        return list(expanded_keywords)
    
    def _rank_tasks_by_relevance(
        self, 
        question: str, 
        codebundles: List[Codebundle], 
        keywords: List[str]
    ) -> List[Tuple[Codebundle, float]]:
        """Rank codebundles by relevance to the question"""
        scored_tasks = []
        
        for codebundle in codebundles:
            score = 0.0
            
            # Text fields to search in
            text_fields = [
                (codebundle.name or "", 3.0),  # Name gets highest weight
                (codebundle.display_name or "", 2.5),
                (codebundle.description or "", 2.0),
                (codebundle.ai_enhanced_description or "", 2.2),  # AI descriptions get slightly higher weight
                (codebundle.doc or "", 1.5),
                (str(codebundle.support_tags or []), 1.8),
                (str(codebundle.tasks or []), 1.5),
                (codebundle.discovery_platform or "", 1.3),
                (str(codebundle.discovery_resource_types or []), 1.2)
            ]
            
            # Calculate keyword matches (more strict)
            for text, weight in text_fields:
                text_lower = text.lower()
                for keyword in keywords:
                    # Only count exact word boundaries, not partial matches
                    if re.search(r'\b' + re.escape(keyword) + r'\b', text_lower):
                        score += weight
                    # No partial matches - they create too much noise
            
            # Boost score for certain indicators
            question_lower = question.lower()
            
            # Boost for troubleshooting/debugging questions
            if any(word in question_lower for word in ['failing', 'fail', 'error', 'debug', 'troubleshoot', 'issue', 'problem']):
                if any(tag in str(codebundle.support_tags or []).lower() for tag in ['debug', 'troubleshoot', 'error', 'diagnostic']):
                    score += 2.0
            
            # Boost for platform-specific questions
            platforms = ['kubernetes', 'k8s', 'azure', 'aws', 'gcp', 'docker']
            for platform in platforms:
                if platform in question_lower:
                    if platform in (codebundle.discovery_platform or "").lower():
                        score += 1.5
                    if platform in str(codebundle.support_tags or []).lower():
                        score += 1.0
            
            # Boost for access level preferences
            if 'read-only' in question_lower or 'readonly' in question_lower:
                if codebundle.access_level == 'read-only':
                    score += 1.0
            
            scored_tasks.append((codebundle, score))
        
        # Sort by score (descending)
        scored_tasks.sort(key=lambda x: x[1], reverse=True)
        
        # Filter out tasks with very low relevance scores
        # Only keep tasks with a minimum absolute score (not just relative)
        MIN_RELEVANCE_THRESHOLD = 3.0  # Minimum score to be considered relevant (increased from 1.0)
        filtered_tasks = [(cb, score) for cb, score in scored_tasks if score >= MIN_RELEVANCE_THRESHOLD]
        
        # Normalize scores to percentages (0-100%)
        if filtered_tasks:
            max_score = filtered_tasks[0][1] if filtered_tasks[0][1] > 0 else 1.0
            normalized_tasks = []
            for codebundle, score in filtered_tasks:
                # Convert to percentage and cap at 100%
                percentage = min(100.0, (score / max_score) * 100.0)
                normalized_tasks.append((codebundle, percentage))
            return normalized_tasks
        
        return []  # Return empty list if no tasks meet threshold
    
    def _build_context(self, question: str, relevant_tasks: List[Dict[str, Any]]) -> str:
        """Build context string for the AI from relevant tasks - focused on task names"""
        context_parts = []
        
        for i, task in enumerate(relevant_tasks, 1):
            context_parts.extend([
                f"## Codebundle {i}: {task['codebundle_name']}",
                f"**Collection:** {task['collection_name']}",
                f"**Description:** {task['description'] or 'No description available'}",
                f"**Platform:** {task.get('platform', 'Generic')}",
                f"**Support Tags:** {', '.join(task['support_tags']) if task['support_tags'] else 'None'}",
                ""
            ])
            
            # Emphasize the tasks - this is what we want to recommend
            if task['tasks']:
                context_parts.append("**TASKS (these are what you should recommend):**")
                for task_name in task['tasks']:
                    if isinstance(task_name, str):
                        context_parts.append(f'- "{task_name}"')
                    elif isinstance(task_name, dict):
                        context_parts.append(f'- "{task_name.get("name", "Unknown Task")}"')
                context_parts.append("")
            
            # Add SLIs if available
            if task.get('slis'):
                context_parts.append("**SLI TASKS:**")
                for sli_name in task['slis']:
                    if isinstance(sli_name, str):
                        context_parts.append(f'- "{sli_name}"')
                    elif isinstance(sli_name, dict):
                        context_parts.append(f'- "{sli_name.get("name", "Unknown SLI")}"')
                context_parts.append("")
            
            # Add access level and permissions for context
            if task['access_level'] != 'unknown':
                context_parts.append(f"**Access Level:** {task['access_level']}")
            
            if task['minimum_iam_requirements']:
                context_parts.append(f"**Required Permissions:** {', '.join(task['minimum_iam_requirements'])}")
            
            context_parts.extend(["", "---", ""])
        
        return "\n".join(context_parts)
    
    async def _generate_answer(self, question: str, context: str) -> str:
        """Generate an answer using the AI service"""
        try:
            client = self.ai_service._get_ai_client()
            model_name = self.ai_service._get_model_name()
            
            # Use the improved chat prompts
            system_prompt = AIPrompts.get_system_prompt('chat_query')
            user_prompt = AIPrompts.get_chat_query_prompt(question, context)

            response = client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=800,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error generating AI answer: {e}")
            # Fallback to a simple context-based answer
            return self._generate_fallback_answer(question, context)
    
    def _generate_fallback_answer(self, question: str, context: str) -> str:
        """Generate a simple fallback answer when AI is not available"""
        # Extract actual task names from context (look for quoted task names)
        lines = context.split('\n')
        task_names = []
        codebundle_names = []
        
        current_codebundle = None
        for line in lines:
            if line.startswith('## Codebundle'):
                # Extract codebundle name
                current_codebundle = line.split(':', 1)[-1].strip()
                codebundle_names.append(current_codebundle)
            elif line.startswith('- "') and line.endswith('"'):
                # Extract task name (in quotes)
                task_name = line.strip('- "')
                if current_codebundle:
                    task_names.append((task_name, current_codebundle))
        
        if not task_names:
            return f"""**No Matching Tasks Found**

I couldn't find any tasks in the CodeCollection registry that match your request for "{question}".

**Would you like these tasks added to the registry?**

Based on your question, it would be helpful to have tasks that can handle: {question}

You can create a GitHub issue to request these tasks be added to the registry."""
        
        answer_parts = [
            f"**Tasks Available in Registry for: {question}**",
            ""
        ]
        
        for i, (task_name, codebundle_name) in enumerate(task_names, 1):
            answer_parts.append(f'{i}. **"{task_name}"** (from {codebundle_name})')
        
        answer_parts.extend([
            "",
            "These are the available tasks from the CodeCollection registry that match your query."
        ])
        
        return "\n".join(answer_parts)
