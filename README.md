# UpdateChecker

A portable Windows application that keeps your system up to date. It scans for **program** (Winget) and **driver** (PowerShell/WMI) updates, installs them one-by-one with automatic **System Restore points**, and logs everything to a **local SQLite database**.

## Features

- **Program updates** — detects outdated apps through Winget.
- **Driver updates** — scans drivers via PowerShell/WMI and groups them by category (Display, Network, Audio, etc.).
- **Safe installation** — select and install updates one-by-one; a System Restore point is created automatically before each install.
- **Update history** — every check and install is recorded in SQLite with search, filtering and CSV export.
- **Dark-mode GUI** — Tkinter interface with toast notifications when updates are available.
- **Portable** — bundles into a single `.exe` with PyInstaller; config and database live next to the executable.
- **Cloud sync** — optional backup/sync of the update history to **Synology WebDAV** or a **GitHub repository** (useful across multiple PCs, with machine name tracking).

## Requirements

- **Windows 10/11**
- **Python 3.10+**
- **Winget** (built-in on recent Windows versions)
- Administrative privileges for installing updates and creating restore points

## Installation

```bash
cd UpdateChecker
pip install -r requirements.txt
```

## Usage

```bash
python UpdateChecker/main.py
```

> Run it as Administrator so it can install updates and create restore points. If you launch it without admin rights, it will prompt for elevation automatically.

## Building a portable .exe

```bash
cd UpdateChecker
pyinstaller build.spec
```

The executable is generated in `dist/`. `config.json` and the SQLite database are stored in the same folder, keeping the app fully portable (e.g. run from a USB drive).

## Configuration

`config.json` stores app settings and optional cloud sync credentials:

```json
{
  "synology": { "quickconnect_id": "", "username": "", "password": "", "auto_sync": false },
  "github":   { "repo_name": "UpdateChecker-Backup", "personal_access_token": "", "branch": "main", "auto_sync": false },
  "preferences": { "check_programs": true, "check_drivers": true, "create_restore_points": true }
}
```

Fill in the sync fields in the Settings dialog to enable cloud backup.

## Project structure

```
UpdateChecker/
├── main.py                     # Entry point + GUI (Tkinter)
├── config.json                 # App configuration
├── build.spec                  # PyInstaller spec for portable .exe
├── requirements.txt
├── assets/                     # App icon
└── modules/
    ├── database.py             # SQLite history (search, filter, export CSV)
    ├── winget_checker.py       # Program update detection (Winget)
    ├── driver_checker.py       # Driver update detection (PowerShell/WMI)
    ├── updater.py              # Install workflow (one-by-one)
    ├── system_restore.py       # Restore point creation/enabling
    ├── notifications.py        # Toast notifications
    ├── synology_sync.py        # Synology WebDAV sync
    └── github_sync.py          # GitHub repo backup
```

## Changelog

See [CHANGELOG.md](CHANGELOG.md).

## License

MIT License