"""Persistent Playwright browser session for the MTV MAP Companion."""

import os
from pathlib import Path
import subprocess
import sys
from types import TracebackType
from typing import Any

from window_layout import (
    CHROME_WINDOW_TITLE,
    chrome_window_arguments,
    tile_chrome_window,
)
from runtime_paths import browser_profile_dir


PROFILE_DIR = browser_profile_dir()


class BrowserManagerError(RuntimeError):
    """Raised when the Companion browser cannot be started."""


class BrowserManager:
    """Own the persistent visible Chrome/Chromium session used by the Companion."""

    def __init__(self) -> None:
        self._playwright: Any = None
        self._context: Any = None
        self.page: Any = None

    def __enter__(self) -> "BrowserManager":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            answer = input(
                "Playwright is required but not installed. Install it now? [y/N]: "
            ).strip().lower()
            if answer not in {"y", "yes"}:
                raise BrowserManagerError("Playwright installation was declined.")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "playwright"],
                    check=True,
                )
                from playwright.sync_api import sync_playwright
            except (ImportError, subprocess.CalledProcessError) as install_error:
                raise BrowserManagerError(
                    "Playwright could not be installed automatically. "
                    "Run: python3 -m pip install playwright"
                ) from install_error

        try:
            self._playwright = sync_playwright().start()

            launch_options: dict[str, Any] = {
                "headless": False,
                "no_viewport": True,
            }

            if sys.platform.startswith("linux"):
                launch_options["args"] = chrome_window_arguments()

                nss_library_dir = Path("/usr/lib/x86_64-linux-gnu/nss")
                if nss_library_dir.is_dir():
                    browser_environment = os.environ.copy()
                    current_library_path = browser_environment.get(
                        "LD_LIBRARY_PATH",
                        "",
                    )
                    browser_environment["LD_LIBRARY_PATH"] = str(
                        nss_library_dir
                    ) + (
                        f":{current_library_path}"
                        if current_library_path
                        else ""
                    )
                    launch_options["env"] = browser_environment

            self._context = None
            chrome_error: Exception | None = None

            # Prefer the user's installed Google Chrome. Fall back to the
            # Playwright-managed Chromium installed by bootstrap.py.
            try:
                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    channel="chrome",
                    **launch_options,
                )
            except Exception as error:
                chrome_error = error

            if self._context is None:
                chromium_path = Path(self._playwright.chromium.executable_path)
                if not chromium_path.exists():
                    detail = (
                        f" System Chrome launch failed: {chrome_error}"
                        if chrome_error
                        else ""
                    )
                    raise BrowserManagerError(
                        "No compatible Chrome/Chromium browser is available. "
                        "Run the Companion launcher again so it can install Chromium."
                        + detail
                    )

                self._context = self._playwright.chromium.launch_persistent_context(
                    user_data_dir=PROFILE_DIR,
                    **launch_options,
                )

            self.page = (
                self._context.pages[0]
                if self._context.pages
                else self._context.new_page()
            )

            # Give the managed browser a stable title so Linux window-management
            # helpers can find the correct Chrome window.
            self.page.evaluate(
                "title => { document.title = title; }",
                CHROME_WINDOW_TITLE,
            )

            for _ in range(30):
                if tile_chrome_window():
                    break
                self.page.wait_for_timeout(100)

        except subprocess.CalledProcessError as error:
            self.close()
            raise BrowserManagerError(
                "Could not install the Playwright Chromium browser."
            ) from error
        except Exception as error:
            self.close()
            raise BrowserManagerError(
                f"Could not launch Chrome: {error}"
            ) from error

        return self

    @property
    def context(self) -> Any:
        """Return the shared persistent Playwright browser context."""
        return self._context

    def close(self) -> None:
        """Close the browser cleanly so persistent profile state is saved."""
        if self._context is not None:
            try:
                self._context.close()
            except Exception:
                pass
            self._context = None

        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
