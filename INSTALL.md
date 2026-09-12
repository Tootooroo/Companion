# MTV MAP Companion — Installation & First-Run Guide

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

GitHub documents **Code → Download ZIP** as the normal way to download a repository without using Git.

## Do not run files from inside the ZIP

The Companion needs to create its own private Python environment and access files beside the launcher.

If you are viewing the contents of a compressed ZIP without having extracted it first, stop and extract the ZIP.

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

You may also see additional project files. That is normal.

---

# 2. Which launcher do I use?

Use the launcher for your device:

| Device | Launcher |
|---|---|
| Windows 10 / 11 | `START_COMPANION.bat` |
| macOS | `START_COMPANION.command` |
| Linux desktop | `START_COMPANION.sh` |
| Chromebook / ChromeOS | `CHROMEOS_SETUP.sh` once, then `START_COMPANION.sh` |

The Companion requires:

```text
Python 3.10 or newer
```

The launcher handles the Companion's Python packages automatically after Python itself is available.

---

# 3. macOS installation

This section is important because macOS normally blocks a newly downloaded unsigned script the first time it is opened.

## Step 1 — Download and extract

1. Open:
   `https://github.com/Tootooroo/Companion`
2. Click **Code**.
3. Click **Download ZIP**.
4. Open your **Downloads** folder.
5. Double-click the downloaded ZIP.
6. Finder creates an extracted folder such as `Companion-main`.
7. Open that extracted folder.

Do not run `START_COMPANION.command` from inside the ZIP.

---

## Step 2 — Check Python

Open **Terminal**:

```text
Applications → Utilities → Terminal
```

Run:

```bash
python3 --version
```

A good result looks similar to:

```text
Python 3.12.4
```

Any version **3.10 or newer** is acceptable.

### If Python is missing or too old

Install a current Python 3 version using your company's approved software source or the official Python installer.

After installation:

1. Quit Terminal.
2. Open Terminal again.
3. Run:

```bash
python3 --version
```

Do not continue until the command reports Python 3.10 or newer.

---

## Step 3 — First attempt to open the launcher

In Finder, double-click:

```text
START_COMPANION.command
```

Because this file came from the internet and is not an Apple-notarized application, macOS may block it on the first attempt.

A common message is similar to:

```text
Apple cannot check "START_COMPANION.command" for malicious software.
```

The alert may offer **Done** or another dismissal button.

If this happens:

1. Click **Done**.
2. Open the Apple menu.
3. Open **System Settings**.
4. Select **Privacy & Security**.
5. Scroll down to the **Security** section.
6. Look for a message saying `START_COMPANION.command` was blocked.
7. Click **Open Anyway**.
8. macOS may ask for your Mac password or Touch ID. Approve it.
9. A confirmation warning appears again.
10. Click **Open**.

Apple documents this as the normal one-time process for allowing a trusted downloaded item that macOS has blocked.

After you approve it once, macOS should remember the exception and later launches should normally work by double-clicking the file.

> Only use **Open Anyway** when you intentionally downloaded the Companion from the expected repository and your company permits it. If the Mac is managed and your organization blocks the file, contact your administrator rather than bypassing company policy.

---

## Step 4 — If macOS says you do not have appropriate access privileges

If you see a message similar to:

```text
The file "START_COMPANION.command" could not be executed because
you do not have appropriate access privileges.
```

the launcher may have lost its executable permission.

Open Terminal and type:

```bash
cd 
```

There is a space after `cd`.

Do **not** press Enter yet.

Drag the extracted `Companion-main` folder from Finder directly into the Terminal window. Terminal inserts the full path.

Now press Enter.

Then run:

```bash
chmod +x START_COMPANION.command START_COMPANION.sh CHROMEOS_SETUP.sh
```

Then run:

```bash
./START_COMPANION.command
```

After that, double-clicking `START_COMPANION.command` should also work.

---

## Step 5 — First-run setup

A Terminal window opens and the launcher starts `bootstrap.py`.

On the first run you may see messages such as:

```text
First run: creating a private Python environment...
```

and:

```text
Installing/updating Companion dependencies...
```

This is expected.

The Companion creates a private folder named:

```text
.venv
```

inside the extracted Companion folder.

It then installs the packages listed in `requirements.txt`.

You normally do **not** need to type pip commands yourself.

If Google Chrome is not installed, the bootstrap can also install a private Playwright Chromium browser.

The first startup can take longer than later startups because packages and a browser may need to be downloaded.

Do not close the Terminal window while this is happening.

---

## Step 6 — Sign in to Buganizer and Salesforce

After setup, the Companion starts its managed browser.

You should see tabs for:

- **MTV Companion**
- **Buganizer**
- **Salesforce**

If Buganizer asks you to sign in:

1. Complete the normal Google/company sign-in.
2. Complete MFA if required.
3. Wait for Partner IssueTracker to load.

If Salesforce opens a Salesforce / Okta login page:

1. Complete the normal company sign-in.
2. Complete MFA if required.
3. Wait for the actual Salesforce Lightning page to load.

The MTV Companion status page should eventually show:

```text
Buganizer    Connected
Salesforce   Connected
```

The managed browser minimizes only after both services are connected.

---

## Step 7 — Use the map

Open the MTV Robot Map on the **same Mac**.

Select a robot and choose:

```text
Paperwork → Begin
```

The local Paperwork window should open.

Keep the Companion running while using Paperwork.

When completely finished, restore the managed Companion browser and click:

```text
End session
```

Use **End session** instead of manually killing the Python process whenever possible.

---

# 4. Windows 10 / Windows 11 installation

## Step 1 — Download and extract

1. Open:
   `https://github.com/Tootooroo/Companion`
2. Click **Code**.
3. Click **Download ZIP**.
4. Open your **Downloads** folder.
5. Right-click the downloaded ZIP.
6. Choose **Extract All...**
7. Choose a normal folder such as Downloads or Documents.
8. Click **Extract**.
9. Open the extracted `Companion-main` folder.

Do not run the launcher from inside the ZIP preview.

---

## Step 2 — Check Python

Press the Windows key, type:

```text
cmd
```

and open **Command Prompt**.

Run:

```cmd
py --version
```

If that does not work, try:

```cmd
python --version
```

You need Python 3.10 or newer.

Example:

```text
Python 3.12.4
```

### If Python is missing

Install a current Python 3 version from your company's approved software source or the official Python installer.

If you use the standard Python installer, enable:

```text
Add python.exe to PATH
```

during installation.

After Python installs:

1. Close Command Prompt.
2. Open it again.
3. Run:

```cmd
py --version
```

or:

```cmd
python --version
```

---

## Step 3 — Run the Companion

In the extracted Companion folder, double-click:

```text
START_COMPANION.bat
```

A Command Prompt window opens.

The launcher automatically looks for `py` first and then `python`.

On first run it may show:

```text
First run: creating a private Python environment...
```

and:

```text
Installing/updating Companion dependencies...
```

Wait for setup to finish.

---

## Step 4 — Windows security warnings

Windows or your company's security software may warn about a downloaded script.

If Windows SmartScreen displays **Windows protected your PC**, and you have confirmed that the files came from the expected `Tootooroo/Companion` repository and your organization allows them, Windows may provide **More info → Run anyway**.

If your company blocks the script or your account does not have permission to run it, contact your administrator. Do not disable company security software.

---

## Step 5 — Sign in

The managed browser opens MTV Companion, Buganizer, and Salesforce.

Complete any Buganizer / Google and Salesforce / Okta sign-ins.

Wait until:

```text
Buganizer    Connected
Salesforce   Connected
```

Then the managed browser minimizes.

---

## Step 6 — Use the map

Open the MTV Robot Map on the same Windows computer and choose:

```text
Paperwork → Begin
```

Keep the Command Prompt / Companion process running.

When completely finished, use **End session** in the managed MTV Companion page.

---

# 5. Linux desktop installation

The commands below are written for Debian / Ubuntu based systems.

Other distributions may use a different package manager.

## Step 1 — Download and extract

Download the repository using:

```text
Code → Download ZIP
```

from:

```text
https://github.com/Tootooroo/Companion
```

Extract the ZIP.

If you prefer the terminal and the downloaded ZIP is in the current directory, you can use:

```bash
unzip Companion-main.zip
```

The exact ZIP name may be different. Using your graphical file manager is completely fine.

Enter the extracted folder, for example:

```bash
cd Companion-main
```

---

## Step 2 — Install Python support

Run:

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

If `sudo` asks for your password, type the password for your computer account and press Enter.

Linux normally does not display password characters while you type. That is normal.

Check Python:

```bash
python3 --version
```

It must be Python 3.10 or newer.

---

## Step 3 — Make the launcher executable

From inside the extracted Companion folder, run:

```bash
chmod +x START_COMPANION.sh
```

Then launch:

```bash
./START_COMPANION.sh
```

---

## Step 4 — First-run setup

The launcher runs `bootstrap.py`.

It automatically creates `.venv` and installs the Companion's Python requirements.

If Chrome / Chromium is unavailable, it attempts to install Playwright Chromium.

If Playwright reports that Linux system libraries are missing, run from the Companion folder:

```bash
sudo .venv/bin/python -m playwright install-deps chromium
```

Then run:

```bash
.venv/bin/python -m playwright install chromium
```

Then restart:

```bash
./START_COMPANION.sh
```

---

## Step 5 — Sign in and use Paperwork

Complete Buganizer and Salesforce authentication in the managed browser.

Wait for both indicators to say **Connected**.

Then open the MTV Robot Map on the same computer and choose:

```text
Paperwork → Begin
```

When completely finished, use **End session**.

---

# 6. Chromebook / ChromeOS installation

The Companion is a Python + Playwright desktop helper. It does **not** run directly as a normal ChromeOS web page.

ChromeOS requires the **Linux development environment (Crostini)**.

If the Chromebook is company-managed and Linux is disabled, an administrator must enable/approve it.

---

## Step 1 — Enable Linux

Open ChromeOS **Settings**.

Go to:

```text
Developers → Linux development environment
```

Enable Linux and complete the ChromeOS setup.

---

## Step 2 — Download and extract the Companion

Open:

```text
https://github.com/Tootooroo/Companion
```

Choose:

```text
Code → Download ZIP
```

Extract the ZIP.

Move the extracted `Companion-main` folder into:

```text
Linux files
```

Keeping the Companion in Linux files avoids path and permission issues between normal ChromeOS storage and the Linux container.

---

## Step 3 — Open the Linux Terminal

Open the ChromeOS **Terminal** application.

Enter the Companion directory, for example:

```bash
cd Companion-main
```

If the folder has a different name or location, use that path instead.

---

## Step 4 — Make the scripts executable

Run:

```bash
chmod +x CHROMEOS_SETUP.sh START_COMPANION.sh
```

---

## Step 5 — Run the one-time ChromeOS setup

Run:

```bash
./CHROMEOS_SETUP.sh
```

This script uses the Linux package manager to install:

- Python 3,
- Python virtual-environment support,
- pip,
- Playwright system dependencies,
- Chromium when required.

The script may display `sudo` commands and package-installation messages.

If asked:

```text
Do you want to continue? [Y/n]
```

type:

```text
Y
```

and press Enter.

If asked for a Linux password, enter it and press Enter. The password may not appear while you type.

Wait until the script says setup is complete.

---

## Step 6 — Start the Companion

After the one-time setup, run:

```bash
./START_COMPANION.sh
```

For future sessions, you normally only need:

```bash
./START_COMPANION.sh
```

You do **not** need to rerun `CHROMEOS_SETUP.sh` every time.

Complete Buganizer and Salesforce sign-in, wait for both to show **Connected**, then use **Paperwork → Begin** from the map.

---

# 7. What the launcher installs automatically

The launchers call:

```text
bootstrap.py
```

The bootstrap:

1. verifies that Python is at least version 3.10,
2. creates a private `.venv`,
3. installs packages from `requirements.txt`,
4. checks for a usable Chrome / Chromium browser,
5. installs Playwright Chromium if necessary,
6. starts `companion.py`.

You normally should **not** run `pip install` yourself.

You normally should **not** edit `.venv`.

---

# 8. If the terminal asks whether it may install a package/browser

The current bootstrap normally installs requirements automatically.

Some lower-level recovery paths may still display prompts similar to:

```text
Playwright is required but not installed. Install it now? [y/N]:
```

If you intentionally downloaded the Companion from the official repository and want setup to continue, type:

```text
y
```

and press Enter.

You may also see:

```text
A compatible browser is required. Install Playwright Chromium now? [y/N]:
```

Type:

```text
y
```

and press Enter.

If Linux / ChromeOS reports missing browser system libraries, use:

```bash
sudo .venv/bin/python -m playwright install-deps chromium
```

followed by:

```bash
.venv/bin/python -m playwright install chromium
```

Then start the launcher again.

---

# 9. Normal startup behavior

Every time the Companion starts, it checks Buganizer and Salesforce authentication.

The managed browser contains:

- the MTV Companion control page,
- Buganizer,
- Salesforce.

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

If a sign-in is needed, the browser remains visible.

Once both are connected, the browser minimizes automatically.

The login session is stored in a persistent local browser profile, so users normally do not need to log in from scratch every launch. Company SSO, Okta, or Salesforce policies can still expire a session and require authentication again.

---

# 10. Verify that the Companion is running

While the Companion is running, open this address in a browser on the same computer:

```text
http://127.0.0.1:8765/health
```

A working Companion returns JSON containing:

```json
{"ok": true}
```

If the page does not load, the local Companion is not currently serving on that computer.

---

# 11. Exit vs End session

These are intentionally different.

## Exit

The **Exit** button in the Paperwork window ends only the current robot paperwork workspace.

The Companion stays running so another robot can be opened later.

## End session

The **End session** button is on the MTV Companion control page in the managed browser.

Use it when you are completely finished.

It shuts down the local Companion and closes its managed browser resources.

On macOS, the launcher also attempts to close the Terminal window that launched the Companion after a clean shutdown.

---

# 12. Updating to a newer Companion version

When the GitHub repository is updated:

1. Use **End session** on the currently running Companion.
2. Return to:
   `https://github.com/Tootooroo/Companion`
3. Click **Code → Download ZIP**.
4. Extract the new ZIP into a new folder.
5. Run the correct launcher again.

Do not copy the old `.venv` folder into the new download.

The Companion's persistent browser profile is stored separately from the repository folder, so normal source updates should not require you to sign in again unless the authentication session itself has expired.

---

# 13. Common problems

## "Companion is not running"

Start the launcher for your operating system, then test:

```text
http://127.0.0.1:8765/health
```

---

## "Address already in use" / port 8765

Another Companion process is probably already running.

Do not start multiple copies.

Find the existing MTV Companion managed browser and use **End session**.

If an old process was left behind and cannot be found, restarting the computer is a simple way to clear it.

---

## Python is missing

### Windows

Try:

```cmd
py --version
```

or:

```cmd
python --version
```

### macOS / Linux / ChromeOS

Run:

```bash
python3 --version
```

Install Python 3.10 or newer if necessary.

---

## `.venv` cannot be created

Common causes:

- the ZIP was not extracted,
- the folder is read-only,
- Python venv support is missing,
- company security policy blocked the process.

On Debian / Ubuntu:

```bash
sudo apt install python3-venv
```

Then rerun the launcher.

---

## Playwright / Chromium installation failed

First, retry the launcher.

On Linux / ChromeOS, if the error specifically mentions missing system dependencies:

```bash
sudo .venv/bin/python -m playwright install-deps chromium
```

then:

```bash
.venv/bin/python -m playwright install chromium
```

Then start the Companion again.

---

## macOS says Apple cannot check the launcher

First attempt to open:

```text
START_COMPANION.command
```

Then:

```text
System Settings
→ Privacy & Security
→ Security
→ Open Anyway
```

Approve the authentication prompt, then click **Open** on the confirmation warning.

This is normally needed only for the first approved launch of that downloaded copy.

---

## macOS says "appropriate access privileges"

From Terminal, enter the extracted Companion folder and run:

```bash
chmod +x START_COMPANION.command
```

Then:

```bash
./START_COMPANION.command
```

---

## Salesforce keeps opening a login page

Complete the Salesforce / Okta login normally and wait for the Salesforce Lightning application to load.

If it happens every launch, your company security policy may be expiring or clearing the session.

Do not delete the Companion browser profile as a first troubleshooting step.

---

## Buganizer or Salesforce does not become Connected

Open the affected managed-browser tab and make sure the actual application is loaded, not:

- a login page,
- an access denied page,
- an MFA screen,
- a company error page.

The Companion cannot bypass account permissions, SSO, VPN, or company network requirements.

---

# 14. Things that can break the Companion

Avoid the following:

- running files before extracting the ZIP,
- deleting Python source files,
- renaming launchers or project files,
- editing `requirements.txt` without testing,
- changing port `8765`,
- starting two Companion copies,
- deleting `.venv` while the Companion is running,
- deleting the persistent browser profile unless intentionally resetting authentication,
- manually changing Buganizer or Salesforce tabs while automation is actively working,
- repeatedly clicking Commit while the UI says **Working...**,
- closing the terminal / command window while the Companion is running,
- bypassing organization-managed security restrictions.

Buganizer, Salesforce, Google authentication, Okta, browser versions, and company network policies are external systems. Changes to those systems can occasionally require the Companion automation to be updated.

---

# 15. What to collect if you need help

If setup or Paperwork fails, collect:

1. your operating system,
2. your Python version,
3. the exact terminal / command-window error,
4. whether `http://127.0.0.1:8765/health` loads,
5. whether Buganizer shows Connected,
6. whether Salesforce shows Connected,
7. a screenshot of the page where the workflow stopped.

Do **not** send:

- passwords,
- MFA codes,
- cookies,
- authentication tokens,
- private credentials.

