# MTV MAP Companion

MTV MAP Companion is the local desktop helper used by the **MTV Robot Map** to automate Paperwork in Buganizer and Salesforce.

The map runs in a normal web browser. The Companion runs locally and provides the map with a local service at:

```text
http://127.0.0.1:8765
```

`127.0.0.1` means **this computer only**. The Companion is not a public server.

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

When Begin is clicked, the Companion opens the exact Buganizer issue and matching Salesforce Case and prepares the Paperwork workflow.

---

# Paperwork workflow

The Paperwork window provides:

- **Claim**
- **Reassign**
- **Exit**

# Companion interfaces

There are two Companion interfaces with different purposes.

## MTV Companion control page

This page lives inside the Playwright-managed browser.

It shows:

- Buganizer connection status;
- Salesforce connection status;
- **End session**.

If either service needs authentication, the browser remains visible.

When both services are connected, the managed browser minimizes automatically on first launch.

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

# Browser and authentication

The Companion uses a persistent local browser profile.

This means:

- every person signs in with their own approved account;
- login state can survive Companion restarts;
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

For download and setup instructions, see **[INSTALL.md](INSTALL.md)**.

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

## External UI changes can break selectors

Buganizer and Salesforce are external applications. Changes to their HTML, labels, authentication routes, or Lightning controls may require updates to `paperwork.py`.

Do not repeatedly click Commit after an automation error until the actual Buganizer/Salesforce state has been checked.

---

# Troubleshooting

For installation problems, permissions, Python setup, Playwright/Chromium recovery, authentication problems, and OS-specific commands, use:

**[INSTALL.md](INSTALL.md)**

The install guide is organized by operating system so users can jump directly to the instructions for their device.
