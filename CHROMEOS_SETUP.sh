#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "MTV MAP Companion - ChromeOS Linux setup"
echo "This runs inside ChromeOS Linux (Crostini), not in the ChromeOS shell."
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip
python3 bootstrap.py || true
if [ -x ".venv/bin/python" ]; then
  sudo ".venv/bin/python" -m playwright install-deps chromium
  ".venv/bin/python" -m playwright install chromium
  echo
  echo "Setup complete. Run ./START_COMPANION.sh"
fi
