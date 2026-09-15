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
import re
import shutil
import subprocess
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
    """Give Chrome monitor-aware initial bounds on Linux/X11."""
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
