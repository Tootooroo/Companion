#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
if command -v python3 >/dev/null 2>&1; then
  exec python3 bootstrap.py
fi
echo "Python 3.10 or newer is required."
echo "On Debian/Ubuntu/ChromeOS Linux: sudo apt install python3 python3-venv"
exit 1
