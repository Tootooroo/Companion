"""Cross-platform-aware Linux/X11 window placement for MTV MAP Companion.

The browser's final Paperwork placement is handled by Companion using the
active display geometry supplied by the MTV Map.  This module handles the
initial Linux/X11 Chrome window placement and optional terminal tiling.

Important: on multi-monitor Linux desktops, _NET_WORKAREA normally describes
the entire virtual desktop.  Splitting that rectangle in half can place a
window across two physical monitors.  We therefore select one real monitor
first, intersect it with the desktop work area, and only then calculate halves.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
import shutil
import subprocess
import sys
import time


ASSISTANT_TERMINAL_TITLE = "MTV MAP Companion"
COMMAND_TERMINAL_TITLE = "MTV MAP Companion Commands"
CHROME_WINDOW_CLASS = "mtv-map-companion-chrome"
CHROME_WINDOW_TITLE = "MTV MAP Companion Browser"


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def center(self) -> tuple[int, int]:
        return (self.x + self.width // 2, self.y + self.height // 2)

    def contains(self, px: int, py: int) -> bool:
        return self.x <= px < self.right and self.y <= py < self.bottom

    def intersect(self, other: "Rect") -> "Rect | None":
        x1 = max(self.x, other.x)
        y1 = max(self.y, other.y)
        x2 = min(self.right, other.right)
        y2 = min(self.bottom, other.bottom)
        if x2 <= x1 or y2 <= y1:
            return None
        return Rect(x1, y1, x2 - x1, y2 - y1)


@dataclass(frozen=True)
class ScreenLayout:
    """Usable rectangle of one actual display, in virtual-desktop coordinates."""

    width: int
    height: int
    x: int = 0
    y: int = 0

    @property
    def rect(self) -> Rect:
        return Rect(self.x, self.y, self.width, self.height)

    @property
    def left(self) -> tuple[int, int, int, int]:
        left_width = self.width // 2
        return (self.x, self.y, left_width, self.height)

    @property
    def right(self) -> tuple[int, int, int, int]:
        left_width = self.width // 2
        return (
            self.x + left_width,
            self.y,
            self.width - left_width,
            self.height,
        )

    @property
    def chrome(self) -> tuple[int, int, int, int]:
        # Initial browser placement. Paperwork later refines this using the
        # exact display geometry reported by the Map.
        return self.right

    @property
    def commands(self) -> tuple[int, int, int, int]:
        left_width = self.width // 2
        top_height = self.height // 2
        return (
            self.x + left_width,
            self.y + top_height,
            self.width - left_width,
            self.height - top_height,
        )


def _run_text(command: list[str], timeout: float = 2.0) -> str:
    return subprocess.check_output(
        command,
        text=True,
        stderr=subprocess.DEVNULL,
        timeout=timeout,
    )


def _xrandr_monitors() -> list[Rect]:
    """Return real X11 monitor rectangles, including non-primary monitors."""
    if not shutil.which("xrandr"):
        return []
    try:
        output = _run_text(["xrandr", "--listactivemonitors"])
    except (OSError, subprocess.SubprocessError):
        return []

    monitors: list[Rect] = []
    # Examples:
    #  0: +*eDP-1 2560/302x1600/189+0+0  eDP-1
    #  1: +HDMI-1 3840/597x2160/336+2560+0 HDMI-1
    pattern = re.compile(r"\s(\d+)/\d+x(\d+)/\d+([+-]\d+)([+-]\d+)\s")
    for line in output.splitlines()[1:]:
        match = pattern.search(line)
        if not match:
            continue
        width, height, x, y = (int(value) for value in match.groups())
        if width > 0 and height > 0:
            monitors.append(Rect(x, y, width, height))
    return monitors


def _active_window_center() -> tuple[int, int] | None:
    """Return the center of the currently active X11 window."""
    if not shutil.which("xdotool"):
        return None
    try:
        window_id = _run_text(["xdotool", "getactivewindow"]).strip()
        output = _run_text(
            ["xdotool", "getwindowgeometry", "--shell", window_id]
        )
        values: dict[str, int] = {}
        for line in output.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in {"X", "Y", "WIDTH", "HEIGHT"}:
                values[key] = int(value)
        if {"X", "Y", "WIDTH", "HEIGHT"} <= values.keys():
            return (
                values["X"] + values["WIDTH"] // 2,
                values["Y"] + values["HEIGHT"] // 2,
            )
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def _pointer_position() -> tuple[int, int] | None:
    """Fallback: monitor containing the pointer is usually the user's active one."""
    if not shutil.which("xdotool"):
        return None
    try:
        output = _run_text(["xdotool", "getmouselocation", "--shell"])
        values: dict[str, int] = {}
        for line in output.splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key in {"X", "Y"}:
                values[key] = int(value)
        if "X" in values and "Y" in values:
            return values["X"], values["Y"]
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    return None


def _desktop_work_area() -> Rect | None:
    """Return EWMH work area (virtual desktop minus panels/docks), if available."""
    if not shutil.which("wmctrl"):
        return None
    try:
        output = _run_text(["wmctrl", "-d"])
    except (OSError, subprocess.SubprocessError):
        return None
    current_line = next((line for line in output.splitlines() if " * " in line), "")
    match = re.search(r"WA:\s*(-?\d+),(-?\d+)\s+(\d+)x(\d+)", current_line)
    if not match:
        return None
    x, y, width, height = (int(value) for value in match.groups())
    if width <= 0 or height <= 0:
        return None
    return Rect(x, y, width, height)


def _choose_monitor(monitors: list[Rect]) -> Rect | None:
    if not monitors:
        return None

    # Prefer the monitor where the user is actively working.
    point = _active_window_center() or _pointer_position()
    if point:
        for monitor in monitors:
            if monitor.contains(*point):
                return monitor

    # xrandr lists the primary monitor first on most desktops; if not, using
    # the first active monitor is still safer than splitting the full virtual desktop.
    return monitors[0]


def get_screen_layout() -> ScreenLayout | None:
    """Return the usable rectangle of one physical X11 display.

    Works for laptops, 1080p/1440p/4K external monitors, scaled desktops, and
    monitors arranged left/right or above/below.  Geometry is pixel-based; the
    physical diagonal size (14\", 27\", etc.) does not need special cases.
    """
    # Never probe X11 tools on macOS/Windows.  A Mac can have XQuartz/xrandr
    # installed; invoking those binaries can launch XQuartz even though the
    # Companion does not need it.  Native macOS/Windows placement is handled
    # by Chromium DevTools Protocol in companion.py.
    if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
        return None

    monitors = _xrandr_monitors()
    monitor = _choose_monitor(monitors)
    work_area = _desktop_work_area()

    if monitor is not None:
        usable = monitor
        if work_area is not None:
            intersection = monitor.intersect(work_area)
            # Only accept a meaningful intersection. Some WMs publish unusual
            # work-area values on multi-monitor configurations.
            if (
                intersection is not None
                and intersection.width >= max(400, monitor.width // 2)
                and intersection.height >= max(300, monitor.height // 2)
            ):
                usable = intersection
        return ScreenLayout(
            width=usable.width,
            height=usable.height,
            x=usable.x,
            y=usable.y,
        )

    # Single-display/fallback path for X11 systems without xrandr output.
    if work_area is not None:
        return ScreenLayout(
            width=work_area.width,
            height=work_area.height,
            x=work_area.x,
            y=work_area.y,
        )

    if shutil.which("xdotool"):
        try:
            output = _run_text(["xdotool", "getdisplaygeometry"])
            width, height = (int(value) for value in output.split())
            if width > 0 and height > 0:
                return ScreenLayout(width, height)
        except (OSError, ValueError, subprocess.SubprocessError):
            pass

    return None


def tile_active_assistant_window() -> bool:
    """Fill the left half of the active monitor with the active terminal."""
    layout = get_screen_layout()
    if layout is None or not shutil.which("wmctrl") or not shutil.which("xdotool"):
        return False
    try:
        window_id = _run_text(["xdotool", "getactivewindow"]).strip()
        subprocess.run(
            ["xdotool", "set_window", "--name", ASSISTANT_TERMINAL_TITLE, window_id],
            check=True,
            timeout=2,
        )
        return _move_window(window_id, layout.left, identify_by_id=True)
    except (OSError, subprocess.SubprocessError):
        return False


def tile_command_terminal() -> bool:
    """Fill the bottom-right quadrant of the active monitor."""
    layout = get_screen_layout()
    if layout is None:
        return False
    return _move_window(COMMAND_TERMINAL_TITLE, layout.commands, identify_by_id=False)


def tile_chrome_window() -> bool:
    """Fill the right half of the active monitor after Chrome maps its window."""
    layout = get_screen_layout()
    if layout is None:
        return False
    if _move_window(CHROME_WINDOW_TITLE, layout.chrome, identify_by_id=False):
        return True
    return _move_window(
        CHROME_WINDOW_CLASS,
        layout.chrome,
        identify_by_id=False,
        identify_by_class=True,
    )


def chrome_window_arguments() -> list[str]:
    """Give Chrome monitor-aware initial bounds only on Linux/X11."""
    if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
        return []
    layout = get_screen_layout()
    arguments = [f"--class={CHROME_WINDOW_CLASS}"]
    if layout is None:
        return arguments
    x, y, width, height = layout.chrome
    return [
        *arguments,
        f"--window-position={x},{y}",
        f"--window-size={width},{height}",
    ]




def is_chromeos_crostini() -> bool:
    """Return True only for a ChromeOS Linux/Crostini session.

    Normal Linux desktops must keep their existing minimize/restore behavior.
    Crostini is identified using ChromeOS/Sommelier-specific environment/files.
    """
    if not sys.platform.startswith("linux"):
        return False
    if os.environ.get("SOMMELIER_VERSION"):
        return True
    if os.environ.get("CROS_USER_ID_HASH"):
        return True
    if os.path.exists("/dev/.cros_milestone"):
        return True
    if os.path.isdir("/mnt/chromeos"):
        return True
    return False


def park_chrome_window() -> bool:
    """Push managed Chromium behind other windows without minimizing it.

    ChromeOS/Crostini can reliably minimize a Linux window but does not reliably
    remap it when Chromium later requests windowState=normal. Keeping the window
    mapped avoids that compositor edge case. If Chromium is the only visible
    window, lowering it naturally leaves it visible.
    """
    if not is_chromeos_crostini() or not os.environ.get("DISPLAY"):
        return False

    ids = _chrome_window_ids()
    if not ids:
        return False

    window_id = ids[-1]
    lowered = False

    if shutil.which("xdotool"):
        try:
            subprocess.run(
                ["xdotool", "windowlower", window_id],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
            lowered = True
        except (OSError, subprocess.SubprocessError):
            pass

    # EWMH "below" is a harmless additional hint where Sommelier honors it.
    if shutil.which("wmctrl"):
        try:
            subprocess.run(
                ["wmctrl", "-i", "-r", _wmctrl_window_id(window_id), "-b", "add,below"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=1,
            )
            lowered = True
        except (OSError, subprocess.SubprocessError):
            pass

    return lowered


def _chrome_window_ids() -> list[str]:
    """Find the managed Chrome X11/XWayland window, including minimized windows.

    Crostini/Sommelier does not always preserve Chromium's custom WM_CLASS on the
    host-visible window.  A minimized window also disappears from xdotool's
    --onlyvisible search.  Enumerate all top-level windows and accept the stable
    class/title first, then a conservative Chrome/Chromium fallback.
    """
    if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
        return []
    ids: list[str] = []
    if shutil.which("xdotool"):
        searches = [
            ["xdotool", "search", "--class", CHROME_WINDOW_CLASS],
            ["xdotool", "search", "--name", CHROME_WINDOW_TITLE],
        ]
        for command in searches:
            try:
                for wid in _run_text(command, timeout=1).split():
                    if wid not in ids:
                        ids.append(wid)
            except (OSError, subprocess.SubprocessError):
                pass
    if ids:
        return ids

    # ChromeOS Crostini fallback: Sommelier may expose google-chrome/Google-chrome
    # or chromium/Chromium instead of the requested --class. Use wmctrl's complete
    # window list (which includes minimized windows), preferring the newest match.
    if shutil.which("wmctrl"):
        try:
            output = _run_text(["wmctrl", "-lx"], timeout=1)
            candidates=[]
            for line in output.splitlines():
                parts=line.split(None,4)
                if len(parts)<4:
                    continue
                wid=parts[0]
                blob=line.casefold()
                if any(token in blob for token in (
                    CHROME_WINDOW_CLASS.casefold(),
                    "google-chrome", "google_chrome", "chromium", "chrome.chrome"
                )):
                    candidates.append(wid)
            ids.extend(reversed(candidates))
        except (OSError, subprocess.SubprocessError):
            pass
    return ids


def _wmctrl_window_id(window_id: str) -> str:
    """Convert xdotool's decimal id to wmctrl's hexadecimal id form."""
    try:
        return hex(int(window_id, 0))
    except ValueError:
        return window_id


def restore_chrome_window() -> bool:
    """Restore/raise managed Chrome on Linux/X11/Crostini only."""
    if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
        return False
    ids=_chrome_window_ids()
    if not ids:
        return False
    ok=False
    for wid in reversed(ids):
        # xdotool's windowmap is important on Crostini: after minimizing, the
        # Sommelier/XWayland window can be unmapped, so CDP 'normal' alone does
        # not make it visible again.
        if shutil.which("xdotool"):
            try:
                subprocess.run(["xdotool", "windowmap", wid], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                subprocess.run(["xdotool", "windowraise", wid], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                ok=True
            except (OSError, subprocess.SubprocessError):
                pass
        if shutil.which("wmctrl"):
            try:
                hx=_wmctrl_window_id(wid)
                subprocess.run(["wmctrl", "-i", "-r", hx, "-b", "remove,hidden,below,maximized_vert,maximized_horz,fullscreen"],
                               check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                subprocess.run(["wmctrl", "-i", "-a", hx], check=False,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
                ok=True
            except (OSError, subprocess.SubprocessError):
                pass
        if ok:
            return True
    return False


def minimize_chrome_window() -> bool:
    """Minimize managed Chrome on Linux/X11/Crostini only."""
    if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
        return False
    if not shutil.which("xdotool"):
        return False
    ids=_chrome_window_ids()
    if not ids:
        return False
    try:
        subprocess.run(["xdotool", "windowminimize", ids[-1]], check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def move_chrome_window_to_bounds(x: int, y: int, width: int, height: int) -> bool:
    """Apply exact map-supplied bounds to managed Chrome on Linux/Crostini."""
    if not sys.platform.startswith("linux") or not os.environ.get("DISPLAY"):
        return False
    geometry=(int(x),int(y),int(width),int(height))
    if geometry[2] < 200 or geometry[3] < 200:
        return False
    restore_chrome_window()
    ids=_chrome_window_ids()
    if not ids:
        return False
    # Address the exact window by id. This avoids Crostini WM_CLASS/title
    # translation and makes placement deterministic after restore.
    return _move_window(ids[-1], geometry, identify_by_id=True)


def _move_window(
    target: str,
    geometry: tuple[int, int, int, int],
    *,
    identify_by_id: bool,
    identify_by_class: bool = False,
) -> bool:
    """Normalize and place an X11 window using monitor-relative geometry."""
    if not shutil.which("wmctrl"):
        return False

    selector = ["-i"] if identify_by_id else (["-x"] if identify_by_class else [])
    x, y, width, height = geometry
    if width < 200 or height < 200:
        return False

    try:
        subprocess.run(
            [
                "wmctrl",
                *selector,
                "-r",
                target,
                "-b",
                "remove,maximized_vert,maximized_horz,fullscreen",
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=2,
        )

        geometry_value = f"0,{x},{y},{width},{height}"
        # Some WMs apply geometry only after the maximize state has settled.
        for attempt in range(2):
            subprocess.run(
                ["wmctrl", *selector, "-r", target, "-e", geometry_value],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            if attempt == 0:
                time.sleep(0.12)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
