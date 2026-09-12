"""Fixed status dashboard for the interactive assistant terminal."""

import shutil
import sys
import threading


class StatusDisplay:
    """Reserve terminal header lines while normal output scrolls below them."""

    HEADER_ROWS = 5

    def __init__(self) -> None:
        self.enabled = False
        self.workflow = "Home"
        self.status = "Starting"
        self.detail = "Preparing Repair Assistant"
        self._lock = threading.Lock()

    def initialize(self) -> None:
        if not sys.stdout.isatty():
            return
        rows = shutil.get_terminal_size(fallback=(80, 24)).lines
        if rows <= self.HEADER_ROWS + 2:
            return
        self.enabled = True
        sys.stdout.write(
            "\033[2J\033[H"
            f"\033[{self.HEADER_ROWS + 1};{rows}r"
            f"\033[{self.HEADER_ROWS + 1};1H"
        )
        sys.stdout.flush()
        self._draw()

    def update(
        self,
        status: str,
        detail: str = "",
        workflow: str | None = None,
    ) -> None:
        if workflow is not None:
            self.workflow = workflow
        self.status = status
        self.detail = detail
        self._draw()

    def reset_home(self) -> None:
        self.update("Ready", "Choose a workflow", workflow="Home")

    def shutdown(self) -> None:
        if not self.enabled:
            return
        with self._lock:
            sys.stdout.write("\0337\033[r\0338")
            sys.stdout.flush()
        self.enabled = False

    def _draw(self) -> None:
        if not self.enabled:
            return
        width = shutil.get_terminal_size(fallback=(80, 24)).columns
        rule = "=" * max(1, width)
        lines = (
            rule,
            f" Workflow: {self.workflow}",
            f" Status:   {self.status}",
            f" Detail:   {self.detail or '-'}",
            rule,
        )
        with self._lock:
            sys.stdout.write("\0337")
            for row, line in enumerate(lines, start=1):
                sys.stdout.write(f"\033[{row};1H\033[2K{line[:width]}")
            sys.stdout.write("\0338")
            sys.stdout.flush()


STATUS = StatusDisplay()


def set_status(status: str, detail: str = "", workflow: str | None = None) -> None:
    """Update the shared terminal dashboard."""
    STATUS.update(status, detail, workflow)
