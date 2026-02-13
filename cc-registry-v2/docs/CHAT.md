# Registry Chat System

## Overview

The Registry Chat system provides conversational AI assistance for finding CodeBundles, documentation, and troubleshooting guidance. It uses MCP (Model Context Protocol) for semantic search and Azure OpenAI for natural language synthesis.

**User Access:** http://localhost:3000/chat (public)

---

## Architecture

### Flow
1. User sends question to `/api/v1/chat/query`
2. System classifies the question (follow-up, keyword, documentation, meta, or general)
3. **Follow-up:** Extracts codebundle name from conversation history, does focused lookup
4. **Meta question:** Returns system capabilities without searching
5. **Keyword question:** Searches Robot Framework keyword libraries via MCP
6. **General query:**
   a. Runs MCP semantic search for codebundles (`find_codebundle`)
   b. Always runs MCP documentation search in parallel (`find_documentation`)
   c. Filters results by relevance score (min 0.58) and resource type hints
   d. LLM synthesizes answer from codebundle results + doc results + conversation history
7. LLM classifies answer source (`[SOURCE:codebundles]`, `[SOURCE:documentation]`, `[SOURCE:mixed]`)
8. Response includes relevant CodeBundles as cards + confidence metadata
9. Interaction logged to in-memory debug store

### Key Components

**Backend:**
- `backend/app/routers/mcp_chat.py` — Main chat endpoint, question classification, follow-up detection, relevance filtering, LLM integration
- `backend/app/services/ai_service.py` — `AIEnhancementService` class wrapping Azure OpenAI client
- `backend/app/services/ai_prompts.py` — Prompt templates (used by AI enhancement, not chat directly)
- `backend/app/services/mcp_client.py` — HTTP client for MCP server tools (`find_codebundle`, `find_documentation`, `keyword_usage_help`)
- `backend/app/routers/chat_debug.py` — Debug API endpoints and in-memory chat storage

**Frontend:**
- `frontend/src/pages/Chat.tsx` — Chat UI with conversation history
- `frontend/src/pages/ChatDebug.tsx` — Admin-only debug console
- `frontend/src/services/api.ts` — API client for chat endpoint

---

## Question Classification

The system classifies each incoming question into one of five categories:

### 1. Follow-up Questions
Detected when the question contains trigger phrases AND conversation history exists.

**Trigger phrases include:**
- Codebundle references: `this codebundle`, `that codebundle`, `same codebundle`
- Info requests: `tell me more`, `more details`, `more about it`
- Link requests: `show me the link`, `give me the link`, `where can i find this`
- Usage requests: `how do i use this`, `how to use this`

**Behavior:**
- Extracts codebundle slug from conversation history (regex match)
- Runs focused `find_codebundle` search for that specific codebundle
- LLM receives special follow-up prompt emphasizing conversation context
- No codebundle cards shown in response (info is in the text)

### 2. Meta Questions
Questions about the assistant itself: `what can you do`, `hello`, `what tools do you have`

**Behavior:** Returns static system capabilities text. No MCP search performed.

### 3. Keyword/Library Questions
Questions about Robot Framework keywords: `library`, `rw.cli`, `robot framework`

**Behavior:** Calls MCP `keyword_usage_help` tool. No codebundle search.

### 4. Documentation Questions (classification only)
Questions about setup, configuration, how-to: `how to`, `configure`, `install`, `runwhen-local`

**Note:** This classification is detected but no longer gates behavior. Documentation is now ALWAYS searched alongside codebundles for all general queries.

### 5. General Queries (default)
Everything else — infrastructure troubleshooting, monitoring, scaling, etc.

**Behavior:** Full search pipeline (see Dual Search below).

---

## Dual Search Pipeline

For general queries, the system always runs two MCP searches:

### Codebundle Search
- Tool: `find_codebundle` via MCP
- Returns ranked codebundles with relevance scores
- Platform detected from query (`kubernetes`, `aws`, `azure`, `gcp`)

### Documentation Search
- Tool: `find_documentation` via MCP
- Searches RunWhen docs (installation, configuration, guides, FAQs)
- Results appended to MCP context as `## Documentation Resources`
- Runs for every query, not just docs-classified ones

### Relevance Filtering
After MCP returns results, the backend applies filtering:

- **Minimum relevance:** 0.58 (below this, results are dropped)
- **Strong relevance:** 0.64+ (prioritized, bypasses some filters)
- **Resource type hints:** Query keywords like `app service`, `postgres`, `redis` map to slug patterns, excluding irrelevant resource types
- **Platform filtering:** Mismatched platforms excluded unless score > 0.70
- **Cap:** Maximum 5 codebundles shown to keep UI clean

### Conversation Context Enhancement
When a follow-up references context (`for this`, `something else`, `different`), the system extracts the original user question from conversation history and combines it with the current query to improve search quality.

---

## LLM Synthesis

The `_generate_llm_answer` function builds a multi-message prompt:

1. **System prompt** — Role definition, formatting rules, critical rules for when to recommend codebundles vs docs
2. **Conversation history** — Last 6 messages (3 turns) for context
3. **User prompt** — Current question + search results + doc results + source classification instructions

**Source classification:** The LLM tags its response with `[SOURCE:codebundles]`, `[SOURCE:documentation]`, `[SOURCE:libraries]`, or `[SOURCE:mixed]`. This tag is stripped from the displayed answer and used to set the `answer_source` field in the response.

**No-match handling:** If the LLM determines no codebundles match, it includes `[NO_MATCHING_CODEBUNDLE]` which triggers the "Request CodeBundle" button in the UI.

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
  "context_limit": 10,
  "include_enhanced_descriptions": true,
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
      "codebundle_name": "k8s-deployment-healthcheck",
      "codebundle_slug": "k8s-deployment-healthcheck",
      "collection_name": "rw-public-codecollection",
      "collection_slug": "rw-public-codecollection",
      "description": "...",
      "support_tags": ["kubernetes", "deployment"],
      "tasks": ["Check Deployment Replicas", "..."],
      "slis": [],
      "access_level": "read-only",
      "relevance_score": 0.89,
      "platform": "Kubernetes",
      "resource_types": []
    }
  ],
  "confidence_score": null,
  "sources_used": ["MCP Codebundle Search", "MCP Documentation Search"],
  "query_metadata": {
    "query_processed_at": "2026-02-09T10:30:00Z",
    "is_followup": false,
    "platform_filter": "Kubernetes",
    "mcp_tools": ["find_codebundle", "find_documentation"],
    "llm_enabled": true
  },
  "no_match": false,
  "answer_source": "codebundles"
}
```

---

## Common Issues

### AI Enhancement Not Enabled
**Symptom:** Chat returns generic responses or errors about AI not configured

**Fix:**
1. Check `az.secret` has required Azure OpenAI variables
2. Verify `env_file: - az.secret` in docker-compose for backend AND worker
3. Rebuild: `docker-compose up -d --force-recreate backend worker`
4. Check logs: `docker-compose logs backend | grep AI_ENHANCEMENT`

### Poor Search Results
**Symptom:** Relevant codebundles not appearing in results

**Troubleshooting:**
1. Check MCP server is running: `curl http://localhost:8000/health`
2. Verify semantic search index is populated (check MCP server logs)
3. Review query in Chat Debug UI for relevance scores
4. Check if relevance filtering is too aggressive (MIN_RELEVANCE = 0.58 in `mcp_chat.py`)
5. Check resource hint/exclude patterns if the query mentions a specific technology

### Source Classification Wrong
**Symptom:** Answer says "Source: Documentation" but codebundles were found, or vice versa

**Cause:** LLM's `[SOURCE:...]` tag doesn't match the actual content. The backend has fallback heuristics but they may not cover all cases.

**Fix:** Review the source classification rules in the LLM prompt and the fallback logic after the LLM response.

### Follow-ups Not Detected
**Symptom:** System treats follow-up as new query, loses context

**Fix:**
1. Ensure `conversation_history` is passed in request body
2. Check if question contains one of the trigger phrases (see Question Classification above)
3. Review Chat Debug UI to see `is_followup` flag in metadata
4. Add new phrases to the follow-up detection list in `mcp_chat.py`

---

## Development

### Adding New Follow-up Phrases
Edit `backend/app/routers/mcp_chat.py` — find the `is_followup_question` assignment and add new phrases to the list.

### Adding Resource Type Hints
Edit the `resource_hints` / `resource_excludes` block in `mcp_chat.py` to add new technology keyword mappings (e.g., mapping `elasticsearch` to slug patterns).

### Adjusting LLM Behavior
Edit the `_generate_llm_answer` function in `mcp_chat.py`:
- `system_prompt` — General behavior, formatting rules, critical rules
- `user_prompt` — Per-query context with search results and classification instructions
- Follow-up variant — Emphasizes conversation context over new search

### Testing Changes
1. Make code changes
2. Rebuild: `docker-compose up -d --build backend`
3. Test in UI: http://localhost:3000/chat
4. Review in Debug UI: http://localhost:3000/chat-debug (admin only)
5. Use Test Query tab to run controlled test scenarios

---

## Performance & Quality

**Target Metrics:**
- Response time: < 3 seconds for new queries
- Follow-up response: < 2 seconds
- Relevance score: > 0.58 for shown results
- No-match rate: < 10% of queries

**Monitoring:**
- Use Chat Debug UI Quality Analysis tab
- Check `/api/v1/chat/debug/analyze-quality?window_hours=24`
- Review problem queries in Recent Chats tab

---

Last Updated: 2026-02-09
