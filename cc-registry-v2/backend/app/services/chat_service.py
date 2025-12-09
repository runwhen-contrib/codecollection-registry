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
from sqlalchemy import func, or_, and_

from app.models import Codebundle, CodeCollection, AIConfiguration
from app.services.ai_service import AIEnhancementService

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
        context_limit: int = 5,
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
            
            # 2. Search in support tags
            for keyword in keywords:
                # Use PostgreSQL's JSON operators for tag search
                search_conditions.append(
                    func.cast(Codebundle.support_tags, func.text('text')).ilike(f"%{keyword}%")
                )
            
            # 3. Search in task names (stored in JSON)
            for keyword in keywords:
                search_conditions.append(
                    func.cast(Codebundle.tasks, func.text('text')).ilike(f"%{keyword}%")
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
            
            # Calculate keyword matches
            for text, weight in text_fields:
                text_lower = text.lower()
                for keyword in keywords:
                    if keyword in text_lower:
                        # Exact word match gets full score
                        if f" {keyword} " in f" {text_lower} " or text_lower.startswith(keyword) or text_lower.endswith(keyword):
                            score += weight
                        # Partial match gets half score
                        else:
                            score += weight * 0.5
            
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
        
        return scored_tasks
    
    def _build_context(self, question: str, relevant_tasks: List[Dict[str, Any]]) -> str:
        """Build context string for the AI from relevant tasks"""
        context_parts = [
            "# CodeCollection Registry - Available Tasks and Libraries",
            "",
            f"User Question: {question}",
            "",
            "## Relevant Tasks Found:",
            ""
        ]
        
        for i, task in enumerate(relevant_tasks, 1):
            context_parts.extend([
                f"### {i}. {task['codebundle_name']}",
                f"**Collection:** {task['collection_name']}",
                f"**Description:** {task['description'] or 'No description available'}",
                f"**Platform:** {task.get('platform', 'Generic')}",
                f"**Access Level:** {task['access_level']}",
                f"**Support Tags:** {', '.join(task['support_tags']) if task['support_tags'] else 'None'}",
                ""
            ])
            
            # Add tasks if available
            if task['tasks']:
                context_parts.append("**Available Tasks:**")
                for task_name in task['tasks'][:3]:  # Limit to first 3 tasks
                    if isinstance(task_name, str):
                        context_parts.append(f"- {task_name}")
                    elif isinstance(task_name, dict):
                        context_parts.append(f"- {task_name.get('name', 'Unknown Task')}")
                context_parts.append("")
            
            # Add IAM requirements if available
            if task['minimum_iam_requirements']:
                context_parts.extend([
                    "**Required Permissions:**",
                    f"- {', '.join(task['minimum_iam_requirements'])}",
                    ""
                ])
            
            # Add source URL if available
            if task['runbook_source_url']:
                context_parts.extend([
                    f"**Source:** {task['runbook_source_url']}",
                    ""
                ])
            
            context_parts.append("---")
            context_parts.append("")
        
        return "\n".join(context_parts)
    
    async def _generate_answer(self, question: str, context: str) -> str:
        """Generate an answer using the AI service"""
        try:
            client = self.ai_service._get_ai_client()
            model_name = self.ai_service._get_model_name()
            
            system_prompt = """You are a helpful assistant for the CodeCollection Registry. Your job is to help users find the right tasks and libraries for their needs.

When answering questions:
1. Be specific and actionable
2. Recommend the most relevant tasks from the provided context
3. Explain what each recommended task does
4. Mention any important requirements (permissions, platforms, etc.)
5. If multiple options exist, explain the differences
6. Keep answers concise but informative
7. Always base your recommendations on the provided context

If you can't find relevant information in the context, say so clearly."""

            user_prompt = f"""Based on the following context about available CodeCollection tasks and libraries, please answer the user's question.

{context}

Question: {question}

Please provide a helpful answer that recommends specific tasks and explains how they address the user's needs."""

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
        # Extract task names from context
        lines = context.split('\n')
        task_names = []
        
        for line in lines:
            if line.startswith('### '):
                # Extract task name
                task_name = line.replace('### ', '').split('.', 1)[-1].strip()
                task_names.append(task_name)
        
        if not task_names:
            return "I couldn't find any relevant tasks for your question. Please try rephrasing your query or check if the tasks you're looking for are available in the registry."
        
        answer_parts = [
            f"Based on your question '{question}', I found the following relevant tasks:",
            ""
        ]
        
        for i, task_name in enumerate(task_names, 1):
            answer_parts.append(f"{i}. **{task_name}**")
        
        answer_parts.extend([
            "",
            "Please check the task details above for more information about descriptions, requirements, and usage instructions."
        ])
        
        return "\n".join(answer_parts)
