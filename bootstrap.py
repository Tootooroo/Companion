#!/usr/bin/env python3
"""One-command installer/updater/launcher for MTV MAP Companion."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
VENV = ROOT / ".venv"
STATE_FILE = VENV / ".mtv-bootstrap.json"
REQUIREMENTS = ROOT / "requirements.txt"
MIN_PYTHON = (3, 10)
BOOTSTRAP_VERSION = 3

def die(message: str, code: int = 1) -> "None":
    print(f"\nERROR: {message}\n", file=sys.stderr)
    input("Press Enter to close...") if sys.platform == "win32" else None
    raise SystemExit(code)

def requirements_fingerprint() -> str:
    digest = hashlib.sha256()
    digest.update(REQUIREMENTS.read_bytes())
    digest.update(str(BOOTSTRAP_VERSION).encode())
    digest.update(platform.system().encode())
    digest.update(platform.machine().encode())
    return digest.hexdigest()

def venv_python() -> Path:
    if sys.platform == "win32":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"

def run(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    print("+", " ".join(str(a) for a in args))
    return subprocess.run(args, cwd=ROOT, check=check)

def state() -> dict:
    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def write_state(data: dict) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def ensure_python() -> None:
    if sys.version_info < MIN_PYTHON:
        die(
            f"Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+ is required; "
            f"this launcher is using {sys.version.split()[0]}."
        )

def ensure_venv() -> Path:
    py = venv_python()
    if py.exists():
        return py
    print("\nFirst run: creating a private Python environment...")
    run([sys.executable, "-m", "venv", str(VENV)])
    py = venv_python()
    if not py.exists():
        die("The Python virtual environment could not be created.")
    return py

def ensure_packages(py: Path) -> None:
    wanted = requirements_fingerprint()
    current = state()
    if current.get("fingerprint") == wanted:
        return

    print("\nInstalling/updating Companion dependencies...")
    run([str(py), "-m", "pip", "install", "--disable-pip-version-check", "-r", str(REQUIREMENTS)])
    write_state({"fingerprint": wanted, "browser_installed": False})

def chrome_likely_available() -> bool:
    if sys.platform == "darwin":
        return Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome").exists()
    if sys.platform == "win32":
        candidates = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        suffixes = [
            Path("Google/Chrome/Application/chrome.exe"),
            Path("Chromium/Application/chrome.exe"),
        ]
        return any(
            base and (Path(base) / suffix).exists()
            for base in candidates for suffix in suffixes
        )
    return bool(
        shutil.which("google-chrome")
        or shutil.which("google-chrome-stable")
        or shutil.which("chromium")
        or shutil.which("chromium-browser")
    )

def ensure_browser(py: Path) -> None:
    current = state()
    if chrome_likely_available():
        return
    if current.get("browser_installed"):
        return

    print("\nNo system Google Chrome detected; installing private Playwright Chromium...")
    result = run([str(py), "-m", "playwright", "install", "chromium"], check=False)
    if result.returncode != 0:
        if sys.platform.startswith("linux"):
            print(
                "\nChromium downloaded but Linux system libraries may be missing.\n"
                "On Debian/Ubuntu/ChromeOS Linux, run:\n"
                f'  sudo "{py}" -m playwright install-deps chromium\n'
                "then launch the Companion again."
            )
        die("Could not install the Playwright Chromium browser.")

    current = state()
    current["browser_installed"] = True
    write_state(current)

def main() -> None:
    os.chdir(ROOT)
    ensure_python()
    py = ensure_venv()
    ensure_packages(py)
    ensure_browser(py)

    print("\nStarting MTV MAP Companion...")
    print("Keep this window open while you use Paperwork on the map.\n")
    try:
        raise SystemExit(run([str(py), str(ROOT / "companion.py")], check=False).returncode)
    except KeyboardInterrupt:
        raise SystemExit(0)

if __name__ == "__main__":
    main()
