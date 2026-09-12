# Package notes

This is a portable source package, not one universal executable. Windows, macOS, Linux, and ChromeOS use different runtime/browser binaries, so the package includes platform launchers that create the correct local environment on first run.

The architecture intentionally remains local-only (`127.0.0.1:8765`). The shared Google Apps Script map talks to the Companion running on the same device. This preserves the existing security model and avoids moving authenticated Buganizer/Salesforce browser sessions to a remote server.

For ChromeOS, use the Linux development environment (Crostini). Android/iOS are not supported by the current Playwright-based architecture.


## v3.3 UI ownership

- The startup Companion tab remains in the Playwright browser so a user can end the entire Companion session without starting paperwork.
- That startup page is now a compact status/session-control UI.
- The Paperwork window opened by **Begin** no longer contains **End session**. Its **Exit** action closes/resets only the current paperwork workspace.
- The full Companion can only be stopped from the startup Playwright Companion tab.


## v3.4 session cleanup and authentication

- **End session** now shuts down the localhost service, invalidates the active workspace,
  closes the entire Playwright browser context (Companion, Buganizer, Salesforce), and
  broadcasts a shutdown event so any Begin popup closes too.
- On macOS, the `.command` launcher captures its own Terminal window and closes that exact
  window after a clean Companion shutdown.
- Buganizer is considered connected only on Partner IssueTracker `/issues` routes.
- Salesforce is considered connected only after it reaches an authenticated Lightning
  `/lightning/...` route; generic Salesforce login hosts no longer count.
- The startup browser stays visible while either service requires sign-in.
- After both indicators are green, the Companion control tab is brought forward for a
  3-second confirmation period before the managed browser minimizes.


## v3.5 authentication + shutdown reliability

- Startup status now means **application ready**, not merely "the URL looks like a login host".
- Buganizer turns green only on Partner IssueTracker `/issues` after the app shell is present.
- Salesforce turns green only on a Lightning `/lightning/...` route after the Lightning UI is visible.
- Salesforce/Okta login no longer falsely marks Salesforce connected or causes premature minimizing.
- The managed browser stays visible whenever either login is still required.
- If both sessions are already valid, startup minimizes quickly; after an interactive login, the final
  two-green state remains visible briefly before minimizing.
- The Begin popup now performs a tiny local `/health` lifecycle check so **End session** closes it even
  though it may be running in a different Chrome profile from the Playwright control tab.
- Shutdown exposes `shutting_down=true` for a short grace period, then closes Playwright, the server,
  and the launcher terminal as before.


## v3.6 startup UI cleanup

- Removed redundant healthy-state copy from the Companion control page.
- The ready state now shows only the title, service indicators, and End session control.
- Setup messages are action-oriented and appear only when the user needs to sign in or wait.
- The extra connected-status message is hidden when both services are healthy.


## v3.11 Salesforce Reassign integration

- Existing map communication, startup authentication, Buganizer Commit behavior, launchers, profile storage, and shutdown behavior are unchanged.
- Reassign is now two-stage: Buganizer first, then Salesforce.
- The Salesforce stage assigns the Case to the current Salesforce user, posts the same Details to the Case Feed, fills the approved team route fields, saves them, and closes the Case.
- Team route choices are centralized in `salesforce_routes.py`.
- Salesforce steps are tracked in session state so retrying after a later Salesforce error does not intentionally repeat earlier completed Salesforce steps.
- Claim remains unchanged for now.


## v3.11 Salesforce Reassign correction

The portable Companion now follows the Repair Assistant Salesforce sequence more
closely instead of treating Salesforce as a generic follow-up action:

1. Reopen and verify the exact Salesforce Case.
2. Return to **Details** and inspect the current Case Owner.
3. Identify the logged-in Salesforce user.
4. If ownership is different, use the visible **Change Owner** dialog and select
   that exact user. Multiple visible owner suggestions are matched using the
   authenticated Salesforce user id/name/email instead of a terminal prompt.
5. Return to **Details**.
6. Save the same Paperwork Details text into the Salesforce **Description** field.
7. Return/remain on **Details** and fill the route-specific Case dropdown fields.
8. Save the routed fields.
9. Edit Status to **Closed**, save, and verify Closed.

Buganizer still commits first. A Salesforce failure does not intentionally
re-run the completed Buganizer mutation. Salesforce stages are tracked so a
retry can continue from the first incomplete Salesforce stage.


## v3.11 Salesforce Reassign reliability

- Restored the coworker's actual Salesforce Feed workflow for Paperwork Details:
  Feed -> Share an update -> Share.
- Case Owner is checked first. If it already matches the authenticated Salesforce
  user, Change Owner is skipped.
- When Change Owner lists multiple people, the Companion identifies the current
  Salesforce user from the authenticated session and filters/matches that exact
  person instead of choosing the first result.
- Route fields are inspected before editing. Values that already match are skipped,
  and Salesforce edit mode is not opened at all when every routed field is correct.
- The live Salesforce field label `Assembly Component` is now used, with
  compatibility for older markup that still exposes `Component`.
- Status is still skipped when the Case is already Closed.
- The Paperwork popup no longer treats two brief /health misses during a long
  Salesforce operation as a stopped Companion. This prevents the UI from
  interrupting an active Salesforce request and reduces raw `Failed to fetch`
  errors.


## v3.11 Salesforce Component verification fix

- Salesforce `Component` and `Assembly Component` are treated as two different fields.
- Reassign routes populate and verify `Component`.
- `Assembly Component` is left untouched.
- Saved-value verification ignores the edit-button text (for example,
  `Edit Component`) so a successful Salesforce save does not produce a false
  verification failure.


## v3.11 Buganizer -> Salesforce synchronization barrier

Salesforce closeout now waits for the backend Buganizer synchronization before
changing Salesforce. The Case must reach **Customer Responded** before owner,
Feed, route-field, or Closed mutations begin. A Case that is already **Closed**
is also accepted for retry/recovery.

The wait is state-driven rather than a blind fixed sleep: the Companion checks
the live Status immediately, gives Lightning a short chance to update, then
refreshes at a bounded cadence until the state appears or a 120-second safety
timeout expires. If synchronization does not arrive, Salesforce is left
untouched and the user gets a retry-safe error.

This removes the race where Salesforce could be closed first and then reopened
by the later Buganizer synchronization.
