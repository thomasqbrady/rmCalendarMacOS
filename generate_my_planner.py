#!/usr/bin/env python3
"""Legacy wrapper — use 'rmcal' instead.

This script is kept for backwards compatibility. Install the package
and use the 'rmcal' command directly:

    pip install -e "."
    rmcal              # Interactive TUI
    rmcal register     # Register with reMarkable Cloud
    rmcal sync         # Headless sync
    rmcal daemon install  # Enable auto-sync
"""

from rmcal.__main__ import cli

if __name__ == "__main__":
    cli()
