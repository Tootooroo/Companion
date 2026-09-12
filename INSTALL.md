# MTV MAP Companion — Beginner Installation Guide

This guide is written for someone who has never installed or run the Companion before.

Follow the steps **in order**.

> **Important**
>
> 1. Download the complete Companion ZIP.
> 2. **Extract the ZIP before running anything.**
> 3. Use the launcher made for your operating system.
> 4. Do not rename/delete random project files.
> 5. Do not start multiple Companion copies.
> 6. Complete Buganizer and Salesforce sign-in before using **Paperwork → Begin**.

---

# Before you start

You need:

- a Windows, macOS, Linux, or supported ChromeOS computer,
- permission to install/run Python,
- internet/company-network access,
- access to Buganizer,
- access to Salesforce,
- your normal Google / Okta / Salesforce login credentials,
- the MTV MAP Companion ZIP.

The Companion should run on the **same computer** where you use the MTV Robot Map.

---

# Step 1 — Download and extract the ZIP

Download the Companion ZIP to Downloads or another normal folder.

## Do NOT run it from inside the ZIP

You must extract it first.

After extraction, the folder should contain files similar to:

```text
MTV_MAP_Companion/
├── README.md
├── INSTALL.md
├── companion.py
├── paperwork.py
├── spine_browser.py
├── runtime_paths.py
├── bootstrap.py
├── requirements.txt
├── START_COMPANION.bat
├── START_COMPANION.command
├── START_COMPANION.sh
└── CHROMEOS_SETUP.sh
```

If you only see a ZIP icon and are opening files without an extracted normal folder, stop and extract it first.

---

# Which instructions should I use?

Use only the section for your computer:

- **Windows 10/11** → `START_COMPANION.bat`
- **macOS** → `START_COMPANION.command`
- **Linux** → `START_COMPANION.sh`
- **Chromebook / ChromeOS** → enable Linux first, then use `CHROMEOS_SETUP.sh`

---

# Windows 10 / Windows 11

## 1. Install Python

The Companion requires:

```text
Python 3.10 or newer
```

If you are not sure whether Python is installed:

1. Press the Windows key.
2. Type `cmd`.
3. Open **Command Prompt**.
4. Type:

```cmd
py --version
```

If that does not work, type:

```cmd
python --version
```

A good result looks like:

```text
Python 3.12.4
```

Any Python 3.10+ version is acceptable.

### If Python is not installed

Install Python 3 from the official Python installer or your company's approved software center.

When using the standard Windows Python installer, enable:

```text
Add python.exe to PATH
```

Then finish the installation.

Close and reopen Command Prompt after installing Python.

Test again:

```cmd
py --version
```

---

## 2. Extract the Companion ZIP

In File Explorer:

1. Right-click the downloaded ZIP.
2. Choose **Extract All...**
3. Choose a normal location such as Documents or Downloads.
4. Open the extracted folder.

Do not double-click the launcher while still browsing inside the ZIP.

---

## 3. Start the Companion

Double-click:

```text
START_COMPANION.bat
```

A Command Prompt window should open.

On first run it may display:

```text
First run: creating a private Python environment...
```

Then:

```text
Installing/updating Companion dependencies...
```

This is normal.

Let it finish.

---

## 4. If Windows shows a security warning

Your organization may show Windows SmartScreen or another security product.

Only continue if:

- you received the ZIP from the expected trusted project source,
- the file name and folder are correct,
- your company policy allows running it.

If company policy blocks scripts/programs, do not bypass company security controls. Ask your administrator.

---

## 5. First browser setup

The Companion opens a managed Chrome/Chromium browser.

You should see:

- MTV Companion,
- Buganizer,
- Salesforce.

If Buganizer requires login, sign in normally.

If Salesforce opens Okta/login, sign in normally.

Complete MFA if requested.

The Companion status page should eventually show:

```text
Buganizer    Connected
Salesforce   Connected
```

When both are connected, the managed browser minimizes automatically.

---

## 6. Use the map

Open the MTV Robot Map on this same Windows computer.

Choose:

```text
Paperwork → Begin
```

The Paperwork window should open.

---

# macOS

## 1. Check Python

Open **Terminal**.

You can find Terminal in:

```text
Applications → Utilities → Terminal
```

Type:

```bash
python3 --version
```

A good result looks like:

```text
Python 3.12.4
```

Python must be 3.10 or newer.

---

## 2. Install Python if necessary

If Terminal says:

```text
command not found: python3
```

or your Python is older than 3.10, install a current Python 3 release using:

- your company's approved software center,
- the official Python installer,
- Homebrew if your organization uses it.

After installation, close Terminal, reopen it, and run:

```bash
python3 --version
```

---

## 3. Extract the ZIP

Double-click the ZIP in Finder.

Finder should create a normal folder.

Open the extracted folder.

---

## 4. Start the Companion

Double-click:

```text
START_COMPANION.command
```

A Terminal window should open and begin setup.

---

## 5. If macOS says you do not have appropriate access privileges

Open Terminal.

Type:

```bash
cd 
```

Do not press Enter yet.

Drag the extracted `MTV_MAP_Companion` folder from Finder into the Terminal window.

Terminal will insert the folder path.

Now press Enter.

Then type:

```bash
chmod +x START_COMPANION.command START_COMPANION.sh CHROMEOS_SETUP.sh
```

Press Enter.

Then start it:

```bash
./START_COMPANION.command
```

---

## 6. If macOS says the file cannot be opened

Control-click / right-click:

```text
START_COMPANION.command
```

Choose:

```text
Open
```

Then approve it if macOS offers the normal Open confirmation.

If your company blocks unsigned scripts through device management, do not bypass company policy. Ask your administrator.

---

## 7. First-run package installation

The Terminal may show:

```text
First run: creating a private Python environment...
```

and:

```text
Installing/updating Companion dependencies...
```

Wait for it to finish.

You normally do not need to type anything.

---

## 8. First browser sign-in

A managed Chrome/Chromium browser opens.

If Buganizer needs authentication, complete it.

If Salesforce shows a login/Okta page, complete it.

Wait until the Companion page shows:

```text
Buganizer    Connected
Salesforce   Connected
```

When both are connected, the managed browser minimizes automatically.

---

## 9. Use the map

Open the MTV Robot Map on the same Mac.

Choose:

```text
Paperwork → Begin
```

---

# Linux

The following examples use Debian/Ubuntu commands.

Other Linux distributions may use different package-manager commands.

## 1. Install Python and venv support

Open a terminal and run:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip
```

If asked:

```text
Do you want to continue? [Y/n]
```

type:

```text
Y
```

and press Enter.

If `sudo` asks for your password, type your computer password and press Enter.

**The password may not appear on screen while you type. This is normal.**

---

## 2. Extract the ZIP

Extract it using your file manager or:

```bash
unzip MTV_MAP_Companion_cross_platform_v3.6.zip
```

Then enter the folder:

```bash
cd MTV_MAP_Companion
```

---

## 3. Give the launcher permission to run

Type:

```bash
chmod +x START_COMPANION.sh
```

---

## 4. Start the Companion

Type:

```bash
./START_COMPANION.sh
```

The first run creates `.venv` and installs Python dependencies.

---

## 5. If Playwright says Linux system libraries are missing

From inside the Companion folder, run:

```bash
sudo .venv/bin/python -m playwright install-deps chromium
```

Then:

```bash
.venv/bin/python -m playwright install chromium
```

Then restart:

```bash
./START_COMPANION.sh
```

If the first command asks for your password, enter your computer password and press Enter.

---

# ChromeOS / Chromebook

The Companion does not run as a normal ChromeOS browser extension or web page.

It requires the ChromeOS **Linux development environment (Crostini)**.

If your Chromebook is managed and Linux is disabled by your organization, you cannot install this version without administrator approval.

---

## 1. Enable Linux

Open ChromeOS Settings.

Go to:

```text
Developers → Linux development environment
```

Enable Linux.

Wait for ChromeOS to complete setup.

---

## 2. Put the Companion in Linux files

Download and extract the ZIP.

Move/copy the extracted Companion folder into:

```text
Linux files
```

This avoids path and permission problems between ChromeOS storage and the Linux container.

---

## 3. Open the Linux Terminal

Use the ChromeOS Terminal app.

Enter the Companion folder.

For example:

```bash
cd MTV_MAP_Companion
```

If your folder is somewhere else, use the correct path.

---

## 4. Make the scripts executable

Run:

```bash
chmod +x CHROMEOS_SETUP.sh START_COMPANION.sh
```

---

## 5. Run the one-time ChromeOS setup

Run:

```bash
./CHROMEOS_SETUP.sh
```

The script installs:

- Python,
- Python venv,
- pip,
- required Playwright Linux libraries,
- Chromium if required.

It uses `sudo`.

### If asked:

```text
Do you want to continue? [Y/n]
```

type:

```text
Y
```

and press Enter.

### If asked for a password

Enter the Linux/container password if one has been configured.

Nothing may appear while typing. That is normal.

---

## 6. Start the Companion after setup

Run:

```bash
./START_COMPANION.sh
```

For later sessions, you normally only need:

```bash
./START_COMPANION.sh
```

You do not need to run `CHROMEOS_SETUP.sh` every time.

---

# What happens during first run?

The launcher runs `bootstrap.py`.

It automatically:

1. checks Python version,
2. creates:

```text
.venv
```

3. installs packages from:

```text
requirements.txt
```

4. checks for Chrome/Chromium,
5. installs Playwright Chromium when required,
6. starts the Companion.

The first run can take longer than later runs because packages/browser files may need to be downloaded.

Later runs reuse the existing environment.

---

# What should I type if the Companion asks to install something?

Normally the bootstrap installs requirements without asking.

However, if you see:

```text
Playwright is required but not installed. Install it now? [y/N]:
```

type:

```text
y
```

then press Enter.

If you see a browser prompt similar to:

```text
A compatible browser is required. Install Playwright Chromium now? [y/N]:
```

type:

```text
y
```

then press Enter.

If installation fails on Linux/ChromeOS because of missing libraries, use:

```bash
sudo .venv/bin/python -m playwright install-deps chromium
```

then:

```bash
.venv/bin/python -m playwright install chromium
```

then start the Companion again.

---

# Do I need to run pip manually?

Usually, **no**.

Do not manually install random versions of Playwright.

The launcher runs:

```text
bootstrap.py
```

which installs the dependencies specified by the project.

Only use manual pip/Playwright commands when troubleshooting a specific installation error.

---

# First startup and sign-in

Every startup verifies authentication.

The managed browser opens:

1. MTV Companion control page,
2. Buganizer,
3. Salesforce.

The control page shows separate indicators.

Possible states include:

```text
Buganizer    Connected
Salesforce   Sign in
```

or:

```text
Buganizer    Connected
Salesforce   Connected
```

The Companion should **not minimize while a required sign-in is incomplete**.

If Salesforce opens an Okta/login screen:

1. complete the login,
2. complete MFA if requested,
3. wait for the actual Salesforce Lightning interface,
4. wait for the Companion indicator to become Connected.

When both services are Connected, the browser minimizes automatically.

---

# If the Companion says Connected but the website is not usable

Do not immediately click Begin repeatedly.

Try:

1. restore the managed browser,
2. open the Buganizer tab,
3. verify the actual IssueTracker page loads,
4. open the Salesforce tab,
5. verify the actual Salesforce Lightning page loads,
6. refresh the affected website once if needed,
7. restart the Companion if the state does not recover.

If this happens repeatedly, report it as a Companion authentication-detection issue.

---

# Using Paperwork

After both startup indicators are Connected:

1. Open the MTV Robot Map on the same computer.
2. Click a robot.
3. Choose:

```text
Paperwork → Begin
```

4. The local Paperwork window opens.
5. Wait for Buganizer and Salesforce to show Ready.
6. Choose Claim, Reassign, or Exit.

## Reassign workflow

Reassign now completes both backend systems.

1. Choose **Reassign**.
2. Choose the destination team.
3. Enter optional **Details**.
4. Press **Commit**.
5. Wait while Buganizer saves the comment/assignee.
6. The Paperwork window changes to the **Salesforce** step.
7. Choose the route options shown for that team. Only choices that cannot be known automatically are shown.
8. Press **Complete Salesforce**.
9. The Companion assigns the Salesforce Case to the current Salesforce user, saves the same Details into Salesforce Case Feed when supplied, fills the routed fields, saves them, and closes the Case.
10. Wait for the final **Reassigned** completion screen before exiting.

Do **not** click Commit repeatedly while a button says **Working…**.

If the Salesforce step reports an error after Buganizer has already succeeded, stay on the Salesforce step and read the error before retrying. The Companion tracks successful Salesforce steps during the current session so a retry does not intentionally repeat them.

## Claim workflow

Claim remains the existing Buganizer workflow in this release. Salesforce Claim automation is not part of v3.11 yet.

---

# Exit vs End session

These buttons do different things.

## Exit

The **Exit** button in the Paperwork Begin window:

- ends the current robot paperwork workspace,
- returns the Companion to idle,
- keeps the Companion running.

Use Exit when you are finished with one robot but may work on another.

## End session

**End session** is on the MTV Companion control page inside the managed browser.

It:

- stops the local Companion,
- closes the managed browser,
- closes an open Begin/Paperwork window,
- releases port `8765`,
- closes the launcher Terminal window on macOS when possible.

Use End session when you are completely finished.

---

# Verify that the Companion is running

Open this in a browser on the same computer:

```text
http://127.0.0.1:8765/health
```

You should receive JSON containing:

```json
{"ok": true}
```

If the page does not load, the Companion is not currently serving on that computer.

---

# Common problems

## "Companion is not running"

Start the Companion using the correct launcher.

Then test:

```text
http://127.0.0.1:8765/health
```

If that does not load, check the terminal for an error.

---

## "Address already in use" / port 8765 is busy

Another Companion copy may already be running.

Do not open several copies.

Find the existing managed Companion browser and use:

```text
End session
```

Then start one new copy.

If you cannot find it, restart the computer as a simple last-resort way to clear an orphan local process.

---

## Python is too old

Check:

### Windows

```cmd
py --version
```

### macOS/Linux/ChromeOS

```bash
python3 --version
```

Install Python 3.10 or newer.

---

## `.venv` cannot be created

Possible causes:

- running from inside the ZIP,
- folder is read-only,
- Python venv support is missing,
- antivirus/security policy blocks script execution.

Fix the cause, then run the launcher again.

On Debian/Ubuntu:

```bash
sudo apt install python3-venv
```

---

## Playwright / Chromium download failed

Check internet/proxy access.

Run the launcher again.

On Linux/ChromeOS, if the message says system dependencies are missing:

```bash
sudo .venv/bin/python -m playwright install-deps chromium
.venv/bin/python -m playwright install chromium
```

---

## macOS launcher says "appropriate access privileges"

From Terminal, enter the Companion folder and run:

```bash
chmod +x START_COMPANION.command
```

Then:

```bash
./START_COMPANION.command
```

---

## Salesforce keeps opening the login page

This normally means the Salesforce session is not currently valid.

Complete login/Okta/MFA and wait until the actual Lightning page loads.

If it happens every single launch:

1. confirm the Companion is using the same local user account,
2. do not delete the Companion browser profile,
3. confirm browser/security policy is not clearing cookies on exit,
4. confirm Salesforce/Okta policy allows the session to persist,
5. report it if authentication succeeds but the Companion never changes to Connected.

---

## Buganizer opens but does not show Connected

Wait until the actual Partner IssueTracker `/issues` application loads.

If you are on a login/access-denied page, sign in or resolve access first.

---

## Begin opens but Salesforce cannot find the Case

Make sure Salesforce is fully authenticated and the Case actually exists/is visible to your account.

The Companion searches Salesforce using the 9-digit Buganizer ID.

If Salesforce UI/search behavior has changed, the automation selector may need an update.

---

# Things you should NOT do

To avoid breaking the installation:

- Do not run directly from inside the ZIP.
- Do not delete project Python files.
- Do not rename launcher files unless you also understand the scripts.
- Do not change port `8765`.
- Do not change endpoint names.
- Do not edit `requirements.txt` casually.
- Do not manually upgrade Playwright just because a newer version exists.
- Do not distribute `.venv`.
- Do not distribute browser profiles.
- Do not share cookies/tokens.
- Do not start two Companion copies.
- Do not repeatedly press Commit after a timeout without checking the actual Buganizer issue.
- Do not delete the browser profile unless you intentionally want to sign in again.
- Do not bypass your organization's security policy.

---

# What can legitimately cause the Companion to stop working?

Even if the local code has not changed, these external changes can affect it:

- Buganizer page layout changes,
- Salesforce Lightning layout changes,
- Google/Okta authentication changes,
- company VPN/network policy,
- expired login,
- account permission changes,
- Chrome updates,
- operating-system security updates,
- Playwright/browser compatibility changes,
- port `8765` being used by another process.

If something suddenly breaks after previously working, capture:

1. the terminal error,
2. the Companion status page,
3. the Buganizer/Salesforce page being shown,
4. what action was clicked,
5. operating system.

That information makes troubleshooting much faster.

---

# Updating to a new release

1. Use **End session**.
2. Download the new release ZIP.
3. Extract it into a fresh folder.
4. Run the platform launcher again.

Do not copy `.venv` from an old release unless you specifically know why.

The persistent authentication profile is stored separately, so a normal source-package update should not require deleting the login profile.

---

# Resetting the installation

Only use these steps when troubleshooting.

## Reset Python environment only

End the Companion.

Delete:

```text
.venv
```

from the extracted Companion folder.

Run the launcher again.

The bootstrap recreates it.

This should not delete saved Buganizer/Salesforce login.

## Reset browser login/profile

This signs the user out.

Only do this if you intentionally want a clean browser session.

Profile locations are documented in `README.md`.

After removing the profile, start the Companion and sign into both services again.

---

# Need help?

Before asking for help, collect:

- operating system,
- Python version,
- exact error text from the terminal,
- whether `/health` loads,
- Buganizer indicator state,
- Salesforce indicator state,
- screenshot of the page where it stopped.

Do not send passwords, MFA codes, cookies, tokens, or other credentials.
