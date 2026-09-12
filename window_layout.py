"""Exact X11 work-area placement for Repair Assistant windows."""

from dataclasses import dataclass
import re
import shutil
import subprocess
import time


ASSISTANT_TERMINAL_TITLE = "Repair Assistant"
COMMAND_TERMINAL_TITLE = "Repair Assistant Commands"
CHROME_WINDOW_CLASS = "repair-assistant-chrome"
CHROME_WINDOW_TITLE = "Repair Assistant Browser"


@dataclass(frozen=True)
class ScreenLayout:
    """GNOME's usable desktop rectangle, excluding panels and docks."""

    width: int
    height: int
    x: int = 0
    y: int = 0

    @property
    def left(self) -> tuple[int, int, int, int]:
        return (self.x, self.y, self.width // 2, self.height)

    @property
    def chrome(self) -> tuple[int, int, int, int]:
        left_width = self.width // 2
        return (
            self.x + left_width,
            self.y,
            self.width - left_width,
            self.height // 2,
        )

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


def get_screen_layout() -> ScreenLayout | None:
    """Read the active X11 workspace's usable rectangle."""
    layout = _wmctrl_work_area()
    if layout is not None:
        return layout
    if not shutil.which("xdotool"):
        return None
    try:
        output = subprocess.check_output(
            ["xdotool", "getdisplaygeometry"], text=True, timeout=5
        )
        width, height = (int(value) for value in output.split())
        return ScreenLayout(width, height)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _wmctrl_work_area() -> ScreenLayout | None:
    """Parse the current desktop's `WA:` rectangle from `wmctrl -d`."""
    if not shutil.which("wmctrl"):
        return None
    try:
        output = subprocess.check_output(["wmctrl", "-d"], text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return None
    current_line = next((line for line in output.splitlines() if " * " in line), "")
    match = re.search(r"WA:\s*(-?\d+),(-?\d+)\s+(\d+)x(\d+)", current_line)
    if match is None:
        return None
    x, y, width, height = (int(value) for value in match.groups())
    return ScreenLayout(width=width, height=height, x=x, y=y)


def tile_active_assistant_window() -> bool:
    """Identify the active terminal and fill the left half of the work area."""
    layout = get_screen_layout()
    if layout is None or not shutil.which("wmctrl") or not shutil.which("xdotool"):
        return False
    try:
        window_id = subprocess.check_output(
            ["xdotool", "getactivewindow"], text=True, timeout=5
        ).strip()
        subprocess.run(
            ["xdotool", "set_window", "--name", ASSISTANT_TERMINAL_TITLE, window_id],
            check=True,
            timeout=5,
        )
        _move_window(window_id, layout.left, identify_by_id=True)
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def tile_command_terminal() -> bool:
    """Fill the bottom-right quadrant with the persistent command terminal."""
    layout = get_screen_layout()
    if layout is None:
        return False
    return _move_window(
        COMMAND_TERMINAL_TITLE,
        layout.commands,
        identify_by_id=False,
    )


def tile_chrome_window() -> bool:
    """Fill the top-right quadrant after Chrome has mapped its X11 window."""
    layout = get_screen_layout()
    if layout is None:
        return False
    # Chrome may ignore --class when an existing Chrome process handles the
    # launch. The temporary page title uniquely identifies our browser window.
    if _move_window(
        CHROME_WINDOW_TITLE,
        layout.chrome,
        identify_by_id=False,
    ):
        return True
    return _move_window(
        CHROME_WINDOW_CLASS,
        layout.chrome,
        identify_by_id=False,
        identify_by_class=True,
    )


def chrome_window_arguments() -> list[str]:
    """Provide an initial placement while Chrome's X11 window is mapping."""
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
    """Remove maximization and apply outer geometry twice after mapping."""
    if not shutil.which("wmctrl"):
        return False
    selector = ["-i"] if identify_by_id else (["-x"] if identify_by_class else [])
    x, y, width, height = geometry
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
            timeout=5,
        )
        geometry_value = f"0,{x},{y},{width},{height}"
        for attempt in range(2):
            subprocess.run(
                ["wmctrl", *selector, "-r", target, "-e", geometry_value],
                check=True,
                timeout=5,
            )
            if attempt == 0:
                time.sleep(0.15)
        return True
    except (OSError, subprocess.SubprocessError):
        return False
