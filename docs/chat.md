# Registry Chat System

## Overview

The Registry Chat system provides conversational AI assistance for finding CodeBundles, documentation, and troubleshooting guidance. It uses MCP (Model Context Protocol) for semantic search and Azure OpenAI for natural language synthesis.

**User Access:** http://localhost:3000/chat (public)

---

## Architecture

### Flow
1. User sends question to `/api/v1/chat/query`
2. System detects if follow-up question (checks conversation history + phrase patterns)
3. **Follow-up:** Uses conversation context, optional focused search
4. **New query:** Full MCP semantic search across codebundles
5. LLM synthesizes answer from context + search results
6. Response includes relevant CodeBundles and confidence scores
7. Interaction logged for quality analysis

### Key Components

**Backend:**
- `backend/app/routers/mcp_chat.py` - Main chat endpoint, follow-up detection, LLM integration
- `backend/app/services/ai_enhancement_service.py` - Azure OpenAI client wrapper
- MCP Server - Semantic search over codebundle corpus

**Frontend:**
- `frontend/src/pages/Chat.tsx` - Chat UI with conversation history
- `frontend/src/services/api.ts` - API client for chat endpoint

---

## Follow-up Question Detection

### How It Works
The system detects when a user is asking about a previously mentioned codebundle rather than starting a new query.

**Detection Phrases:**
```python
# Triggers follow-up mode (lines 166-178 in mcp_chat.py)
'this codebundle', 'that codebundle', 'same codebundle',
'show me the link', 'what is the link', 'link to this',
'how do i use this', 'how to use this',
'tell me more', 'more details', 'more about it',
'where can i find this', 'give me the link'
```

**Requirements:**
- Question contains one of the trigger phrases
- `conversation_history` is present in request body
- At least one previous message in conversation

**Behavior:**
- Extracts codebundle name from conversation history (regex pattern)
- Runs optional focused search for that specific codebundle
- Prioritizes conversation context over new search results
- LLM receives special prompt emphasizing conversation context

### Known Issues & Fixes

#### Issue: Contradictory Responses (Fixed 2026-01-19)

**Problem:** System recommended a codebundle, then claimed it couldn't find it on follow-up.

**Example:**
```
User: Help me troubleshoot a deployment
Bot: ✓ Use k8s-deployment-healthcheck

User: show me the link to this codebundle
Bot: ❌ [NO_MATCHING_CODEBUNDLE] I couldn't find it
```

**Root Cause:**
1. Follow-up detection didn't recognize "show me the link"
2. System ran new semantic search for that phrase → 0 results
3. LLM didn't prioritize conversation context

**Fix Location:** `backend/app/routers/mcp_chat.py`
- Lines 166-178: Enhanced phrase detection (added link/usage requests)
- Lines 864-891: Special LLM prompt for follow-ups
- Lines 232-275: Follow-up response handling with conversation context priority

**Testing:**
```bash
# Test follow-up detection
curl -X POST http://localhost:8001/api/v1/chat/query \
  -H "Content-Type: application/json" \
  -d '{
    "question": "show me the link to this codebundle",
    "conversation_history": [
      {"role": "user", "content": "Help me with deployments"},
      {"role": "assistant", "content": "Use **k8s-deployment-healthcheck**"}
    ]
  }'
```

---

## Configuration

### Environment Variables
```bash
# Required in az.secret
AI_SERVICE_PROVIDER=azure-openai
AI_ENHANCEMENT_ENABLED=true
AZURE_OPENAI_ENDPOINT=https://...
AZURE_OPENAI_KEY=...
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4-turbo
```

### API Request Format
```json
{
  "question": "How do I troubleshoot a deployment?",
  "context_limit": 5,
  "conversation_history": [
    {"role": "user", "content": "previous question"},
    {"role": "assistant", "content": "previous answer"}
  ]
}
```

### API Response Format
```json
{
  "answer": "To troubleshoot...",
  "relevant_tasks": [
    {
      "codebundle_name": "**k8s-deployment-healthcheck**",
      "codebundle_slug": "k8s-deployment-healthcheck",
      "platform": "Kubernetes",
      "relevance_score": 0.89,
      "description": "...",
      "collection_name": "rw-public-codecollection"
    }
  ],
  "confidence_score": 0.85,
  "sources_used": ["MCP Semantic Search", "Azure OpenAI"],
  "query_metadata": {
    "query_processed_at": "2026-01-19T10:30:00Z",
    "is_followup": false,
    "platform_detected": "kubernetes"
  }
}
```

---

## Common Issues

### AI Enhancement Not Enabled
**Symptom:** Chat returns generic responses or errors about AI not configured

**Fix:**
1. Check `az.secret` has required Azure OpenAI variables
2. Verify `env_file: - az.secret` in docker-compose for backend/worker
3. Restart: `docker-compose up --force-recreate backend worker`
4. Check logs: `docker-compose logs backend | grep AI_ENHANCEMENT`

### Poor Search Results
**Symptom:** Relevant codebundles not appearing in results

**Troubleshooting:**
1. Check MCP server is running and accessible
2. Verify semantic search index is populated
3. Review query in Chat Debug UI for relevance scores
4. Consider reindexing codebundles if corpus changed

### Follow-ups Not Detected
**Symptom:** System treats follow-up as new query, loses context

**Fix:**
1. Ensure `conversation_history` is passed in request
2. Check if question contains trigger phrases (see Detection Phrases above)
3. Review Chat Debug UI to see `is_followup` flag in metadata
4. Add new phrases to detection list in `mcp_chat.py` if needed

---

## Development

### Adding New Detection Phrases
Edit `backend/app/routers/mcp_chat.py` lines 166-178:

```python
is_followup_question = any(phrase in question_lower for phrase in [
    'existing phrases...',
    'your new phrase',  # Add here
])
```

### Adjusting LLM Prompts
Edit `backend/app/routers/mcp_chat.py` lines 802-891:
- `system_prompt` - General behavior instructions
- `user_prompt` - Context for current query
- Follow-up prompt variant at lines 867-879

### Testing Changes
1. Make code changes
2. Restart backend: `docker-compose restart backend`
3. Test in UI: http://localhost:3000/chat
4. Review in Debug UI: http://localhost:3000/chat-debug (admin only)

---

## Performance & Quality

**Target Metrics:**
- Response time: < 3 seconds for new queries
- Follow-up response: < 2 seconds
- Relevance score: > 0.6 for top result
- No-match rate: < 10% of queries

**Monitoring:**
- Use Chat Debug UI Quality Analysis tab
- Check `/api/v1/chat/debug/analyze-quality?window_hours=24`
- Review problem queries in Recent Chats tab

---

Last Updated: 2026-01-19
