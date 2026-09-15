#!/bin/bash
set -u
cd "$(dirname "$0")"
clear

echo "MTV MAP Companion"
echo "================="

TERMINAL_WINDOW_ID=""
if command -v osascript >/dev/null 2>&1; then
  TERMINAL_WINDOW_ID="$(osascript -e 'tell application "Terminal" to id of front window' 2>/dev/null || true)"
fi

find_python() {
  local p
  for p in python3.14 python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$p" >/dev/null 2>&1 && "$p" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
      command -v "$p"; return 0
    fi
  done
  return 1
}

PYTHON="$(find_python || true)"
if [ -z "$PYTHON" ]; then
  echo; echo "Python 3.10 or newer is required."
  echo "Opening the official Python download page..."
  open "https://www.python.org/downloads/macos/" >/dev/null 2>&1 || true
  echo; echo "Install Python, then double-click START_COMPANION.command again."
  echo; read -r -p "Press Enter to close..."; exit 1
fi

"$PYTHON" bootstrap.py
STATUS=$?
if [ "$STATUS" -eq 0 ] && [ -n "$TERMINAL_WINDOW_ID" ]; then
  nohup /bin/bash -c "sleep 0.6; osascript -e 'tell application \"Terminal\" to close (first window whose id is ${TERMINAL_WINDOW_ID})' >/dev/null 2>&1" >/dev/null 2>&1 &
fi
exit "$STATUS"
