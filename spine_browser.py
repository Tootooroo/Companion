"""Persistent browser session for interacting with the SPINE dashboard."""

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess
import sys
from types import TracebackType
from typing import Any
from urllib.parse import urlparse

from window_layout import (
    CHROME_WINDOW_TITLE,
    chrome_window_arguments,
    tile_chrome_window,
)
from status_display import set_status
from runtime_paths import browser_profile_dir


SPINE_URL = "https://spine.apptronik.com/manufacturing"
PROFILE_DIR = browser_profile_dir()


@dataclass(frozen=True)
class ChildUnit:
    """A child unit installed beneath a FRU in SPINE."""

    depth: str
    serial_number: str
    part_number: str
    deviations: str
    install_location: str


@dataclass(frozen=True)
class UnitDetails:
    """SPINE identity fields for a FRU or individual component."""

    serial_number: str
    part_number: str
    revision: str

    @property
    def apn(self) -> str:
        """Return the Apptronik part number including its revision."""
        return " ".join(value for value in (self.part_number, self.revision) if value)


class SpineBrowserError(RuntimeError):
    """Raised when the SPINE browser cannot be started or authenticated."""


class SpineBrowser:
    """Own a visible Chrome session that retains SPINE authentication."""

    def __init__(self) -> None:
        self._playwright: Any = None
        self._context: Any = None
        self.page: Any = None

    def __enter__(self) -> "SpineBrowser":
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            answer = input(
                "Playwright is required but not installed. Install it now? [y/N]: "
            ).strip().lower()
            if answer not in {"y", "yes"}:
                raise SpineBrowserError("Playwright installation was declined.")
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install", "playwright"],
                    check=True,
                )
                from playwright.sync_api import sync_playwright
            except (ImportError, subprocess.CalledProcessError) as install_error:
                raise SpineBrowserError(
                    "Playwright could not be installed automatically. "
                    "Run: python3 -m pip install playwright"
                ) from install_error

        try:
            self._playwright = sync_playwright().start()
            # Prefer the user's installed Google Chrome on every desktop OS.
            # Playwright's "chrome" channel resolves the platform-specific path
            # itself (including Windows, where shutil.which() is unreliable for
            # a normal Chrome installation). If that launch fails, fall back to
            # the Playwright-managed Chromium installed by bootstrap.py.
            prefer_system_chrome = True
            # Do NOT use Playwright's default fixed 1280x720 viewport.
            # The paperwork browser is resized to half of the technician's real
            # display via CDP. no_viewport=True makes the webpage viewport follow
            # the actual Chrome window dimensions, so Buganizer/Salesforce reflow
            # instead of being clipped inside a narrow outer window.
            launch_options = {
                "headless": False,
                "no_viewport": True,
            }
            if sys.platform.startswith("linux"):
                launch_options["args"] = chrome_window_arguments()
            if sys.platform.startswith("linux"):
                nss_library_dir = Path("/usr/lib/x86_64-linux-gnu/nss")
                if nss_library_dir.is_dir():
                    browser_environment = os.environ.copy()
                    current_library_path = browser_environment.get(
                        "LD_LIBRARY_PATH", ""
                    )
                    browser_environment["LD_LIBRARY_PATH"] = str(
                        nss_library_dir
                    ) + (
                        f":{current_library_path}" if current_library_path else ""
                    )
                    launch_options["env"] = browser_environment
            self._context = None
            chrome_error: Exception | None = None
            if prefer_system_chrome:
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
                    detail = f" System Chrome launch failed: {chrome_error}" if chrome_error else ""
                    raise SpineBrowserError(
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
            # Identify this exact Chrome window by title. Chrome can ignore its
            # requested X11 class when another Chrome process brokers launch.
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
            raise SpineBrowserError(
                "Could not install the Playwright Chromium browser."
            ) from error
        except Exception as error:
            self.close()
            raise SpineBrowserError(f"Could not launch Chrome: {error}") from error

        return self

    def boot(self) -> None:
        """Open SPINE and allow the technician to complete authentication."""
        self.open_dashboard()
        print("If prompted, complete Google sign-in in the Chrome window.")
        input("When the SPINE Manufacturing dashboard is visible, press Enter: ")
        self.confirm_authenticated()

    @property
    def context(self) -> Any:
        """Return the shared persistent browser context."""
        return self._context

    def open_dashboard(self) -> None:
        """Open SPINE without pausing for authentication confirmation."""
        print("\nOpening the SPINE dashboard in Chrome...")
        set_status("Authenticating", "Opening SPINE")
        try:
            self.page.goto(SPINE_URL, wait_until="domcontentloaded")
        except Exception as error:
            raise SpineBrowserError(f"Could not open SPINE: {error}") from error

    def confirm_authenticated(self) -> None:
        """Verify that an authenticated SPINE page is open in any tab."""
        authenticated_page = next(
            (page for page in self._context.pages if self._is_authenticated_spine(page.url)),
            None,
        )
        if authenticated_page is None:
            open_urls = ", ".join(page.url for page in self._context.pages)
            raise SpineBrowserError(
                "SPINE authentication was not confirmed. "
                f"Open browser pages: {open_urls}"
            )

        self.page = authenticated_page
        set_status("Authenticated", "SPINE is ready")
        print("SPINE browser session is ready.")

    @staticmethod
    def _is_authenticated_spine(url: str) -> bool:
        """Return whether a URL appears to be an authenticated SPINE page."""
        parsed = urlparse(url)
        return (
            parsed.hostname == "spine.apptronik.com"
            and not parsed.path.startswith("/auth/")
        )

    def get_child_units(
        self,
        serial_number: str,
        excluded_location_prefixes: tuple[str, ...] = (),
    ) -> list[ChildUnit]:
        """Open a unit by serial number and return its child-unit table."""
        try:
            self._open_unit(serial_number)

            section_title = self.page.get_by_text("Child Units", exact=True)
            section_title.scroll_into_view_if_needed()
            section = section_title.locator(
                'xpath=ancestor::*[@data-slot="card"][1]'
            )
            section.locator(
                'tbody a[href*="/manufacturing/units/"]'
            ).first.wait_for(state="visible", timeout=15_000)
            rows = section.locator("tbody tr")

            child_units: list[ChildUnit] = []
            for row in rows.all():
                cells = [text.strip() for text in row.locator("td").all_inner_texts()]
                if len(cells) < 5:
                    continue

                install_location = " / ".join(cells[4].splitlines())
                if not install_location:
                    continue

                location_key = cells[4].splitlines()[-1].strip().lower()
                if location_key.startswith(excluded_location_prefixes):
                    continue

                child_units.append(
                    ChildUnit(
                        depth=cells[0],
                        serial_number=cells[1],
                        part_number=cells[2],
                        deviations=", ".join(cells[3].splitlines()),
                        install_location=install_location,
                    )
                )

            return child_units
        except Exception as error:
            raise SpineBrowserError(
                f"Could not retrieve child units for {serial_number}: {error}"
            ) from error

    def get_unit_details(self, serial_number: str) -> UnitDetails:
        """Return a unit's serial number, part number, and revision from SPINE."""
        try:
            self._open_unit(serial_number)
            serial_label = self.page.get_by_text("Serial number", exact=True).first
            details_card = serial_label.locator(
                'xpath=ancestor::*[@data-slot="card"][1]'
            )
            details_card.wait_for(state="visible", timeout=15_000)
            lines = [line.strip() for line in details_card.inner_text().splitlines()]

            def value_after(label: str) -> str:
                try:
                    index = lines.index(label)
                except ValueError as error:
                    raise SpineBrowserError(
                        f"SPINE unit details did not contain '{label}'."
                    ) from error
                for value in lines[index + 1 :]:
                    if value:
                        return value
                raise SpineBrowserError(
                    f"SPINE unit details did not contain a value for '{label}'."
                )

            details = UnitDetails(
                serial_number=value_after("Serial number"),
                part_number=value_after("Part number"),
                revision=value_after("Revision"),
            )
            if details.serial_number.casefold() != serial_number.casefold():
                raise SpineBrowserError(
                    f"SPINE opened serial {details.serial_number}, expected {serial_number}."
                )
            return details
        except SpineBrowserError:
            raise
        except Exception as error:
            raise SpineBrowserError(
                f"Could not retrieve unit details for {serial_number}: {error}"
            ) from error

    def _open_unit(self, serial_number: str) -> None:
        """Search for an exact serial and open its manufacturing unit page."""
        self.page.goto(SPINE_URL, wait_until="domcontentloaded")
        search_box = self.page.get_by_placeholder(
            "Search serial numbers, part numbers, deviations..."
        )
        search_box.fill(serial_number)
        result = self.page.get_by_role("option").filter(has_text=serial_number)
        result.wait_for(state="visible", timeout=15_000)
        expected = serial_number.casefold()
        exact_result = next(
            (
                option
                for option in result.all()
                if option.inner_text().splitlines()
                and option.inner_text().splitlines()[0].strip().casefold() == expected
            ),
            None,
        )
        if exact_result is None:
            raise SpineBrowserError(f"Serial {serial_number} was not found in SPINE.")
        exact_result.click()
        self.page.wait_for_url(
            "**/manufacturing/units/**",
            timeout=15_000,
            wait_until="domcontentloaded",
        )

    def serial_exists(self, serial_number: str) -> bool:
        """Return whether an exact serial-number result exists in SPINE."""
        try:
            from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

            self.page.goto(SPINE_URL, wait_until="domcontentloaded")
            search_box = self.page.get_by_placeholder(
                "Search serial numbers, part numbers, deviations..."
            )
            search_box.fill(serial_number)
            results = self.page.get_by_role("option").filter(
                has_text=serial_number
            )
            try:
                results.first.wait_for(state="visible", timeout=10_000)
            except PlaywrightTimeoutError:
                return False

            expected = serial_number.casefold()
            return any(
                text.splitlines()
                and text.splitlines()[0].strip().casefold() == expected
                for text in results.all_inner_texts()
            )
        except Exception as error:
            raise SpineBrowserError(
                f"Could not verify serial {serial_number} in SPINE: {error}"
            ) from error

    def close(self) -> None:
        """Close the browser cleanly so profile state is saved."""
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
