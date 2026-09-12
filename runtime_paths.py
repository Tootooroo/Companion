"""Cross-platform writable paths used by MTV MAP Companion."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP_NAME = "MTV_MAP_Companion"

def user_data_dir() -> Path:
    """Return a per-user writable application-data directory."""
    if sys.platform == "win32":
        base = Path(
            os.environ.get("LOCALAPPDATA")
            or os.environ.get("APPDATA")
            or (Path.home() / "AppData" / "Local")
        )
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))

    path = base / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def browser_profile_dir() -> Path:
    path = user_data_dir() / "browser-profile"
    path.mkdir(parents=True, exist_ok=True)
    return path
