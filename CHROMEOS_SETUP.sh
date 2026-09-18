#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
echo "MTV MAP Companion - ChromeOS Linux setup"
echo "=========================================="
echo "This runs inside ChromeOS Linux (Crostini), not the ChromeOS shell."
echo
sudo apt-get update
# Crostini window tools are required so the Linux browser window can be
# restored/moved by the ChromeOS host compositor after Paperwork → Begin.
sudo apt-get install -y python3 python3-venv python3-pip wmctrl xdotool x11-xserver-utils
if ! python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
  echo "Python 3.10 or newer is required in ChromeOS Linux." >&2; exit 1
fi
chmod +x START_COMPANION.sh CHROMEOS_SETUP.sh 2>/dev/null || true
python3 bootstrap.py --setup-only
echo; echo "Setup complete. Start Companion with: ./START_COMPANION.sh"
