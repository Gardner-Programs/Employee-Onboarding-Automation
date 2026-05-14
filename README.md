# Employee Onboarding Automation

A full-stack Python automation suite for IT onboarding. Provisions new-hire accounts across Google Workspace, Active Directory, 8x8 PBX, and Transport Pro from a single Google Sheets source of truth. Available as both a CLI tool and a Tkinter desktop GUI.

## Overview

When a new employee is added to the onboarding Google Sheet, this tool:

1. Creates their **Google Workspace** account, sets org unit, profile photo, and custom schema fields used for email signature templating
2. Adds them to appropriate **Google Groups** (regional distribution lists)
3. Creates an **Active Directory** account (if the role requires server access) in the correct OU
4. Provisions a **8x8 VoIP** extension and direct-dial number, enables SMS, configures SSO, and registers the number with the **Free Caller Registry**
5. Creates a **Transport Pro** dispatch user with correct terminal visibility
6. Generates a **PDF login sheet** and uploads it to the appropriate Google Drive shared folder

## Repository Structure

```
Employee-Onboarding-Automation/
├── cli/                        # Command-line version (Firefox + geckodriver)
│   ├── autoAccounts.py         # Main orchestrator — run this
│   ├── config.py               # WebDriver, Google Sheets, environment config
│   ├── data_processing.py      # Reads and normalizes onboarding sheet data
│   ├── gmail_service.py        # Google Workspace user creation & group membership
│   ├── ad_service.py           # Active Directory account creation via PowerShell
│   ├── pbx_8x8_service.py      # 8x8 Admin Console automation + FCR registration
│   ├── tpp_service.py          # Transport Pro user provisioning
│   ├── fcr_service.py          # Free Caller Registry number registration
│   ├── pdf_service.py          # Login sheet PDF generation + Drive upload
│   ├── utils.py                # Shared helpers: email sending, 2FA code retrieval, login
│   └── number_report.py        # Standalone 8x8 number availability report
│
└── gui/                        # Desktop GUI version (Chrome + chromedriver)
    ├── main.py                 # Entry point — run this or the packaged .exe
    ├── requirements.txt
    ├── gui/
    │   └── app.py              # Tkinter main window with login, task selection, progress log
    └── scripts/                # Service modules (same logic as CLI, adapted for GUI)
        ├── authenticator.py    # Google service account auth with runtime admin delegation
        ├── config.py           # Chrome WebDriver, spreadsheet key, app data paths
        ├── data_processing.py
        ├── gmail_service.py
        ├── ad_service.py
        ├── pbx_8x8_service.py
        ├── tpp_service.py
        ├── fcr_service.py
        ├── pdf_service.py
        ├── utils.py
        └── session_manager.py  # Selenium cookie persistence across runs
```

## Key Design Patterns

- **Single source of truth**: All new-hire data is read from a Google Sheet; the sheet is updated in-place as 8x8 extensions and direct lines are assigned
- **Service account delegation**: A Google service account with domain-wide delegation is used to act as any admin user without storing individual OAuth tokens
- **Session persistence** (GUI): Selenium cookie state for 8x8, Transport Pro, and FCR is saved to `%LOCALAPPDATA%\AccountTool\sessions\` so re-authentication through 2FA is only required after sessions expire
- **Frozen exe support**: The GUI is packaged with PyInstaller; the code handles both `sys._MEIPASS` (frozen) and source paths transparently
- **Terminal hierarchy matching**: Transport Pro terminal assignment uses a fuzzy parent→child matching algorithm that syncs live terminal data to a Google Sheet cache
- **Email signature templating**: Custom schema fields (`Signature_Info`) written during onboarding are consumed by a separate email signature management system

## Setup

### Prerequisites

- Python 3.9+
- Chrome (GUI) or Firefox (CLI) installed
- `wkhtmltopdf` installed and on PATH (for PDF generation)
- A Google Cloud service account with domain-wide delegation and the following scopes:
  - `admin.directory.user`, `admin.directory.orgunit`, `admin.directory.group`
  - `gmail.*`, `drive`, `spreadsheets`

### Configuration

1. Copy `.env.example` to `.env` and fill in your values:
   ```bash
   cp .env.example .env
   ```
2. Place your service account key JSON in a `Keys/` folder adjacent to the repo (or set `KEY_PATH` in `.env` to its absolute path)
3. In `cli/config.py` or `gui/scripts/config.py`, replace `YOUR_SPREADSHEET_KEY_HERE` with your onboarding Google Sheet ID

### Running the CLI

```bash
cd cli
pip install -r requirements.txt
python autoAccounts.py
```

### Running the GUI

```bash
cd gui
pip install -r requirements.txt
python main.py
```

Enter your admin `@company.com` email at the login prompt. The app loads new-hire data from the sheet and presents checkboxes to run each provisioning step independently.

## Technologies Used

- **Google APIs**: Admin SDK (Directory, Org Units, Groups), Gmail, Drive v3
- **Selenium WebDriver**: Chrome (GUI) / Firefox (CLI) for automating 8x8, Transport Pro, and FCR web portals
- **gspread / gspread-dataframe**: Google Sheets read/write
- **PowerShell subprocess**: Active Directory account creation via `New-ADUser`
- **pdfkit / wkhtmltopdf**: HTML-to-PDF login sheet generation
- **Tkinter**: Desktop GUI with threaded background task execution
- **PyInstaller**: Single-file Windows executable packaging
