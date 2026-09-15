#!/usr/bin/env bash
set -u
cd "$(dirname "$0")"
echo "MTV MAP Companion"
echo "================="
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
if [ -z "$PYTHON" ] && command -v apt-get >/dev/null 2>&1; then
  echo; echo "Python 3.10+ was not found. Installing Python support..."
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y python3 python3-venv python3-pip
  else
    apt-get update && apt-get install -y python3 python3-venv python3-pip
  fi
  PYTHON="$(find_python || true)"
fi
if [ -z "$PYTHON" ]; then
  echo; echo "Python 3.10 or newer is required."
  echo "Install Python 3.10+ and python venv support, then run this launcher again."
  exit 1
fi

# A machine can have Python but not the distro's venv package. Detect that
# before bootstrap so first launch can repair it on Debian/Ubuntu.
if ! "$PYTHON" -c 'import venv' >/dev/null 2>&1 && command -v apt-get >/dev/null 2>&1; then
  echo; echo "Python venv support is missing. Installing it..."
  if command -v sudo >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y python3-venv python3-pip
  else
    apt-get update && apt-get install -y python3-venv python3-pip
  fi
fi

exec "$PYTHON" bootstrap.py
