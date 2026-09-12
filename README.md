# MTV MAP Companion

MTV MAP Companion is the local desktop helper used by the **MTV Robot Map** to automate Paperwork in Buganizer and Salesforce.

The map runs in a normal web browser. The Companion runs locally on the technician's computer and provides the map with a local service at:

```text
http://127.0.0.1:8765
```

`127.0.0.1` means **this computer only**. The Companion is not a public server and should not be exposed to the internet or local network.

> **New user?** Start with [INSTALL.md](INSTALL.md). It contains the GitHub download instructions and separate setup guides for macOS, Windows, Linux, and ChromeOS.

---

## Quick overview

When the Companion starts, it:

1. Creates or reuses its private Python environment.
2. Starts the local service on `127.0.0.1:8765`.
3. Opens a Playwright-managed Chrome/Chromium browser.
4. Opens the **MTV Companion**, **Buganizer**, and **Salesforce** tabs.
5. Verifies that Buganizer and Salesforce are actually authenticated.
6. Keeps the browser visible if the user needs to sign in.
7. Minimizes the managed browser once both services are connected.
8. Waits for **Paperwork → Begin** from the MTV Robot Map.

When Begin is clicked, the map sends the selected robot and bug information to the local Companion and opens the **MTV Paperwork** window.

The Companion then opens the exact Buganizer issue and matching Salesforce Case and prepares the Paperwork workflow.

---

# Paperwork workflow

The Paperwork window provides:

- **Claim**
- **Reassign**
- **Exit**

## Claim

Claim is currently a Buganizer-only workflow.

It:

- assigns the Buganizer issue to `robotics-support@google.com`;
- posts the optional **Details** text as a Buganizer comment;
- verifies the Buganizer changes.

Salesforce Claim automation is intentionally separate and is not part of the current Claim flow.

---

## Reassign

Reassign automates both Buganizer and Salesforce.

### Stage 1 — Buganizer

The user:

1. Clicks **Reassign**.
2. Selects a team.
3. Confirms the Buganizer assignee.
4. Enters optional **Details**.
5. Clicks **Commit**.

The Companion then:

1. posts the Details to Buganizer when supplied;
2. changes the Buganizer assignee;
3. verifies the saved Buganizer result.

Only after Buganizer succeeds does the workflow advance to Salesforce.

### Stage 2 — Salesforce

The Paperwork window changes to the Salesforce step and asks only for route choices that cannot be determined automatically.

Before making **any Salesforce changes**, the Companion waits for the Buganizer-to-Salesforce backend synchronization.

The Salesforce Case must reach:

```text
Customer Responded
```

before the Companion changes the Case.

This synchronization barrier is important. If the Companion closed Salesforce before the Buganizer backend update arrived, that later update could reopen or overwrite the Case.

The wait is state-driven rather than a fixed delay. The Companion checks Salesforce immediately and continues as soon as the correct status appears.

After synchronization, the Companion:

1. verifies the exact Salesforce Case;
2. opens the Case **Details** tab;
3. checks the current Case Owner;
4. skips ownership changes when the correct user already owns the Case;
5. otherwise assigns the Case to the currently authenticated Salesforce user;
6. handles multiple Change Owner results by identifying the logged-in Salesforce user instead of blindly selecting the first result;
7. opens the Case **Feed**;
8. posts the same Details text used in Buganizer, when Details were supplied;
9. skips the Feed post when the exact Details are already present;
10. returns to **Details**;
11. checks the routed Salesforce fields;
12. changes only fields that are not already correct;
13. saves and verifies the routed fields;
14. checks the Case Status;
15. skips the close action if the Case is already Closed;
16. otherwise sets Status to **Closed**, saves, and verifies the result.

The workflow is designed to be retry-safe. If Salesforce fails after Buganizer already succeeded, retrying the Salesforce step does not intentionally repeat the Buganizer mutation. Salesforce operations also check the live Case before changing values that may already be correct.

---

# Salesforce Reassign routes

The route definitions are stored in:

```text
salesforce_routes.py
```

The Companion only asks the user for values that cannot be determined from the selected Reassign team.

## Mechatronics

### MANUS

```text
Operation: Data Collection / Teleoperation
Type: Hardware
Sub Category: Teleop Headset & Accessories
Component: Manus
Resolution Reason: Google Migrated
```

### OTHER

```text
Operation: Data Collection / Teleoperation
Type: Hardware
Sub Category: Teleop Headset & Accessories
Component: Misc. HARDWARE
Resolution Reason: Google Migrated
```

## Lab Build Team

### GANTRY

```text
Operation: Robot Start-Up
Type: Hardware
Sub Category: Gantry
Component: Full Assembly
Resolution Reason: Google Migrated
```

### SHARPA

The user chooses:

**Operation**
- `Data Collection / Teleoperation`
- `Evaluation / Autonomous Behavior`

**Sub Category**
- `R Hand`
- `L Hand`

The remaining fields are automatic:

```text
Type: Hardware
Component: Sharpa Cable
Resolution Reason: Google Migrated
```

### ESTOP

```text
Operation: Robot Positioning / Locomotion
Type: Hardware
Sub Category: E-Stop
Component: E-Stop
Resolution Reason: Google Migrated
```

## Release Team

The user chooses:

**Operation**
- `Robot Positioning / Locomotion`
- `Robot Start-Up`

**Component**
- `Ansible`
- `Apollo Operator`
- `Robotics UI`
- `SW Update`
- `Configuration`
- `Unknown Software`

Automatic fields:

```text
Type: Software
Resolution Reason: Google Migrated
```

## Research Team

The user chooses:

**Operation**
- `Robot Positioning / Locomotion`
- `Evaluation / Autonomous Behavior`

**Component**
- `Apollo Operator`
- `Helios`
- `Robotics UI`
- `Configuration`
- `Orca`
- `Tracking/IK`
- `Unknown Software`

Automatic fields:

```text
Type: Software
Resolution Reason: Google Migrated
```

## Engineering Team

The user chooses:

**Operation**
- `Robot Positioning / Locomotion`
- `Evaluation / Autonomous Behavior`

**Component**
- `Apollo Operator`
- `Helios`
- `Robotics UI`
- `Orca`
- `Configuration`
- `Unknown Software`

Automatic fields:

```text
Type: Software
Resolution Reason: Google Migrated
```

## Other / `fedynchuk@google.com`

No additional Salesforce choice is required.

```text
Operation: Robot Start-Up
Type: Software
Component: Dev PC
Resolution Reason: Google Migrated
```

The approved software routes do not set **Sub Category** because no Sub Category value is defined for those routes.

---

# Companion interfaces

There are two Companion interfaces with different purposes.

## MTV Companion control page

This page lives inside the Playwright-managed browser.

It shows:

- Buganizer connection status;
- Salesforce connection status;
- **End session**.

If either service needs authentication, the browser remains visible.

When both services are connected, the managed browser minimizes automatically.

## MTV Paperwork window

This window is opened by **Paperwork → Begin** from the map.

It contains the active robot paperwork workflow.

**Exit** ends only the current robot Paperwork session. The Companion continues running.

**End session** is intentionally available from the MTV Companion control page and shuts down the entire Companion.

---

# End session

Use **End session** when completely finished with the Companion.

It is designed to clean up:

- the localhost Companion service;
- the Playwright-managed browser;
- the managed Companion, Buganizer, and Salesforce tabs;
- an open Paperwork window;
- the launcher Terminal window on macOS when possible.

After shutdown, the map will no longer find the Companion at:

```text
127.0.0.1:8765
```

Run the platform launcher again the next time the Companion is needed.

---

# Code structure

## `bootstrap.py`

First-run installer and normal launcher helper.

It:

- requires Python 3.10 or newer;
- creates `.venv`;
- installs packages from `requirements.txt`;
- tracks the requirements fingerprint;
- detects Google Chrome/Chromium;
- installs Playwright Chromium when necessary;
- starts `companion.py`.

Normal users should not need to install Python packages manually.

## `companion.py`

Main Companion application.

It owns:

- the localhost HTTP server;
- `/health`;
- `/launch`;
- startup/authentication state;
- the MTV Companion control page;
- the MTV Paperwork UI;
- Paperwork session state;
- Claim/Reassign actions;
- the Buganizer → Salesforce synchronization barrier;
- End session;
- browser/window coordination;
- the dedicated Playwright browser-worker queue.

Playwright browser operations are serialized through one worker so browser mutations do not run concurrently.

## `paperwork.py`

Browser automation for Buganizer and Salesforce.

It contains logic for:

- opening exact Buganizer issues;
- posting Buganizer comments;
- changing Buganizer assignees;
- opening/searching exact Salesforce Cases;
- reading Salesforce Case Status;
- waiting for `Customer Responded`;
- checking/changing Salesforce Case Owner;
- identifying the authenticated Salesforce user;
- posting Details to the Salesforce Feed;
- checking/updating routed Case fields;
- setting and verifying Status `Closed`.

These automations depend on the controls exposed by Buganizer and Salesforce. Significant website UI changes can require selector updates.

## `salesforce_routes.py`

Contains the approved Salesforce field mappings for each Reassign route.

Keeping the routing data separate from browser automation makes route changes easier to review and test.

## `spine_browser.py`

The module name is historical. In the Companion it acts as the persistent Playwright browser manager.

It:

- starts Playwright;
- prefers installed Google Chrome;
- falls back to Playwright Chromium;
- creates a persistent browser context;
- preserves authentication state between launches;
- exposes browser pages to the Companion worker.

## `runtime_paths.py`

Chooses the per-user location for the persistent browser profile.

Typical locations:

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

Deleting this profile normally requires the user to sign into Buganizer and Salesforce again.

## `requirements.txt`

Defines the Python dependency constraints used by the bootstrap.

Do not change dependency versions without testing the Companion against them.

## Launchers

| File | Platform |
|---|---|
| `START_COMPANION.command` | macOS |
| `START_COMPANION.bat` | Windows |
| `START_COMPANION.sh` | Linux |
| `CHROMEOS_SETUP.sh` | ChromeOS Linux one-time setup |

## `status_display.py`

Terminal status-display helper retained for related command-line workflows.

## `window_layout.py`

Best-effort window placement support, primarily for Linux/X11. The map and `companion.py` also coordinate the main Paperwork split-screen geometry.

---

# Browser and authentication

The Companion uses a persistent local browser profile.

This means:

- every technician signs in with their own approved account;
- login state can survive Companion restarts;
- the GitHub repository does not contain a technician's authenticated browser session;
- sending/downloading the source does not send another user's cookies or passwords.

The user must already have legitimate access to:

- Buganizer / Partner IssueTracker;
- Salesforce;
- required company SSO / Okta;
- required company network or VPN resources.

The Companion does not bypass authentication or permissions. MFA is completed normally in the managed browser.

---

# Supported devices

Supported desktop targets:

- macOS
- Windows 10 / 11
- Linux desktop
- ChromeOS through the Linux development environment (Crostini)

Not currently supported as native installations:

- iPhone / iPad
- Android phones/tablets
- ChromeOS without Linux enabled
- locked-down devices that cannot run Python/local processes

For download and setup instructions, see **[INSTALL.md](INSTALL.md)**.

---

# Security and privacy

The Companion is intentionally local.

- It binds to `127.0.0.1`, not `0.0.0.0`.
- Do not forward or expose port `8765`.
- Do not distribute browser profiles.
- Do not add passwords, cookies, tokens, or credentials to the repository.
- Do not commit `.venv`.
- Do not commit generated browser profiles.
- Each technician must authenticate using their own approved account.

Files/folders that should not be committed or distributed include:

```text
.venv/
__pycache__/
*.pyc
browser-profile/
.spine-browser-profile/
.env
```

---

# Normal user workflow

After installation:

1. Run the launcher for your operating system.
2. Complete Buganizer/Salesforce sign-in if requested.
3. Wait for both indicators to show **Connected**.
4. Open the MTV Robot Map on the same computer.
5. Select a robot.
6. Choose **Paperwork → Begin**.
7. Wait for the exact Buganizer and Salesforce records to be prepared.
8. Choose **Claim**, **Reassign**, or **Exit**.
9. Complete the Paperwork workflow.
10. Use **Exit** when finished with only the current robot.
11. Use **End session** when completely finished with the Companion.

---

# Updating

To update the Companion:

1. Use **End session**.
2. Download the latest repository ZIP.
3. Extract it into a new folder.
4. Run the launcher for your operating system.

The persistent authentication profile is stored outside the source folder, so a normal source update should not erase saved sign-in.

See **[INSTALL.md](INSTALL.md)** for the full update instructions.

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

The response can also report startup readiness, authentication state, platform/version information, and shutdown state.

---

# Important development notes

## Do not run multiple Companion copies

Only one process should use:

```text
127.0.0.1:8765
```

A second copy may fail because the port is already in use.

## Do not change the map/Companion contract casually

Changes to these can break communication:

- port `8765`;
- `/health`;
- `/launch`;
- expected JSON fields;
- session behavior.

## Keep browser mutations serialized

The Companion intentionally routes synchronous Playwright work through one browser worker. Do not move browser mutations onto arbitrary HTTP/request threads.

## Preserve the Salesforce synchronization barrier

For Reassign, do not move Salesforce writes ahead of the `Customer Responded` check.

The required ordering is:

```text
Buganizer Commit
      ↓
Wait for Salesforce Customer Responded
      ↓
Check / assign Salesforce owner
      ↓
Post Details to Feed
      ↓
Check / update routed fields
      ↓
Set Closed
      ↓
Verify
```

Removing that barrier can reintroduce the race where the later Buganizer backend synchronization reopens or overwrites an already-closed Salesforce Case.

## Keep Salesforce operations idempotent

Before changing Salesforce, check whether the desired state is already present.

This applies to:

- Case Owner;
- Feed Details;
- routed fields;
- Closed status.

This makes retries safer and avoids unnecessary Lightning edits.

## External UI changes can break selectors

Buganizer and Salesforce are external applications. Changes to their HTML, labels, authentication routes, or Lightning controls may require updates to `paperwork.py`.

Do not repeatedly click Commit after an automation error until the actual Buganizer/Salesforce state has been checked.

---

# Troubleshooting

For installation problems, permissions, Python setup, Playwright/Chromium recovery, authentication problems, and OS-specific commands, use:

**[INSTALL.md](INSTALL.md)**

The install guide is organized by operating system so users can jump directly to the instructions for their device.
