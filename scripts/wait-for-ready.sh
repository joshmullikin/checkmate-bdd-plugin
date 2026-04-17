#!/usr/bin/env bash
# wait-for-ready.sh <url> <timeout_secs>
# Polls <url> with exponential backoff until HTTP 200 or timeout.
# Exit 0 = ready, exit 1 = timed out.

URL="$1"
TIMEOUT="${2:-30}"
DEADLINE=$(( $(date +%s) + TIMEOUT ))
DELAY=1

echo "Waiting for $URL (timeout: ${TIMEOUT}s)..."

while true; do
  if curl -sf --max-time 2 "$URL" > /dev/null 2>&1; then
    echo "Ready: $URL"
    exit 0
  fi

  NOW=$(date +%s)
  if [ "$NOW" -ge "$DEADLINE" ]; then
    echo "Timeout waiting for $URL after ${TIMEOUT}s"
    exit 1
  fi

  sleep "$DELAY"
  DELAY=$(( DELAY * 2 ))
  if [ "$DELAY" -gt 10 ]; then DELAY=10; fi
done
