# MTV MAP Companion — Installation Guide

This guide is for running **Companion** with the MTV Robot Map.

You do **not** need to know Git, Python, or Playwright to use the Companion. Follow the section for your operating system and complete the steps in order.

> **Important**
>
> - Download the Companion from the official repository:  
>   **https://github.com/Tootooroo/Companion**
> - **Extract / unzip the download before running anything.**
> - Run the launcher for your operating system from the extracted folder.
> - Keep the Companion's terminal / command window open while using Paperwork.
> - Complete Buganizer and Salesforce sign-in when prompted.
> - Do not move, rename, delete, or edit Companion files unless you know exactly what you are changing.
> - Do not run two Companion copies at the same time.

---

# 1. How the download works

If the MTV Robot Map cannot find the Companion, the map's Companion link will take you to:

```text
https://github.com/Tootooroo/Companion
```

On the GitHub page:

1. Click the green **Code** button above the file list.
2. Click **Download ZIP**.
3. Wait for the ZIP file to finish downloading.
4. Find the downloaded ZIP in your **Downloads** folder.
5. Extract / unzip it.
6. Open the extracted folder.

GitHub normally names the extracted folder something similar to:

```text
Companion-main
```

That folder name is fine. You do not need to rename it.

**Do not run the Companion from inside the ZIP.** It must be extracted so it can create its private Python environment and access the other Companion files.

A normal extracted Companion folder should contain files similar to:

```text
Companion-main/
├── README.md
├── INSTALL.md
├── bootstrap.py
├── companion.py
├── paperwork.py
├── salesforce_routes.py
├── spine_browser.py
├── runtime_paths.py
├── requirements.txt
├── START_COMPANION.bat
├── START_COMPANION.command
├── START_COMPANION.sh
└── CHROMEOS_SETUP.sh
```

Choose your device below.

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

If Python is missing or older than 3.10, install a current Python 3 version using the official Python installer. Then close/reopen Terminal and check `python3 --version` again.

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

## 4. Complete sign-in

The managed browser opens with:

- MTV Companion
- Buganizer
- Salesforce

If Buganizer requests authentication, complete your normal company/Google sign-in and MFA.

If Salesforce opens Salesforce/Okta login, complete sign-in and MFA and wait for the actual Salesforce Lightning page.

Wait until the MTV Companion page shows:

```text
Buganizer    Connected
Salesforce   Connected
```

Once both are connected, the managed browser minimizes automatically.

## 5. Use Paperwork

Open the MTV Robot Map on the same Mac.

Select a robot and choose:

```text
Paperwork → Begin
```

Leave the Companion running while doing paperwork.

When you are completely finished, restore the managed browser and click **End session**.

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

## 4. Complete sign-in

The managed browser opens MTV Companion, Buganizer, and Salesforce.

Complete any Google/company and Salesforce/Okta authentication.

Wait for:

```text
Buganizer    Connected
Salesforce   Connected
```

The browser minimizes after both are connected.

## 5. Use Paperwork

Open the MTV Robot Map on the same computer and choose:

```text
Paperwork → Begin
```

When completely finished, use **End session** from the managed MTV Companion page.

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

## 5. Sign in and use Paperwork

Complete Buganizer and Salesforce authentication.

Wait until both show **Connected**, then open the MTV Robot Map and use:

```text
Paperwork → Begin
```

Use **End session** when completely finished.

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

Complete Buganizer and Salesforce authentication, wait for both to show **Connected**, then use **Paperwork → Begin** from the MTV Robot Map.

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
