# Changelog

## [1.1.0] - 2026-07-09

### Added
- Select All button to quickly select all available updates
- Hierarchical driver treeview grouped by category (Display, Network, Audio, etc.)

### Fixed
- Driver detection no longer shows individual filenames; now displays real device names grouped by category

## [1.0.0] - 2026-07-09

### Added
- Initial release of UpdateChecker portable application
- Main GUI window with tabs for Programs and Drivers
- Program update detection via Winget CLI
- Driver update detection via PowerShell + WMI
- One-by-one update installation with progress bar
- System restore point creation before each update
- Windows toast notifications via win10toast
- SQLite database for update history tracking
- Synology WebDAV sync for database backup
- GitHub backup for source code and database
- Settings dialog for configuration
- History viewer with filtering and CSV export
- Computer name tracking per update entry
- Dark theme Tkinter interface
- Administrator privilege detection and elevation
- Build configuration with PyInstaller (single .exe)
- Fully portable - no installation required
