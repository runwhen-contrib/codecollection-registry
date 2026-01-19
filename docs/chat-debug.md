# Chat Debug Console

## Overview

The Chat Debug Console is a hidden admin-only UI for analyzing chat quality, debugging conversation issues, and testing queries. It provides insights into why certain queries succeed or fail.

**Access:** http://localhost:3000/chat-debug (requires admin login: `dev@example.com` / `password`)

---

## Features

### Tab 1: Recent Chats

View all recent chat interactions with detailed metadata.

**Features:**
- **Sorting:** Newest first (default), Oldest first, Most tasks, Least tasks
- **Filtering:**
  - All Chats (default)
  - No Match Only - Queries that found no codebundles
  - Successful Only - Queries with matches
- **Search:** Filter by question text
- **Stats Summary:** Shows count of successful vs no-match queries
- **Visual Indicators:**
  - ✅ Green checkmark - Successful query
  - ❌ Red X - No match found
  - Blue left border - Follow-up question
  - Chip badge - Shows conversation turn number

**View Options:**
```
┌─────────────────────────────────────────────────────┐
│ Limit: [20] ☑ Include Full Prompts                 │
│ Search: [____________] Filter: [All▾] Sort: [New▾] │
└─────────────────────────────────────────────────────┘

Showing 15 of 20 chats  [❌ 2 No Match]  [✅ 18 Success]

┌────────────────────────────────────────────────────┐
│ ✓ show me the link to this codebundle             │
│ ┃ 3:04 PM • 0 tasks • [Turn 3 in conversation]    │ ← Follow-up
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│ ✓ yes, replica status                              │
│ ┃ 3:04 PM • 5 tasks • [Turn 2 in conversation]    │ ← Follow-up
└────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────┐
│ ✓ Help me troubleshoot a deployment               │
│   3:04 PM • 5 tasks found                          │ ← New
└────────────────────────────────────────────────────┘
```

**Understanding Follow-ups:**
- Blue left border + indentation = Follow-up question
- "Turn X in conversation" badge = Conversation turn number
- "Used conversation context only" = Normal for follow-ups with 0 new tasks

### Tab 2: Test Query

Simulate a chat query with full debug output.

**Input:**
- **Test Question** - Any question to test
- **Conversation History (JSON)** - Optional prior messages for follow-up testing

**Output:**
1. **Query Metadata**
   - Platform detected
   - Search strategy (new vs follow-up)
   - Task counts
   - Timing information

2. **Issues Detected**
   - No results found
   - Low relevance scores
   - Follow-up detection failed
   - Platform mismatch

3. **Recommendations**
   - Suggested query improvements
   - Alternative search strategies
   - Configuration adjustments

4. **Relevant Tasks**
   - List of matching codebundles
   - Relevance scores
   - Platform information

5. **Final Answer**
   - Complete LLM response
   - Includes all formatting

**Example Test:**
```json
Question: "show me the link to this codebundle"

Conversation History:
[
  {
    "role": "user",
    "content": "Help me troubleshoot deployment issues"
  },
  {
    "role": "assistant",
    "content": "Use **k8s-deployment-healthcheck** for deployment troubleshooting."
  }
]

Expected: Should detect as follow-up, provide link to k8s-deployment-healthcheck
```

### Tab 3: Quality Analysis

Aggregated metrics over a time window.

**Metrics:**
- **Total Chats** - Number of queries in window
- **No-Match Rate** - % of queries with no results
- **Avg Tasks Found** - Average number of matching codebundles
- **Follow-up Failure Rate** - % of follow-ups that failed

**Time Windows:**
- Last 1 hour
- Last 6 hours
- Last 24 hours (default)
- Last 7 days

**Problem Queries:**
- Shows queries with issues (no match, low quality)
- Click to see full details
- Helps identify patterns in failures

**Recommendations:**
- System-generated suggestions for improving quality
- Based on analysis of failed queries
- Actionable items for configuration/prompt tuning

---

## Backend API

### Recent Chats
```bash
GET /api/v1/chat/debug/recent-chats?limit=20&include_prompts=false

Response:
{
  "count": 20,
  "chats": [
    {
      "timestamp": "2026-01-19T15:04:12.261801",
      "question": "show me the link to this codebundle",
      "conversation_history": [...],
      "relevant_tasks_count": 0,
      "relevant_tasks": [],
      "final_answer": "Here's the link...",
      "no_match_flag": false,
      "query_metadata": {
        "is_followup": true,
        "conversation_length": 4,
        "focused_codebundle": "k8s-triage-deploymentreplicas"
      }
    }
  ]
}
```

### Quality Analysis
```bash
GET /api/v1/chat/debug/analyze-quality?window_hours=24

Response:
{
  "total_chats": 50,
  "no_match_count": 5,
  "no_match_rate": 0.10,
  "avg_tasks_found": 3.2,
  "followup_failure_rate": 0.05,
  "recommendations": [
    "No-match rate is within acceptable range",
    "Follow-up detection working well"
  ],
  "problem_queries": [
    {
      "question": "cli deployment",
      "reason": "Too vague, no platform detected"
    }
  ]
}
```

### Test Query
```bash
POST /api/v1/chat/debug/test-query
Content-Type: application/json

{
  "question": "show me the link",
  "conversation_history": [...]
}

Response:
{
  "query_metadata": {...},
  "issues_detected": [...],
  "recommendations": [...],
  "relevant_tasks": [...],
  "final_answer": "..."
}
```

### Clear History
```bash
DELETE /api/v1/chat/debug/clear-history

Response: {"message": "Chat history cleared"}
```

---

## Use Cases

### 1. Debugging Contradictory Responses

**Symptom:** Chat recommends a codebundle, then claims it can't find it.

**Steps:**
1. Go to Recent Chats tab
2. Find the conversation sequence (look for follow-up indicators)
3. Check if follow-ups have `is_followup: true` in metadata
4. If false → follow-up detection failed, add phrase to detection list
5. If true but still failed → check LLM prompt handling

### 2. Finding Why Search Failed

**Symptom:** User query should match but returns no results.

**Steps:**
1. Go to Test Query tab
2. Enter the exact query
3. Review "Issues Detected" section
4. Check relevance scores in "Relevant Tasks"
5. Look for platform mismatch or vague keywords
6. Adjust query or MCP search parameters

### 3. Quality Auditing

**Symptom:** Users report chat quality declining.

**Steps:**
1. Go to Quality Analysis tab
2. Set window to Last 7 Days
3. Check No-Match Rate trend
4. Review Problem Queries
5. Look for patterns (platform confusion, vague queries, etc.)
6. Apply recommendations or adjust prompts

### 4. Testing Changes

**Scenario:** You modified follow-up detection or LLM prompts.

**Steps:**
1. Make code changes
2. Restart backend: `docker-compose restart backend`
3. Go to Test Query tab
4. Run test scenarios:
   - New query (no history)
   - Follow-up with link request
   - Follow-up with "how to use"
   - Multi-turn conversation
5. Verify `is_followup` flag and answer quality
6. Check Recent Chats to see real-time results

---

## Filtering & Sorting Tips

### Find All Follow-up Failures
1. Set Sort: "Least Tasks"
2. Scroll through entries with 0 tasks
3. Look for blue border (follow-up indicator)
4. These are follow-ups that should have used conversation context

### Find Recent No-Match Errors
1. Set Filter: "No Match Only"
2. Set Sort: "Newest First"
3. Review top 5-10 queries
4. Identify common patterns (platforms, keywords)

### Find Highest Quality Matches
1. Set Filter: "Successful Only"
2. Set Sort: "Most Tasks"
3. See what queries work best
4. Use as examples for prompt engineering

### Search Specific Topics
1. Enter keyword in Search box (e.g., "azure", "kubernetes")
2. Review all queries about that topic
3. Check success rate
4. Identify platform-specific issues

---

## Automatic Logging

All chat queries are automatically logged to the debug history:

**Logged Data:**
- Timestamp
- User question
- Conversation history
- MCP search response
- LLM prompts (system + user)
- LLM response
- Final answer
- Relevant tasks with relevance scores
- No-match flag
- Query metadata (follow-up, platform, timings)

**Storage:**
- In-memory storage (last 100 queries)
- Persists until backend restart
- Consider database storage for production

**Privacy:**
- No user identification stored
- Only query content and results
- Admin-only access

---

## Troubleshooting

### Debug Console 404 Error
**Cause:** Frontend not configured for correct API port
**Fix:** Check `frontend/src/services/api.ts` → `API_BASE_URL = http://localhost:8001/api/v1`

### No Chat History Showing
**Cause:** Automatic logging not working or backend restarted
**Fix:** 
- Have a conversation in Registry Chat first
- Check backend logs for `store_chat_debug` calls
- Verify `/api/v1/chat/debug/recent-chats` returns data

### Follow-ups Not Detected in Debug UI
**Cause:** `is_followup` flag not set correctly
**Fix:**
- Check conversation history is passed in request
- Verify question contains trigger phrases
- Review detection logic in `mcp_chat.py` lines 166-178

### Stats Don't Match Reality
**Cause:** Data filtered by time window or limit
**Fix:**
- Increase limit to 100 (max)
- Adjust time window in Quality Analysis
- Check if backend was restarted (clears in-memory data)

---

## Performance Considerations

**In-Memory Storage:**
- Stores last 100 queries (configurable via `MAX_STORED_CHATS`)
- Lost on backend restart
- Fast access, no database overhead

**For Production:**
- Consider persistent storage (PostgreSQL)
- Add retention policy (e.g., 30 days)
- Index on timestamp for fast queries
- Add user ID if needed for support

**API Performance:**
- Recent chats query: ~10ms
- Quality analysis: ~20ms (aggregation)
- Test query: 2-5 seconds (includes full chat flow)

---

Last Updated: 2026-01-19
