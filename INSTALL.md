# MTV MAP Companion — Installation Guide

Follow the section for your device from top to bottom. You do not need Git or programming experience.

> **Before you start**
>
> - Download only from the Companion repository: `https://github.com/Tootooroo/Companion`
> - **Unzip the download before running anything.**
> - Run only the launcher for your operating system.
> - Keep the launcher/terminal window open while using Paperwork.
> - Sign in to Buganizer and Salesforce when the Companion asks.
> - Do not run two copies of the Companion at the same time.

---

# Download the Companion

When the MTV Robot Map says the Companion is not installed or running, use the Companion download link on the map. It opens the official Companion repository:

```text
https://github.com/Tootooroo/Companion
```

On GitHub:

1. Click the green **Code** button above the file list.
2. Click **Download ZIP**.
3. Wait for the download to finish.
4. Open your **Downloads** folder.
5. Extract / unzip the downloaded ZIP.
6. Open the extracted folder. GitHub normally names it something similar to:

```text
Companion-main
```

> **Important:** Do not run the Companion from inside the ZIP. Extract it first. The Companion needs access to all of the files in the folder and must be able to create its private Python environment.

Inside the extracted folder you should see launchers including:

```text
START_COMPANION.bat
START_COMPANION.command
START_COMPANION.sh
CHROMEOS_SETUP.sh
```

---

# Choose your device

You only need to follow the installation section for your operating system.

### [🍎 macOS](#macos)
Use `START_COMPANION.command`

### [🪟 Windows 10 / 11](#windows-10--11)
Use `START_COMPANION.bat`

### [🐧 Linux](#linux)
Use `START_COMPANION.sh`

### [💻 Chromebook / ChromeOS](#chromebook--chromeos)
Run `CHROMEOS_SETUP.sh` once, then use `START_COMPANION.sh`

After completing your operating-system setup, continue to the shared **First Launch & Sign-In** section.

---

# macOS

Use:

```text
START_COMPANION.command
```

## 1. Check Python

Open **Terminal** from:

```text
Applications → Utilities → Terminal
```

Run:

```bash
python3 --version
```

You need **Python 3.10 or newer**.

A valid result looks like:

```text
Python 3.12.4
```

If Python is missing or older than 3.10, install a current Python 3 version using your company's approved software source or the official Python installer. Then close/reopen Terminal and check `python3 --version` again.

## 2. Open the launcher

Open the extracted `Companion-main` folder and double-click:

```text
START_COMPANION.command
```

### If macOS blocks it the first time

A newly downloaded copy may show a warning that Apple cannot verify/check the file.

If that happens:

1. Click **Done** on the warning.
2. Open **Apple menu → System Settings**.
3. Select **Privacy & Security**.
4. Scroll down to the **Security** section.
5. Find the message saying `START_COMPANION.command` was blocked.
6. Click **Open Anyway**.
7. Approve with your Mac password or Touch ID if requested.
8. macOS shows one more confirmation.
9. Click **Open**.

This should normally be required only the first time that downloaded copy is approved.

Only approve the launcher if you intentionally downloaded it from the expected Companion repository and your organization permits it.

### If macOS says you do not have appropriate access privileges

Open Terminal and type:

```bash
cd 
```

Leave the space after `cd` and **do not press Enter yet**.

Drag the extracted `Companion-main` folder from Finder into Terminal. The folder path will appear automatically.

Press Enter.

Then run:

```bash
chmod +x START_COMPANION.command
```

Then start it with:

```bash
./START_COMPANION.command
```

## 3. Let first-time setup finish

A Terminal window opens.

On the first run you may see:

```text
First run: creating a private Python environment...
```

and:

```text
Installing/updating Companion dependencies...
```

This is normal. The Companion creates its own `.venv` and installs the required Python packages automatically.

The first launch may take longer because dependencies or Chromium may need to download. **Do not close Terminal while setup is running.**

## 4. Continue to First Launch & Sign-In

Your Mac setup is complete. Continue to [First Launch & Sign-In](#first-launch--sign-in).

[↑ Back to device selection](#choose-your-device)

---

# Windows 10 / 11

Use:

```text
START_COMPANION.bat
```

## 1. Check Python

Press the Windows key, type:

```text
cmd
```

and open **Command Prompt**.

Run:

```cmd
py --version
```

If that command is not recognized, try:

```cmd
python --version
```

You need **Python 3.10 or newer**.

If Python is missing, install a current Python 3 version using your company's approved software source or the official Python installer.

When using the normal Windows Python installer, enable:

```text
Add python.exe to PATH
```

After installation, close/reopen Command Prompt and check the version again.

## 2. Open the launcher

Open the extracted `Companion-main` folder and double-click:

```text
START_COMPANION.bat
```

A Command Prompt window opens.

If Windows displays a security warning, continue only if you downloaded the files from the expected Companion repository and your organization allows them. If company security blocks the launcher, contact your administrator instead of disabling security software.

## 3. Let first-time setup finish

The launcher automatically creates the private Python environment and installs the required packages.

You may see:

```text
First run: creating a private Python environment...
```

and:

```text
Installing/updating Companion dependencies...
```

Wait for setup to finish and leave the Command Prompt window open.

## 4. Continue to First Launch & Sign-In

Your Windows setup is complete. Continue to [First Launch & Sign-In](#first-launch--sign-in).

[↑ Back to device selection](#choose-your-device)

---

# Linux

Use:

```text
START_COMPANION.sh
```

These commands are for Ubuntu/Debian-based Linux systems.

## 1. Install Python support

Open Terminal and run:

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

If `sudo` asks for your password, type your computer password and press Enter. Linux normally shows no characters while you type a password.

Check:

```bash
python3 --version
```

You need Python 3.10 or newer.

## 2. Open the extracted folder

In Terminal, change into the extracted folder. For example:

```bash
cd ~/Downloads/Companion-main
```

Your path may be different.

## 3. Allow the launcher to run

Run:

```bash
chmod +x START_COMPANION.sh
```

Then:

```bash
./START_COMPANION.sh
```

## 4. Let setup finish

The launcher creates `.venv`, installs the Python requirements, and starts the Companion.

If Playwright reports missing Linux browser libraries, run from the Companion folder:

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

## 5. Continue to First Launch & Sign-In

Your Linux setup is complete. Continue to [First Launch & Sign-In](#first-launch--sign-in).

[↑ Back to device selection](#choose-your-device)

---

# Chromebook / ChromeOS

The Companion requires the ChromeOS **Linux development environment (Crostini)**. It cannot run as a normal ChromeOS webpage by itself.

Use:

```text
CHROMEOS_SETUP.sh
```

once, then use:

```text
START_COMPANION.sh
```

for normal launches.

## 1. Enable Linux

Open ChromeOS:

```text
Settings → Developers → Linux development environment
```

Enable Linux and let ChromeOS finish setting it up.

If this option is disabled on a managed Chromebook, contact your administrator.

## 2. Move the Companion into Linux files

Download and extract the Companion ZIP.

Move the extracted `Companion-main` folder into:

```text
Linux files
```

## 3. Run the one-time setup

Open the ChromeOS **Terminal** app.

Enter the Companion folder:

```bash
cd Companion-main
```

Make the scripts executable:

```bash
chmod +x CHROMEOS_SETUP.sh START_COMPANION.sh
```

Run:

```bash
./CHROMEOS_SETUP.sh
```

The setup installs the required Linux/Python/Playwright components.

If asked:

```text
Do you want to continue? [Y/n]
```

type `Y` and press Enter.

Wait until setup finishes.

## 4. Start the Companion

Run:

```bash
./START_COMPANION.sh
```

For future sessions, normally run only `START_COMPANION.sh`; the ChromeOS setup script is not needed every time.

## 5. Continue to First Launch & Sign-In

Your ChromeOS setup is complete. Continue to [First Launch & Sign-In](#first-launch--sign-in).

[↑ Back to device selection](#choose-your-device)

---

# First Launch & Sign-In

These steps are the same on macOS, Windows, Linux, and ChromeOS.

## 1. Let the Companion start

After you run the launcher, keep its Terminal / Command Prompt window open.

On a first run, the Companion may create its private Python environment and install required packages. Let this finish before closing anything.

The managed browser then opens with:

- **MTV Companion**
- **Buganizer**
- **Salesforce**

## 2. Complete Buganizer sign-in if needed

If Buganizer asks you to sign in:

1. Complete your normal Google/company sign-in.
2. Complete MFA if requested.
3. Wait for Partner IssueTracker to finish loading.

If you are already signed in, no action is required.

## 3. Complete Salesforce sign-in if needed

If Salesforce opens Salesforce/Okta login:

1. Complete your normal company sign-in.
2. Complete MFA if requested.
3. Wait for the actual Salesforce Lightning page to load.

If you are already signed in, no action is required.

## 4. Wait for both services to be ready

The MTV Companion control page should show:

```text
Buganizer    Connected
Salesforce   Connected
```

If either service still says **Sign in**, return to that browser tab and finish authentication.

Once both services are connected, the managed browser minimizes automatically.

## 5. Open Paperwork from the map

Open the MTV Robot Map on the **same computer** where the Companion is running.

Select a robot and choose:

```text
Paperwork → Begin
```

The Paperwork window opens and the Companion handles the local paperwork workflow.

Leave the Companion running while you are using Paperwork.

When you are completely finished, restore the managed MTV Companion browser and click:

```text
End session
```

[↑ Back to device selection](#choose-your-device)

---

# If setup asks to install Playwright or Chromium

The normal launcher handles dependencies automatically, but a recovery path may ask:

```text
Playwright is required but not installed. Install it now? [y/N]:
```

Type:

```text
y
```

and press Enter.

If asked:

```text
A compatible browser is required. Install Playwright Chromium now? [y/N]:
```

type:

```text
y
```

and press Enter.

Wait for the installation to complete before closing the terminal.

---

# How to know the Companion is running

While the Companion is running, open this address on the same computer:

```text
http://127.0.0.1:8765/health
```

A working Companion returns information containing:

```json
{"ok": true}
```

If the page does not load, the Companion is not currently running correctly.

---

# Exit vs End session

## Exit

**Exit** in the Paperwork window ends the current robot paperwork only.

The Companion stays running so you can work on another robot.

## End session

**End session** on the MTV Companion control page shuts down the entire Companion.

Use **End session** when you are done for the day/session.

---

# Updating the Companion

When a new version is available:

1. Use **End session** on the current Companion.
2. Return to the Companion GitHub repository.
3. Click **Code → Download ZIP**.
4. Extract the new ZIP into a new folder.
5. Run the correct launcher for your operating system.

Do not copy the old `.venv` into the new download.

Your saved Buganizer/Salesforce browser profile is stored separately, so updating the Companion normally does not erase your saved sign-in.

---

# Troubleshooting

## The map says the Companion is not running

Start the correct launcher, wait for setup/sign-in to finish, then reload/retry the map.

Check:

```text
http://127.0.0.1:8765/health
```

---

## "Address already in use" or port 8765 is busy

Another Companion copy is probably already running.

Do not start multiple copies.

Find the existing MTV Companion window and use **End session**. If an abandoned process cannot be found, restart the computer and launch one clean copy.

---

## Python is missing or too old

You need Python 3.10 or newer.

Windows:

```cmd
py --version
```

or:

```cmd
python --version
```

macOS/Linux/ChromeOS:

```bash
python3 --version
```

---

## macOS blocks `START_COMPANION.command`

Try opening the launcher once, click **Done**, then go to:

```text
System Settings
→ Privacy & Security
→ Security
→ Open Anyway
```

Approve the prompt and click **Open**.

---

## macOS says you do not have appropriate access privileges

From Terminal, enter the extracted Companion folder and run:

```bash
chmod +x START_COMPANION.command
./START_COMPANION.command
```

---

## Buganizer or Salesforce does not show Connected

Open the affected managed-browser tab.

Make sure you are not still on:

- a login page,
- an MFA screen,
- an access-denied page,
- an Okta page,
- a company/network error page.

Complete authentication and wait for the actual application to load.

---

## Playwright/Chromium fails on Linux or ChromeOS

From the Companion folder run:

```bash
sudo .venv/bin/python -m playwright install-deps chromium
.venv/bin/python -m playwright install chromium
```

Then restart the launcher.

---

# Important rules

To avoid breaking the Companion:

- **Always unzip it before running it.**
- Do not run two Companion copies.
- Do not close the terminal/command window while Paperwork is in use.
- Do not delete or rename project files.
- Do not edit `requirements.txt` unless you are developing/testing the Companion.
- Do not delete `.venv` while the Companion is running.
- Do not repeatedly click Commit while the UI says **Working...**.
- Do not manually interfere with Buganizer/Salesforce while the Companion is actively automating them.
- Do not bypass company security, SSO, VPN, or account-permission requirements.
- Do not share passwords, MFA codes, cookies, or authentication tokens.

If something fails, take a screenshot of the error and the Buganizer/Salesforce page where the workflow stopped.
