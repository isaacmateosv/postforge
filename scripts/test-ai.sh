#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# See COPYRIGHT and LICENSE for copying terms and the no-warranty notice.
cd "$(dirname "$0")/.."
set -a; . ./.env; set +a

MODEL="${LOCAL_LLM_MODEL:-llama3.2:3b}"
GEMINI_MODEL="${GEMINI_MODEL:-gemini-flash-latest}"
FAIL=0

echo "======================================================"
echo "  TEST 1: Local Ollama Bridge (Free GPU Metal Runner)"
echo "======================================================"

# 1. Test Container-to-Host Network Reachability via Node fetch
if docker exec -i pm-postiz node -e "fetch('http://host.docker.internal:11434/api/tags').then(r => process.exit(r.ok ? 0 : 1)).catch(() => process.exit(1))"; then
  echo "✔ Network bridge SUCCESS: Postiz container can reach host Ollama."
else
  echo "✖ Network bridge FAILED: Host Ollama not reachable on host.docker.internal:11434"
  FAIL=1
fi

# 2. Generate a few tokens with the configured model, then evict it (keep_alive: 0)
echo "Generating with ${MODEL} (evicted right after)..."
REPLY=$(curl -s -m 300 http://localhost:11434/api/generate \
  -d "{\"model\": \"${MODEL}\", \"prompt\": \"Reply with the single word: pong\", \"stream\": false, \"keep_alive\": 0, \"options\": {\"num_predict\": 5}}" \
  | python3 -c 'import sys, json; d = json.load(sys.stdin); print(d.get("response", "").strip() or d.get("error", "no response"))' 2>/dev/null)
if [ -n "$REPLY" ] && ! echo "$REPLY" | grep -qi "error\|not found"; then
  echo "✔ Local LLM SUCCESS: ${MODEL} replied '${REPLY}'."
else
  echo "✖ Local LLM FAILED: ${REPLY:-Ollama unreachable (run ./publish-machine.sh start)}"
  FAIL=1
fi

echo ""
echo "======================================================"
echo "  TEST 2: Google AI Studio Fallback (Gemini API)"
echo "======================================================"
if [ "$(printf '%s' "${GEMINI_ENABLED:-false}" | tr '[:upper:]' '[:lower:]')" != "true" ]; then
  echo "⚠ Gemini is switched off (GEMINI_ENABLED=true in .env turns it on). Skipping cloud test: nothing sent to Google."
elif [ -z "$GEMINI_API_KEY" ] || [ "$GEMINI_API_KEY" = "your_gemini_api_key_here" ]; then
  echo "⚠ GEMINI_API_KEY is not set in .env. Skipping cloud test."
else
  # Key goes in a header, not the URL, so it never shows up in process lists or logs.
  GEMINI_RESULT=$(curl -s -m 200 -w '\n%{http_code}' \
    "https://generativelanguage.googleapis.com/v1beta/models/${GEMINI_MODEL}:generateContent" \
    -H "x-goog-api-key: ${GEMINI_API_KEY}" \
    -H 'Content-Type: application/json' \
    -d '{"contents":[{"parts":[{"text":"Reply with the single word: pong"}]}],"generationConfig":{"thinkingConfig":{"thinkingLevel":"low"}}}')
  GEMINI_CODE=$(echo "$GEMINI_RESULT" | tail -1)
  GEMINI_INFO=$(echo "$GEMINI_RESULT" | sed '$d' | python3 -c 'import sys, json; d = json.load(sys.stdin); print(d.get("modelVersion") or d.get("error", {}).get("message", "")[:200])' 2>/dev/null)

  if [ "$GEMINI_CODE" = "200" ]; then
    echo "✔ Gemini API SUCCESS (HTTP 200): ${GEMINI_MODEL} -> ${GEMINI_INFO}."
  elif [ "$GEMINI_CODE" = "503" ] || [ "$GEMINI_CODE" = "429" ]; then
    echo "⚠ Gemini key accepted but the model is busy (HTTP ${GEMINI_CODE}): ${GEMINI_INFO}"
  else
    echo "✖ Gemini API returned HTTP ${GEMINI_CODE}: ${GEMINI_INFO}"
    FAIL=1
  fi
fi

exit $FAIL
