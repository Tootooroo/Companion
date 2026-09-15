#!/usr/bin/env python3
from __future__ import annotations

import builtins
import html
import json
import platform
import queue
import re
import threading
import time
import urllib.parse
from concurrent.futures import Future, TimeoutError as FutureTimeoutError
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Callable

from paperwork import (
    BUGANIZER_ISSUES_URL,
    SALESFORCE_CASES_URL,
    PaperworkError,
    _search_salesforce_case,
    _assert_salesforce_case_matches_bug,
    claim_salesforce_case,
    close_salesforce_case,
    post_buganizer_comment_direct,
    post_salesforce_feed_comment,
    reassign_buganizer_issue,
    reassign_buganizer_issue_to,
    set_salesforce_case_fields,
)
from salesforce_routes import (
    SalesforceRouteError,
    get_claim_form_spec,
    get_reassign_form_spec,
    resolve_claim_route,
    resolve_reassign_route,
)
from browser_manager import BrowserManager


HOST = "127.0.0.1"
PORT = 8765
BUG_RE = re.compile(r"^\d{9}$")
SHUTDOWN_REQUESTED = threading.Event()
SERVER: ThreadingHTTPServer | None = None

REASSIGN_TARGETS = {
    "Mechatronics": "robotics-support@google.com",
    "Lab Build Team": "seeger@google.com",
    "Release Team": "saramesh@google.com",
    "Research Team": "atari-support@google.com",
    "Engineering Team": "atari-support@google.com",
}
OTHER_ASSIGNEES = (
    "fedynchuk@google.com",
)
REASSIGN_TEAMS = tuple(REASSIGN_TARGETS) + ("Other",)


def clean(value: Any) -> str:
    return str(value or "").strip()


def safe_url(value: str) -> str:
    value = clean(value)
    if not value:
        return ""
    try:
        parsed = urllib.parse.urlparse(value)
    except Exception:
        return ""
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return value


def allowed_bug_url(value: str) -> str:
    value = safe_url(value)
    if not value:
        return ""
    host = (urllib.parse.urlparse(value).hostname or "").lower()
    return value if host.endswith(".google.com") or host == "issuetracker.google.com" else ""


def allowed_sf_url(value: str) -> str:
    value = safe_url(value)
    if not value:
        return ""
    host = (urllib.parse.urlparse(value).hostname or "").lower()
    return value if host.endswith(".force.com") or host.endswith(".salesforce.com") else ""


@dataclass
class Workspace:
    # Playwright objects. These are ONLY touched by BrowserWorker's one thread.
    browser: BrowserManager | None = None
    bug_page: Any = None
    sf_page: Any = None

    # UI/session state. Protected by lock.
    bug_number: str = ""
    robot_id: str = ""
    location_label: str = "Unknown"
    bug_url: str = ""
    sf_url: str = ""
    action: str = ""
    team: str = ""
    assignee_email: str = ""
    details: str = ""
    result_message: str = ""
    sf_owner: str = ""
    sf_owner_claimed: bool = False
    sf_description_saved: bool = False
    sf_fields_saved: bool = False
    sf_closed: bool = False

    opening: bool = False
    bug_opened: bool = False
    sf_opened: bool = False
    sf_phase: str = "Not opened"
    launch_error: str = ""
    startup_phase: str = "Starting..."
    startup_ready: bool = False
    startup_error: str = ""
    startup_bug_authenticated: bool = False
    startup_sf_authenticated: bool = False
    session_id: int = 0

    # Geometry supplied by the shared map for this technician's active display.
    # The map owns the LEFT companion window; Playwright owns the RIGHT ticket window.
    screen_left: int = 0
    screen_top: int = 0
    screen_width: int = 0
    screen_height: int = 0
    split_x: int = 0

    lock: threading.RLock = field(default_factory=threading.RLock)

    def new_session(
        self,
        bug_number: str,
        robot_id: str,
        bug_url: str,
        location_label: str = "Unknown",
        geometry: dict[str, int] | None = None,
    ) -> int:
        """Create/reset UI state for a fresh Begin click."""
        geometry = geometry or {}
        with self.lock:
            self.session_id += 1
            sid = self.session_id
            self.bug_number = bug_number
            self.robot_id = robot_id
            self.location_label = clean(location_label) or "Unknown"
            self.bug_url = bug_url
            self.sf_url = ""
            self.action = ""
            self.team = ""
            self.assignee_email = ""
            self.details = ""
            self.result_message = ""
            self.sf_owner = ""
            self.sf_owner_claimed = False
            self.sf_description_saved = False
            self.sf_fields_saved = False
            self.sf_closed = False
            self.opening = True
            self.bug_opened = False
            self.sf_opened = False
            self.sf_phase = "Opening Salesforce..."
            self.launch_error = ""

            self.screen_left = int(geometry.get("screen_left", 0) or 0)
            self.screen_top = int(geometry.get("screen_top", 0) or 0)
            self.screen_width = max(0, int(geometry.get("screen_width", 0) or 0))
            self.screen_height = max(0, int(geometry.get("screen_height", 0) or 0))
            self.split_x = max(0, int(geometry.get("split_x", 0) or 0))
            return sid

    def invalidate_session(self) -> None:
        """Exit invalidates in-flight UI updates but leaves the companion alive."""
        with self.lock:
            self.session_id += 1
            self.action = ""
            self.team = ""
            self.opening = False
            self.launch_error = ""

    def session_is_current(self, sid: int) -> bool:
        with self.lock:
            return sid == self.session_id

    def update_launch(
        self,
        sid: int,
        *,
        opening: bool | None = None,
        bug_opened: bool | None = None,
        sf_opened: bool | None = None,
        sf_url: str | None = None,
        sf_phase: str | None = None,
        error: str | None = None,
    ) -> None:
        with self.lock:
            if sid != self.session_id:
                return
            if opening is not None:
                self.opening = opening
            if bug_opened is not None:
                self.bug_opened = bug_opened
            if sf_opened is not None:
                self.sf_opened = sf_opened
            if sf_url is not None:
                self.sf_url = sf_url
            if sf_phase is not None:
                self.sf_phase = sf_phase
            if error is not None:
                self.launch_error = error

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "bug_number": self.bug_number,
                "robot_id": self.robot_id,
                "location_label": self.location_label,
                "bug_url": self.bug_url,
                "sf_url": self.sf_url,
                "action": self.action,
                "team": self.team,
                "assignee_email": self.assignee_email,
                "details": self.details,
                "result_message": self.result_message,
                "sf_owner": self.sf_owner,
                "sf_owner_claimed": self.sf_owner_claimed,
                "sf_description_saved": self.sf_description_saved,
                "sf_fields_saved": self.sf_fields_saved,
                "sf_closed": self.sf_closed,
                "opening": self.opening,
                "bug_opened": self.bug_opened,
                "sf_opened": self.sf_opened,
                "sf_phase": self.sf_phase,
                "launch_error": self.launch_error,
                "startup_phase": self.startup_phase,
                "startup_ready": self.startup_ready,
                "startup_error": self.startup_error,
                "startup_bug_authenticated": self.startup_bug_authenticated,
                "startup_sf_authenticated": self.startup_sf_authenticated,
                "session_id": self.session_id,
                "screen_left": self.screen_left,
                "screen_top": self.screen_top,
                "screen_width": self.screen_width,
                "screen_height": self.screen_height,
                "split_x": self.split_x,
            }

    def choose(self, action: str, team: str = "") -> None:
        with self.lock:
            self.action = action
            self.team = team
            if not action:
                self.assignee_email = ""
                self.details = ""
                self.result_message = ""

    def show_reassign_targets(self) -> None:
        with self.lock:
            self.action = "reassign_select"
            self.team = ""
            self.assignee_email = ""
            self.details = ""
            self.result_message = ""
            self.sf_owner = ""
            self.sf_owner_claimed = False
            self.sf_description_saved = False
            self.sf_fields_saved = False
            self.sf_closed = False

    def select_reassign_target(self, team: str) -> None:
        with self.lock:
            self.action = "reassign_form"
            self.team = team
            self.assignee_email = REASSIGN_TARGETS.get(team, "")
            self.details = ""
            self.result_message = ""
            self.sf_owner = ""
            self.sf_owner_claimed = False
            self.sf_description_saved = False
            self.sf_fields_saved = False
            self.sf_closed = False

    def begin_salesforce_reassign(
        self,
        *,
        team: str,
        assignee_email: str,
        details: str,
        result_message: str,
    ) -> None:
        """Buganizer is committed; move this Reassign into Salesforce closeout."""
        with self.lock:
            self.action = "salesforce_reassign_form"
            self.team = team
            self.assignee_email = assignee_email
            self.details = details
            self.result_message = result_message
            self.sf_owner = ""
            self.sf_owner_claimed = False
            self.sf_description_saved = False
            self.sf_fields_saved = False
            self.sf_closed = False

    def update_salesforce_progress(
        self,
        *,
        owner: str | None = None,
        owner_claimed: bool | None = None,
        description_saved: bool | None = None,
        fields_saved: bool | None = None,
        closed: bool | None = None,
    ) -> None:
        """Record completed Salesforce steps so a retry does not repeat them."""
        with self.lock:
            if owner is not None:
                self.sf_owner = owner
            if owner_claimed is not None:
                self.sf_owner_claimed = owner_claimed
            if description_saved is not None:
                self.sf_description_saved = description_saved
            if fields_saved is not None:
                self.sf_fields_saved = fields_saved
            if closed is not None:
                self.sf_closed = closed

    def finish_reassign(
        self,
        *,
        team: str,
        assignee_email: str,
        details: str,
        result_message: str,
        sf_owner: str = "",
    ) -> None:
        with self.lock:
            self.action = "reassign_done"
            self.team = team
            self.assignee_email = assignee_email
            self.details = details
            self.result_message = result_message
            if sf_owner:
                self.sf_owner = sf_owner


    def show_claim_form(self) -> None:
        with self.lock:
            self.action = "claim_form"
            self.team = ""
            self.assignee_email = "robotics-support@google.com"
            self.details = ""
            self.result_message = ""
            self.sf_owner = ""
            self.sf_owner_claimed = False
            self.sf_description_saved = False
            self.sf_fields_saved = False
            self.sf_closed = False

    def begin_salesforce_claim(
        self,
        *,
        details: str,
        result_message: str,
    ) -> None:
        """Buganizer Claim is committed; move directly to Salesforce routing."""
        with self.lock:
            self.action = "salesforce_claim_form"
            self.team = ""
            self.assignee_email = "robotics-support@google.com"
            self.details = details
            self.result_message = result_message
            self.sf_owner = ""
            self.sf_owner_claimed = False
            self.sf_description_saved = False
            self.sf_fields_saved = False
            self.sf_closed = False

    def show_salesforce_claim_form(self) -> None:
        """Expose Claim routing only after Salesforce reached Customer Responded."""
        with self.lock:
            if self.action != "salesforce_claim_wait":
                return
            self.action = "salesforce_claim_form"

    def finish_claim(
        self,
        *,
        details: str,
        result_message: str,
        sf_owner: str = "",
    ) -> None:
        with self.lock:
            self.action = "claim_done"
            self.team = ""
            self.assignee_email = "robotics-support@google.com"
            self.details = details
            self.result_message = result_message
            if sf_owner:
                self.sf_owner = sf_owner

    @staticmethod
    def usable(page: Any) -> bool:
        try:
            return bool(page) and not page.is_closed()
        except Exception:
            return False

    def update_startup(
        self,
        *,
        phase: str | None = None,
        ready: bool | None = None,
        error: str | None = None,
        bug_authenticated: bool | None = None,
        sf_authenticated: bool | None = None,
    ) -> None:
        with self.lock:
            if phase is not None:
                self.startup_phase = phase
            if ready is not None:
                self.startup_ready = ready
            if error is not None:
                self.startup_error = error
            if bug_authenticated is not None:
                self.startup_bug_authenticated = bug_authenticated
            if sf_authenticated is not None:
                self.startup_sf_authenticated = sf_authenticated

    def set_managed_window_state(self, page: Any, state: str) -> None:
        """Best-effort minimize/restore for the managed Chrome window."""
        try:
            assert self.browser is not None
            cdp = self.browser.context.new_cdp_session(page)
            info = cdp.send("Browser.getWindowForTarget")
            window_id = info.get("windowId")
            if not window_id:
                return
            cdp.send(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": {"windowState": state},
                },
            )
        except Exception as error:
            print(f"Could not set paperwork browser state to {state}: {error}")

    def bootstrap_companion(self) -> None:
        """
        Preflight authentication before the first Begin.

        The managed browser keeps exactly the startup Companion tab, Buganizer,
        and Salesforce. It remains visible whenever either service still needs
        sign-in. It minimizes only after both applications are genuinely ready.
        """
        self.update_startup(
            phase="Checking Buganizer and Salesforce...",
            ready=False,
            error="",
            bug_authenticated=False,
            sf_authenticated=False,
        )

        setup_page = None
        try:
            self.ensure_browser()
            assert self.browser is not None

            if not self.usable(self.bug_page):
                self.bug_page = self.new_page()
            if not self.usable(self.sf_page):
                self.sf_page = self.new_page()

            setup_page = self.new_page()
            setup_page.goto(
                f"http://{HOST}:{PORT}/startup",
                wait_until="domcontentloaded",
                timeout=15_000,
            )

            # Navigate directly to the real app destinations. Persistent cookies
            # are reused automatically. If a session has expired, the normal
            # login/Okta redirect remains visible for the technician.
            self.bug_page.goto(
                BUGANIZER_ISSUES_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            self.sf_page.goto(
                SALESFORCE_CASES_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            first_check = True
            waited_for_auth = False
            last_front = ""

            while not SHUTDOWN_REQUESTED.is_set():
                bug_ready = self._buganizer_page_ready(self.bug_page)
                sf_ready = self._salesforce_page_ready(self.sf_page)

                self.update_startup(
                    bug_authenticated=bug_ready,
                    sf_authenticated=sf_ready,
                    ready=bug_ready and sf_ready,
                    error="",
                )

                if bug_ready and sf_ready:
                    self.update_startup(
                        phase="Buganizer and Salesforce connected.",
                        ready=True,
                    )

                    # Show the accurate final green state before minimizing. If
                    # both sessions were already valid, keep this very short.
                    try:
                        setup_page.reload(
                            wait_until="domcontentloaded",
                            timeout=5_000,
                        )
                        setup_page.bring_to_front()
                        setup_page.wait_for_timeout(250 if not waited_for_auth else 850)
                    except Exception:
                        pass

                    if not SHUTDOWN_REQUESTED.is_set():
                        self.set_managed_window_state(setup_page, "minimized")
                    return

                if first_check and (not bug_ready or not sf_ready):
                    waited_for_auth = True
                first_check = False

                if not bug_ready:
                    self.update_startup(
                        phase="Buganizer sign-in required.",
                        ready=False,
                    )
                    if last_front != "bug":
                        try:
                            self.set_managed_window_state(self.bug_page, "normal")
                            self.bug_page.bring_to_front()
                            last_front = "bug"
                        except Exception:
                            pass
                elif not sf_ready:
                    # If Salesforce is already on Lightning but its application
                    # shell is still loading, do not call it authenticated yet.
                    sf_url = clean(self.sf_page.url)
                    if self._salesforce_host_is_authenticated(sf_url):
                        phase = "Loading Salesforce..."
                    else:
                        phase = "Salesforce / Okta sign-in required."
                    self.update_startup(phase=phase, ready=False)
                    if last_front != "sf":
                        try:
                            self.set_managed_window_state(self.sf_page, "normal")
                            self.sf_page.bring_to_front()
                            last_front = "sf"
                        except Exception:
                            pass

                # Update the compact control tab without adding network/browser
                # churn. A light reload only happens after state changes.
                try:
                    if self.usable(setup_page):
                        setup_page.reload(
                            wait_until="domcontentloaded",
                            timeout=3_000,
                        )
                except Exception:
                    pass

                active = self.sf_page if self.usable(self.sf_page) else self.bug_page
                active.wait_for_timeout(350)

        except Exception as error:
            if SHUTDOWN_REQUESTED.is_set():
                return
            print(f"Companion startup needs attention: {error}")
            self.update_startup(
                phase="Companion running; sign-in still required.",
                ready=False,
                error=str(error),
            )

    def close_browser(self) -> None:
        """Close/reset the managed Playwright session."""
        browser = self.browser
        self.browser = None
        self.bug_page = None
        self.sf_page = None
        if browser is not None:
            try:
                browser.__exit__(None, None, None)
            except Exception:
                pass

    def ensure_browser(self) -> None:
        """
        Ensure the persistent browser context is alive.

        A user may manually close the Buganizer/Salesforce tabs, or even close
        the entire Playwright Chrome window. The old implementation only tested
        `self.browser is not None`, leaving a dead context cached forever.
        """
        if self.browser is not None:
            try:
                # Accessing pages is a lightweight way to detect a dead context.
                _ = self.browser.context.pages
                return
            except Exception:
                self.close_browser()

        self.browser = BrowserManager()
        self.browser.__enter__()

    def new_page(self) -> Any:
        """
        Create a page, recovering once if the user closed the whole browser.
        """
        self.ensure_browser()
        assert self.browser is not None
        try:
            return self.browser.context.new_page()
        except Exception:
            self.close_browser()
            self.ensure_browser()
            assert self.browser is not None
            return self.browser.context.new_page()

    @staticmethod
    def _buganizer_host_is_authenticated(url: str) -> bool:
        """Return True only after Partner IssueTracker itself has loaded."""
        try:
            parsed = urllib.parse.urlparse(clean(url))
            host = (parsed.hostname or "").lower()
            path = parsed.path or "/"
        except Exception:
            return False

        return (
            host == "partnerissuetracker.corp.google.com"
            and (path == "/issues" or path.startswith("/issues/"))
        )

    def _buganizer_page_ready(self, page: Any) -> bool:
        """Return True only when the authenticated IssueTracker app is usable."""
        try:
            if not self._buganizer_host_is_authenticated(clean(page.url)):
                return False

            # Avoid treating an intermediate redirect/error shell as connected.
            body = page.locator("body")
            if not body.is_visible():
                return False

            # Partner IssueTracker normally exposes at least one of these once
            # the application shell has loaded. If markup changes, the valid
            # /issues route plus a non-empty body remains a safe fallback.
            markers = (
                'textarea[aria-label="Comment box - add your comment"]',
                'a[href*="/issues/"]',
                '[aria-label*="Issue"]',
            )
            for selector in markers:
                try:
                    if page.locator(selector).count() > 0:
                        return True
                except Exception:
                    pass

            return bool("issue" in clean(body.inner_text()).lower())
        except Exception:
            return False

    def wait_for_buganizer_authentication(
        self,
        page: Any,
        sid: int,
        timeout_seconds: float = 300.0,
    ) -> None:
        """Wait for manual Google/SSO verification if the session expired."""
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            if SHUTDOWN_REQUESTED.is_set() or not self.session_is_current(sid):
                return
            try:
                current = clean(page.url)
            except Exception:
                current = ""

            if self._buganizer_page_ready(page):
                self.update_startup(
                    bug_authenticated=True,
                    ready=bool(self.snapshot().get("startup_sf_authenticated")),
                    error="",
                )
                return

            self.update_startup(
                phase="Waiting for Buganizer sign-in...",
                bug_authenticated=False,
                ready=False,
            )
            try:
                page.bring_to_front()
            except Exception:
                pass
            page.wait_for_timeout(500)

        raise PaperworkError(
            "Buganizer authentication timed out. Complete sign-in in the "
            "visible Buganizer tab, then press Begin again."
        )

    @staticmethod
    def _salesforce_host_is_authenticated(url: str) -> bool:
        """Return True only after Salesforce has reached the Lightning app."""
        try:
            parsed = urllib.parse.urlparse(clean(url))
            host = (parsed.hostname or "").lower()
            path = parsed.path or "/"
        except Exception:
            return False

        # Generic salesforce.com/login hosts are intentionally excluded.
        return (
            (host.endswith(".lightning.force.com") or host == "lightning.force.com")
            and (path == "/lightning" or path.startswith("/lightning/"))
        )

    def _salesforce_page_ready(self, page: Any) -> bool:
        """Return True only when the authenticated Salesforce UI is usable.

        This is stricter than a URL check. It prevents the Companion from
        showing green / minimizing while Salesforce is still on login, Okta,
        or an only-partially-loaded Lightning shell.
        """
        try:
            if not self._salesforce_host_is_authenticated(clean(page.url)):
                return False

            selectors = (
                'button[aria-label="Search"]',
                'input[title="Search Salesforce"]',
                'input[aria-label="Search Salesforce"]',
                '.slds-global-header',
                'one-app-nav-bar',
            )
            for selector in selectors:
                try:
                    locator = page.locator(selector).first
                    if locator.count() and locator.is_visible():
                        return True
                except Exception:
                    pass
            return False
        except Exception:
            return False

    def wait_for_salesforce_authentication(
        self,
        page: Any,
        sid: int,
        timeout_seconds: float = 300.0,
    ) -> None:
        """
        Wait for manual Okta/SSO verification on first use.

        The worker thread can wait here safely because /health and the Paperwork
        UI run on ThreadingHTTPServer and remain responsive.
        """
        deadline = time.monotonic() + timeout_seconds
        last_url = ""

        while time.monotonic() < deadline:
            if not self.session_is_current(sid):
                return

            try:
                last_url = clean(page.url)
            except Exception:
                last_url = ""

            if self._salesforce_page_ready(page):
                self.update_launch(
                    sid,
                    sf_phase="Salesforce authenticated",
                )
                self.update_startup(
                    sf_authenticated=True,
                    ready=bool(self.snapshot().get("startup_bug_authenticated")),
                    error="",
                )
                return

            self.update_launch(
                sid,
                sf_phase="Waiting for Okta verification...",
            )
            self.update_startup(
                phase="Waiting for Salesforce / Okta sign-in...",
                sf_authenticated=False,
                ready=False,
            )
            try:
                page.bring_to_front()
            except Exception:
                pass
            page.wait_for_timeout(500)

        raise PaperworkError(
            "Salesforce authentication timed out. Complete Okta verification "
            "in the visible Salesforce tab, then press Begin again."
        )

    def open_exact_salesforce_case(
        self,
        page: Any,
        sid: int,
        bug_number: str,
    ) -> str:
        """
        After authentication, always return to the known Cases page and search
        the Buganizer ID. This is important because first-time Okta login often
        returns to All Cases without replaying the search that triggered login.
        """
        if not self.session_is_current(sid):
            return ""

        self.update_launch(sid, sf_phase="Opening Salesforce Cases...")

        page.goto(
            SALESFORCE_CASES_URL,
            wait_until="domcontentloaded",
            timeout=60_000,
        )

        # Give Lightning a chance to finish bootstrapping, then retry the search
        # because the global search control can appear a little after DOMContentLoaded.
        self.update_launch(
            sid,
            sf_phase=f"Searching Salesforce for bug {bug_number}...",
        )

        last_error: Exception | None = None
        for attempt in range(1, 5):
            if not self.session_is_current(sid):
                return ""

            try:
                _search_salesforce_case(page, bug_number)
                last_error = None
                break
            except Exception as error:
                last_error = error
                if attempt == 4:
                    break
                page.wait_for_timeout(1200)

        if last_error is not None:
            raise PaperworkError(
                f"Salesforce is authenticated, but the Case for bug "
                f"{bug_number} could not be opened: {last_error}"
            )

        # Search helper clicks the result. Confirm that we really landed on a
        # Salesforce Case before enabling Claim/Reassign.
        deadline = time.monotonic() + 15.0
        while time.monotonic() < deadline:
            if not self.session_is_current(sid):
                return ""

            current = clean(page.url)
            if "/lightning/r/Case/" in current:
                try:
                    _assert_salesforce_case_matches_bug(page, bug_number)
                except PaperworkError:
                    page.wait_for_timeout(120)
                    continue
                self.update_launch(
                    sid,
                    sf_phase="Exact Salesforce ticket opened",
                )
                return current

            page.wait_for_timeout(250)

        raise PaperworkError(
            f"Salesforce search ran for bug {bug_number}, but the browser did "
            "not reach an exact Case page. Do not Claim/Reassign yet."
        )

    def tile_ticket_window(self, page: Any, sid: int) -> None:
        """
        Put the Playwright-managed Chrome window on the RIGHT half of the same
        display where the user clicked Begin.

        Uses Chromium DevTools Protocol when available. This is best-effort:
        paperwork remains functional if a platform/window manager refuses bounds.
        """
        state = self.snapshot()
        if sid != state["session_id"]:
            return

        screen_width = int(state.get("screen_width") or 0)
        screen_height = int(state.get("screen_height") or 0)
        if screen_width < 600 or screen_height < 400:
            return

        left = int(state.get("screen_left") or 0)
        top = int(state.get("screen_top") or 0)

        split_x = int(state.get("split_x") or 0)
        if split_x <= 0 or split_x >= screen_width:
            split_x = screen_width // 2

        right_width = max(420, screen_width - split_x)
        right_left = left + split_x

        try:
            assert self.browser is not None
            cdp = self.browser.context.new_cdp_session(page)
            window_info = cdp.send("Browser.getWindowForTarget")
            window_id = window_info.get("windowId")
            if not window_id:
                return

            # Some Chromium builds will not apply bounds while maximized.
            try:
                cdp.send(
                    "Browser.setWindowBounds",
                    {
                        "windowId": window_id,
                        "bounds": {"windowState": "normal"},
                    },
                )
            except Exception:
                pass

            requested_bounds = {
                "left": right_left,
                "top": top,
                "width": right_width,
                "height": screen_height,
                "windowState": "normal",
            }

            cdp.send(
                "Browser.setWindowBounds",
                {
                    "windowId": window_id,
                    "bounds": requested_bounds,
                },
            )

            # macOS/Chrome can accept the first move before the previous
            # maximized/full-size state has completely settled. Reapply once
            # after a short delay so both position AND width/height stick.
            try:
                page.wait_for_timeout(180)
                current = cdp.send(
                    "Browser.getWindowBounds",
                    {"windowId": window_id},
                ).get("bounds", {})
                width_off = abs(int(current.get("width", right_width)) - right_width)
                height_off = abs(int(current.get("height", screen_height)) - screen_height)
                left_off = abs(int(current.get("left", right_left)) - right_left)

                if width_off > 24 or height_off > 40 or left_off > 24:
                    cdp.send(
                        "Browser.setWindowBounds",
                        {
                            "windowId": window_id,
                            "bounds": requested_bounds,
                        },
                    )
            except Exception:
                # Bounds verification is best effort; navigation still works.
                pass
        except Exception as error:
            # Window tiling is UI polish, not a reason to fail paperwork.
            print(f"Could not tile ticket window: {error}")

    def activate_ticket_tabs(self) -> None:
        """Keep Buganizer and Salesforce available as two tabs in one window."""
        try:
            if self.usable(self.bug_page):
                self.bug_page.bring_to_front()
        except Exception:
            pass

    def prepare_records(
        self,
        sid: int,
        bug_number: str,
        robot_id: str,
        bug_url: str,
        sf_url: str = "",
    ) -> None:
        """
        Open/reuse Buganizer and Salesforce pages for one workspace.

        IMPORTANT: this method must run only on BrowserWorker's Playwright thread.
        """
        if not self.session_is_current(sid):
            return

        try:
            self.ensure_browser()
            assert self.browser is not None

            if self.usable(self.sf_page):
                self.set_managed_window_state(self.sf_page, "normal")

            # BUGANIZER
            if not self.usable(self.bug_page):
                self.bug_page = self.new_page()

            try:
                self.bug_page.goto(
                    bug_url,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
            except Exception:
                # If the entire browser died between the liveness test and goto,
                # recreate the persistent context once and retry cleanly.
                self.close_browser()
                self.ensure_browser()
                self.bug_page = self.new_page()
                self.bug_page.goto(
                    bug_url,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )

            self.wait_for_buganizer_authentication(self.bug_page, sid)

            if not self.session_is_current(sid):
                return

            # Authentication can redirect away from the requested issue. Re-open
            # the exact bug after sign-in so first use and expired sessions are safe.
            if bug_number not in clean(self.bug_page.url):
                self.bug_page.goto(
                    bug_url,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )

            self.update_launch(sid, bug_opened=True)

            # The Playwright Chrome window is separate from the user's map Chrome.
            # Move it to the right half of the active display.
            self.tile_ticket_window(self.bug_page, sid)

            if not self.session_is_current(sid):
                return

            # SALESFORCE
            if not self.usable(self.sf_page):
                self.sf_page = self.new_page()

            self.update_launch(
                sid,
                sf_phase="Opening Salesforce...",
            )

            # If the master sheet already supplied an exact Salesforce URL, use
            # it. Otherwise start from Cases. On first use this may redirect to
            # Okta; we then wait for the technician to finish MFA manually.
            self.sf_page.goto(
                sf_url or SALESFORCE_CASES_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

            self.wait_for_salesforce_authentication(self.sf_page, sid)

            if not self.session_is_current(sid):
                return

            self.update_startup(
                phase="Salesforce authenticated. Companion ready.",
                ready=True,
                error="",
            )

            exact_sf_url = ""
            if sf_url:
                # Authentication may have interrupted the original direct URL,
                # so explicitly navigate to the exact Case again after SSO.
                self.update_launch(
                    sid,
                    sf_phase="Opening exact Salesforce ticket...",
                )
                self.sf_page.goto(
                    sf_url,
                    wait_until="domcontentloaded",
                    timeout=60_000,
                )
                current = clean(self.sf_page.url)
                if "/lightning/r/Case/" not in current:
                    raise PaperworkError(
                        "The saved Salesforce link did not open an exact Case."
                    )
                exact_sf_url = current
                self.update_launch(
                    sid,
                    sf_phase="Exact Salesforce ticket opened",
                )
            elif bug_number:
                # IMPORTANT: first-time Okta login commonly returns to All Cases.
                # Always perform the bug-number search *after* authentication.
                exact_sf_url = self.open_exact_salesforce_case(
                    self.sf_page,
                    sid,
                    bug_number,
                )

            if not exact_sf_url:
                raise PaperworkError(
                    "Could not determine the exact Salesforce Case for this bug."
                )

            self.update_launch(
                sid,
                sf_opened=True,
                sf_url=exact_sf_url,
            )

            try:
                self.trim_salesforce_workspace_tabs(keep=5)
            except Exception:
                pass

            # Keep Buganizer visible by default. Salesforce remains next to it as
            # a normal tab and can be clicked by the technician for reference.
            self.activate_ticket_tabs()
            self.update_launch(sid, opening=False)

        except Exception as error:
            # Never kill the localhost companion because one launch failed.
            print(f"Could not prepare paperwork records: {error}")
            self.update_launch(
                sid,
                opening=False,
                error=str(error),
            )

    def execute_claim(self) -> str:
        """
        Run the coworker's proven Claim operations.

        This is called only from BrowserWorker, so every Playwright operation
        remains on the same thread that created the browser.
        """
        snap = self.snapshot()
        if (
            not snap["bug_number"]
            or self.bug_page is None
            or self.sf_page is None
            or not self.usable(self.bug_page)
            or not self.usable(self.sf_page)
        ):
            raise PaperworkError(
                "Paperwork records are not open. Press Begin again first."
            )

        original_input = builtins.input

        def ui_input(prompt: str = "") -> str:
            lower = prompt.lower()
            if "reassign buganizer" in lower and "enter y" in lower:
                return "Y"
            if "which person is the current user" in lower:
                return "1"
            raise PaperworkError(
                "Claim requested an unexpected terminal prompt: " + prompt
            )

        try:
            builtins.input = ui_input
            reassign_buganizer_issue(self.bug_page, snap["bug_number"])
            owner = claim_salesforce_case(self.sf_page, snap["bug_number"])
        finally:
            builtins.input = original_input

        return owner

    def _ensure_exact_buganizer_issue(self, snap: dict[str, Any]) -> None:
        """Guarantee that Commit operates on this workspace's exact bug."""
        if (
            not snap["bug_number"]
            or self.bug_page is None
            or not self.usable(self.bug_page)
        ):
            raise PaperworkError(
                "Buganizer is not open. Press Begin again first."
            )

        current_bug_url = clean(self.bug_page.url)
        if snap["bug_number"] not in current_bug_url:
            exact_bug_url = allowed_bug_url(snap.get("bug_url", ""))
            if not exact_bug_url:
                raise PaperworkError(
                    "The exact Buganizer issue URL is no longer available. "
                    "Press Begin again before committing."
                )

            self.bug_page.goto(
                exact_bug_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )

        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            try:
                if snap["bug_number"] in clean(self.bug_page.url):
                    return
            except Exception:
                pass
            self.bug_page.wait_for_timeout(200)

        raise PaperworkError(
            "Buganizer did not return to the expected issue. "
            "No changes were committed."
        )

    def _commit_buganizer(
        self,
        *,
        details: str,
        assignee_email: str,
    ) -> dict[str, Any]:
        """Shared Commit implementation used by Claim and every Reassign target.

        Sequence:
          1. exact bug
          2. optional Details -> comment box -> Comment -> verify
          3. target assignee -> Save -> close edit panel -> verify

        If the target assignee is already correct, step 3 is skipped while
        optional Details are still posted.
        """
        snap = self.snapshot()
        self._ensure_exact_buganizer_issue(snap)

        details = clean(details)
        assignee_email = clean(assignee_email)

        comment_changed = post_buganizer_comment_direct(
            self.bug_page,
            snap["bug_number"],
            details,
        )

        assignee_changed = reassign_buganizer_issue_to(
            self.bug_page,
            snap["bug_number"],
            assignee_email,
        )

        return {
            "assignee_email": assignee_email,
            "details": details,
            "comment_changed": comment_changed,
            "assignee_changed": assignee_changed,
        }

    def execute_claim_buganizer(self, details: str) -> dict[str, Any]:
        """Claim = shared Buganizer Commit to robotics-support@google.com."""
        return self._commit_buganizer(
            details=details,
            assignee_email="robotics-support@google.com",
        )

    def execute_reassign(
        self,
        team: str,
        assignee_email: str,
        details: str,
    ) -> dict[str, Any]:
        """Reassign = same Commit behavior as Claim, with a different target."""
        team = clean(team)
        assignee_email = clean(assignee_email)

        if team != "Other":
            target = REASSIGN_TARGETS.get(team)
            if not target:
                raise PaperworkError("Unsupported reassignment team.")
            assignee_email = target
        elif assignee_email not in OTHER_ASSIGNEES:
            raise PaperworkError(
                "Choose a valid assignee from the Other dropdown."
            )

        result = self._commit_buganizer(
            details=details,
            assignee_email=assignee_email,
        )
        result["team"] = team
        return result



    def _ensure_salesforce_case_for_commit(
        self,
        snap: dict[str, Any],
    ) -> None:
        """Fail fast unless the active visible Salesforce Case is this bug.

        Do not navigate or search here. The technician may keep older Salesforce
        workspace tabs for reference; Complete must never silently switch Cases.
        """
        if self.sf_page is None or not self.usable(self.sf_page):
            raise PaperworkError(
                "Salesforce is not open. Press Begin again before continuing."
            )
        bug_number = clean(snap.get("bug_number"))
        _assert_salesforce_case_matches_bug(self.sf_page, bug_number)

    def trim_salesforce_workspace_tabs(self, keep: int = 5) -> None:
        """Best-effort cap for Salesforce Service Console Case workspace tabs."""
        if self.sf_page is None or not self.usable(self.sf_page):
            return
        keep = max(1, int(keep))
        # Workspace tabs have close buttons in the console tab strip. Work only
        # with visible buttons and never close the selected/active tab.
        for _ in range(8):
            buttons = self.sf_page.locator(
                'button[title^="Close "]:visible, button[aria-label^="Close "]:visible'
            )
            visible = []
            for i in range(buttons.count()):
                b = buttons.nth(i)
                try:
                    if b.is_visible() and b.is_enabled():
                        visible.append(b)
                except Exception:
                    pass
            # This list can include non-Case console tabs; only trim when clearly
            # above the requested cap and close from the oldest/left side.
            if len(visible) <= keep:
                return
            closed = False
            for b in visible:
                try:
                    parent = b.locator('xpath=ancestor::*[@role="tab" or contains(@class,"tabItem")][1]')
                    selected = parent.get_attribute("aria-selected") if parent.count() else None
                    if selected == "true":
                        continue
                    b.click(timeout=800)
                    self.sf_page.wait_for_timeout(80)
                    closed = True
                    break
                except Exception:
                    continue
            if not closed:
                return


    def execute_salesforce_reassign(
        self,
        fields: dict[str, str],
    ) -> dict[str, Any]:
        """Complete the Salesforce half of Reassign after manual verification.

        The Paperwork UI requires the technician to confirm that Salesforce has
        received the Buganizer update before this method performs any mutation.
        """
        snap = self.snapshot()
        if not snap["team"] or snap["action"] != "salesforce_reassign_form":
            raise PaperworkError(
                "Salesforce closeout is not ready. Complete Buganizer first."
            )

        self._ensure_salesforce_case_for_commit(snap)
        assert self.sf_page is not None

        self.set_managed_window_state(self.sf_page, "normal")
        try:
            self.sf_page.bring_to_front()
        except Exception:
            pass

        bug_number = clean(snap["bug_number"])
        details = clean(snap.get("details"))

        self.update_launch(
            int(snap["session_id"]),
            sf_phase="Checking Salesforce owner...",
        )

        # 1. Details -> current owner -> Change Owner only if necessary.
        owner = claim_salesforce_case(self.sf_page, bug_number)
        self.update_salesforce_progress(
            owner=owner,
            owner_claimed=True,
        )

        # 2. Feed -> same Details, skip exact duplicate.
        if details:
            self.update_launch(
                int(snap["session_id"]),
                sf_phase="Checking Salesforce Feed...",
            )
            post_salesforce_feed_comment(
                self.sf_page,
                bug_number,
                details,
            )
        self.update_salesforce_progress(description_saved=True)

        # 3. Details -> only mismatched route fields -> save + verify.
        self.update_launch(
            int(snap["session_id"]),
            sf_phase="Checking Salesforce routing fields...",
        )
        set_salesforce_case_fields(
            self.sf_page,
            bug_number,
            fields,
        )
        self.update_salesforce_progress(fields_saved=True)

        # 4. Details -> Closed only if needed -> save + verify.
        self.update_launch(
            int(snap["session_id"]),
            sf_phase="Checking Salesforce Case status...",
        )
        status_changed = close_salesforce_case(
            self.sf_page,
            bug_number,
        )
        self.update_salesforce_progress(closed=True)

        self.update_launch(
            int(snap["session_id"]),
            sf_phase="Salesforce paperwork complete",
        )

        return {
            "owner": owner,
            "details_saved": bool(details),
            "fields": dict(fields),
            "closed": True,
            "status_changed": status_changed,
        }


    def execute_salesforce_claim(
        self,
        fields: dict[str, str],
    ) -> dict[str, Any]:
        """Complete the Salesforce half of Claim after manual verification.

        The Paperwork UI requires the technician to confirm that Salesforce has
        received the Buganizer update before this method performs any mutation.
        """
        snap = self.snapshot()
        if snap["action"] != "salesforce_claim_form":
            raise PaperworkError(
                "Salesforce Claim closeout is not ready. Complete Buganizer first."
            )

        self._ensure_salesforce_case_for_commit(snap)
        assert self.sf_page is not None

        self.set_managed_window_state(self.sf_page, "normal")
        try:
            self.sf_page.bring_to_front()
        except Exception:
            pass

        bug_number = clean(snap["bug_number"])
        details = clean(snap.get("details"))

        self.update_launch(
            int(snap["session_id"]),
            sf_phase="Checking Salesforce owner...",
        )
        owner = claim_salesforce_case(self.sf_page, bug_number)
        self.update_salesforce_progress(
            owner=owner,
            owner_claimed=True,
        )

        if details:
            self.update_launch(
                int(snap["session_id"]),
                sf_phase="Checking Salesforce Feed...",
            )
            post_salesforce_feed_comment(
                self.sf_page,
                bug_number,
                details,
            )
        self.update_salesforce_progress(description_saved=True)

        self.update_launch(
            int(snap["session_id"]),
            sf_phase="Checking Salesforce routing fields...",
        )
        set_salesforce_case_fields(
            self.sf_page,
            bug_number,
            fields,
        )
        self.update_salesforce_progress(fields_saved=True)

        self.update_launch(
            int(snap["session_id"]),
            sf_phase="Checking Salesforce Case status...",
        )
        status_changed = close_salesforce_case(
            self.sf_page,
            bug_number,
        )
        self.update_salesforce_progress(closed=True)

        self.update_launch(
            int(snap["session_id"]),
            sf_phase="Salesforce paperwork complete",
        )

        return {
            "owner": owner,
            "details_saved": bool(details),
            "fields": dict(fields),
            "closed": True,
            "status_changed": status_changed,
        }


WORKSPACE = Workspace()


class BrowserWorker:
    """
    One permanent worker thread owns Playwright.

    Playwright's synchronous API is thread-affine. A ThreadingHTTPServer is
    useful for keeping /health responsive, but HTTP request threads must NOT
    directly manipulate Playwright pages. Everything browser-related is routed
    through this single queue instead.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[
            tuple[Callable[..., Any] | None, tuple[Any, ...], dict[str, Any], Future[Any]]
        ] = queue.Queue()
        self._thread = threading.Thread(
            target=self._run,
            name="MTV-Paperwork-Browser",
            daemon=True,
        )
        self._thread.start()

    def _run(self) -> None:
        while True:
            func, args, kwargs, future = self._queue.get()
            if func is None:
                try:
                    WORKSPACE.close_browser()
                    future.set_result(None)
                except Exception as error:
                    future.set_exception(error)
                return

            try:
                result = func(*args, **kwargs)
            except BaseException as error:
                future.set_exception(error)
            else:
                future.set_result(result)

    def submit(
        self,
        func: Callable[..., Any],
        *args: Any,
        wait: bool = False,
        timeout: float | None = None,
        **kwargs: Any,
    ) -> Any:
        future: Future[Any] = Future()
        self._queue.put((func, args, kwargs, future))
        if not wait:
            return future
        return future.result(timeout=timeout)

    def stop(self) -> None:
        future: Future[Any] = Future()
        self._queue.put((None, (), {}, future))
        try:
            future.result(timeout=8)
        except Exception:
            pass


BROWSER_WORKER = BrowserWorker()


def request_shutdown() -> None:
    """Stop the full Companion after giving open popup UIs time to self-close."""
    SHUTDOWN_REQUESTED.set()
    WORKSPACE.invalidate_session()

    # The Begin popup can live in a different Chrome profile from Playwright, so
    # browser storage/BroadcastChannel are not reliable across the two windows.
    # Keep localhost alive very briefly so the popup's lightweight health poll
    # can observe shutting_down=True and call window.close().
    time.sleep(0.45)

    server = SERVER
    if server is not None:
        try:
            server.shutdown()
        except Exception as error:
            print(f"Could not stop companion server cleanly: {error}")


def begin_workspace(
    robot: str,
    bug: str,
    bug_url: str,
    sf_url: str = "",
    geometry: dict[str, int] | None = None,
    location_label: str = "Unknown",
) -> int:
    """
    Start a new workspace without blocking the localhost HTTP server.

    The SHARED MAP owns the companion UI window and places it on the left half.
    This companion owns only the Playwright ticket window on the right half.
    """
    sid = WORKSPACE.new_session(
        bug,
        robot,
        bug_url,
        location_label,
        geometry,
    )

    BROWSER_WORKER.submit(
        WORKSPACE.prepare_records,
        sid,
        bug,
        robot,
        bug_url,
        sf_url,
        wait=False,
    )
    return sid


def reset_workspace() -> None:
    """
    Reset the current Paperwork UI without stopping the companion.

    We intentionally keep the persistent browser context alive. Existing ticket
    tabs may be reused on the next Begin, and manually closed tabs are recreated.
    """
    WORKSPACE.invalidate_session()


def render_startup_page() -> str:
    state = WORKSPACE.snapshot()
    ready = bool(state.get("startup_ready"))
    bug_ready = bool(state.get("startup_bug_authenticated"))
    sf_ready = bool(state.get("startup_sf_authenticated"))
    error = clean(state.get("startup_error"))

    if ready:
        title = "Companion ready"
        subtitle = ""
        badge = "READY"
        badge_class = "ready"
    else:
        title = "Sign-in required"
        badge = "SETUP"
        badge_class = "setup"

        if not bug_ready and not sf_ready:
            subtitle = "Sign in to Buganizer and Salesforce."
        elif not bug_ready:
            subtitle = "Sign in to Buganizer."
        elif not sf_ready:
            subtitle = "Sign in to Salesforce."
        else:
            subtitle = "Finishing setup…"

    refresh_js = "" if ready else "setTimeout(()=>location.reload(),700);"

    def service(label: str, connected: bool) -> str:
        cls = "good" if connected else "waiting"
        status = "Connected" if connected else "Sign in"
        return (
            f'<div class="service {cls}">'
            f'<i></i><div class="service-copy">'
            f'<strong>{html.escape(label)}</strong>'
            f'<span>{status}</span>'
            f'</div></div>'
        )

    subtitle_markup = (
        f'<p class="sub">{html.escape(subtitle)}</p>'
        if subtitle
        else ""
    )

    error_markup = (
        f'<div class="notice error">{html.escape(error)}</div>'
        if error and not ready
        else ""
    )

    phase = clean(state.get("startup_phase"))
    phase_markup = ""
    if not ready and phase:
        normalized = phase.lower()
        redundant = any(
            phrase in normalized
            for phrase in (
                "sign-in required",
                "sign in required",
                "checking buganizer and salesforce",
            )
        )
        if not redundant:
            phase_markup = f'<div class="notice">{html.escape(phase)}</div>'

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MTV Paperwork Companion</title>
<style>
*{{box-sizing:border-box}}
body{{
  margin:0;min-height:100vh;display:grid;place-items:center;padding:22px;
  background:#f5f5f7;color:#1d1d1f;
  font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}}
.card{{
  width:min(430px,100%);background:rgba(255,255,255,.95);
  border:1px solid rgba(0,0,0,.09);border-radius:20px;padding:23px;
  box-shadow:0 12px 36px rgba(0,0,0,.065);
}}
.top{{display:flex;align-items:center;justify-content:space-between;gap:12px}}
.brand{{font-size:13px;font-weight:800;letter-spacing:.10em}}
.badge{{
  padding:5px 8px;border-radius:999px;font-size:9px;font-weight:800;
  text-transform:uppercase;white-space:nowrap;
}}
.badge.ready{{color:#067647;background:#ecfdf3;border:1px solid #abefc6}}
.badge.setup{{color:#b54708;background:#fffaeb;border:1px solid #fedf89}}
h1{{margin:18px 0 0;font-size:21px;line-height:1.15;letter-spacing:-.025em}}
.sub{{margin:7px 0 0;color:#6e6e73;font-size:12px;line-height:1.45}}
.services{{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-top:18px}}
.service{{
  display:flex;align-items:center;gap:9px;min-height:58px;padding:11px 12px;
  border:1px solid rgba(0,0,0,.07);border-radius:12px;background:#f8f8fa;
}}
.service i{{flex:0 0 auto;width:7px;height:7px;border-radius:50%;background:#e0a300}}
.service.good i{{background:#16a34a}}
.service-copy{{min-width:0}}
.service strong{{display:block;font-size:11px;font-weight:700;line-height:1.2}}
.service span{{display:block;margin-top:2px;color:#86868b;font-size:9px;line-height:1.2}}
.notice{{
  margin-top:10px;padding:9px 10px;border-radius:10px;background:#f8f8fa;
  color:#6e6e73;border:1px solid rgba(0,0,0,.06);font-size:10px;line-height:1.4;
}}
.notice.error{{background:#fff1f3;border-color:#fda4af;color:#be123c}}
.divider{{height:1px;background:rgba(0,0,0,.075);margin:19px 0 17px}}
.session-row{{display:flex;align-items:center;justify-content:space-between;gap:16px}}
.session-copy strong{{display:block;font-size:12px}}
.session-copy span{{display:block;margin-top:2px;color:#86868b;font-size:9px;line-height:1.35}}
.end{{
  flex:none;border:1px solid #d92d20;background:#fff;color:#b42318;
  border-radius:10px;padding:9px 12px;font:inherit;font-size:11px;font-weight:750;
  cursor:pointer;white-space:nowrap;
}}
.end:hover{{background:#fef3f2}}
.end:disabled{{opacity:.55;cursor:wait}}
</style>
</head>
<body>
<div class="card">
  <div class="top">
    <div class="brand">MTV COMPANION</div>
    <div class="badge {badge_class}">{badge}</div>
  </div>

  <h1>{html.escape(title)}</h1>
  {subtitle_markup}

  <div class="services">
    {service("Buganizer", bug_ready)}
    {service("Salesforce", sf_ready)}
  </div>

  {phase_markup}
  {error_markup}

  <div class="divider"></div>

  <div class="session-row">
    <div class="session-copy">
      <strong>Companion session</strong>
      <span>Stops Paperwork and closes the managed browser.</span>
    </div>
    <button class="end" id="endSession" onclick="endSession()">End session</button>
  </div>
</div>

<script>
async function endSession(){{
  const button=document.getElementById('endSession');
  if(button){{button.disabled=true;button.textContent='Ending…';}}

  document.body.innerHTML=
    '<div style="font-family:-apple-system,BlinkMacSystemFont,system-ui;padding:40px;text-align:center;color:#6e6e73">' +
    '<h2 style="color:#1d1d1f">Ending Companion…</h2>' +
    '<p>Closing Paperwork and the managed browser.</p></div>';

  try{{
    await fetch('/api/shutdown',{{method:'POST'}});
  }}catch(_e){{}}
}}
{refresh_js}
</script>
</body>
</html>"""



def render_salesforce_reassign_form(state: dict[str, Any]) -> str:
    """Render the Salesforce route picker after Buganizer has committed."""
    team = clean(state.get("team"))
    try:
        spec = get_reassign_form_spec(team)
    except SalesforceRouteError as error:
        return (
            '<section class="card"><div class="eyebrow">Salesforce</div>'
            '<h2>Route unavailable</h2>'
            f'<p class="muted">{html.escape(str(error))}</p>'
            '<button class="secondary full" onclick="exitWorkspace()">Exit</button>'
            '</section>'
        )

    selectors: list[str] = []
    for selector in spec.get("selectors", []):
        key = clean(selector.get("key"))
        label = clean(selector.get("label"))
        options = [clean(value) for value in selector.get("options", []) if clean(value)]
        when = selector.get("when") or {}
        when_key = clean(when.get("key"))
        when_value = clean(when.get("value"))

        attrs = ' class="salesforce-field"'
        if when_key and when_value:
            attrs += (
                f' data-when-key="{html.escape(when_key, quote=True)}"'
                f' data-when-value="{html.escape(when_value, quote=True)}"'
                ' hidden'
            )

        option_html = ['<option value="">Choose…</option>']
        option_html.extend(
            f'<option value="{html.escape(value, quote=True)}">'
            f'{html.escape(value)}</option>'
            for value in options
        )

        selectors.append(
            '<div' + attrs + '>'
            f'<label class="form-label salesforce-label" for="sf_{html.escape(key, quote=True)}">{html.escape(label)}</label>'
            '<div class="select-wrap">'
            f'<select class="form-select" id="sf_{html.escape(key, quote=True)}" '
            f'data-salesforce-select="{html.escape(key, quote=True)}" '
            'onchange="updateSalesforceRouteVisibility()" required>'
            + ''.join(option_html) +
            '</select></div></div>'
        )

    selector_markup = "".join(selectors)
    if not selector_markup:
        selector_markup = (
            '<div class="route-summary">'
            '<span>Salesforce route</span>'
            '<strong>Robot Start-Up · Software · Dev PC · Google Migrated</strong>'
            '</div>'
        )

    return f"""
    <section class="card">
      <div class="eyebrow">Salesforce</div>
      <h2>{html.escape(team)}</h2>
      <p class="muted salesforce-help">Choose the matching route. The remaining Salesforce fields are filled automatically.</p>

      {selector_markup}

      <div class="two form-actions">
        <button class="secondary" onclick="exitWorkspace()">Exit</button>
        <button class="primary" id="salesforceCommit" onclick="submitSalesforceReassign()">Complete</button>
      </div>
    </section>"""




def render_salesforce_claim_form(state: dict[str, Any]) -> str:
    """Render the Salesforce Claim taxonomy after Buganizer Claim commits."""
    try:
        spec = get_claim_form_spec()
    except SalesforceRouteError as error:
        return (
            '<section class="card"><div class="eyebrow">Salesforce</div>'
            '<h2>Claim route unavailable</h2>'
            f'<p class="muted">{html.escape(str(error))}</p>'
            '<button class="secondary full" onclick="exitWorkspace()">Exit</button>'
            '</section>'
        )

    selectors: list[str] = []
    for index, selector in enumerate(spec.get("selectors", [])):
        key = clean(selector.get("key"))
        label = clean(selector.get("label"))
        options = [
            clean(value)
            for value in selector.get("options", [])
            if clean(value)
        ]
        when = selector.get("when") or {}
        when_key = clean(when.get("key"))
        when_value = clean(when.get("value"))

        attrs = ' class="salesforce-field"'
        if when_key and when_value:
            attrs += (
                f' data-when-key="{html.escape(when_key, quote=True)}"'
                f' data-when-value="{html.escape(when_value, quote=True)}"'
                ' hidden'
            )

        field_id = f"sf_claim_{key}_{index}"
        option_html = ['<option value="">Choose…</option>']
        option_html.extend(
            f'<option value="{html.escape(value, quote=True)}">'
            f'{html.escape(value)}</option>'
            for value in options
        )

        selectors.append(
            '<div' + attrs + '>'
            f'<label class="form-label salesforce-label" '
            f'for="{html.escape(field_id, quote=True)}">'
            f'{html.escape(label)}</label>'
            '<div class="select-wrap">'
            f'<select class="form-select" '
            f'id="{html.escape(field_id, quote=True)}" '
            f'data-salesforce-select="{html.escape(key, quote=True)}" '
            'onchange="updateSalesforceRouteVisibility()" required>'
            + ''.join(option_html) +
            '</select></div></div>'
        )

    return f"""
    <section class="card">
      <div class="eyebrow">Salesforce</div>
      <h2>Complete Claim</h2>
      {''.join(selectors)}

      <div class="two form-actions">
        <button class="secondary" onclick="exitWorkspace()">Exit</button>
        <button class="primary" id="salesforceClaimCommit"
          onclick="submitSalesforceClaim()">Complete</button>
      </div>
    </section>"""



def render_page(message: str = "") -> str:
    state = WORKSPACE.snapshot()

    bug = html.escape(state["bug_number"] or "—")
    robot = html.escape(state["robot_id"] or "—")
    sf_label = (
        f"Assigned to {state['sf_owner']}"
        if state.get("sf_owner")
        else "Ticket found"
        if state["sf_url"]
        else "Finding ticket"
        if state["opening"]
        else "Not connected"
    )

    has_error = bool(state.get("launch_error"))

    if state["bug_opened"]:
        bug_status_class = "good"
        bug_status_text = "Ready"
    elif state["opening"]:
        bug_status_class = "loading"
        bug_status_text = "Loading"
    elif has_error:
        bug_status_class = "error"
        bug_status_text = "Couldn't connect"
    else:
        bug_status_class = "idle"
        bug_status_text = "Idle"

    if state["sf_opened"] and state["sf_url"]:
        sf_status_class = "good"
        sf_status_text = "Ready"
    elif state["opening"]:
        sf_status_class = "loading"
        sf_status_text = "Loading"
    elif has_error:
        sf_status_class = "error"
        sf_status_text = "Couldn't connect"
    else:
        sf_status_class = "idle"
        sf_status_text = "Idle"

    if state["action"] == "claim":
        body = """
        <section class="card">
          <div class="eyebrow">Selected</div>
          <h2>Claim</h2>
          <p class="muted">The Claim workflow has completed for Buganizer and Salesforce.</p>
          <button class="primary full" onclick="exitWorkspace()">Exit</button>
        </section>"""
    elif state["action"] == "claim_form":
        body = """
        <section class="card">
          <div class="eyebrow">Claim</div>
          <h2>Assign to Yourself</h2>

          <div class="assignee-summary">
            <span>Assign to</span>
            <strong>robotics-support@google.com</strong>
          </div>

          <label class="form-label details-label" for="claimDetails">Details <span>(optional)</span></label>
          <textarea
            class="form-textarea"
            id="claimDetails"
            placeholder="Add any details you would like included…"
          ></textarea>

          <div class="two form-actions">
            <button class="secondary" onclick="resetChoice()">Back</button>
            <button class="primary" id="claimCommit" onclick="submitClaim()">Commit</button>
          </div>
        </section>"""
    elif state["action"] == "salesforce_claim_wait":
        body = f"""
        <section class="card">
          <div class="eyebrow">Claim</div>
          <h2>Waiting for Salesforce</h2>
          <p class="muted">
            Buganizer is complete. Waiting for the backend update to change
            Salesforce to <strong>Customer Responded</strong>.
          </p>
          <p class="muted">{html.escape(state.get("sf_phase") or "")}</p>
          <div class="two form-actions">
            <button class="secondary" onclick="exitWorkspace()">Exit</button>
            <button class="primary" id="claimSyncRetry"
              onclick="retryClaimSync()">Check again</button>
          </div>
        </section>"""
    elif state["action"] == "salesforce_claim_form":
        body = render_salesforce_claim_form(state)
    elif state["action"] == "claim_done":
        body = f"""
        <section class="card">
          <div class="eyebrow">Completed</div>
          <h2>Claimed</h2>
          <div class="completion-summary">
            <strong>robotics-support@google.com</strong>
            <span>Buganizer</span>
            <span>Salesforce: {html.escape(state.get("sf_owner") or "Current user")} · Closed</span>
          </div>
          <p class="muted">{html.escape(state["result_message"] or "Buganizer and Salesforce claim complete.")}</p>
          <button class="primary full" onclick="exitWorkspace()">Exit</button>
        </section>"""
    elif state["action"] == "reassign_select":
        body = """
        <section class="card" id="teams">
          <div class="eyebrow">Reassign</div>
          <h2>Select a team</h2>
          <div class="team-list">
            <button class="team-chip team-mechatronics" onclick="team('Mechatronics')">Mechatronics</button>
            <button class="team-chip team-lab-build" onclick="team('Lab Build Team')">Lab Build Team</button>
            <button class="team-chip team-release" onclick="team('Release Team')">Release Team</button>
            <button class="team-chip team-research" onclick="team('Research Team')">Research Team</button>
            <button class="team-chip team-engineering" onclick="team('Engineering Team')">Engineering Team</button>
            <button class="team-chip team-other" onclick="team('Other')">Other</button>
          </div>
          <button class="back" onclick="resetChoice()">Back</button>
        </section>"""
    elif state["action"] == "reassign_form" and state["team"]:
        selected_team = html.escape(state["team"])
        mapped_email = html.escape(
            REASSIGN_TARGETS.get(state["team"], "")
        )
        other_email = (
            """
            <div class="assignee-summary other-assignee-summary">
              <span>Assign to</span>
              <div class="other-select-wrap">
                <select class="form-select other-assignee-select" id="assigneeEmail">
                  <option value="fedynchuk@google.com">fedynchuk@google.com</option>
                </select>
              </div>
            </div>
            """
            if state["team"] == "Other"
            else f"""
            <div class="assignee-summary">
              <span>Assign to</span>
              <strong>{mapped_email}</strong>
            </div>
            """
        )

        body = f"""
        <section class="card">
          <div class="eyebrow">Reassign</div>
          <h2>{selected_team}</h2>

          {other_email}

          <label class="form-label details-label" for="reassignDetails">Details <span>(optional)</span></label>
          <textarea
            class="form-textarea"
            id="reassignDetails"
            placeholder="Add any details you would like included…"
          ></textarea>

          <div class="two form-actions">
            <button class="secondary" onclick="backToReassign()">Back</button>
            <button class="primary" id="reassignContinue" data-team="{html.escape(state["team"], quote=True)}" onclick="submitReassign()">Commit</button>
          </div>
        </section>"""
    elif state["action"] == "salesforce_reassign_form" and state["team"]:
        body = render_salesforce_reassign_form(state)
    elif state["action"] == "reassign_done" and state["team"]:
        body = f"""
        <section class="card">
          <div class="eyebrow">Completed</div>
          <h2>Reassigned</h2>
          <div class="completion-summary">
            <strong>{html.escape(state["team"])}</strong>
            <span>Buganizer: {html.escape(state["assignee_email"])}</span>
            <span>Salesforce: {html.escape(state.get("sf_owner") or "Current user")} · Closed</span>
          </div>
          <p class="muted">{html.escape(state["result_message"] or "Buganizer and Salesforce paperwork complete.")}</p>
          <button class="primary full" onclick="exitWorkspace()">Exit</button>
        </section>"""
    else:
        disabled = " disabled" if state["opening"] else ""
        body = f"""
        <section class="card" id="actions">
          <div class="eyebrow">Task</div>
          <h2>What would you like to do?</h2>
          <div class="three">
            <button class="primary"{disabled} onclick="choose('claim_form')">Claim</button>
            <button{disabled} onclick="showTeams()">Reassign</button>
            <button onclick="exitWorkspace()">Exit</button>
          </div>
          {"<p class='muted center'>Preparing both records…</p>" if state["opening"] else ""}
        </section>
        <section class="card hidden" id="teams">
          <div class="eyebrow">Reassign</div>
          <h2>Select a team</h2>
          <div class="team-list">
            <button class="team-chip team-mechatronics" onclick="team('Mechatronics')">Mechatronics</button>
            <button class="team-chip team-lab-build" onclick="team('Lab Build Team')">Lab Build Team</button>
            <button class="team-chip team-release" onclick="team('Release Team')">Release Team</button>
            <button class="team-chip team-research" onclick="team('Research Team')">Research Team</button>
            <button class="team-chip team-engineering" onclick="team('Engineering Team')">Engineering Team</button>
            <button class="team-chip team-other" onclick="team('Other')">Other</button>
          </div>
          <button class="back" onclick="hideTeams()">Back</button>
        </section>"""

    messages: list[str] = []
    if message:
        messages.append(message)
    if state["launch_error"]:
        messages.append(
            "The companion is still running, but opening the records needs attention: "
            + state["launch_error"]
        )

    msg = "".join(
        f'<div class="message">{html.escape(item)}</div>' for item in messages
    )

    opening_js = "true" if state["opening"] else "false"
    sid = int(state["session_id"])

    return f"""<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MTV Paperwork</title>
<style>
*{{box-sizing:border-box}}
body{{margin:0;background:#f6f7f9;color:#101828;font-family:Inter,system-ui,-apple-system,"Segoe UI",sans-serif}}
.wrap{{max-width:440px;margin:auto;padding:18px}}
.top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:14px}}
.brand{{font-size:13px;font-weight:950;letter-spacing:.08em}}
.safe{{font-size:9px;font-weight:900;color:#667085;border:1px solid #d0d5dd;padding:4px 7px;border-radius:999px}}
.card{{background:#fff;border:1px solid #e4e7ec;border-radius:16px;padding:16px;margin-bottom:12px;box-shadow:0 4px 14px rgba(16,24,40,.05)}}
.eyebrow{{font-size:9px;font-weight:950;color:#667085;letter-spacing:.1em;text-transform:uppercase;margin-bottom:5px}}
h1{{font-size:21px;margin:0}}
h2{{font-size:16px;margin:0 0 12px}}
p{{font-size:12px;line-height:1.45;margin:8px 0 0}}
.records{{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:14px}}
.record{{padding:10px;border:1px solid #eaecf0;border-radius:11px}}
.record span{{display:block;font-size:9px;font-weight:850;color:#667085}}
.record strong{{display:block;font-size:12px;margin-top:3px}}
.statuses{{display:flex;gap:8px;margin-top:10px}}
.status{{flex:1;padding:8px;border-radius:10px;font-size:10px;font-weight:850;border:1px solid}}
.ok{{color:#15803d;background:#f0fdf4;border-color:#86efac}}
.warn{{color:#92400e;background:#fffbeb;border-color:#fde68a}}
.pending{{color:#344054;background:#f8fafc;border-color:#d0d5dd}}
button{{border:1px solid #d0d5dd;background:#fff;border-radius:11px;padding:11px 12px;font:inherit;font-size:12px;font-weight:850;cursor:pointer}}
button:hover:not(:disabled){{background:#f9fafb}}
button:disabled{{opacity:.48;cursor:wait}}
.primary{{background:#101828;color:#fff;border-color:#101828}}
.primary:hover:not(:disabled){{background:#1d2939}}
.secondary{{background:#fff}}
.full{{width:100%}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:9px}}
.three{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:9px}}
.team-list{{display:grid;gap:8px}}
.hidden{{display:none}}
.back{{margin-top:8px;border:0;padding-left:0;color:#667085}}
.muted{{color:#667085;font-size:10px}}
.center{{text-align:center}}
.team-selected{{font-size:15px;font-weight:950;margin-bottom:10px}}
.message{{padding:10px;margin-bottom:12px;border:1px solid #fed7aa;background:#fff7ed;color:#9a3412;border-radius:10px;font-size:11px}}
.footer{{text-align:center;color:#98a2b3;font-size:9px;padding:2px}}

/* Final responsive Paperwork UI */
:root{{
 --ui-bg:#f5f5f7;--ui-surface:rgba(255,255,255,.9);--ui-text:#1d1d1f;
 --ui-secondary:#6e6e73;--ui-tertiary:#86868b;--ui-line:rgba(0,0,0,.085);
 --ui-blue:#0071e3;
}}
body{{
 background:radial-gradient(circle at 50% -12%,rgba(255,255,255,.98),rgba(255,255,255,.15) 42%,transparent 62%),var(--ui-bg)!important;
 color:var(--ui-text)!important;
 font-family:-apple-system,BlinkMacSystemFont,"SF Pro Text","SF Pro Display","Helvetica Neue",Arial,sans-serif!important;
 -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility;
}}
.wrap{{max-width:650px!important;padding:34px 24px 28px!important}}
.top{{margin-bottom:22px!important;padding:0 2px!important}}
.brand{{color:#171719!important;font-size:14px!important;font-weight:700!important;letter-spacing:.115em!important}}
.safe{{
 min-height:28px;display:inline-flex;align-items:center;padding:0 11px!important;
 border:1px solid rgba(0,0,0,.11)!important;border-radius:999px!important;
 background:rgba(255,255,255,.62)!important;color:var(--ui-secondary)!important;
 font-size:11px!important;font-weight:650!important;letter-spacing:.01em!important
}}
.card{{
 padding:27px!important;margin-bottom:17px!important;border:1px solid var(--ui-line)!important;
 border-radius:22px!important;background:var(--ui-surface)!important;
 box-shadow:0 12px 36px rgba(0,0,0,.055),0 1px 2px rgba(0,0,0,.03)!important;
 backdrop-filter:saturate(180%) blur(22px)
}}
.eyebrow{{
 margin-bottom:7px!important;color:var(--ui-tertiary)!important;font-size:10px!important;
 font-weight:650!important;letter-spacing:.1em!important
}}
h1{{color:var(--ui-text)!important;font-size:34px!important;line-height:1.08!important;font-weight:700!important;letter-spacing:-.035em!important}}
h2{{color:var(--ui-text)!important;font-size:23px!important;line-height:1.15!important;font-weight:650!important;letter-spacing:-.025em!important}}
.records{{gap:12px!important;margin-top:25px!important}}
.record{{
 padding:15px 16px!important;border:1px solid rgba(0,0,0,.075)!important;
 border-radius:16px!important;background:rgba(248,248,250,.82)!important
}}
.record span{{color:var(--ui-tertiary)!important;font-size:10px!important;font-weight:650!important;letter-spacing:.065em!important}}
.record strong{{margin-top:4px!important;color:var(--ui-text)!important;font-size:16px!important;line-height:1.25!important;font-weight:650!important}}
.statuses{{gap:12px!important;margin-top:12px!important}}
.status{{min-height:42px!important;padding:8px 13px!important;border-radius:14px!important;font-size:12px!important;font-weight:600!important}}
.status.ok{{color:#167a36!important;background:#f0faf2!important;border-color:#b7e5c1!important}}
.status.warn{{color:#946200!important;background:#fff9e8!important;border-color:#efd789!important}}
button{{
 min-height:50px;border-radius:14px!important;font-size:15px!important;font-weight:600!important;
 letter-spacing:-.01em;transition:transform .12s ease,background .12s ease,border-color .12s ease!important
}}
button:active{{transform:scale(.985)}}
button.primary{{background:var(--ui-blue)!important;border-color:var(--ui-blue)!important;color:white!important;box-shadow:0 2px 7px rgba(0,113,227,.17)}}
button.primary:hover{{background:#0077ed!important}}
.two,.three{{gap:10px!important}}.three{{grid-template-columns:1.15fr 1fr .82fr!important}}
.team-list{{
 overflow:hidden;margin-top:17px;gap:0!important;border:1px solid var(--ui-line);
 border-radius:16px;background:rgba(248,248,250,.75)
}}
.team-list button{{
 min-height:50px;border:0!important;border-bottom:1px solid var(--ui-line)!important;
 border-radius:0!important;background:transparent!important;color:var(--ui-text)!important;text-align:left
}}
.team-list button:last-child{{border-bottom:0!important}}.team-list button:hover{{background:rgba(0,0,0,.025)!important}}
.back{{margin-top:13px!important;color:var(--ui-blue)!important;font-weight:550!important}}
.message{{margin-bottom:14px!important;border-radius:14px!important;font-size:12px!important}}
.footer{{padding-top:2px!important;color:#a1a1a6!important;font-size:10px!important}}
@media(max-width:560px){{
 .wrap{{padding:22px 14px 20px!important}}.card{{padding:21px!important;border-radius:19px!important}}
 h1{{font-size:29px!important}}h2{{font-size:21px!important}}
 .records,.statuses,.three,.two{{grid-template-columns:1fr!important}}button{{min-height:48px}}
}}
@media(prefers-reduced-motion:reduce){{*{{transition:none!important}}}}

/* Final clean UI refinements */
:root{{
 --ui-accent:#3a3a3c;
 --ui-accent-hover:#2c2c2e;
 --ui-good:#34a853;
 --ui-loading:#d39a19;
 --ui-error:#d84a45;
 --ui-idle:#9a9aa0;
}}
.safe{{
 max-width:48%;
 overflow:hidden;
 text-overflow:ellipsis;
 white-space:nowrap;
}}
.records{{align-items:stretch}}
.record{{min-width:0}}
.record-head{{
 display:flex;
 align-items:center;
 justify-content:space-between;
 gap:10px;
 min-width:0;
}}
.record-head>span:first-child{{
 display:block;
 min-width:0;
}}
.mini-status{{
 display:inline-flex!important;
 flex:0 0 auto;
 align-items:center;
 gap:6px;
 padding:4px 7px;
 border-radius:999px;
 background:rgba(0,0,0,.035);
 color:var(--ui-secondary)!important;
 font-size:9px!important;
 line-height:1!important;
 font-weight:650!important;
 letter-spacing:0!important;
 text-transform:none!important;
}}
.mini-status i{{
 display:block;
 width:7px;
 height:7px;
 border-radius:50%;
 background:var(--ui-idle);
}}
.mini-status.good i{{background:var(--ui-good)}}
.mini-status.loading i{{background:var(--ui-loading)}}
.mini-status.error i{{background:var(--ui-error)}}
.mini-status.idle i{{background:var(--ui-idle)}}
.record strong{{
 overflow:hidden;
 text-overflow:ellipsis;
 white-space:nowrap;
}}
.statuses{{display:none!important}}
button.primary{{
 background:var(--ui-accent)!important;
 border-color:var(--ui-accent)!important;
 box-shadow:0 2px 7px rgba(0,0,0,.10)!important;
}}
button.primary:hover:not(:disabled){{
 background:var(--ui-accent-hover)!important;
}}
.back{{
 color:#55555a!important;
}}
.team-list{{
 display:grid!important;
 grid-template-columns:repeat(3,minmax(0,1fr));
 gap:11px!important;
 overflow:visible!important;
 margin-top:20px!important;
 border:0!important;
 border-radius:0!important;
 background:transparent!important;
}}
.team-list .team-chip{{
 width:100%!important;
 height:48px!important;
 min-height:48px!important;
 padding:0 14px!important;
 border:2px solid currentColor!important;
 border-radius:999px!important;
 text-align:center!important;
 white-space:nowrap;
 font-size:14px!important;
 font-weight:650!important;
 line-height:1!important;
 box-shadow:0 1px 2px rgba(0,0,0,.025);
 overflow:hidden;
 text-overflow:ellipsis;
}}

/* ORCA-inspired group palette, separated more clearly for fast scanning. */
.team-list .team-mechatronics{{
 color:#7A5547!important;
 background:#F2E8E3!important;
 border-color:#9B6C58!important;
}}
.team-list .team-lab-build{{
 color:#8B2BC2!important;
 background:#F5E9FB!important;
 border-color:#A63BD8!important;
}}
.team-list .team-engineering{{
 color:#4F46A5!important;
 background:#ECEBFA!important;
 border-color:#665CC7!important;
}}
.team-list .team-release{{
 color:#B87400!important;
 background:#FFF3D6!important;
 border-color:#DE9200!important;
}}
.team-list .team-research{{
 color:#A9471B!important;
 background:#FBE8E1!important;
 border-color:#C65B2A!important;
}}

/* Keep every team bubble visually identical, including Engineering. */
.team-list .team-chip{{
 display:flex!important;
 align-items:center!important;
 justify-content:center!important;
 box-sizing:border-box!important;
 width:100%!important;
 height:48px!important;
 min-height:48px!important;
 max-height:48px!important;
 padding:0 14px!important;
 margin:0!important;
 border-style:solid!important;
 border-width:2px!important;
 border-radius:999px!important;
 line-height:1!important;
 vertical-align:middle!important;
 overflow:hidden!important;
 text-overflow:ellipsis!important;
 white-space:nowrap!important;
 box-shadow:none!important;
}}


/* Explicitly restore the full capsule border on the final team item.
   Older list styling removed the bottom border from :last-child. */
.team-list button.team-chip:last-child{{
 border-bottom-style:solid!important;
 border-bottom-width:2px!important;
 border-bottom-color:inherit!important;
}}
.team-list button.team-engineering:last-child{{
 border-bottom-color:#665CC7!important;
}}
.team-list .team-chip:hover{{
 filter:brightness(.975);
 box-shadow:0 2px 6px rgba(0,0,0,.05)!important;
}}
.team-list .team-chip:active{{
 transform:scale(.985);
}}
@media(max-width:560px){{
 .safe{{max-width:52%}}
 .record-head{{align-items:flex-start}}
 .mini-status{{margin-top:-1px}}
 .team-list{{
   grid-template-columns:repeat(2,minmax(0,1fr));
   gap:9px!important;
 }}
 .team-list .team-chip{{
   height:44px!important;
   min-height:44px!important;
   max-height:44px!important;
   padding:0 12px!important;
   font-size:13px!important;
 }}
}}
@media(max-width:390px){{
 .team-list{{grid-template-columns:1fr}}
}}
}}

.form-label{{
 display:block;
 margin:20px 0 8px;
 color:var(--ui-secondary);
 font-size:12px;
 font-weight:650;
}}
.form-label span{{
 color:#a1a1a6;
 font-weight:500;
}}
.form-input,.form-textarea{{
 width:100%;
 border:1px solid rgba(0,0,0,.12);
 border-radius:14px;
 background:rgba(248,248,250,.92);
 color:var(--ui-text);
 font:inherit;
 font-size:14px;
 outline:none;
 transition:border-color .12s ease,box-shadow .12s ease,background .12s ease;
}}
.form-input{{
 height:48px;
 padding:0 14px;
}}
.form-textarea{{
 min-height:116px;
 padding:13px 14px;
 resize:vertical;
 line-height:1.45;
}}
.form-input:focus,.form-textarea:focus{{
 border-color:#7d7d82;
 background:#fff;
 box-shadow:0 0 0 3px rgba(0,0,0,.06);
}}
.form-actions{{
 margin-top:18px;
}}
.assignee-summary{{
 display:flex;
 align-items:center;
 justify-content:space-between;
 gap:12px;
 margin-top:18px;
 padding:13px 15px;
 border:1px solid rgba(0,0,0,.08);
 border-radius:14px;
 background:rgba(248,248,250,.8);
}}
.assignee-summary span{{
 color:var(--ui-tertiary);
 font-size:11px;
 font-weight:650;
 text-transform:uppercase;
 letter-spacing:.06em;
}}
.assignee-summary strong{{
 min-width:0;
 overflow:hidden;
 text-overflow:ellipsis;
 color:var(--ui-text);
 font-size:13px;
 font-weight:650;
 white-space:nowrap;
}}
.completion-summary{{
 display:flex;
 flex-direction:column;
 gap:4px;
 margin:16px 0;
 padding:14px 15px;
 border-radius:14px;
 background:rgba(248,248,250,.84);
 border:1px solid rgba(0,0,0,.08);
}}
.completion-summary strong{{
 font-size:15px;
}}
.completion-summary span{{
 color:var(--ui-secondary);
 font-size:12px;
}}
.team-list .team-other{{
 color:#55555A!important;
 background:#F2F2F4!important;
 border-color:#8E8E93!important;
}}

.details-label{{
 margin-top:28px!important;
}}
.assignee-label{{
 margin-top:20px!important;
}}
.select-wrap{{
 position:relative;
 width:100%;
}}
.select-wrap::after{{
 content:"";
 position:absolute;
 right:16px;
 top:50%;
 width:8px;
 height:8px;
 border-right:2px solid #7a7a80;
 border-bottom:2px solid #7a7a80;
 transform:translateY(-65%) rotate(45deg);
 pointer-events:none;
}}
.form-select{{
 appearance:none;
 -webkit-appearance:none;
 width:100%;
 height:48px;
 padding:0 46px 0 14px;
 border:1px solid rgba(0,0,0,.12);
 border-radius:14px;
 background:rgba(248,248,250,.92);
 color:var(--ui-text);
 font:inherit;
 font-size:14px;
 font-weight:550;
 outline:none;
 cursor:pointer;
 transition:border-color .12s ease,box-shadow .12s ease,background .12s ease;
}}
.form-select:focus{{
 border-color:#7d7d82;
 background:#fff;
 box-shadow:0 0 0 3px rgba(0,0,0,.06);
}}

/* Reassign form spacing polish */
.assignee-summary{{
 margin-top:22px!important;
}}
.assignee-label{{
 margin-top:22px!important;
 margin-bottom:9px!important;
}}
.details-label{{
 display:flex!important;
 align-items:baseline!important;
 gap:6px!important;
 margin-top:30px!important;
 margin-bottom:10px!important;
 color:var(--ui-text)!important;
 font-size:14px!important;
 font-weight:600!important;
}}
.details-label span{{
 color:#8e8e93!important;
 font-size:14px!important;
 font-weight:500!important;
}}
.form-textarea{{
 display:block!important;
 margin-top:0!important;
}}
.form-actions{{
 margin-top:22px!important;
}}

/* Final Reassign form spacing / Other-row alignment */
.details-label{{
 margin-top:16px!important;
 margin-bottom:9px!important;
}}
.assignee-summary{{
 margin-top:20px!important;
}}
.other-assignee-summary{{
 display:grid!important;
 grid-template-columns:auto minmax(300px,1fr)!important;
 align-items:center!important;
 gap:22px!important;
 min-height:58px!important;
 padding:8px 10px 8px 15px!important;
}}
.other-assignee-summary>span{{
 white-space:nowrap!important;
}}
.other-select-wrap{{
 position:relative;
 min-width:0;
 width:100%;
}}
.other-select-wrap::after{{
 content:"";
 position:absolute;
 right:15px;
 top:50%;
 width:8px;
 height:8px;
 border-right:2px solid #7a7a80;
 border-bottom:2px solid #7a7a80;
 transform:translateY(-65%) rotate(45deg);
 pointer-events:none;
}}
.other-assignee-select{{
 display:block!important;
 width:100%!important;
 min-width:0!important;
 height:42px!important;
 padding:0 42px 0 14px!important;
 margin:0!important;
 border:1px solid rgba(0,0,0,.10)!important;
 border-radius:12px!important;
 background:rgba(255,255,255,.72)!important;
 color:var(--ui-text)!important;
 font-size:13px!important;
 font-weight:650!important;
 text-overflow:ellipsis;
 white-space:nowrap;
 overflow:hidden;
}}
.other-assignee-select:focus{{
 background:#fff!important;
 border-color:#7d7d82!important;
 box-shadow:0 0 0 3px rgba(0,0,0,.05)!important;
}}
@media(max-width:560px){{
 .other-assignee-summary{{
   grid-template-columns:auto minmax(0,1fr)!important;
   gap:12px!important;
 }}
 .other-assignee-select{{
   font-size:12px!important;
 }}
}}

/* Final Other Assign-To row: same outer dimensions as all team rows. */
.other-assignee-summary{{
 display:flex!important;
 align-items:center!important;
 justify-content:space-between!important;
 gap:16px!important;
 min-height:0!important;
 margin-top:20px!important;
 padding:13px 15px!important;
}}
.other-assignee-summary>span{{
 flex:0 0 auto;
 white-space:nowrap!important;
}}
.other-select-wrap{{
 position:relative;
 flex:1 1 auto;
 min-width:260px;
 max-width:72%;
 height:28px;
}}
.other-select-wrap::after{{
 content:"";
 position:absolute;
 right:2px;
 top:50%;
 width:7px;
 height:7px;
 border-right:2px solid #7a7a80;
 border-bottom:2px solid #7a7a80;
 transform:translateY(-68%) rotate(45deg);
 pointer-events:none;
}}
.other-assignee-select{{
 appearance:none!important;
 -webkit-appearance:none!important;
 display:block!important;
 width:100%!important;
 height:28px!important;
 min-height:28px!important;
 padding:0 26px 0 8px!important;
 margin:0!important;
 border:0!important;
 border-radius:8px!important;
 background:transparent!important;
 color:var(--ui-text)!important;
 font:inherit!important;
 font-size:13px!important;
 font-weight:650!important;
 line-height:28px!important;
 text-align:right;
 text-align-last:right;
 outline:none!important;
 box-shadow:none!important;
 white-space:nowrap!important;
 overflow:hidden!important;
 text-overflow:ellipsis!important;
 cursor:pointer;
}}
.other-assignee-select:focus{{
 background:rgba(0,0,0,.035)!important;
 box-shadow:0 0 0 2px rgba(0,0,0,.04)!important;
}}
@media(max-width:560px){{
 .other-assignee-summary{{
   gap:10px!important;
 }}
 .other-select-wrap{{
   min-width:0;
   max-width:75%;
 }}
 .other-assignee-select{{
   font-size:12px!important;
 }}
}}

/* Other row must match the exact visual height of predefined Assign To rows. */
.other-assignee-summary{{
 display:flex!important;
 align-items:center!important;
 justify-content:space-between!important;
 gap:16px!important;
 min-height:0!important;
 margin-top:20px!important;
 padding:13px 15px!important;
}}
.other-assignee-summary>span{{
 flex:0 0 auto;
 white-space:nowrap!important;
}}
.other-select-wrap{{
 position:relative;
 flex:1 1 auto;
 min-width:260px;
 max-width:72%;
 height:18px!important;
}}
.other-select-wrap::after{{
 content:"";
 position:absolute;
 right:1px;
 top:50%;
 width:6px;
 height:6px;
 border-right:2px solid #7a7a80;
 border-bottom:2px solid #7a7a80;
 transform:translateY(-70%) rotate(45deg);
 pointer-events:none;
}}
.other-assignee-select{{
 appearance:none!important;
 -webkit-appearance:none!important;
 display:block!important;
 width:100%!important;
 height:18px!important;
 min-height:18px!important;
 max-height:18px!important;
 padding:0 23px 0 8px!important;
 margin:0!important;
 border:0!important;
 border-radius:6px!important;
 background:transparent!important;
 color:var(--ui-text)!important;
 font:inherit!important;
 font-size:13px!important;
 font-weight:650!important;
 line-height:18px!important;
 text-align:right;
 text-align-last:right;
 outline:none!important;
 box-shadow:none!important;
 white-space:nowrap!important;
 overflow:hidden!important;
 text-overflow:ellipsis!important;
 cursor:pointer;
}}
.other-assignee-select:focus{{
 background:rgba(0,0,0,.035)!important;
 box-shadow:none!important;
}}
@media(max-width:560px){{
 .other-assignee-summary{{gap:10px!important}}
 .other-select-wrap{{
   min-width:0;
   max-width:75%;
   height:18px!important;
 }}
 .other-assignee-select{{
   height:18px!important;
   min-height:18px!important;
   max-height:18px!important;
   font-size:12px!important;
 }}
}}

.salesforce-help{{
 margin-bottom:16px!important;
}}
.salesforce-field{{
 margin-top:14px;
}}
.salesforce-field[hidden]{{
 display:none!important;
}}
.salesforce-label{{
 margin:0 0 8px!important;
 color:var(--ui-text)!important;
 font-size:13px!important;
 font-weight:600!important;
}}
.route-summary{{
 display:flex;
 flex-direction:column;
 gap:4px;
 margin-top:18px;
 padding:14px 15px;
 border:1px solid rgba(0,0,0,.08);
 border-radius:14px;
 background:rgba(248,248,250,.84);
}}
.route-summary span{{
 color:var(--ui-tertiary);
 font-size:10px;
 font-weight:650;
 text-transform:uppercase;
 letter-spacing:.06em;
}}
.route-summary strong{{
 font-size:13px;
 line-height:1.4;
}}
</style>
</head>
<body>
<div class="wrap">
  <div class="top">
    <div class="brand">MTV PAPERWORK</div>
    <div class="safe" title="{html.escape(state.get("location_label") or "Unknown")}">{html.escape(state.get("location_label") or "Unknown")}</div>
  </div>

  {msg}

  <section class="card">
    <div class="eyebrow">Workspace</div>
    <h1>Robot {robot}</h1>
    <div class="records">
      <div class="record">
        <div class="record-head">
          <span>BUGANIZER</span>
          <span class="mini-status {bug_status_class}"><i></i>{html.escape(bug_status_text)}</span>
        </div>
        <strong>{bug}</strong>
      </div>
      <div class="record">
        <div class="record-head">
          <span>SALESFORCE</span>
          <span class="mini-status {sf_status_class}"><i></i>{html.escape(sf_status_text)}</span>
        </div>
        <strong>{html.escape(sf_label)}</strong>
      </div>
    </div>
  </section>

  {body}

  <div class="footer">Local companion · 127.0.0.1:{PORT}</div>
</div>

<script>
const INITIAL_OPENING = {opening_js};
const INITIAL_SESSION = {sid};

let companionMisses = 0;
let actionInFlight = false;

function closeBecauseCompanionEnded() {{
  try {{ window.close(); }} catch (_) {{}}
  setTimeout(() => {{
    document.body.innerHTML =
      '<div style="font-family:system-ui;padding:32px;text-align:center;color:#667085">' +
      '<h2 style="color:#101828">Companion ended</h2>' +
      '<p>This paperwork window can be closed.</p></div>';
  }}, 120);
}}

// This popup may be in the technician's normal Chrome while the control page is
// in Playwright's private profile. Poll localhost directly so End session can
// reliably close this window across browsers/profiles/platforms.
const lifecycleTimer = setInterval(async () => {{
  try {{
    const r = await fetch('/health', {{cache:'no-store'}});
    if(!r.ok) throw new Error('health');
    const health = await r.json();
    companionMisses = 0;
    if(health.shutting_down) {{
      clearInterval(lifecycleTimer);
      closeBecauseCompanionEnded();
    }}
  }} catch (_) {{
    // Browser automation can briefly occupy the local process. Never tear down
    // the Paperwork popup while a Commit/Complete action is still in flight.
    if(actionInFlight) {{
      companionMisses = 0;
      return;
    }}
    companionMisses += 1;
    // Only treat a sustained outage as a stopped Companion.
    if(companionMisses >= 10) {{
      clearInterval(lifecycleTimer);
      closeBecauseCompanionEnded();
    }}
  }}
}}, 350);

async function post(data) {{
  actionInFlight = true;
  try {{
    const r = await fetch('/api/action', {{
      method:'POST',
      headers:{{'Content-Type':'application/json'}},
      body:JSON.stringify(data)
    }});
    const payload = await r.json().catch(() => ({{}}));
    if(!r.ok) throw new Error(payload.error || 'Paperwork action failed.');
    location.reload();
  }} catch (error) {{
    // Do not surface Chrome's unhelpful raw "Failed to fetch" message.  Check
    // whether the Companion is still alive and give a retry-safe instruction.
    if(String(error?.message || error).includes('Failed to fetch')) {{
      try {{
        const health = await fetch('/health', {{cache:'no-store'}});
        if(health.ok) {{
          throw new Error(
            'The Salesforce request was interrupted, but the Companion is still running. ' +
            'The workflow checks Salesforce before changing anything, so press Complete ' +
            'Salesforce again to continue safely.'
          );
        }}
      }} catch (healthError) {{
        if(
          healthError?.message &&
          !String(healthError.message).includes('Failed to fetch')
        ) throw healthError;
      }}
    }}
    throw error;
  }} finally {{
    actionInFlight = false;
  }}
}}

async function choose(action) {{
  try {{
    await post({{action}});
  }} catch (err) {{
    alert(err.message || String(err));
  }}
}}

async function submitClaim() {{
  const button=document.getElementById('claimCommit');
  if(button){{
    button.disabled=true;
    button.textContent='Working…';
  }}

  try {{
    const details=String(
      document.getElementById('claimDetails')?.value||''
    );

    await post({{
      action:'submit_claim',
      details
    }});
  }} catch (err) {{
    if(button){{
      button.disabled=false;
      button.textContent='Commit';
    }}
    alert(err.message || String(err));
  }}
}}

async function retryClaimSync() {{
  const button=document.getElementById('claimSyncRetry');
  if(button){{
    button.disabled=true;
    button.textContent='Checking…';
  }}
  try {{
    await post({{
      action:'submit_claim',
      details:''
    }});
  }} catch (err) {{
    if(button){{
      button.disabled=false;
      button.textContent='Check again';
    }}
    alert(err.message || String(err));
  }}
}}

async function team(name) {{
  try {{
    await post({{action:'select_reassign',team:name}});
  }} catch (err) {{
    alert(err.message || String(err));
  }}
}}

async function submitReassign() {{
  const button=document.getElementById('reassignContinue');
  const teamName=String(button?.dataset?.team||'').trim();

  if(!teamName){{
    alert('Reassignment target is missing. Go back and select the team again.');
    return;
  }}

  if(button){{
    button.disabled=true;
    button.textContent='Working…';
  }}

  try {{
    const details=String(
      document.getElementById('reassignDetails')?.value||''
    );
    const assigneeEmail=String(
      document.getElementById('assigneeEmail')?.value||''
    ).trim();

    await post({{
      action:'submit_reassign',
      team:teamName,
      assignee_email:assigneeEmail,
      details
    }});
  }} catch (err) {{
    if(button){{
      button.disabled=false;
      button.textContent='Commit';
    }}
    alert(err.message || String(err));
  }}
}}


function updateSalesforceRouteVisibility() {{
  // Claim has chained conditional fields (Type -> Sub Category -> Component).
  // Resolve visibility repeatedly so changing a parent clears/hides every stale
  // dependent selector in the same UI event.
  for(let pass=0; pass<4; pass++){{
    const values={{}};
    document.querySelectorAll('[data-salesforce-select]').forEach(select => {{
      const group=select.closest('.salesforce-field');
      if(!group || !group.hidden){{
        values[String(select.dataset.salesforceSelect||'')]=String(select.value||'');
      }}
    }});

    let changed=false;
    document.querySelectorAll('.salesforce-field[data-when-key]').forEach(group => {{
      const key=String(group.dataset.whenKey||'');
      const wanted=String(group.dataset.whenValue||'');
      const visible=values[key]===wanted;
      if(group.hidden===visible) changed=true;
      group.hidden=!visible;
      const select=group.querySelector('[data-salesforce-select]');
      if(select){{
        select.required=visible;
        if(!visible && select.value){{
          select.value='';
          changed=true;
        }}
      }}
    }});
    if(!changed) break;
  }}
}}

async function submitSalesforceReassign() {{
  const button=document.getElementById('salesforceCommit');
  const selections={{}};

  updateSalesforceRouteVisibility();

  for(const select of document.querySelectorAll('[data-salesforce-select]')){{
    const group=select.closest('.salesforce-field');
    if(group && group.hidden) continue;
    const key=String(select.dataset.salesforceSelect||'').trim();
    const value=String(select.value||'').trim();
    if(select.required && !value){{
      alert('Choose ' + String(select.previousElementSibling?.textContent || select.id || 'a Salesforce option') + '.');
      select.focus();
      return;
    }}
    if(key) selections[key]=value;
  }}

  if(button){{
    button.disabled=true;
    button.textContent='Working…';
  }}

  try {{
    await post({{
      action:'submit_salesforce_reassign',
      selections
    }});
  }} catch (err) {{
    if(button){{
      button.disabled=false;
      button.textContent='Complete';
    }}
    alert(err.message || String(err));
  }}
}}


async function submitSalesforceClaim() {{
  const button=document.getElementById('salesforceClaimCommit');
  const selections={{}};

  updateSalesforceRouteVisibility();

  for(const select of document.querySelectorAll('[data-salesforce-select]')){{
    const group=select.closest('.salesforce-field');
    if(group && group.hidden) continue;

    const key=String(select.dataset.salesforceSelect||'').trim();
    const value=String(select.value||'').trim();
    if(select.required && !value){{
      alert(
        'Choose ' +
        String(select.previousElementSibling?.textContent || select.id || 'a Salesforce option') +
        '.'
      );
      select.focus();
      return;
    }}
    if(key) selections[key]=value;
  }}

  if(button){{
    button.disabled=true;
    button.textContent='Working…';
  }}

  try {{
    await post({{
      action:'submit_salesforce_claim',
      selections
    }});
  }} catch (err) {{
    if(button){{
      button.disabled=false;
      button.textContent='Complete';
    }}
    alert(err.message || String(err));
  }}
}}


document.addEventListener('DOMContentLoaded', updateSalesforceRouteVisibility);

async function resetChoice() {{
  try {{
    await post({{action:'reset'}});
  }} catch (err) {{
    alert(err.message || String(err));
  }}
}}

async function backToReassign() {{
  try {{
    await post({{action:'back_to_reassign'}});
  }} catch (err) {{
    alert(err.message || String(err));
  }}
}}

async function exitWorkspace() {{
  try {{
    const r = await fetch('/api/exit', {{method:'POST'}});
    if(!r.ok) throw new Error('Could not reset the workspace.');

    // window.close() works when the browser considers this a script-opened tab.
    // If it refuses, replace the page with a harmless closed state. The local
    // companion process itself keeps running for the next robot.
    window.close();
    setTimeout(() => {{
      document.body.innerHTML =
        '<div style="font-family:system-ui;padding:32px;text-align:center;color:#667085">' +
        '<h2 style="color:#101828">Paperwork closed</h2>' +
        '<p>You can close this tab and return to the MTV Robot Map.</p>' +
        '</div>';
    }}, 150);
  }} catch (err) {{
    alert(err.message || String(err));
  }}
}}

function showTeams() {{
  document.getElementById('actions').classList.add('hidden');
  document.getElementById('teams').classList.remove('hidden');
}}

function hideTeams() {{
  document.getElementById('teams').classList.add('hidden');
  document.getElementById('actions').classList.remove('hidden');
}}

// While the worker prepares the two records, poll only lightweight JSON state.
// The HTTP server remains responsive because Playwright is on its own thread.
if (INITIAL_OPENING) {{
  const timer = setInterval(async () => {{
    try {{
      const r = await fetch('/api/state', {{cache:'no-store'}});
      if(!r.ok) return;
      const state = await r.json();
      if(state.session_id !== INITIAL_SESSION) {{
        clearInterval(timer);
        return;
      }}
      if(!state.opening) {{
        clearInterval(timer);
        location.reload();
      }}
    }} catch (_) {{
      // A temporary failed poll must not turn into "companion not running".
    }}
  }}, 600);
}}
</script>
</body>
</html>"""


def launch_geometry(payload: dict[str, Any]) -> dict[str, int]:
    """Sanitize display geometry supplied by the map."""
    def integer(name: str, default: int = 0) -> int:
        try:
            return int(float(payload.get(name, default) or default))
        except (TypeError, ValueError):
            return default

    width = max(0, integer("screen_width"))
    height = max(0, integer("screen_height"))
    split_x = integer("split_x")

    if width and (split_x <= 0 or split_x >= width):
        split_x = width // 2

    return {
        "screen_left": integer("screen_left"),
        "screen_top": integer("screen_top"),
        "screen_width": width,
        "screen_height": height,
        "split_x": max(0, split_x),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        print("[Paperwork UI] " + fmt % args)

    def base_headers(self) -> None:
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Connection", "close")

    def cors_headers(self) -> None:
        # Only endpoints called by the shared map need cross-origin access.
        # Destructive UI actions remain same-origin to localhost.
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Private-Network", "true")

    def html(self, value: str, status: int = 200, *, cors: bool = False) -> None:
        data = value.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.base_headers()
        if cors:
            self.cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def json(
        self,
        value: dict[str, Any],
        status: int = 200,
        *,
        cors: bool = False,
    ) -> None:
        data = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.base_headers()
        if cors:
            self.cors_headers()
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self) -> None:
        path = urllib.parse.urlparse(self.path).path
        self.send_response(HTTPStatus.NO_CONTENT)
        self.base_headers()
        if path in {"/health", "/launch", "/start"}:
            self.cors_headers()
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path == "/health":
            state = WORKSPACE.snapshot()
            self.json(
                {
                    "ok": True,
                    "service": "MTV Paperwork Companion",
                    "version": "3.13",
                    "platform": platform.system().lower(),
                    "ready": bool(state.get("startup_ready")),
                    "buganizer_authenticated": bool(state.get("startup_bug_authenticated")),
                    "salesforce_authenticated": bool(state.get("startup_sf_authenticated")),
                    "startup_phase": state.get("startup_phase", ""),
                    "shutting_down": SHUTDOWN_REQUESTED.is_set(),
                },
                cors=True,
            )
            return

        if path == "/startup":
            self.html(render_startup_page())
            return

        if path == "/api/state":
            state = WORKSPACE.snapshot()
            self.json(
                {
                    "ok": True,
                    "session_id": state["session_id"],
                    "opening": state["opening"],
                    "bug_opened": state["bug_opened"],
                    "sf_opened": state["sf_opened"],
                    "sf_phase": state["sf_phase"],
                    "sf_exact": bool(state["sf_url"]),
                    "error": state["launch_error"],
                    "startup_ready": state["startup_ready"],
                    "startup_bug_authenticated": state["startup_bug_authenticated"],
                    "startup_sf_authenticated": state["startup_sf_authenticated"],
                    "startup_phase": state["startup_phase"],
                    "startup_error": state["startup_error"],
                }
            )
            return

        if path == "/":
            self.html(render_page())
            return

        if path not in {"/start", "/launch"}:
            self.html("<h1>Not found</h1>", HTTPStatus.NOT_FOUND)
            return

        q = urllib.parse.parse_qs(parsed.query)
        bug_url = allowed_bug_url(q.get("bug_url", [""])[0])
        sf_url = allowed_sf_url(q.get("sf_url", [""])[0])
        bug = clean((q.get("bug_id") or q.get("bug") or [""])[0])
        robot = clean((q.get("robot_id") or q.get("robot") or [""])[0])
        location_label = clean((q.get("location") or ["Unknown"])[0]) or "Unknown"

        if not bug_url:
            self.html(
                render_page("Invalid or missing Buganizer URL."),
                HTTPStatus.BAD_REQUEST,
                cors=True,
            )
            return

        if not BUG_RE.fullmatch(bug):
            self.html(
                render_page("Invalid or missing 9-digit Buganizer ID."),
                HTTPStatus.BAD_REQUEST,
                cors=True,
            )
            return

        # Both GET /start and GET /launch now use the same non-blocking path.
        geometry = launch_geometry({
            key: (values[0] if values else "")
            for key, values in q.items()
        })
        sid = begin_workspace(
            robot,
            bug,
            bug_url,
            sf_url,
            geometry,
            location_label,
        )
        self.json(
            {"ok": True, "accepted": True, "session_id": sid},
            HTTPStatus.ACCEPTED,
            cors=True,
        )

    def do_POST(self) -> None:
        path = urllib.parse.urlparse(self.path).path

        # End Session stops the whole local companion. Return the response first,
        # then stop serve_forever() from a separate daemon thread.
        if path == "/api/shutdown":
            self.json({"ok": True, "stopping": True})
            threading.Thread(
                target=request_shutdown,
                name="MTV-Companion-Shutdown",
                daemon=True,
            ).start()
            return

        # /api/exit intentionally accepts an empty body.
        if path == "/api/exit":
            reset_workspace()
            self.json({"ok": True})
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length else b"{}"
            payload = json.loads(raw or b"{}")
        except Exception:
            self.json(
                {"ok": False, "error": "Invalid JSON"},
                HTTPStatus.BAD_REQUEST,
                cors=path == "/launch",
            )
            return

        if path == "/launch":
            bug = clean(payload.get("bug_id"))
            robot = clean(payload.get("robot_id"))
            location_label = clean(payload.get("location")) or "Unknown"
            bug_url = allowed_bug_url(payload.get("bug_url", ""))
            sf_url = allowed_sf_url(payload.get("sf_url", ""))

            if not bug_url or not BUG_RE.fullmatch(bug):
                self.json(
                    {"ok": False, "error": "Invalid paperwork request"},
                    HTTPStatus.BAD_REQUEST,
                    cors=True,
                )
                return

            geometry = launch_geometry(payload)
            sid = begin_workspace(
                robot,
                bug,
                bug_url,
                sf_url,
                geometry,
                location_label,
            )
            self.json(
                {"ok": True, "accepted": True, "session_id": sid},
                HTTPStatus.ACCEPTED,
                cors=True,
            )
            return

        if path != "/api/action":
            self.json({"ok": False}, HTTPStatus.NOT_FOUND)
            return

        action = clean(payload.get("action")).lower()

        if action == "reset":
            WORKSPACE.choose("", "")
            self.json({"ok": True})
            return

        if action == "claim_form":
            state = WORKSPACE.snapshot()
            if state["opening"]:
                self.json(
                    {
                        "ok": False,
                        "error": "The records are still opening. Please wait a moment.",
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            WORKSPACE.show_claim_form()
            self.json({"ok": True})
            return

        if action == "submit_claim":
            state = WORKSPACE.snapshot()
            if state["opening"]:
                self.json(
                    {
                        "ok": False,
                        "error": "The records are still opening. Please wait a moment.",
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            if state["action"] != "claim_form":
                self.json(
                    {
                        "ok": False,
                        "error": "The Claim step is no longer awaiting a "
                                 "Buganizer commit.",
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            details = str(payload.get("details") or "")

            try:
                result = BROWSER_WORKER.submit(
                    WORKSPACE.execute_claim_buganizer,
                    details,
                    wait=True,
                    timeout=180,
                )
            except FutureTimeoutError:
                self.json(
                    {
                        "ok": False,
                        "error": "Claim is taking longer than expected. "
                                 "Check Buganizer before retrying.",
                    },
                    HTTPStatus.GATEWAY_TIMEOUT,
                )
                return
            except Exception as error:
                self.json(
                    {"ok": False, "error": str(error)},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            details_note = (
                " Details were posted as a Buganizer comment."
                if result["comment_changed"]
                else " No additional details were added."
            )
            assignee_note = (
                "Buganizer was assigned successfully."
                if result["assignee_changed"]
                else "Buganizer was already assigned to robotics-support@google.com."
            )

            # Buganizer is complete. The technician will manually verify that
            # Salesforce has received the update before Salesforce automation.
            WORKSPACE.begin_salesforce_claim(
                details=result["details"],
                result_message=assignee_note + details_note,
            )

            print(
                f"Buganizer Claim completed for Bug "
                f"{state['bug_number']}: robotics-support@google.com. "
                "Showing Salesforce route choices for manual verification."
            )
            self.json({"ok": True, "next": "salesforce"})
            return

        if action == "back_to_reassign":
            WORKSPACE.show_reassign_targets()
            self.json({"ok": True})
            return

        if action == "select_reassign":
            selected = clean(payload.get("team"))
            if selected not in REASSIGN_TEAMS:
                self.json(
                    {"ok": False, "error": "Unsupported reassignment target"},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            WORKSPACE.select_reassign_target(selected)
            self.json({"ok": True})
            return

        if action == "submit_reassign":
            state = WORKSPACE.snapshot()
            if state["opening"]:
                self.json(
                    {
                        "ok": False,
                        "error": "The records are still opening. Please wait a moment.",
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            selected = clean(payload.get("team"))
            if selected not in REASSIGN_TEAMS:
                self.json(
                    {"ok": False, "error": "Unsupported reassignment target"},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            details = str(payload.get("details") or "")
            assignee_email = clean(payload.get("assignee_email"))

            if selected != "Other":
                assignee_email = REASSIGN_TARGETS[selected]
            elif assignee_email not in OTHER_ASSIGNEES:
                self.json(
                    {
                        "ok": False,
                        "error": "Choose a valid assignee from the Other dropdown.",
                    },
                    HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                result = BROWSER_WORKER.submit(
                    WORKSPACE.execute_reassign,
                    selected,
                    assignee_email,
                    details,
                    wait=True,
                    timeout=180,
                )
            except FutureTimeoutError:
                self.json(
                    {
                        "ok": False,
                        "error": "Reassignment is taking longer than expected. Check Buganizer before retrying.",
                    },
                    HTTPStatus.GATEWAY_TIMEOUT,
                )
                return
            except Exception as error:
                self.json(
                    {"ok": False, "error": str(error)},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            details_note = (
                " Details were posted as a Buganizer comment."
                if result["comment_changed"]
                else " No additional details were added."
            )
            assignee_note = (
                "Buganizer was reassigned successfully."
                if result["assignee_changed"]
                else "Buganizer was already assigned to this recipient."
            )

            WORKSPACE.begin_salesforce_reassign(
                team=result["team"],
                assignee_email=result["assignee_email"],
                details=result["details"],
                result_message=assignee_note + details_note,
            )

            print(
                f"Buganizer Reassign completed for Bug {state['bug_number']}: "
                f"{result['assignee_email']}. Waiting for Salesforce route."
            )
            self.json({"ok": True, "next": "salesforce"})
            return

        if action == "submit_salesforce_claim":
            state = WORKSPACE.snapshot()
            if state["action"] != "salesforce_claim_form":
                self.json(
                    {
                        "ok": False,
                        "error": "Complete the Buganizer Claim step first.",
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            selections = payload.get("selections") or {}
            if not isinstance(selections, dict):
                self.json(
                    {
                        "ok": False,
                        "error": "Invalid Salesforce Claim selections.",
                    },
                    HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                route = resolve_claim_route(selections)
            except SalesforceRouteError as error:
                self.json(
                    {"ok": False, "error": str(error)},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            fields = route.as_dict()

            try:
                result = BROWSER_WORKER.submit(
                    WORKSPACE.execute_salesforce_claim,
                    fields,
                    wait=True,
                    timeout=420,
                )
            except FutureTimeoutError:
                self.json(
                    {
                        "ok": False,
                        "error": "Salesforce is taking longer than expected. "
                                 "It may still be waiting for the Buganizer sync. "
                                 "Check Salesforce before retrying; completed "
                                 "steps are retry-safe.",
                    },
                    HTTPStatus.GATEWAY_TIMEOUT,
                )
                return
            except Exception as error:
                self.json(
                    {"ok": False, "error": str(error)},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            if result.get("status_changed"):
                self.json(
                    {
                        "ok": False,
                        "error": 'Salesforce Status was changed to Closed. Verify that Buganizer has already finished updating Salesforce. If the Case is correct and remains Closed, click Exit. If Buganizer has not updated Salesforce yet, or changes the Case afterward, wait for that update to finish and then click Complete again.',
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            bug_note = clean(state.get("result_message"))
            sf_note = (
                f" Salesforce was assigned to "
                f"{result['owner'] or 'the current user'}, "
                "the Claim fields were saved"
            )
            if state.get("details"):
                sf_note += ", the same Details were posted to the Salesforce Feed"
            sf_note += ", and the Case was closed."

            WORKSPACE.finish_claim(
                details=state["details"],
                result_message=(bug_note + sf_note).strip(),
                sf_owner=result["owner"],
            )

            print(
                f"Salesforce Claim closeout completed for Bug "
                f"{state['bug_number']}: owner={result['owner']}"
            )
            self.json({"ok": True})
            return

        if action == "submit_salesforce_reassign":
            state = WORKSPACE.snapshot()
            if state["action"] != "salesforce_reassign_form" or not state["team"]:
                self.json(
                    {
                        "ok": False,
                        "error": "Complete the Buganizer Reassign step first.",
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            selections = payload.get("selections") or {}
            if not isinstance(selections, dict):
                self.json(
                    {"ok": False, "error": "Invalid Salesforce route selections."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            try:
                route = resolve_reassign_route(state["team"], selections)
            except SalesforceRouteError as error:
                self.json(
                    {"ok": False, "error": str(error)},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            fields = route.as_dict()

            try:
                result = BROWSER_WORKER.submit(
                    WORKSPACE.execute_salesforce_reassign,
                    fields,
                    wait=True,
                    timeout=420,
                )
            except FutureTimeoutError:
                self.json(
                    {
                        "ok": False,
                        "error": "Salesforce is taking longer than expected. "
                                 "Check the Salesforce tab before retrying. "
                                 "Completed Salesforce steps will not be repeated.",
                    },
                    HTTPStatus.GATEWAY_TIMEOUT,
                )
                return
            except Exception as error:
                self.json(
                    {"ok": False, "error": str(error)},
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                )
                return

            if result.get("status_changed"):
                self.json(
                    {
                        "ok": False,
                        "error": 'Salesforce Status was changed to Closed. Verify that Buganizer has already finished updating Salesforce. If the Case is correct and remains Closed, click Exit. If Buganizer has not updated Salesforce yet, or changes the Case afterward, wait for that update to finish and then click Complete again.',
                    },
                    HTTPStatus.CONFLICT,
                )
                return

            bug_note = clean(state.get("result_message"))
            sf_note = (
                f" Salesforce was assigned to {result['owner'] or 'the current user'}, "
                "the routed fields were saved"
            )
            if state.get("details"):
                sf_note += ", the same Details were posted to the Salesforce Feed"
            sf_note += ", and the Case was closed."

            WORKSPACE.finish_reassign(
                team=state["team"],
                assignee_email=state["assignee_email"],
                details=state["details"],
                result_message=(bug_note + sf_note).strip(),
                sf_owner=result["owner"],
            )

            print(
                f"Salesforce closeout completed for Bug {state['bug_number']}: "
                f"{state['team']} / owner={result['owner']}"
            )
            self.json({"ok": True})
            return

        self.json(
            {"ok": False, "error": "Unsupported action"},
            HTTPStatus.BAD_REQUEST,
        )


def main() -> None:
    global SERVER

    SHUTDOWN_REQUESTED.clear()

    print(f"MTV Paperwork Companion: http://{HOST}:{PORT}")
    print("Startup opens the Companion UI, Buganizer, and Salesforce immediately.")
    print("Complete any Buganizer / Salesforce / Okta sign-in before first use.")
    print("When both services are authenticated, managed Chrome minimizes automatically.")
    print("Paperwork -> Begin restores/uses the authenticated ticket browser.")
    print("Use End session in the Companion UI when you are finished.")
    print("Ctrl+C also stops the companion.\n")

    # ThreadingHTTPServer is deliberate. /health and UI requests must remain
    # responsive even while Salesforce/Buganizer automation is still working.
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    SERVER = server

    BROWSER_WORKER.submit(
        WORKSPACE.bootstrap_companion,
        wait=False,
    )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping...")
        SHUTDOWN_REQUESTED.set()
    finally:
        SHUTDOWN_REQUESTED.set()
        try:
            server.shutdown()
        except Exception:
            pass
        server.server_close()
        SERVER = None
        BROWSER_WORKER.stop()
        print("MTV Paperwork Companion stopped.")


if __name__ == "__main__":
    main()
