"""Paperwork workflows for opening and updating repair records."""

from collections.abc import Callable
import re
import time
from typing import Any

from browser_manager import BrowserManager
from status_display import set_status


BUGANIZER_ISSUES_URL = "https://partnerissuetracker.corp.google.com/issues/"
SALESFORCE_CASES_URL = (
    "https://apptronik.lightning.force.com/lightning/o/Case/list"
    "?filterName=Field_Service_Unassigned"
)
SALESFORCE_SEARCH_KEY_DELAY_MS = 20
SALESFORCE_INSTANT_RESULT_TIMEOUT_MS = 5_000
BUGANIZER_ASSIGNEE = "robotics-support@google.com"


class PaperworkError(RuntimeError):
    """Raised when a paperwork page cannot be opened."""


def prompt_bug_number() -> str | None:
    """Collect an exact nine-digit Buganizer number or return Home."""
    while True:
        value = input(
            "\nEnter the 9-digit Buganizer number, or B to go back: "
        ).strip()
        if value.lower() in {"b", "back", "home", "quit"}:
            return None
        if len(value) == 9 and value.isdigit():
            return value
        print("Invalid bug number. Enter exactly 9 digits, or B to go back.")


def buganizer_url(bug_number: str) -> str:
    """Build the exact Buganizer issue URL after validating its identifier."""
    if len(bug_number) != 9 or not bug_number.isdigit():
        raise PaperworkError("Buganizer numbers must contain exactly 9 digits.")
    return f"{BUGANIZER_ISSUES_URL}{bug_number}"


def prompt_bug_comment() -> str | None:
    """Collect a comment, return an empty string to skip, or None to cancel."""
    while True:
        value = input(
            "Enter the description to add as a Buganizer comment, "
            "type SKIP for no comment, or B to cancel: "
        ).strip()
        if value.lower() in {"b", "back", "home", "quit"}:
            return None
        if value.lower() == "skip":
            return ""
        if value:
            return value
        print("The Buganizer comment cannot be empty.")


def post_buganizer_comment_direct(
    page: Any,
    bug_number: str,
    comment: str,
) -> bool:
    """Post an optional Buganizer comment and verify it appears.

    Blank comments are valid and are skipped. The textarea is explicitly
    clicked and focused before typing so an accidental click elsewhere in the
    browser cannot redirect keyboard input.
    """
    comment = comment.strip()
    if not comment:
        return False

    try:
        comment_input = page.locator(
            'textarea[aria-label="Comment box - add your comment"]'
        ).first

        try:
            comment_input.wait_for(state="visible", timeout=8_000)
        except Exception:
            comment_input = page.get_by_placeholder(
                "Add a comment.",
                exact=True,
            ).first
            comment_input.wait_for(state="visible", timeout=8_000)

        comment_input.scroll_into_view_if_needed()
        comment_input.click()
        comment_input.focus()

        # Clear only the Buganizer comment textarea, then type the user's details.
        comment_input.fill("")
        comment_input.type(comment, delay=5)

        if comment_input.input_value().strip() != comment:
            raise PaperworkError(
                "Buganizer did not retain the complete comment text."
            )

        comment_button = page.get_by_role(
            "button",
            name="Comment",
            exact=True,
        ).first
        comment_button.wait_for(state="visible", timeout=5_000)

        # Angular enables the Comment button only after the textarea input
        # event has propagated.
        enable_deadline = time.monotonic() + 8.0
        while time.monotonic() < enable_deadline:
            if comment_button.is_enabled():
                break
            page.wait_for_timeout(150)
        else:
            raise PaperworkError(
                "Buganizer Comment button did not become enabled."
            )

        comment_button.click()

        # A successful post normally clears/rerenders the draft field.
        clear_deadline = time.monotonic() + 12.0
        while time.monotonic() < clear_deadline:
            try:
                if not comment_input.input_value().strip():
                    break
            except Exception:
                break
            page.wait_for_timeout(200)
        else:
            raise PaperworkError(
                "Buganizer did not clear the comment box after submission."
            )

        # Verify the submitted text is visible in the issue after posting.
        normalized = " ".join(comment.split())
        verify_deadline = time.monotonic() + 15.0
        while time.monotonic() < verify_deadline:
            try:
                page_text = " ".join(
                    page.locator("body").inner_text().split()
                )
                if normalized in page_text:
                    print(
                        f"Posted Buganizer comment on issue {bug_number}."
                    )
                    return True
            except Exception:
                pass
            page.wait_for_timeout(250)

        raise PaperworkError(
            "Buganizer accepted the Comment action, but the submitted text "
            "could not be verified in the issue comments."
        )

    except PaperworkError:
        raise
    except Exception as error:
        raise PaperworkError(
            f"Could not post the comment to Buganizer issue {bug_number}: "
            f"{error}"
        ) from error



def post_buganizer_comment(page: Any, bug_number: str, comment: str) -> None:
    """Post an operator-supplied comment after confirmation and verify it."""
    comment = comment.strip()
    if not comment:
        raise PaperworkError("The Buganizer comment cannot be empty.")

    print("\nBuganizer comment preview:")
    print(comment)
    confirmation = input(
        f"Post this comment to Buganizer issue {bug_number}? "
        "Enter Y to confirm: "
    ).strip().lower()
    if confirmation not in {"y", "yes"}:
        raise PaperworkError("Buganizer comment posting was not confirmed.")

    post_buganizer_comment_direct(page, bug_number, comment)
    print(f"Posted the operator comment to Buganizer issue {bug_number}.")


def append_buganizer_description(
    page: Any,
    bug_number: str,
    details: str,
) -> bool:
    """Append optional operator details to the Buganizer Description.

    Blank details are valid and produce no edit.

    The helper is retry-safe: if the exact details already appear in the
    Description, it does not append them a second time.
    """
    details = details.strip()
    if not details:
        return False

    try:
        description_label = page.get_by_text(
            re.compile(r"^DESCRIPTION$", re.IGNORECASE),
            exact=True,
        ).first
        description_label.wait_for(state="visible", timeout=10_000)

        # Scope to the Description card so we never click another Edit button.
        description_card = description_label.locator(
            "xpath=ancestor::*[.//button[normalize-space()='Edit']][1]"
        )
        edit_button = description_card.get_by_role(
            "button",
            name="Edit",
            exact=True,
        ).first
        edit_button.wait_for(state="visible", timeout=5_000)

        # If a retry occurs after Description saved but before assignee saved,
        # avoid duplicating the exact text.
        current_description = clean_text(description_card.inner_text())
        if details in current_description:
            print(
                f"Buganizer issue {bug_number} already contains the supplied "
                "Description details."
            )
            return False

        edit_button.click()

        # Partner IssueTracker normally opens a pop-over edit panel. Keep an
        # inline fallback because its UI varies between builds.
        dialog = page.locator('[role="dialog"]:visible').last
        try:
            dialog.wait_for(state="visible", timeout=3_000)
            editor_root = dialog
        except Exception:
            editor_root = description_card

        textarea = editor_root.locator("textarea:visible").first
        editable = editor_root.locator('[contenteditable="true"]:visible').first

        editor_kind = ""
        editor = None

        try:
            textarea.wait_for(state="visible", timeout=1_500)
            editor = textarea
            editor_kind = "textarea"
        except Exception:
            try:
                editable.wait_for(state="visible", timeout=2_500)
                editor = editable
                editor_kind = "contenteditable"
            except Exception as error:
                raise PaperworkError(
                    "Buganizer Description editor opened, but its text field "
                    "could not be found."
                ) from error

        if editor_kind == "textarea":
            existing = editor.input_value()
            if details not in existing:
                separator = "\n\n" if existing.strip() else ""
                editor.fill(existing.rstrip() + separator + details)
        else:
            existing = clean_text(editor.inner_text())
            if details not in existing:
                editor.click()

                # Move the caret to the true end without replacing existing
                # rich-text content or links.
                editor.evaluate(
                    """el => {
                        el.focus();
                        const range = document.createRange();
                        range.selectNodeContents(el);
                        range.collapse(false);
                        const selection = window.getSelection();
                        selection.removeAllRanges();
                        selection.addRange(range);
                    }"""
                )

                if existing.strip():
                    page.keyboard.press("Enter")
                    page.keyboard.press("Enter")

                lines = details.splitlines() or [details]
                for index, line in enumerate(lines):
                    if line:
                        page.keyboard.insert_text(line)
                    if index < len(lines) - 1:
                        page.keyboard.press("Enter")

        # Save within the edit panel/card, not a global Save elsewhere.
        save_button = editor_root.get_by_role(
            "button",
            name="Save",
            exact=True,
        ).first
        save_button.wait_for(state="visible", timeout=5_000)
        save_button.click()

        try:
            if editor_root is dialog:
                dialog.wait_for(state="hidden", timeout=10_000)
        except Exception:
            pass

        # Verify the Description card now contains the submitted details.
        deadline = time.monotonic() + 18
        while time.monotonic() < deadline:
            refreshed = clean_text(description_card.inner_text())
            if details in refreshed:
                print(
                    f"Updated Buganizer Description for issue {bug_number}."
                )
                return True
            page.wait_for_timeout(250)

        raise PaperworkError(
            "Buganizer did not show the supplied details in Description "
            "after Save."
        )

    except PaperworkError:
        raise
    except Exception as error:
        raise PaperworkError(
            f"Could not update Buganizer Description for issue {bug_number}: "
            f"{error}"
        ) from error


def clean_text(value: Any) -> str:
    """Normalize browser text for reliable verification."""
    return " ".join(str(value or "").split())


def reassign_buganizer_issue_to(
    page: Any,
    bug_number: str,
    assignee_email: str,
) -> bool:
    """Assign a Buganizer issue to an exact email and verify the saved result.

    Returns False when the issue is already assigned to the requested address.
    This function is shared by Claim and every Reassign route so they all use
    the exact same browser behavior.
    """
    assignee_email = assignee_email.strip()
    if not assignee_email or "@" not in assignee_email:
        raise PaperworkError("A valid Buganizer assignee email is required.")

    assignee_name = re.compile(r"^Assignee user avatar", re.IGNORECASE)

    def get_assignee_button() -> Any:
        button = page.get_by_role(
            "button",
            name=assignee_name,
        ).first
        button.wait_for(state="visible", timeout=10_000)
        return button

    def assignee_snapshot(button: Any) -> str:
        """Collect all useful visible/accessibility text from the assignee control."""
        values: list[str] = []
        for getter in (
            lambda: button.inner_text(),
            lambda: button.get_attribute("aria-label"),
            lambda: button.get_attribute("title"),
            lambda: button.get_attribute("data-tooltip"),
        ):
            try:
                value = getter()
                if value:
                    values.append(str(value))
            except Exception:
                pass
        return " ".join(values)

    try:
        assignee_button = get_assignee_button()
        current_assignee = assignee_snapshot(assignee_button)
    except Exception as error:
        raise PaperworkError(
            "Could not find the Buganizer Assignee control."
        ) from error

    # Important for repeated Commit attempts:
    # if the correct assignee is already saved, do not reopen/edit it.
    if assignee_email.lower() in current_assignee.lower():
        print(
            f"Buganizer issue {bug_number} is already assigned to "
            f"{assignee_email}; skipping assignee edit."
        )
        return False

    try:
        assignee_button.click()

        editor = page.get_by_role(
            "dialog",
            name=re.compile(r"Pop over edit panel", re.IGNORECASE),
        ).first
        editor.wait_for(state="visible", timeout=6_000)

        assignee_input = editor.locator(
            "input[peoplekitautocomplete]"
        ).first
        assignee_input.wait_for(state="visible", timeout=6_000)

        # Explicit click/focus before typing, just like the proven comment flow.
        assignee_input.click()
        assignee_input.focus()
        assignee_input.fill("")
        assignee_input.type(assignee_email, delay=4)

        if assignee_input.input_value().strip().lower() != assignee_email.lower():
            raise PaperworkError(
                "Buganizer did not retain the complete assignee email."
            )

        # Wait for PeopleKit/autocomplete to populate. Prefer a result that
        # visibly contains the exact email. This works for team aliases and users.
        page.wait_for_timeout(350)

        selected = False
        candidate_locators = [
            page.get_by_role("option").filter(has_text=assignee_email).first,
            page.get_by_text(assignee_email, exact=True).first,
            page.locator(
                f'[role="option"]:has-text("{assignee_email}")'
            ).first,
        ]

        for candidate in candidate_locators:
            try:
                candidate.wait_for(state="visible", timeout=1_800)
                candidate.click()
                selected = True
                break
            except Exception:
                pass

        if not selected:
            # PeopleKit occasionally renders no useful ARIA role. Keyboard
            # selection is safer than saving raw free text.
            assignee_input.press("ArrowDown")
            page.wait_for_timeout(120)
            assignee_input.press("Enter")
            page.wait_for_timeout(250)

        save_button = editor.get_by_role(
            "button",
            name="Save",
            exact=True,
        ).first
        save_button.wait_for(state="visible", timeout=5_000)

        if not save_button.is_enabled():
            # Give the selected PeopleKit token a moment to settle.
            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                if save_button.is_enabled():
                    break
                page.wait_for_timeout(150)

        if not save_button.is_enabled():
            raise PaperworkError(
                f"Buganizer Save did not become enabled for {assignee_email}."
            )

        save_button.click()

        # "Close" the edit cleanly by waiting for the popover to disappear.
        editor.wait_for(state="hidden", timeout=12_000)

        # Reacquire after Angular rerender, then verify using visible + ARIA text.
        verify_deadline = time.monotonic() + 12.0
        last_saved = ""
        while time.monotonic() < verify_deadline:
            try:
                assignee_button = get_assignee_button()
                last_saved = assignee_snapshot(assignee_button)
                if assignee_email.lower() in last_saved.lower():
                    print(
                        f"Reassigned Buganizer issue {bug_number} to "
                        f"{assignee_email}."
                    )
                    return True
            except Exception:
                pass
            page.wait_for_timeout(250)

        raise PaperworkError(
            f"Buganizer Save completed, but {assignee_email} was not "
            f"verified as the assignee. Last assignee state: {last_saved!r}"
        )

    except PaperworkError:
        raise
    except Exception as error:
        raise PaperworkError(
            f"Could not reassign Buganizer issue {bug_number} to "
            f"{assignee_email}: {error}"
        ) from error



def reassign_buganizer_issue(page: Any, bug_number: str) -> bool:
    """Reassign an issue after explicit confirmation and verify the result."""
    assignee_name = re.compile(r"^Assignee user avatar", re.IGNORECASE)
    assignee_button = page.get_by_role(
        "button",
        name=assignee_name,
    ).first
    try:
        assignee_button.wait_for(state="visible", timeout=10_000)
        current_assignee = assignee_button.inner_text()
    except Exception as error:
        raise PaperworkError(
            "Could not find the Buganizer Assignee control."
        ) from error

    if BUGANIZER_ASSIGNEE.lower() in current_assignee.lower():
        print(f"Buganizer issue {bug_number} is already assigned correctly.")
        return False

    confirmation = input(
        f"Reassign Buganizer issue {bug_number} to {BUGANIZER_ASSIGNEE}? "
        "Enter Y to confirm: "
    ).strip().lower()
    if confirmation not in {"y", "yes"}:
        raise PaperworkError("Buganizer reassignment was not confirmed.")

    return reassign_buganizer_issue_to(
        page,
        bug_number,
        BUGANIZER_ASSIGNEE,
    )


def open_paperwork_records(
    bug_number: str,
    browser_factory: Callable[[], Any] = BrowserManager,
) -> None:
    """Open Buganizer and the first matching Salesforce Cases result."""
    issue_url = buganizer_url(bug_number)
    set_status(
        "Opening records",
        f"Issue {bug_number}",
        workflow="Paperwork",
    )
    try:
        with browser_factory() as browser:
            browser.page.goto(
                issue_url,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            salesforce_page = browser.context.new_page()
            salesforce_page.goto(
                SALESFORCE_CASES_URL,
                wait_until="domcontentloaded",
                timeout=60_000,
            )
            set_status(
                "Authenticating",
                "Confirm Buganizer and Salesforce access",
                workflow="Paperwork",
            )
            print(f"\nOpened Buganizer issue {bug_number} and Salesforce in Chrome.")
            print("Complete any required Google or Salesforce sign-in.")
            print(
                "Optional: you may manually claim the Salesforce case now. "
                "The automation will recognize if you already own it."
            )
            input(
                "When the Buganizer issue and Salesforce Cases page are both "
                "loaded, press Enter: "
            )

            set_status(
                "Updating Buganizer",
                f"Assignee for issue {bug_number}",
                workflow="Paperwork / Buganizer",
            )
            reassign_buganizer_issue(browser.page, bug_number)
            comment = prompt_bug_comment()
            if comment is None:
                raise PaperworkError("Buganizer comment entry was cancelled.")
            if comment:
                set_status(
                    "Updating Buganizer",
                    f"Comment for issue {bug_number}",
                    workflow="Paperwork / Buganizer",
                )
                post_buganizer_comment(browser.page, bug_number, comment)
            else:
                print("Skipped the Buganizer comment.")

            set_status(
                "Searching Salesforce",
                f"Bug {bug_number}",
                workflow="Paperwork / Salesforce",
            )
            _search_salesforce_case(salesforce_page, bug_number)
            set_status(
                "Claiming Salesforce case",
                f"Bug {bug_number}",
                workflow="Paperwork / Salesforce",
            )
            owner_name = claim_salesforce_case(salesforce_page, bug_number)
            set_status(
                "Viewing records",
                f"Buganizer and Salesforce for {bug_number}",
                workflow="Paperwork",
            )
            print(
                "Opened the first matching Salesforce Cases result and "
                f"assigned it to {owner_name}."
            )
            input("Press Enter when you are finished viewing the records: ")
    except PaperworkError:
        raise
    except Exception as error:
        raise PaperworkError(
            f"Could not open the paperwork records for bug {bug_number}: {error}"
        ) from error


def _search_salesforce_case(page: Any, bug_number: str) -> None:
    """Use Salesforce global search and open the first Cases-table result."""
    _open_salesforce_global_search(page)
    search_input = _topmost_search_input(page)
    if search_input is None:
        raise PaperworkError(
            "Could not find the Salesforce global search field. Confirm that "
            "the Service Console Cases page is loaded and authenticated."
        )

    # Clicking Salesforce's global search can replace or expand the input.
    # Reacquire it after the click, then use real keystrokes because Lightning's
    # controlled search component does not always react to locator.fill().
    search_input.click()
    page.wait_for_timeout(500)
    search_input = _topmost_search_input(page)
    if search_input is None:
        raise PaperworkError(
            "The Salesforce global search field disappeared after it was opened."
        )
    search_input.click()
    try:
        search_input.press("ControlOrMeta+A")
    except Exception:
        try:
            search_input.press("Meta+A")
        except Exception:
            search_input.press("Control+A")
    search_input.press("Backspace")
    search_input.press_sequentially(
        bug_number,
        delay=SALESFORCE_SEARCH_KEY_DELAY_MS,
    )
    if search_input.input_value().strip() != bug_number:
        raise PaperworkError(
            "Could not enter the bug number in Salesforce's top global search."
        )

    result_pattern = re.compile(rf"\bIssue\s+{re.escape(bug_number)}\b", re.IGNORECASE)

    # Lightning renders the suggestions shown beneath the global search as
    # custom elements, not conventional links. Prefer the matching Case result
    # displayed in that instant-results panel and click its host element.
    instant_result_content = (
        page.locator(".instant-result-item__content")
        .filter(has_text=bug_number)
        .first
    )
    instant_result_error: Exception | None = None
    try:
        instant_result_content.wait_for(
            state="visible",
            timeout=SALESFORCE_INSTANT_RESULT_TIMEOUT_MS,
        )
        instant_result_content.click(timeout=3_000)
        return
    except Exception as error:
        instant_result_error = error

    # Compatibility fallback for Salesforce builds that omit the content class.
    # The underscore variant has also appeared in inspected Lightning markup.
    instant_result = (
        page.locator(
            "search-dialog-instant-result-item, "
            "search_dialog-instant-result-item"
        )
        .filter(has_text=bug_number)
        .first
    )
    try:
        instant_result.wait_for(state="visible", timeout=2_000)
        click_targets = (
            instant_result.locator(".instant-result-item__content").first,
            instant_result.get_by_text(result_pattern).first,
            instant_result,
        )
        for target in click_targets:
            try:
                target.click(timeout=3_000)
                return
            except Exception as error:
                instant_result_error = error
    except Exception as error:
        instant_result_error = error

    # Retain compatibility with Salesforce layouts that expose the same instant
    # result as a conventional link, but never submit the global search with
    # Enter. Submitting changes the UI to a different results mode.
    subject_link = page.get_by_role("link").filter(has_text=result_pattern).first
    try:
        subject_link.wait_for(state="visible", timeout=3_000)
        subject_link.click()
        return
    except Exception:
        pass

    # Salesforce layouts vary. The bottom Cases result remains a table row
    # containing the bug number even when the subject link markup changes.
    try:
        row = page.locator("tr").filter(has_text=bug_number).first
        row.wait_for(state="visible", timeout=3_000)
        row.get_by_role("link").first.click()
    except Exception as error:
        detail = (
            f" Instant-result detail: {instant_result_error}"
            if instant_result_error
            else ""
        )
        raise PaperworkError(
            f"Salesforce returned no clickable Cases result for bug {bug_number}."
            f"{detail}"
        ) from error


def _open_salesforce_details_tab(page: Any) -> Any:
    """Open the Salesforce Case Details tab and return its visible tab/link."""
    candidates = (
        page.locator('a[data-tab-value="detailTab"]').first,
        page.locator('a[data-label="Details"]').first,
        page.get_by_role("tab", name="Details", exact=True).first,
        page.get_by_role("link", name="Details", exact=True).first,
    )
    last_error: Exception | None = None
    for candidate in candidates:
        try:
            candidate.wait_for(state="visible", timeout=4_000)
            if candidate.is_enabled():
                candidate.click()
                page.wait_for_timeout(250)
                return candidate
        except Exception as error:
            last_error = error
    raise PaperworkError(
        "Salesforce did not expose the Case Details tab."
    ) from last_error


def _salesforce_current_user_identity(page: Any) -> dict[str, str]:
    """Identify the user authenticated in this Salesforce browser session.

    The owner dialog can contain multiple people.  We therefore resolve the
    logged-in user before clicking an owner option.  The lookup order is:

      1. Salesforce Chatter's same-origin ``users/me`` endpoint;
      2. Lightning/Aura CurrentUser values;
      3. the visible Salesforce profile menu.

    Nothing is typed into Change Owner until we know which person we are
    looking for.
    """
    identity = {"id": "", "name": "", "email": ""}

    # Same-origin Salesforce endpoint.  It uses the already-authenticated
    # Lightning browser session and does not require storing credentials.
    try:
        api_identity = page.evaluate(
            """async () => {
                const versions = ['v65.0','v64.0','v63.0','v62.0','v61.0'];
                for (const version of versions) {
                    try {
                        const response = await fetch(
                            `/services/data/${version}/chatter/users/me`,
                            {credentials: 'same-origin', headers: {'Accept': 'application/json'}}
                        );
                        if (!response.ok) continue;
                        const data = await response.json();
                        return {
                            id: String(data.id || ''),
                            name: String(data.name || data.displayName || ''),
                            email: String(data.email || '')
                        };
                    } catch (_) {}
                }
                return {id:'', name:'', email:''};
            }"""
        )
        if isinstance(api_identity, dict):
            for key in identity:
                value = str(api_identity.get(key, "") or "").strip()
                if value:
                    identity[key] = value
    except Exception:
        pass

    # Lightning/Aura exposes the authenticated user in many org builds.
    if not (identity["id"] and identity["name"]):
        try:
            aura_identity = page.evaluate(
                """() => {
                    const out = {id:'', name:'', email:''};
                    try {
                        if (window.$A && typeof window.$A.get === 'function') {
                            out.id = window.$A.get('$SObjectType.CurrentUser.Id') || '';
                            out.name = window.$A.get('$SObjectType.CurrentUser.Name') || '';
                            out.email = window.$A.get('$SObjectType.CurrentUser.Email') || '';
                        }
                    } catch (_) {}
                    return out;
                }"""
            )
            if isinstance(aura_identity, dict):
                for key in identity:
                    if not identity[key]:
                        value = str(aura_identity.get(key, "") or "").strip()
                        if value:
                            identity[key] = value
        except Exception:
            pass

    if identity["name"] or identity["email"]:
        return identity

    # UI fallback.  Salesforce normally exposes the user's name in/under the
    # profile avatar even when the API/Aura values are unavailable.
    profile_candidates = (
        page.locator('button.branding-userProfile-button').first,
        page.locator('button[title*="View profile"]').first,
        page.locator('button[aria-label*="View profile"]').first,
        page.locator('button[title*="profile"]').first,
        page.locator('button[aria-label*="profile"]').first,
    )
    profile_button = None
    for candidate in profile_candidates:
        try:
            if candidate.is_visible() and candidate.is_enabled():
                profile_button = candidate
                break
        except Exception:
            continue

    if profile_button is None:
        return identity

    try:
        # Avatar metadata sometimes contains the name without opening the menu.
        for selector in ("img", "span", "div"):
            try:
                child = profile_button.locator(selector).first
                for attr in ("title", "alt", "aria-label"):
                    value = child.get_attribute(attr)
                    if value and len(value.strip()) < 120:
                        identity["name"] = value.strip()
                        break
                if identity["name"]:
                    break
            except Exception:
                continue

        profile_button.click()
        page.wait_for_timeout(250)

        menu_roots = (
            page.locator('.oneUserProfileCard:visible').first,
            page.locator('.profile-card:visible').first,
            page.locator('[role="dialog"]:visible').last,
            page.locator('.slds-popover:visible').last,
        )
        visible_text = ""
        for candidate in menu_roots:
            try:
                if candidate.is_visible():
                    visible_text = candidate.inner_text().strip()
                    if visible_text:
                        break
            except Exception:
                continue

        if visible_text:
            email_match = re.search(
                r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}",
                visible_text,
                flags=re.IGNORECASE,
            )
            if email_match:
                identity["email"] = email_match.group(0)

            if not identity["name"]:
                ignored = {
                    "view profile", "settings", "switch to salesforce classic",
                    "log out", "logout",
                }
                for line in visible_text.splitlines():
                    value = " ".join(line.split()).strip()
                    if (
                        value
                        and value.casefold() not in ignored
                        and "@" not in value
                        and len(value) <= 120
                    ):
                        identity["name"] = value
                        break
    except Exception:
        pass
    finally:
        try:
            page.keyboard.press("Escape")
            page.wait_for_timeout(120)
        except Exception:
            pass

    return identity


def _salesforce_case_owner_text(page: Any) -> str:
    """Return the visible current Case Owner field text when available."""
    containers = (
        page.locator(
            '[data-target-selection-name="sfdc:RecordField.Case.OwnerId"]'
        ).first,
        page.locator(
            '[data-target-selection-name*="Case.Owner"]'
        ).first,
    )
    for container in containers:
        try:
            container.wait_for(state="visible", timeout=2_500)
            text = " ".join(container.inner_text().split()).strip()
            if text:
                return text
        except Exception:
            continue
    return ""


def claim_salesforce_case(page: Any, bug_number: str) -> str:
    """Assign the Case to the currently authenticated Salesforce user.

    This preserves the coworker's working Change Owner interaction but replaces
    the terminal prompt used when multiple people appear with automatic matching
    against the authenticated Salesforce identity.
    """
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(150)
        _open_salesforce_details_tab(page)

        identity = _salesforce_current_user_identity(page)
        current_owner = _salesforce_case_owner_text(page)

        def norm(value: str) -> str:
            return " ".join(str(value or "").split()).casefold()

        identity_tokens = [
            norm(identity.get("name", "")),
            norm(identity.get("email", "")),
            norm(identity.get("id", "")),
        ]
        identity_tokens = [token for token in identity_tokens if token]

        # Retry-safe: if the current Case Owner already matches this user,
        # do not open Change Owner at all.
        if current_owner and any(
            token in norm(current_owner) for token in identity_tokens
        ):
            owner = identity.get("name") or identity.get("email") or current_owner
            print(
                f"Salesforce Case for bug {bug_number} is already assigned "
                f"to {owner}; skipping owner change."
            )
            return owner

        owner_button = None
        for control in page.locator('[title="Change Owner"]').all():
            try:
                if control.is_visible() and control.is_enabled():
                    owner_button = control
                    break
            except Exception:
                continue
        if owner_button is None:
            raise PaperworkError(
                "Could not find the visible Change Owner button beside the "
                "Salesforce Case Owner field."
            )

        try:
            owner_button.click(timeout=5_000)
        except Exception:
            if not owner_button.is_visible() or not owner_button.is_enabled():
                raise
            owner_button.click(force=True, timeout=5_000)

        dialog = page.get_by_role(
            "dialog",
            name=re.compile(r"^Change Case Owner$", re.IGNORECASE),
        ).first
        dialog.wait_for(state="visible", timeout=6_000)

        search = dialog.get_by_role("combobox").first
        search.wait_for(state="visible", timeout=5_000)
        search.click()

        def option_text(option: Any) -> str:
            values: list[str] = []
            try:
                values.append(option.inner_text())
            except Exception:
                pass
            for attribute in (
                "data-recordid", "data-value", "value", "title",
                "aria-label", "id",
            ):
                try:
                    value = option.get_attribute(attribute)
                    if value:
                        values.append(str(value))
                except Exception:
                    pass
            try:
                href = option.locator("a").first.get_attribute("href")
                if href:
                    values.append(href)
            except Exception:
                pass
            return " ".join(values)

        def visible_options() -> list[Any]:
            result: list[Any] = []
            options = dialog.get_by_role("option")
            for index in range(options.count()):
                candidate = options.nth(index)
                try:
                    if candidate.is_visible() and candidate.is_enabled():
                        result.append(candidate)
                except Exception:
                    continue
            return result

        def choose_matching(options: list[Any]) -> Any | None:
            if len(options) == 1:
                return options[0]

            user_id = norm(identity.get("id", ""))
            email = norm(identity.get("email", ""))
            name = norm(identity.get("name", ""))

            scored: list[tuple[int, int, Any]] = []
            for index, option in enumerate(options):
                blob = norm(option_text(option))
                score = 0
                if user_id and user_id in blob:
                    score = 100
                elif email and email in blob:
                    score = 95
                elif name:
                    # Owner options normally have the person's name on line 1.
                    lines = [
                        norm(line)
                        for line in option.inner_text().splitlines()
                        if line.strip()
                    ]
                    if lines and lines[0] == name:
                        score = 90
                    elif name in blob:
                        score = 80
                if score:
                    scored.append((score, -index, option))

            if not scored:
                return None
            scored.sort(key=lambda row: (row[0], row[1]), reverse=True)
            return scored[0][2]

        deadline = time.monotonic() + 5.0
        options: list[Any] = []
        while time.monotonic() < deadline:
            options = visible_options()
            if options:
                break
            page.wait_for_timeout(120)

        selected = choose_matching(options)

        # Multiple names: filter using the authenticated user's exact identity.
        if selected is None and (identity.get("name") or identity.get("email")):
            query = identity.get("email") or identity.get("name")
            search.fill("")
            search.type(query, delay=10)
            page.wait_for_timeout(350)

            deadline = time.monotonic() + 5.0
            while time.monotonic() < deadline:
                options = visible_options()
                selected = choose_matching(options)
                if selected is not None:
                    break
                page.wait_for_timeout(120)

        if selected is None:
            options = visible_options()
            if len(options) == 1:
                selected = options[0]
            elif len(options) > 1:
                labels = [
                    " — ".join(
                        line.strip()
                        for line in option.inner_text().splitlines()
                        if line.strip()
                    )
                    for option in options
                ]
                raise PaperworkError(
                    "Salesforce showed multiple Case Owner choices and the "
                    "logged-in user could not be matched automatically. "
                    "Visible choices: " + "; ".join(labels[:8])
                )
            else:
                raise PaperworkError(
                    "Salesforce did not display a selectable Case Owner."
                )

        selected_text = selected.inner_text().strip()
        owner_name = next(
            (line.strip() for line in selected_text.splitlines() if line.strip()),
            "",
        )
        if not owner_name:
            owner_name = identity.get("name") or identity.get("email")
        if not owner_name:
            raise PaperworkError(
                "Salesforce displayed an owner option without a usable name."
            )

        selected.click(timeout=5_000)

        change_owner = dialog.get_by_role(
            "button",
            name="Change Owner",
            exact=True,
        )
        change_owner.wait_for(state="visible", timeout=5_000)
        change_owner.click(timeout=5_000)

        already_owner = dialog.get_by_text(
            re.compile(r"already owns this record", re.IGNORECASE)
        ).first

        deadline = time.monotonic() + 12.0
        while time.monotonic() < deadline:
            try:
                if not dialog.is_visible():
                    break
            except Exception:
                break
            try:
                if already_owner.is_visible():
                    page.keyboard.press("Escape")
                    dialog.wait_for(state="hidden", timeout=5_000)
                    print(
                        f"Salesforce reports that {owner_name} already owns "
                        f"the Case for bug {bug_number}; skipping."
                    )
                    return owner_name
            except Exception:
                pass
            page.wait_for_timeout(160)
        else:
            raise PaperworkError(
                "Salesforce did not close the Change Case Owner dialog."
            )

        _open_salesforce_details_tab(page)
        verify_deadline = time.monotonic() + 10.0
        while time.monotonic() < verify_deadline:
            saved_owner = _salesforce_case_owner_text(page)
            if saved_owner and norm(owner_name) in norm(saved_owner):
                print(
                    f"Assigned Salesforce Case for bug {bug_number} "
                    f"to {owner_name}."
                )
                return owner_name
            page.wait_for_timeout(180)

        raise PaperworkError(
            f"Salesforce changed ownership, but {owner_name} could not be "
            "verified in Case Owner."
        )

    except PaperworkError:
        raise
    except Exception as error:
        raise PaperworkError(
            f"Could not claim the Salesforce Case for bug {bug_number}: {error}"
        ) from error


def _open_salesforce_global_search(page: Any) -> None:
    """Open Salesforce's header Search assistant when it is collapsed."""
    search_button = page.locator('button[aria-label="Search"]').first
    try:
        if search_button.is_visible() and search_button.is_enabled():
            search_button.click()
            page.wait_for_timeout(500)
    except Exception:
        # The expanded search input may already be visible. The caller performs
        # the authoritative input lookup and reports a useful error if needed.
        return


def _topmost_search_input(page: Any) -> Any | None:
    """Select Salesforce's header search, never the lower list-filter search."""
    # Lightning provides several search inputs. Prefer the explicit global
    # header variants before using screen position as a compatibility fallback.
    preferred_selectors = (
        'input[title="Search Salesforce"]',
        'input[aria-label="Search Salesforce"]',
        'input.slds-input[placeholder="Search..."]',
        'input[placeholder="Search..."]',
        'header input[role="combobox"]',
        '[role="banner"] input[role="combobox"]',
        '.slds-global-header input',
    )
    for selector in preferred_selectors:
        for field in page.locator(selector).all():
            try:
                if field.is_visible() and field.is_enabled():
                    return field
            except Exception:
                continue

    candidates: list[tuple[float, Any]] = []
    for field in page.locator("input").all():
        try:
            searchable_text = " ".join(
                field.get_attribute(attribute) or ""
                for attribute in ("placeholder", "title", "aria-label")
            ).lower()
            box = field.bounding_box()
            is_list_filter = "search this list" in searchable_text
            if (
                field.is_visible()
                and field.is_enabled()
                and box
                and "search" in searchable_text
                and not is_list_filter
            ):
                candidates.append((box["y"], field))
        except Exception:
            continue
    return min(candidates, key=lambda item: item[0])[1] if candidates else None

# ---------------------------------------------------------------------------
# Salesforce closeout helpers used by the portable Reassign workflow.
# These are adapted from the Repair Assistant implementation while keeping the
# portable Companion's browser/session architecture unchanged.
# ---------------------------------------------------------------------------

def post_salesforce_feed_comment(
    page: Any,
    bug_number: str,
    comment: str,
) -> bool:
    """Post the same Paperwork Details to the Salesforce Case Feed.

    If the exact text is already visible in the Feed, the step is skipped.
    """
    comment = comment.strip()
    if not comment:
        return False

    def first_visible(candidates: list[Any], timeout: int = 3_000) -> Any:
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                candidate.wait_for(state="visible", timeout=timeout)
                if candidate.is_enabled():
                    return candidate
            except Exception as error:
                last_error = error
        raise PaperworkError(
            "Salesforce did not expose the expected Case Feed control."
        ) from last_error

    try:
        feed_tab = first_visible(
            [
                page.locator('a[data-tab-value="feedTab"]').first,
                page.locator('a[data-label="Feed"]').first,
                page.get_by_role("tab", name="Feed", exact=True).first,
                page.get_by_role("link", name="Feed", exact=True).first,
            ]
        )
        feed_tab.click()
        page.wait_for_timeout(250)

        normalized = " ".join(comment.split())

        # Retry-safe check.  Recent Case Feed items are rendered in the visible
        # tab; if this exact Details text is already there, do not post again.
        try:
            body_text = " ".join(page.locator("body").inner_text().split())
            if normalized and normalized in body_text:
                print(
                    f"Salesforce Feed for bug {bug_number} already contains "
                    "the submitted Details; skipping."
                )
                return False
        except Exception:
            pass

        share_update = first_visible(
            [
                page.locator('button[title="Share an update..."]').first,
                page.get_by_role(
                    "button", name="Share an update...", exact=True
                ).first,
                page.get_by_text("Share an update...", exact=True).first,
            ],
            timeout=4_000,
        )
        share_update.click()

        for post_control in (
            page.get_by_role("tab", name="Post", exact=True).first,
            page.get_by_role("button", name="Post", exact=True).first,
            page.locator('a[title="Post"]').first,
        ):
            try:
                post_control.wait_for(state="visible", timeout=1_200)
                post_control.click()
                break
            except Exception:
                continue

        editor = first_visible(
            [
                page.locator('textarea[placeholder*="Share an update"]').first,
                page.locator('textarea[aria-label*="Share an update"]').first,
                page.locator(
                    'div[role="textbox"][contenteditable="true"]'
                    '[data-placeholder*="Share"]'
                ).first,
                page.locator(
                    'lightning-input-rich-text div.ql-editor'
                    '[contenteditable="true"]'
                ).first,
                page.locator('div.ql-editor[contenteditable="true"]').first,
                page.locator(
                    'div[role="textbox"][contenteditable="true"]'
                ).first,
            ],
            timeout=4_000,
        )
        editor.scroll_into_view_if_needed()
        editor.click()
        editor.fill(comment)

        entered = (
            editor.input_value()
            if editor.evaluate("element => element.tagName === 'TEXTAREA'")
            else editor.inner_text()
        )
        if " ".join(entered.split()) != normalized:
            raise PaperworkError(
                "Salesforce did not retain the complete Feed Details."
            )

        share_button = first_visible(
            [
                page.locator(
                    'button[title="Click, or press Ctrl+Enter"]'
                ).first,
                page.get_by_role("button", name="Share", exact=True).first,
                page.get_by_role("button", name="Post", exact=True).first,
                page.locator('button:has-text("Share")').first,
            ],
            timeout=3_000,
        )

        deadline = time.monotonic() + 8.0
        while time.monotonic() < deadline:
            if share_button.is_enabled():
                break
            page.wait_for_timeout(120)
        else:
            raise PaperworkError(
                "Salesforce Feed Share button did not become enabled."
            )

        share_button.click()

        clear_deadline = time.monotonic() + 15.0
        while time.monotonic() < clear_deadline:
            try:
                remaining = (
                    editor.input_value()
                    if editor.evaluate(
                        "element => element.tagName === 'TEXTAREA'"
                    )
                    else editor.inner_text()
                )
                if not remaining.strip():
                    break
            except Exception:
                break
            page.wait_for_timeout(160)
        else:
            raise PaperworkError(
                "Salesforce did not clear the Feed editor after Share."
            )

        print(f"Posted Details to Salesforce Feed for bug {bug_number}.")
        return True

    except PaperworkError:
        raise
    except Exception as error:
        raise PaperworkError(
            f"Could not post Details to Salesforce Feed for bug "
            f"{bug_number}: {error}"
        ) from error


def set_salesforce_case_description(
    page: Any,
    bug_number: str,
    details: str,
) -> bool:
    """Write the same Paperwork Details into Salesforce Case Description.

    Blank Details are intentionally skipped. The function is retry-safe for the
    active session: when the exact text is already present, it makes no change.
    """
    details = str(details or "").strip()
    if not details:
        return False

    try:
        _open_salesforce_details_tab(page)

        description_container = page.locator(
            '[data-target-selection-name="sfdc:RecordField.Case.Description"]'
        ).first
        description_container.wait_for(state="visible", timeout=8_000)

        existing = " ".join(description_container.inner_text().split())
        normalized = " ".join(details.split())
        if normalized and normalized in existing:
            print(
                f"Salesforce Description for bug {bug_number} already contains "
                "the submitted Details; skipping."
            )
            return False

        edit_description = None
        candidates = (
            description_container.locator(
                'button[title="Edit Description"]'
            ).first,
            page.locator('button[title="Edit Description"]').first,
            page.get_by_role(
                "button",
                name="Edit Description",
                exact=True,
            ).first,
        )
        for candidate in candidates:
            try:
                candidate.wait_for(state="visible", timeout=3_000)
                if candidate.is_enabled():
                    edit_description = candidate
                    break
            except Exception:
                continue

        if edit_description is None:
            raise PaperworkError(
                "Salesforce did not expose the Edit Description control."
            )

        edit_description.click()

        editor = None
        for candidate in (
            page.locator('textarea[name="Description"]:visible').first,
            page.locator('textarea[aria-label="Description"]:visible').first,
            page.locator('textarea:visible').first,
        ):
            try:
                candidate.wait_for(state="visible", timeout=4_000)
                if candidate.is_enabled():
                    editor = candidate
                    break
            except Exception:
                continue

        if editor is None:
            raise PaperworkError(
                "Salesforce opened Description editing but its text field "
                "could not be found."
            )

        # This field is the Salesforce Case Description for this paperwork
        # closeout. Store the same Details the technician committed to Buganizer.
        editor.click()
        editor.fill(details)
        if " ".join(editor.input_value().split()) != normalized:
            raise PaperworkError(
                "Salesforce did not retain the complete Description text."
            )

        save = None
        for candidate in (
            page.locator('button[name="SaveEdit"]:visible').first,
            page.get_by_role("button", name="Save", exact=True).last,
            page.locator('button:visible:has-text("Save")').last,
        ):
            try:
                candidate.wait_for(state="visible", timeout=4_000)
                if candidate.is_enabled():
                    save = candidate
                    break
            except Exception:
                continue

        if save is None:
            raise PaperworkError(
                "Salesforce Description editor did not expose a Save button."
            )

        save.click()

        # Inline edit should close and the saved Description should render.
        try:
            edit_description.wait_for(state="visible", timeout=12_000)
        except Exception:
            pass

        verify_deadline = time.monotonic() + 12.0
        while time.monotonic() < verify_deadline:
            try:
                description_container.wait_for(state="visible", timeout=1_000)
                saved = " ".join(description_container.inner_text().split())
                if normalized in saved:
                    print(
                        f"Saved Salesforce Description for bug {bug_number}."
                    )
                    return True
            except Exception:
                pass
            page.wait_for_timeout(180)

        raise PaperworkError(
            "Salesforce saved the Description edit, but the submitted text "
            "could not be verified."
        )

    except PaperworkError:
        raise
    except Exception as error:
        raise PaperworkError(
            f"Could not update Salesforce Description for bug "
            f"{bug_number}: {error}"
        ) from error


def set_salesforce_case_fields(
    page: Any,
    bug_number: str,
    fields: dict[str, str],
) -> bool:
    """Set routed Salesforce Case fields and skip values already correct.

    Important: Salesforce exposes both ``Component`` and ``Assembly Component``
    on the Case. They are different fields. Reassign routing uses ``Component``.
    ``Assembly Component`` is intentionally left untouched.
    """

    def first_visible(candidates: list[Any], timeout: int = 5_000) -> Any:
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                candidate.wait_for(state="visible", timeout=timeout)
                if candidate.is_enabled():
                    return candidate
            except Exception as error:
                last_error = error
        raise PaperworkError(
            "Salesforce did not expose the expected Case field control."
        ) from last_error

    def normalized(value: Any) -> str:
        return " ".join(str(value or "").split()).strip()

    # Exact live Salesforce labels. Do NOT alias Component to Assembly Component.
    field_labels = {
        "Operation": ("Operation",),
        "Type": ("Type",),
        "Sub Category": ("Sub Category",),
        "Component": ("Component",),
        "Resolution Reason": ("Resolution Reason",),
    }

    # Known Lightning target-selection names. Component and Assembly Component
    # remain intentionally separate.
    target_selection_names = {
        "Operation": (
            "sfdc:RecordField.Case.Operation__c",
        ),
        "Type": (
            "sfdc:RecordField.Case.Type",
        ),
        "Sub Category": (
            "sfdc:RecordField.Case.Sub_Category__c",
            "sfdc:RecordField.Case.SubCategory__c",
        ),
        "Component": (
            "sfdc:RecordField.Case.Component__c",
        ),
        "Resolution Reason": (
            "sfdc:RecordField.Case.Resolution_Reason__c",
            "sfdc:RecordField.Case.ResolutionReason__c",
        ),
    }

    def display_container(label: str) -> Any | None:
        for target in target_selection_names.get(label, ()):
            container = page.locator(
                f'[data-target-selection-name="{target}"]'
            ).first
            try:
                if container.is_visible():
                    return container
            except Exception:
                continue

        # Fallback: locate the exact visible label and its own field wrapper.
        # Exact matching is critical so "Component" never resolves to
        # "Assembly Component".
        for visible_label in field_labels.get(label, (label,)):
            label_locator = page.get_by_text(
                re.compile(rf"^{re.escape(visible_label)}$", re.IGNORECASE),
                exact=True,
            ).first
            try:
                label_locator.wait_for(state="visible", timeout=900)
                container = label_locator.locator(
                    "xpath=ancestor::*[.//button[contains(@title,'Edit')]][1]"
                )
                if container.is_visible():
                    return container
            except Exception:
                continue
        return None

    def displayed_value(label: str) -> str:
        """Read only the saved field value, never the edit button title."""
        container = display_container(label)
        if container is None:
            return ""

        # Prefer Salesforce's output-field value nodes.
        value_selectors = (
            "lightning-formatted-text",
            "lightning-formatted-rich-text",
            ".test-id__field-value",
            ".slds-form-element__static",
            "slot[name='outputField']",
        )
        for selector in value_selectors:
            nodes = container.locator(selector)
            for index in range(nodes.count()):
                node = nodes.nth(index)
                try:
                    if node.is_visible():
                        value = normalized(node.inner_text())
                        if value and value.casefold() != label.casefold():
                            return value
                except Exception:
                    continue

        # Text fallback: explicitly remove label text and edit-action text.
        try:
            lines = [
                normalized(line)
                for line in container.inner_text().splitlines()
                if normalized(line)
            ]
        except Exception:
            return ""

        ignored = {
            label.casefold(),
            f"edit {label}".casefold(),
            "edit",
        }
        for line in lines:
            lowered = line.casefold()
            if lowered in ignored:
                continue
            if lowered.startswith("edit "):
                continue
            return line
        return ""

    def find_combobox(label: str) -> tuple[Any, str]:
        labels = field_labels.get(label, (label,))
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            for actual_label in labels:
                controls = page.locator(
                    f'button[role="combobox"][aria-label="{actual_label}"]'
                )
                for index in range(controls.count()):
                    candidate = controls.nth(index)
                    try:
                        if candidate.is_visible() and candidate.is_enabled():
                            return candidate, actual_label
                    except Exception:
                        continue
            page.wait_for_timeout(100)
        raise PaperworkError(
            f"Salesforce did not expose the visible {label} dropdown."
        )

    def select_picklist(label: str, value: str) -> bool:
        control, actual_label = find_combobox(label)
        current = normalized(
            control.get_attribute("data-value") or control.inner_text()
        )
        if current == value:
            print(f"Salesforce: {label} is already {value}; skipping.")
            return False

        control.click()
        option_sets = [
            page.locator(
                f'lightning-base-combobox-item[data-value="{value}"]'
            ),
            page.locator(f'[role="option"][data-value="{value}"]'),
            page.get_by_role("option", name=value, exact=True),
            page.get_by_text(value, exact=True),
        ]

        option = None
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline and option is None:
            for options in option_sets:
                for index in range(options.count()):
                    candidate = options.nth(index)
                    try:
                        if not candidate.is_visible() or not candidate.is_enabled():
                            continue
                        candidate_value = normalized(
                            candidate.get_attribute("data-value")
                        )
                        candidate_text = normalized(candidate.inner_text())
                        if candidate_value == value or candidate_text == value:
                            option = candidate
                            break
                    except Exception:
                        continue
                if option is not None:
                    break
            if option is None:
                page.wait_for_timeout(100)

        if option is None:
            # Same fallback used in the coworker's implementation.
            page.keyboard.type(value, delay=12)
            page.keyboard.press("Enter")
        else:
            option.click()

        page.wait_for_timeout(180)
        selected = normalized(
            control.get_attribute("data-value") or control.inner_text()
        )
        if selected != value:
            raise PaperworkError(
                f"Salesforce did not retain {value} in {actual_label}."
            )
        return True

    try:
        _open_salesforce_details_tab(page)

        desired: dict[str, str] = {
            key: normalized(raw_value)
            for key, raw_value in fields.items()
            if key in field_labels and normalized(raw_value)
        }

        # Inspect before editing. This makes retries safe.
        mismatched: dict[str, str] = {}
        for label, value in desired.items():
            current = displayed_value(label)
            if current == value:
                print(f"Salesforce: {label} already {value}; skipping.")
            else:
                mismatched[label] = value

        if not mismatched:
            print(
                f"Salesforce routing fields for bug {bug_number} are already "
                "correct; no edit needed."
            )
            return False

        operation_container = display_container("Operation")
        candidates: list[Any] = []
        if operation_container is not None:
            candidates.extend(
                [
                    operation_container.locator(
                        'button[title="Edit Operation"]'
                    ).first,
                    operation_container.locator(
                        'button[title^="Edit"]'
                    ).first,
                ]
            )
        candidates.extend(
            [
                page.locator('button[title="Edit Operation"]').first,
                page.get_by_role(
                    "button", name="Edit Operation", exact=True
                ).first,
            ]
        )

        edit_operation = first_visible(candidates, timeout=6_000)
        edit_operation.click()

        ordered_labels = (
            "Operation",
            "Type",
            "Sub Category",
            "Component",
            "Resolution Reason",
        )
        changed = False
        for label in ordered_labels:
            value = mismatched.get(label, "")
            if value:
                print(f"Salesforce: setting {label} to {value}...")
                changed = select_picklist(label, value) or changed

        if not changed:
            try:
                page.get_by_role("button", name="Cancel", exact=True).click()
            except Exception:
                page.keyboard.press("Escape")
            return False

        save = first_visible(
            [
                page.locator('button[name="SaveEdit"]:visible').first,
                page.get_by_role("button", name="Save", exact=True).first,
                page.locator('button:visible:has-text("Save")').first,
            ]
        )
        save.click()

        try:
            edit_operation.wait_for(state="visible", timeout=12_000)
        except Exception:
            pass

        _open_salesforce_details_tab(page)

        # Verify the exact fields requested by the route. Assembly Component is
        # intentionally not part of this verification.
        deadline = time.monotonic() + 10.0
        last_wrong: list[str] = []
        while time.monotonic() < deadline:
            wrong: list[str] = []
            for label, value in desired.items():
                current = displayed_value(label)
                if current != value:
                    wrong.append(
                        f"{label}={current!r}, expected {value!r}"
                    )
            if not wrong:
                print(
                    f"Saved and verified Salesforce routing fields for "
                    f"bug {bug_number}."
                )
                return True
            last_wrong = wrong
            page.wait_for_timeout(180)

        raise PaperworkError(
            "Salesforce saved the Case fields, but verification failed: "
            + "; ".join(last_wrong)
        )

    except PaperworkError:
        raise
    except Exception as error:
        raise PaperworkError(
            f"Could not set Salesforce Case fields for bug "
            f"{bug_number}: {error}"
        ) from error


def get_salesforce_case_status(page: Any) -> str:
    """Return the currently saved Salesforce Case Status from Details.

    This reads the displayed value only and ignores the edit control label.
    """
    _open_salesforce_details_tab(page)

    status_container = page.locator(
        '[data-target-selection-name="sfdc:RecordField.Case.Status"]'
    ).first
    status_container.wait_for(state="visible", timeout=8_000)

    # Prefer Salesforce output value nodes.
    for selector in (
        "lightning-formatted-text",
        ".test-id__field-value",
        ".slds-form-element__static",
    ):
        nodes = status_container.locator(selector)
        for index in range(nodes.count()):
            node = nodes.nth(index)
            try:
                if node.is_visible():
                    value = " ".join(node.inner_text().split()).strip()
                    if value and value.casefold() not in {
                        "status",
                        "edit status",
                    }:
                        return value
            except Exception:
                continue

    # Text fallback.
    try:
        lines = [
            " ".join(line.split()).strip()
            for line in status_container.inner_text().splitlines()
            if " ".join(line.split()).strip()
        ]
    except Exception as error:
        raise PaperworkError(
            f"Could not read the Salesforce Case Status: {error}"
        ) from error

    for line in lines:
        lowered = line.casefold()
        if lowered in {"status", "edit status"}:
            continue
        if lowered.startswith("edit "):
            continue
        return line

    raise PaperworkError("Salesforce Case Status could not be determined.")


def wait_for_salesforce_bug_sync(
    page: Any,
    bug_number: str,
    *,
    timeout_seconds: float = 120.0,
) -> str:
    """Wait until Buganizer's async update has reached Salesforce.

    The backend synchronization marks the Case as ``Customer Responded``.
    Salesforce must not be mutated before that state appears, because an
    in-flight Buganizer -> Salesforce sync can otherwise overwrite/reopen the
    Case after our closeout.

    ``Closed`` is also accepted because it means this Case has already passed
    the synchronization point and was previously completed.

    The poll is event/state driven rather than a blind fixed sleep:
      * inspect immediately;
      * briefly allow Lightning to update its live DOM;
      * refresh at a bounded cadence only while still waiting;
      * stop as soon as the authoritative Status is observed.
    """
    accepted = {"customer responded", "closed"}
    deadline = time.monotonic() + timeout_seconds
    last_status = ""
    last_reload = 0.0
    poll_interval = 0.45

    while time.monotonic() < deadline:
        try:
            status = get_salesforce_case_status(page)
            last_status = status
            if status.casefold() in accepted:
                print(
                    f"Salesforce sync ready for bug {bug_number}: "
                    f"Status={status}."
                )
                return status
        except PaperworkError:
            # The Lightning record may be rerendering during an async refresh.
            pass

        now = time.monotonic()

        # Give Lightning a chance to receive/render the backend update without
        # an expensive reload first. Once waiting longer than ~2 seconds,
        # refresh no more than once every 1.8 seconds so we see server-side
        # changes without hammering Salesforce.
        elapsed = timeout_seconds - max(0.0, deadline - now)
        if elapsed >= 2.0 and (now - last_reload) >= 1.8:
            try:
                page.reload(
                    wait_until="domcontentloaded",
                    timeout=30_000,
                )
                last_reload = time.monotonic()
                _open_salesforce_details_tab(page)
            except Exception:
                # A transient Salesforce refresh failure is not proof the sync
                # failed; keep polling until the overall deadline.
                pass

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break

        page.wait_for_timeout(
            int(min(poll_interval, remaining) * 1000)
        )
        poll_interval = min(1.25, poll_interval * 1.15)

    detail = (
        f" Last observed Status: {last_status!r}."
        if last_status
        else ""
    )
    raise PaperworkError(
        "Salesforce is still waiting for the Buganizer update. "
        "The Case did not reach 'Customer Responded' before the safety timeout. "
        "No Salesforce closeout changes were made."
        + detail
    )


def close_salesforce_case(page: Any, bug_number: str) -> None:
    """Set the open Salesforce Case Status to Closed and verify the save."""

    def first_visible(candidates: list[Any], timeout: int = 5_000) -> Any:
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                candidate.wait_for(state="visible", timeout=timeout)
                if candidate.is_enabled():
                    return candidate
            except Exception as error:
                last_error = error
        raise PaperworkError(
            "Salesforce did not expose the expected Case Status control."
        ) from last_error

    try:
        details_tab = first_visible(
            [
                page.locator('a[data-tab-value="detailTab"]').first,
                page.locator('a[data-label="Details"]').first,
                page.get_by_role("tab", name="Details", exact=True).first,
                page.get_by_role("link", name="Details", exact=True).first,
            ]
        )
        details_tab.click()

        status_container = page.locator(
            '[data-target-selection-name="sfdc:RecordField.Case.Status"]'
        ).first
        status_container.wait_for(state="visible", timeout=8_000)
        if re.search(r"\bClosed\b", status_container.inner_text()):
            print(f"Salesforce Case for bug {bug_number} is already Closed.")
            return

        edit_status = first_visible(
            [
                status_container.locator('button[title="Edit Status"]').first,
                page.locator('button[title="Edit Status"]').first,
                page.get_by_role(
                    "button", name="Edit Status", exact=True
                ).first,
            ]
        )
        edit_status.click()

        status = first_visible(
            [
                page.locator(
                    'button[role="combobox"][aria-label="Status"]'
                ).first
            ],
            timeout=8_000,
        )
        current = (
            status.get_attribute("data-value") or status.inner_text()
        ).strip()

        if current != "Closed":
            status.click()
            closed_options = [
                page.locator(
                    'lightning-base-combobox-item[data-value="Closed"]'
                ),
                page.locator('[role="option"][data-value="Closed"]'),
                page.get_by_text("Closed", exact=True),
            ]
            closed = None
            deadline = time.monotonic() + 6.0
            while time.monotonic() < deadline and closed is None:
                for options in closed_options:
                    for index in range(options.count()):
                        candidate = options.nth(index)
                        try:
                            if candidate.is_visible() and candidate.is_enabled():
                                value = (
                                    candidate.get_attribute("data-value") or ""
                                ).strip()
                                text = " ".join(candidate.inner_text().split())
                                if value == "Closed" or text == "Closed":
                                    closed = candidate
                                    break
                        except Exception:
                            continue
                    if closed is not None:
                        break
                if closed is None:
                    page.wait_for_timeout(120)

            if closed is None:
                page.keyboard.type("Closed", delay=20)
                page.keyboard.press("Enter")
            else:
                closed.click()

            page.wait_for_timeout(250)
            selected = (
                status.get_attribute("data-value") or status.inner_text()
            ).strip()
            if selected != "Closed":
                raise PaperworkError(
                    "Salesforce did not retain Closed in the Status dropdown."
                )

        save = first_visible(
            [
                page.locator('button[name="SaveEdit"]').first,
                page.get_by_role("button", name="Save", exact=True).first,
                page.locator('button:has-text("Save")').first,
            ]
        )
        save.click()

        edit_status.wait_for(state="visible", timeout=12_000)
        status_container.wait_for(state="visible", timeout=5_000)
        if not re.search(r"\bClosed\b", status_container.inner_text()):
            raise PaperworkError(
                "Salesforce saved the Case, but Status was not verified as Closed."
            )

        print(f"Closed the Salesforce Case for bug {bug_number}.")

    except PaperworkError:
        raise
    except Exception as error:
        raise PaperworkError(
            f"Could not close the Salesforce Case for bug {bug_number}: "
            f"{error}"
        ) from error

