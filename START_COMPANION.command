#!/bin/bash
set -u
cd "$(dirname "$0")"
clear

echo "MTV MAP Companion"
echo "================="

# Capture this exact Terminal window before starting Python so End session can
# clean it up without accidentally closing an unrelated Terminal window.
TERMINAL_WINDOW_ID=""
if command -v osascript >/dev/null 2>&1; then
  TERMINAL_WINDOW_ID="$(osascript -e 'tell application "Terminal" to id of front window' 2>/dev/null || true)"
fi

if command -v python3 >/dev/null 2>&1; then
  python3 bootstrap.py
  STATUS=$?

  if [ "$STATUS" -eq 0 ] && [ -n "$TERMINAL_WINDOW_ID" ]; then
    # Let this shell finish first, then close only the captured launcher window.
    nohup /bin/bash -c "sleep 0.6; osascript -e 'tell application \"Terminal\" to close (first window whose id is ${TERMINAL_WINDOW_ID})' >/dev/null 2>&1" >/dev/null 2>&1 &
  fi
  exit "$STATUS"
fi

echo
echo "Python 3.10 or newer is required."
echo "Install Python from python.org, then double-click this file again."
echo
read -r -p "Press Enter to close..."
