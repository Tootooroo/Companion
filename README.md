# MTV MAP Companion

MTV MAP Companion is the local desktop helper used by the shared **MTV Robot Map** for the Paperwork workflow.

The map itself runs in a normal web browser. The Companion runs on the technician's own computer and gives the map a safe local service at:

```text
http://127.0.0.1:8765
```

`127.0.0.1` means **this computer only**. The Companion is not a public server and is not meant to be exposed to the internet or to other computers on the network.

> **Important:** Read `INSTALL.md` before the first run. Follow the instructions for your operating system. Do not run the Companion from inside the ZIP file.

---

## What the Companion does

When the Companion starts:

1. It creates or reuses its private Python environment.
2. It starts the local service on `127.0.0.1:8765`.
3. It starts a managed Chrome/Chromium browser using Playwright.
4. It opens:
   - the small **MTV Companion** control/status page,
   - **Buganizer**,
   - **Salesforce**.
5. It checks whether Buganizer and Salesforce are actually signed in and usable.
6. If sign-in is required, the browser stays visible so the user can complete normal Google / Okta / Salesforce authentication.
7. When both services are connected, the managed browser minimizes and waits for the map.

The user can then open the MTV Robot Map and choose:

**Paperwork → Begin**

The map checks the local Companion, sends the selected robot and bug information to it, and opens a separate **MTV Paperwork** window.

The Companion then:

- opens the exact Buganizer issue,
- opens the matching Salesforce Case,
- keeps the local Paperwork UI on the left side of the display,
- keeps the managed Buganizer/Salesforce browser available on the right,
- lets the user choose **Claim**, **Reassign**, or **Exit**.

---

## Important behavior of Claim and Reassign

The Companion opens the exact Buganizer issue and matching Salesforce Case before enabling Paperwork actions.

### Claim

Claim is intentionally unchanged in v3.11. It currently updates **Buganizer only**:

- assigns the Buganizer issue to `robotics-support@google.com`;
- posts optional Details as a Buganizer comment.

Salesforce Claim automation will be handled separately in a later workflow update.

### Reassign

Reassign is now a two-stage workflow.

**Stage 1 — Buganizer**

1. Choose a team.
2. Confirm the Buganizer assignee.
3. Enter optional Details.
4. Press **Commit**.
5. The Companion posts the Details to Buganizer (when supplied), changes the Buganizer assignee, and verifies the saved result.

**Stage 2 — Salesforce**

After Buganizer succeeds, the same Paperwork window automatically changes to the Salesforce step. The user selects only the route choices that cannot be known automatically. The Companion then:

1. returns to the exact Salesforce Case for the same 9-digit Buganizer ID;
2. checks the current Case Owner and changes it to the logged-in Salesforce user when needed;
3. saves the **same Details** into the Salesforce Case **Description** when Details were supplied;
4. fills the routed Salesforce Case fields;
5. saves the Case fields;
6. sets Case Status to **Closed**;
7. verifies the closeout before showing completion.

If Salesforce fails after Buganizer has already succeeded, the UI stays on the Salesforce stage. Retrying the Salesforce step does **not** intentionally repeat completed steps from the current session.

### Salesforce Reassign routes

The route table is stored in `salesforce_routes.py`.

**Mechatronics**

- **MANUS** → Operation `Data Collection / Teleoperation`; Type `Hardware`; Sub Category `Teleop Headset & Accessories`; Component `Manus`; Resolution Reason `Google Migrated`.
- **OTHER** → Operation `Data Collection / Teleoperation`; Type `Hardware`; Sub Category `Teleop Headset & Accessories`; Component `Misc. HARDWARE`; Resolution Reason `Google Migrated`.

**Lab Build Team**

- **GANTRY** → Operation `Robot Start-Up`; Type `Hardware`; Sub Category `Gantry`; Component `Full Assembly`; Resolution Reason `Google Migrated`.
- **SHARPA** → user chooses Operation (`Data Collection / Teleoperation` or `Evaluation / Autonomous Behavior`) and Sub Category (`R Hand` or `L Hand`); Type is `Hardware`; Component is `Sharpa Cable`; Resolution Reason is `Google Migrated`.
- **ESTOP** → Operation `Robot Positioning / Locomotion`; Type `Hardware`; Sub Category `E-Stop`; Component `E-Stop`; Resolution Reason `Google Migrated`.

**Release Team**

- user chooses Operation: `Robot Positioning / Locomotion` or `Robot Start-Up`;
- Type is `Software`;
- user chooses Component: `Ansible`, `Apollo Operator`, `Robotics UI`, `SW Update`, `Configuration`, or `Unknown Software`;
- Resolution Reason is `Google Migrated`.

**Research Team**

- user chooses Operation: `Robot Positioning / Locomotion` or `Evaluation / Autonomous Behavior`;
- Type is `Software`;
- user chooses Component: `Apollo Operator`, `Helios`, `Robotics UI`, `Configuration`, `Orca`, `Tracking/IK`, or `Unknown Software`;
- Resolution Reason is `Google Migrated`.

**Engineering Team**

- user chooses Operation: `Robot Positioning / Locomotion` or `Evaluation / Autonomous Behavior`;
- Type is `Software`;
- user chooses Component: `Apollo Operator`, `Helios`, `Robotics UI`, `Orca`, `Configuration`, or `Unknown Software`;
- Resolution Reason is `Google Migrated`.

**Other / `fedynchuk@google.com`**

- Operation `Robot Start-Up`;
- Type `Software`;
- Component `Dev PC`;
- Resolution Reason `Google Migrated`.

Software routes above intentionally do not set a Sub Category because no Sub Category value was provided in the approved route table.


---

## The two Companion interfaces

There are two different local interfaces on purpose.

### 1. MTV Companion control page

This page lives inside the Playwright-managed browser.

Its job is simple:

- show Buganizer connection status,
- show Salesforce connection status,
- provide **End session**.

When both services are connected, the managed browser minimizes automatically.

If either service needs sign-in, the browser remains visible.

### 2. MTV Paperwork window

This is the window opened after **Paperwork → Begin** from the map.

It shows:

- robot,
- Buganizer issue,
- Salesforce record status,
- Claim,
- Reassign,
- Exit.

**Exit** ends only the current robot paperwork workspace.

It does **not** stop the Companion.

To stop the entire Companion, use **End session** from the MTV Companion control page in the managed browser.

---

## End session

**End session** is the correct way to shut down the Companion.

It is designed to clean up:

- the local Companion server,
- the managed Playwright browser,
- Buganizer/Salesforce/Companion managed tabs,
- an open Paperwork Begin window,
- the launcher Terminal window on macOS when possible.

After End session, the map will no longer see a Companion at `127.0.0.1:8765`.

Run the launcher again the next time Paperwork is needed.

---

# How the code is organized

## `bootstrap.py`

This is the first-run installer and normal launcher helper.

It:

- requires Python 3.10 or newer,
- creates `.venv` inside the extracted Companion folder,
- installs packages from `requirements.txt`,
- remembers the installed requirements fingerprint,
- checks for Google Chrome/Chromium,
- installs Playwright Chromium if a usable system Chrome is not available,
- launches `companion.py`.

Normally users should **not** run pip commands manually. The bootstrap handles them.

---

## `companion.py`

This is the main application.

It contains:

- the localhost HTTP server,
- `/health`,
- `/launch`,
- the startup control UI,
- the Paperwork UI,
- session state,
- authentication checks,
- window placement information,
- Claim/Reassign API actions,
- End session handling,
- the single browser-worker queue.

The server listens on:

```text
127.0.0.1:8765
```

The `/health` endpoint reports information including whether the service is running and whether Buganizer/Salesforce are ready.

---

## `paperwork.py`

This contains the browser automation used for Buganizer and Salesforce.

Examples include:

- opening the exact Buganizer issue,
- posting a Buganizer comment,
- changing the Buganizer assignee,
- searching Salesforce using the Buganizer ID,
- opening the matching Salesforce Case,
- Salesforce owner helper code used by older/other workflows.

These automations depend on the page controls and labels used by Buganizer and Salesforce. If those websites significantly change their UI, selectors may need to be updated.

---

## `spine_browser.py`

Despite the older module name, this class is used as the Companion's persistent Playwright browser manager.

It:

- starts Playwright,
- prefers installed Google Chrome,
- falls back to Playwright Chromium,
- creates one persistent browser context,
- keeps authentication cookies/session state between Companion launches,
- uses the local browser profile path from `runtime_paths.py`,
- exposes pages to the Companion browser worker.

---

## `runtime_paths.py`

This chooses a writable per-user location for the persistent browser profile.

The login profile is **not stored inside the ZIP**.

Typical locations are:

### macOS

```text
~/Library/Application Support/MTV_MAP_Companion/browser-profile
```

### Windows

```text
%LOCALAPPDATA%\MTV_MAP_Companion\browser-profile
```

### Linux / ChromeOS Linux

```text
~/.local/share/MTV_MAP_Companion/browser-profile
```

If this browser-profile folder is deleted, the user will normally need to sign into Buganizer and Salesforce again.

---

## `requirements.txt`

Contains the Python package dependency constraints.

Current main dependency:

```text
playwright>=1.55,<2
```

Do not randomly upgrade or edit dependencies unless you are testing the Companion code against the new version.

---

## Launchers

### `START_COMPANION.bat`

Windows launcher.

### `START_COMPANION.command`

macOS launcher.

### `START_COMPANION.sh`

Linux launcher.

### `CHROMEOS_SETUP.sh`

One-time setup helper for ChromeOS Linux / Crostini.

---

## `status_display.py`

Contains the terminal status-display helper used by related command-line workflows.

---

## `window_layout.py`

Contains best-effort window placement support, mainly for Linux/X11 environments.

The primary Paperwork split-screen geometry is also supplied by the shared map and applied by `companion.py`.

---

# Browser and authentication design

The Companion intentionally uses a **persistent browser profile**.

This means:

- each user signs into their own account,
- authentication can survive Companion restarts,
- the ZIP does not contain another person's login session,
- sending the ZIP to another technician does not send your cookies/passwords.

The first run on another computer should be treated as a new installation.

The user must have legitimate access to:

- Buganizer / Partner IssueTracker,
- Salesforce Field Service,
- required company SSO / Okta / VPN services.

The Companion cannot grant permissions the user does not already have.

MFA is not automated. Complete it normally in the browser.

---

# Supported devices

The package is intended for desktop/laptop systems where Python and Playwright can run.

Supported targets:

- Windows 10/11
- macOS
- Linux desktop
- ChromeOS using the Linux development environment (Crostini)

Not currently supported as native installations:

- iPhone / iPad
- Android phones/tablets
- ChromeOS without Linux enabled
- locked-down devices that do not allow Python/local processes

See `INSTALL.md` for exact setup instructions.

---

# Security and privacy

The Companion is intentionally local.

- It binds to `127.0.0.1`, not `0.0.0.0`.
- Do not forward port `8765`.
- Do not expose port `8765` to the LAN or internet.
- Do not copy or distribute a user's browser profile.
- Do not put passwords, cookies, tokens, or service-account credentials in the project.
- Do not upload `.venv`.
- Do not upload the local browser-profile directory.
- Each technician must sign in using their own approved account.

The distributable ZIP should contain source files and launchers only.

---

# Files/folders that should NOT be shared

Do not package or send:

```text
.venv/
__pycache__/
*.pyc
browser-profile/
.spine-browser-profile/
```

These are machine-specific, generated, or authentication-related.

A fresh user should receive the clean release ZIP.

---

# Normal user workflow

After installation:

1. Start the Companion using the launcher for your OS.
2. Wait for the managed browser.
3. If Buganizer says **Sign in**, complete sign-in.
4. If Salesforce says **Sign in**, complete Salesforce/Okta sign-in.
5. Wait until both service indicators show **Connected**.
6. The managed browser minimizes automatically.
7. Open the MTV Robot Map on the same computer.
8. Select a robot.
9. Choose **Paperwork → Begin**.
10. Wait until Buganizer and Salesforce show Ready in the Paperwork window.
11. Choose Claim, Reassign, or Exit.
12. When completely finished using Paperwork, restore the managed browser and choose **End session**.

---

# Updating the Companion

To update:

1. End the current Companion session.
2. Download the new clean release ZIP.
3. Extract it to a normal folder.
4. Run the platform launcher.

The browser authentication profile is stored separately in the user's application-data directory, so replacing the source folder normally does not erase saved sign-in.

`bootstrap.py` fingerprints `requirements.txt`. If package requirements change, the private `.venv` is automatically updated.

---

# Things that can break the Companion

This section is important.

## Do not run from inside the ZIP

Always extract the ZIP first.

Running files directly from a compressed archive can prevent:

- creation of `.venv`,
- scripts finding sibling files,
- package installation,
- reliable updates.

---

## Do not run two Companion copies at the same time

Only one process can normally use:

```text
127.0.0.1:8765
```

If another copy is already running, the second may fail with an "address already in use" / port error.

Use the existing Companion or End session before starting another one.

---

## Do not edit the source files casually

Changing any of these can break communication between the map and Companion:

- port `8765`,
- endpoint names such as `/health` or `/launch`,
- expected JSON fields,
- browser selectors,
- team mappings,
- authentication checks.

Keep an untouched copy of the working release before development changes.

---

## Do not change `requirements.txt` without testing

The bootstrap sees a changed requirements file and may reinstall dependencies.

An incompatible Playwright version can break browser automation.

---

## Do not delete the browser profile unless you want to reset login

Deleting the per-user `browser-profile` normally signs the user out.

Only do this as a troubleshooting/reset step.

---

## Website UI changes can break automation

Buganizer and Salesforce are external applications.

If their button names, form structure, HTML, or authentication routes change, browser selectors may stop working even though the Companion code itself did not change.

If a Commit action errors:

1. Read the Companion error.
2. Check the actual Buganizer/Salesforce page.
3. Do not repeatedly click Commit until you know whether the first action succeeded.
4. Report the error and the visible page state.

---

## Do not close authentication tabs while setup is incomplete

During startup, allow the Companion to manage its Buganizer and Salesforce tabs.

Closing them during sign-in can make startup fail or force the tab to be recreated.

After the Companion reports ready, tabs can usually be recovered on the next Begin if accidentally closed, but leaving them managed is safest.

---

## Network / VPN / SSO problems are not Companion failures

If company services require VPN, corporate network access, Okta, or another authentication system, those must be working first.

If you cannot manually access Buganizer or Salesforce in a normal approved browser, the Companion cannot bypass that restriction.

---

# Health check

While the Companion is running, open:

```text
http://127.0.0.1:8765/health
```

A healthy response contains:

```json
{"ok": true}
```

Additional fields may show:

- Companion version,
- platform,
- startup readiness,
- Buganizer authentication status,
- Salesforce authentication status,
- shutdown state.

---

# Troubleshooting

For full beginner-friendly troubleshooting and platform-specific commands, see:

**`INSTALL.md`**

Do not guess commands if you are unsure. Follow the section for your operating system.
