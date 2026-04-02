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


def _stable_bin_path(name: str) -> str | None:
    """Find a Homebrew-stable path for a binary, avoiding versioned Cellar paths.

    Versioned Cellar paths (e.g. /opt/homebrew/Cellar/rmcal/0.1.16/…) break
    after ``brew reinstall``.  Prefer the stable symlink under the Homebrew
    prefix (e.g. /opt/homebrew/bin/rmcal) which survives upgrades.
    """
    raw = shutil.which(name)
    if raw is None:
        return None
    raw_path = Path(raw)
    # If the binary lives inside a Cellar dir, try the stable prefix symlink
    if "Cellar" in raw_path.parts:
        try:
            prefix = subprocess.run(
                ["brew", "--prefix"], capture_output=True, text=True,
            ).stdout.strip()
        except OSError:
            prefix = "/opt/homebrew"
        stable = Path(prefix) / "bin" / name
        if stable.exists():
            return str(stable)
    return str(raw_path)


def install_daemon(document_name: str = "rmCalendar") -> None:
    """Install and load the launchd plist for 5-minute auto-sync."""
    # Use stable symlink paths that survive brew upgrades
    rmcal_bin = _stable_bin_path("rmcal")

    if rmcal_bin:
        bin_dir = str(Path(rmcal_bin).parent)
        program_args = f"""    <array>
        <string>{rmcal_bin}</string>
        <string>--name</string>
        <string>{document_name}</string>
        <string>sync</string>
    </array>"""
    else:
        python_path = sys.executable
        bin_dir = str(Path(python_path).parent)
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
    <integer>300</integer>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>{LOG_PATH}</string>
    <key>StandardErrorPath</key>
    <string>{LOG_PATH}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:{bin_dir}</string>
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


def maybe_fix_stale_plist() -> None:
    """If the daemon plist has a versioned Cellar path, rewrite it with the stable path.

    Called at the start of ``rmcal sync`` so the fix happens as the real user
    (not in Homebrew's sandbox where ~/Library writes are blocked).
    """
    if not PLIST_PATH.exists():
        return

    content = PLIST_PATH.read_text()
    if "Cellar" not in content:
        return  # already stable

    # Extract the --name value
    import re
    strings = re.findall(r"<string>([^<]+)</string>", content)
    try:
        idx = strings.index("--name")
        doc_name = strings[idx + 1]
    except (ValueError, IndexError):
        doc_name = "rmCalendar"

    # Rewrite with stable paths
    uninstall_daemon()
    install_daemon(document_name=doc_name)


def get_daemon_log_path() -> Path:
    """Return the path to the daemon log file."""
    return LOG_PATH
