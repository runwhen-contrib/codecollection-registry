#!/bin/bash
# Test script for Chat Debug Tools
# This reproduces the exact issue reported by the user

set -e

BASE_URL="http://localhost:8000"

echo "=================================="
echo "Chat Debug Tool Test Script"
echo "=================================="
echo ""

# Check if backend is running
echo "1. Checking if backend is available..."
if curl -s "$BASE_URL/health" > /dev/null 2>&1; then
    echo "✅ Backend is running"
else
    echo "❌ Backend is not running. Please start it first:"
    echo "   cd cc-registry-v2/backend"
    echo "   python -m uvicorn app.main:app --reload"
    exit 1
fi
echo ""

# Test the exact scenario from the user's report
echo "2. Testing the reported issue..."
echo "   User Question 1: 'Help me troubleshoot a deployment that won't roll out'"
echo "   User Question 2: 'give me a step-by-step on using the codebundle'"
echo ""

# Create the test payload
cat > /tmp/chat_debug_test.json << 'EOF'
{
  "question": "give me a step-by-step on using the codebundle",
  "conversation_history": [
    {
      "role": "user",
      "content": "Help me troubleshoot a deployment that won't roll out"
    },
    {
      "role": "assistant",
      "content": "To help troubleshoot a deployment that won't roll out, I recommend these CodeBundles:\n\n**k8s-deployment-healthcheck**: This bundle provides targeted tasks for diagnosing deployment rollout issues, including:\n- Checking for unready pods in your deployment\n- Counting container restarts to spot crash loops\n- Fetching critical log errors from your deployment's containers\n- Checking if the expected number of replicas are ready and available\n- Reviewing recent warning events related to the deployment\n\n**k8s-troubleshoot-deployment**: General troubleshooting tasks for Kubernetes Deployments, covering common rollout blockers and misconfigurations.\n\nWould you like a step-by-step on using these CodeBundles, or do you have specific symptoms (e.g., error messages, CrashLoopBackOff, unready pods) you want to focus on?"
    }
  ],
  "context_limit": 10
}
EOF

echo "3. Calling debug endpoint..."
RESPONSE=$(curl -s -X POST "$BASE_URL/api/v1/chat/debug/test-query" \
  -H "Content-Type: application/json" \
  -d @/tmp/chat_debug_test.json)

# Extract key information
echo ""
echo "=================================="
echo "DEBUG RESULTS"
echo "=================================="
echo ""

echo "📊 QUERY METADATA:"
echo "  - Is Follow-up: $(echo "$RESPONSE" | jq -r '.debug_entry.query_metadata.is_followup // "false"')"
echo "  - Platform Detected: $(echo "$RESPONSE" | jq -r '.debug_entry.query_metadata.platform_detected // "none"')"
echo "  - All Tasks Found: $(echo "$RESPONSE" | jq -r '.debug_entry.query_metadata.all_tasks_count // 0')"
echo "  - Filtered Tasks: $(echo "$RESPONSE" | jq -r '.debug_entry.query_metadata.filtered_tasks_count // 0')"
echo "  - Conversation Length: $(echo "$RESPONSE" | jq -r '.debug_entry.query_metadata.conversation_length // 0')"
echo ""

echo "🎯 RELEVANT TASKS:"
TASKS=$(echo "$RESPONSE" | jq -r '.debug_entry.relevant_tasks[] | "  - \(.name) (score: \(.relevance_score * 100 | floor)%)"')
if [ -z "$TASKS" ]; then
    echo "  ❌ No relevant tasks found"
else
    echo "$TASKS"
fi
echo ""

echo "🤖 LLM RESPONSE:"
NO_MATCH=$(echo "$RESPONSE" | jq -r '.debug_entry.no_match_flag')
echo "  - No Match Flag: $NO_MATCH"
ANSWER_PREVIEW=$(echo "$RESPONSE" | jq -r '.debug_entry.final_answer' | head -c 200)
echo "  - Answer Preview: $ANSWER_PREVIEW..."
echo ""

echo "⚠️  ISSUES DETECTED:"
ISSUE_COUNT=$(echo "$RESPONSE" | jq -r '.analysis.issue_count // 0')
if [ "$ISSUE_COUNT" -eq 0 ]; then
    echo "  ✅ No issues detected"
else
    echo "  Found $ISSUE_COUNT issue(s):"
    echo "$RESPONSE" | jq -r '.analysis.issues[] | "    - [\(.severity | ascii_upcase)] \(.type): \(.message)"'
fi
echo ""

echo "💡 RECOMMENDATIONS:"
echo "$RESPONSE" | jq -r '.recommendations[] | "  - \(.)"'
echo ""

# Save full response for detailed analysis
echo "4. Full debug output saved to: /tmp/chat_debug_full.json"
echo "$RESPONSE" | jq '.' > /tmp/chat_debug_full.json

echo ""
echo "=================================="
echo "SUMMARY"
echo "=================================="

if [ "$NO_MATCH" == "true" ]; then
    echo "❌ ISSUE REPRODUCED: Chat said 'no match' despite having conversation context"
    echo ""
    echo "This confirms the bug. The follow-up question should have been detected"
    echo "and should reference the previously mentioned codebundles."
else
    echo "✅ Issue NOT reproduced - chat correctly found matches"
    echo ""
    echo "Either the issue is fixed or needs different conversation history."
fi

echo ""
echo "📖 For more details, see: CHAT-DEBUG-GUIDE.md"
echo ""

# Cleanup
rm /tmp/chat_debug_test.json
