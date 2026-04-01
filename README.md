# rmCalendarMacOS

Sync your macOS Calendar to a reMarkable tablet as an interactive PDF planner — with clickable navigation between year, month, week, and day views, plus dedicated meeting notes pages with attendee lists and lined writing space.

The planner auto-syncs every 15 minutes in the background. Your handwritten annotations are preserved across syncs.

## Features

- **Interactive PDF planner** with year, month, week, and day views linked together
- **Meeting notes pages** with time, attendees, and lined space for each meeting
- **Clickable navigation** — tap dates, week numbers, and meeting entries to jump between views
- **Auto-sync** via a background daemon (every 15 minutes, no terminal needed)
- **Annotation preservation** — handwritten notes on your reMarkable survive each sync
- **12-hour time format** throughout
- **TUI setup** — guided first-run experience handles cloud registration, calendar selection, and meeting notes configuration

## Install

```bash
brew install thomasqbrady/remarkable/rmcal
```

Or from source:

```bash
git clone https://github.com/thomasqbrady/rmCalendarMacOS.git
cd rmCalendarMacOS
pip install -e .
```

## Getting Started

Just run:

```bash
rmcal
```

On first launch you'll be guided through:

1. **Cloud registration** — paste a code from [my.remarkable.com](https://my.remarkable.com/device/remarkable?showOtp=true)
2. **Calendar selection** — pick which macOS calendars to include
3. **Meeting notes** — choose which calendars should generate per-meeting notes pages
4. **Upload** — the planner is generated and synced to your reMarkable

macOS will prompt for calendar access automatically.

## Auto-Sync

Enable background sync so your planner stays up to date:

```bash
rmcal daemon install
```

This installs a macOS launchd daemon that runs `rmcal sync` every 15 minutes. No terminal window needed — it runs silently in the background, even after reboot.

```bash
rmcal daemon status      # Check if the daemon is running
rmcal daemon uninstall   # Stop and remove the daemon
```

You can also manage the daemon from the TUI by pressing `d` on the calendar selection screen.

## Commands

| Command | Description |
|---------|-------------|
| `rmcal` | Launch the interactive TUI |
| `rmcal sync` | Headless sync (used by the daemon) |
| `rmcal generate` | Generate PDF without uploading |
| `rmcal register` | Register with reMarkable Cloud |
| `rmcal daemon install` | Enable 15-minute auto-sync |
| `rmcal daemon uninstall` | Disable auto-sync |
| `rmcal daemon status` | Check daemon status |

## Options

```
--name TEXT        Document name on reMarkable (default: rmCalendar)
--start DATE       Start date YYYY-MM-DD (default: first of this month)
--end DATE         End date YYYY-MM-DD (default: 12 months from start)
--no-upload        Generate PDF only, skip cloud upload
-o, --output PATH  Output PDF path
```

## Requirements

- macOS (uses EventKit for native calendar access)
- Python 3.11+
- A reMarkable tablet with cloud sync enabled

## License

MIT
