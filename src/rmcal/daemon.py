"""Daemon management — install, uninstall, and query the launchd auto-sync daemon."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

PLIST_NAME = "com.rmcal.daemon"
PLIST_PATH = Path(f"~/Library/LaunchAgents/{PLIST_NAME}.plist").expanduser()
CONFIG_DIR = Path("~/.config/rmcal").expanduser()
LOG_PATH = CONFIG_DIR / "daemon.log"


def is_daemon_installed() -> bool:
    """Check if the launchd plist file exists."""
    return PLIST_PATH.exists()


def is_daemon_running() -> bool:
    """Check if the daemon is currently loaded in launchd."""
    try:
        result = subprocess.run(
            ["launchctl", "list", PLIST_NAME],
            capture_output=True, text=True,
        )
        return result.returncode == 0
    except OSError:
        return False


def install_daemon(document_name: str = "rmCalendarMacOS Planner") -> None:
    """Install and load the launchd plist for 15-minute auto-sync."""
    python_path = sys.executable

    # Prefer the installed 'rmcal' command; fall back to 'python -m rmcal'
    rmcal_bin = shutil.which("rmcal")
    if rmcal_bin:
        program_args = f"""    <array>
        <string>{rmcal_bin}</string>
        <string>--name</string>
        <string>{document_name}</string>
        <string>sync</string>
    </array>"""
    else:
        program_args = f"""    <array>
        <string>{python_path}</string>
        <string>-m</string>
        <string>rmcal</string>
        <string>--name</string>
        <string>{document_name}</string>
        <string>sync</string>
    </array>"""

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_NAME}</string>
    <key>ProgramArguments</key>
{program_args}
    <key>StartInterval</key>
    <integer>900</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOG_PATH}</string>
    <key>StandardErrorPath</key>
    <string>{LOG_PATH}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{Path(python_path).parent}</string>
    </dict>
</dict>
</plist>
"""

    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_text(plist_content)
    os.system(f"launchctl load {PLIST_PATH}")


def uninstall_daemon() -> None:
    """Unload and remove the launchd plist."""
    if PLIST_PATH.exists():
        os.system(f"launchctl unload {PLIST_PATH}")
        PLIST_PATH.unlink()


def get_daemon_log_path() -> Path:
    """Return the path to the daemon log file."""
    return LOG_PATH
