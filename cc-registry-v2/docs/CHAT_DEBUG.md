# Chat Debug Console

## Overview

The Chat Debug Console is an admin-only UI for analyzing chat quality, debugging conversation issues, and testing queries. It provides insights into why certain queries succeed or fail.

**Access:** http://localhost:3000/chat-debug (requires admin login: `dev@example.com` / `password`)

---

## Features

### Tab 1: Recent Chats

View all recent chat interactions with detailed metadata.

**Features:**
- **Sorting:** Newest first (default), Oldest first, Most tasks, Least tasks
- **Filtering:**
  - All Chats (default)
  - No Match Only — queries that found no codebundles
  - Successful Only — queries with matches
- **Search:** Filter by question text
- **Stats Summary:** Count of successful vs no-match queries
- **Visual Indicators:**
  - Green checkmark — successful query
  - Red X — no match found
  - Blue left border — follow-up question
  - Chip badge — shows conversation turn number

**View Options:**
- `Limit` — number of chats to show (max 100)
- `Include Full Prompts` — shows raw LLM system/user prompts and MCP response text

**Understanding Follow-ups:**
- Blue left border + indentation = follow-up question
- "Turn X in conversation" badge = conversation turn number
- "Used conversation context only" = normal for follow-ups with 0 new tasks

### Tab 2: Test Query

Simulate a chat query with full debug output.

**Input:**
- **Test Question** — any question to test
- **Conversation History (JSON)** — optional prior messages for follow-up testing

**Output:**

The response includes a full `ChatDebugResponse` with:

1. **Debug Entry** — the complete logged interaction:
   - Timestamp, question, conversation history
   - Raw MCP search response
   - Parsed relevant tasks with relevance scores
   - Full LLM system prompt and user prompt
   - Raw LLM response and final processed answer
   - No-match flag and query metadata (platform detected, task counts, AI status)

2. **Analysis** — automated issue detection:
   - `no_tasks_found` (high) — MCP returned 0 tasks above threshold
   - `few_tasks_found` (medium) — only 1 task found
   - `low_relevance` (medium) — highest score below 65%
   - `llm_contradiction` (high) — LLM said "no match" despite having results
   - `followup_failure` (high) — follow-up question lost context

3. **Recommendations** — actionable suggestions based on detected issues

### Tab 3: Quality Analysis

Aggregated metrics over a time window.

**Metrics:**
- **Total Chats** — number of queries in window
- **No-Match Rate** — % of queries with `[NO_MATCHING_CODEBUNDLE]` flag
- **Zero Tasks Rate** — % of queries with 0 relevant tasks
- **Average Tasks Found** — mean number of codebundles per query
- **Follow-up Questions** — count of follow-up queries
- **Follow-up No-Match Rate** — % of follow-ups that failed

**Time Windows:** 1 hour, 6 hours, 24 hours (default), 7 days

**Problem Queries:** Top 10 no-match queries with timestamps and conversation length.

**Recommendations:** System-generated suggestions based on rate thresholds (e.g., >30% no-match rate triggers alerts).

---

## Backend API

All endpoints are under `/api/v1/chat/debug/` and require no authentication (admin check is on the frontend side).

### GET /recent-chats

```bash
GET /api/v1/chat/debug/recent-chats?limit=20&include_prompts=false

Response:
{
  "count": 20,
  "chats": [
    {
      "timestamp": "2026-02-09T15:04:12.261801",
      "question": "show me the link to this codebundle",
      "conversation_history": [...],
      "mcp_response": "[2847 chars]",
      "relevant_tasks_count": 0,
      "relevant_tasks": [],
      "llm_system_prompt": "[1423 chars]",
      "llm_user_prompt": "[892 chars]",
      "llm_response": "[456 chars]",
      "final_answer": "Here's the link...",
      "no_match_flag": false,
      "query_metadata": {
        "platform_detected": null,
        "all_tasks_count": 3,
        "filtered_tasks_count": 0,
        "conversation_length": 4,
        "ai_enabled": true,
        "is_followup": true,
        "focused_codebundle": "k8s-triage-deploymentreplicas"
      }
    }
  ]
}
```

**Notes:**
- When `include_prompts=false` (default), lengthy fields show `[N chars]` summaries
- When `include_prompts=true`, full MCP response, system prompt, and user prompt are included

### GET /analyze-quality

```bash
GET /api/v1/chat/debug/analyze-quality?window_hours=24

Response:
{
  "time_window_hours": 24,
  "total_chats": 50,
  "stats": {
    "no_match_rate": "10.0%",
    "no_match_count": 5,
    "zero_tasks_rate": "14.0%",
    "zero_tasks_count": 7,
    "average_tasks_found": "3.2",
    "follow_up_questions": 12,
    "follow_up_no_match_rate": "8.3%"
  },
  "problem_queries": [
    {
      "question": "cli deployment",
      "timestamp": "2026-02-09T14:23:01.000000",
      "conversation_length": 0
    }
  ],
  "recommendations": [
    "Chat quality metrics look healthy"
  ]
}
```

### POST /test-query

```bash
POST /api/v1/chat/debug/test-query
Content-Type: application/json

{
  "question": "How do I scale out my Azure App Service?",
  "conversation_history": [],
  "context_limit": 10
}

Response:
{
  "debug_entry": {
    "timestamp": "...",
    "question": "How do I scale out my Azure App Service?",
    "conversation_history": [],
    "mcp_response": "## CodeBundle Search Results\n...",
    "relevant_tasks_count": 2,
    "relevant_tasks": [
      {
        "name": "Azure App Service Plan Health",
        "slug": "azure-appservice-plan-health",
        "relevance_score": 0.78,
        "platform": "Azure",
        "description": "Check Azure App Service Plan..."
      }
    ],
    "llm_system_prompt": "You are a helpful assistant...",
    "llm_user_prompt": "User Question: How do I...",
    "llm_response": "[SOURCE:codebundles] To scale out...",
    "final_answer": "To scale out your Azure App Service...",
    "no_match_flag": false,
    "query_metadata": {
      "platform_detected": "Azure",
      "all_tasks_count": 8,
      "filtered_tasks_count": 2,
      "conversation_length": 0,
      "ai_enabled": true
    }
  },
  "analysis": {
    "issues": [],
    "issue_count": 0,
    "severity_summary": {"high": 0, "medium": 0, "low": 0},
    "context": {"is_followup": false}
  },
  "recommendations": [
    "No major issues detected - response quality looks good"
  ]
}
```

**Note:** The test query endpoint uses a simplified LLM prompt compared to the main chat endpoint. It does NOT run the dual documentation search. Use it for debugging codebundle relevance, not for testing the full answer pipeline.

### DELETE /clear-history

```bash
DELETE /api/v1/chat/debug/clear-history

Response:
{
  "status": "success",
  "message": "Cleared 42 chat entries from debug history"
}
```

---

## Use Cases

### 1. Debugging Contradictory Responses

**Symptom:** Chat recommends a codebundle, then claims it can't find it.

**Steps:**
1. Go to Recent Chats tab
2. Find the conversation sequence (look for follow-up indicators)
3. Check if follow-ups have `is_followup: true` in metadata
4. If false: follow-up detection failed — add the user's phrase to the detection list in `mcp_chat.py`
5. If true but still failed: check if `focused_codebundle` was extracted correctly from conversation history

### 2. Finding Why Search Failed

**Symptom:** User query should match but returns no results.

**Steps:**
1. Go to Test Query tab
2. Enter the exact query
3. Check `all_tasks_count` vs `filtered_tasks_count` in metadata — if all_tasks > 0 but filtered = 0, the relevance threshold or resource filters are too aggressive
4. Review relevance scores — are they below 0.58?
5. Check for platform mismatch or resource type exclusion patterns

### 3. Quality Auditing

**Symptom:** Users report chat quality declining.

**Steps:**
1. Go to Quality Analysis tab, set window to 7 days
2. Check no-match rate (target: < 10%)
3. Check follow-up no-match rate (target: < 10%)
4. Review problem queries for patterns (vague queries, unsupported platforms)
5. Apply recommendations

### 4. Testing Code Changes

**Scenario:** You modified follow-up detection, LLM prompts, or relevance filtering.

**Steps:**
1. Make code changes
2. Rebuild: `docker-compose up -d --build backend`
3. Go to Test Query tab
4. Run test scenarios:
   - New query (no history)
   - Follow-up with link request (include conversation history JSON)
   - Platform-specific query (e.g., "Azure App Service scaling")
   - Vague query (e.g., "help with deployments")
5. Verify `is_followup` flag, relevance scores, and answer quality
6. Check Recent Chats to see real-time results

---

## Filtering & Sorting Tips

### Find Follow-up Failures
1. Sort by "Least Tasks"
2. Look for entries with blue border (follow-up indicator) and 0 tasks
3. These are follow-ups that should have used conversation context

### Find Pattern in No-Match Queries
1. Filter: "No Match Only"
2. Sort: "Newest First"
3. Look for common platforms or keywords across failures

### Verify High-Quality Matches
1. Filter: "Successful Only"
2. Sort: "Most Tasks"
3. Use these as examples for prompt engineering benchmarks

---

## Storage & Limitations

**In-Memory Storage:**
- Last 100 queries (configurable via `MAX_STORED_CHATS` constant in `chat_debug.py`)
- Lost on backend restart
- Fast access, no database overhead

**Test Query vs Main Chat:**
- Test query uses a simplified prompt (no documentation search, simpler system prompt)
- Main chat endpoint (`/api/v1/chat/query`) has the full dual-search pipeline, resource filtering, and source classification
- Use Test Query for debugging codebundle relevance; use the main chat UI for full pipeline testing

**Privacy:**
- No user identification stored
- Only query content and results
- Admin-only access (frontend-enforced)

---

Last Updated: 2026-02-09
