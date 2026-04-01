"""CLI entry point for rmCalendarMacOS.

Usage:
    rmcal                    # Interactive TUI (pick calendars, generate, upload)
    rmcal register           # Register with reMarkable Cloud (one-time)
    rmcal sync               # Headless sync (for daemon/cron)
    rmcal generate           # Generate PDF only
    rmcal daemon install     # Install 15-min auto-sync daemon
    rmcal daemon uninstall   # Remove the daemon
    rmcal daemon status      # Check daemon status
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

import click

CONFIG_DIR = Path("~/.config/rmcal").expanduser()
DEFAULT_OUTPUT = CONFIG_DIR / "planner.pdf"


@click.group(invoke_without_command=True)
@click.option("--output", "-o", type=click.Path(path_type=Path), default=str(DEFAULT_OUTPUT),
              help="Output PDF path")
@click.option("--start", default=None, help="Start date (YYYY-MM-DD)")
@click.option("--end", default=None, help="End date (YYYY-MM-DD)")
@click.option("--name", default="rmCalendar", help="Document name on reMarkable")
@click.option("--no-upload", is_flag=True, help="Generate PDF only, skip cloud upload")
@click.pass_context
def cli(ctx: click.Context, output: Path, start: str | None, end: str | None,
        name: str, no_upload: bool) -> None:
    """rmCalendarMacOS: Sync macOS Calendar to reMarkable as an interactive PDF planner."""
    ctx.ensure_object(dict)
    ctx.obj["output"] = Path(output)
    ctx.obj["start"] = date.fromisoformat(start) if start else None
    ctx.obj["end"] = date.fromisoformat(end) if end else None
    ctx.obj["name"] = name
    ctx.obj["upload"] = not no_upload

    if ctx.invoked_subcommand is None:
        # Default: launch TUI
        from rmcal.calendar.macos import is_available
        if not is_available():
            click.echo("ERROR: macOS EventKit not available.")
            click.echo("Install with: pip install pyobjc-framework-EventKit")
            sys.exit(1)

        from rmcal.tui import run_tui
        run_tui(
            output=ctx.obj["output"],
            start_date=ctx.obj["start"],
            end_date=ctx.obj["end"],
            upload_cloud=ctx.obj["upload"],
            document_name=ctx.obj["name"],
        )


@cli.command()
def register() -> None:
    """Register with reMarkable Cloud (one-time setup)."""
    from rmcal.remarkable.cloud import RemarkableCloud

    click.echo("reMarkable Cloud Registration")
    click.echo("=" * 40)
    click.echo()
    click.echo("1. Go to: https://my.remarkable.com/device/remarkable?showOtp=true")
    click.echo("2. Log in and copy the 8-character code")
    click.echo()

    code = click.prompt("Enter code").strip()
    if not code:
        click.echo("No code entered.")
        sys.exit(1)

    click.echo("Registering...")
    with RemarkableCloud() as cloud:
        cloud.register_device(code)

    click.echo("Success! Device registered with reMarkable Cloud.")
    click.echo("This is a one-time setup — the token is saved for future use.")


@cli.command()
@click.pass_context
def sync(ctx: click.Context) -> None:
    """Headless sync using saved calendar selection (for daemon/cron)."""
    from rmcal.calendar.macos import fetch_macos_events, is_available
    from rmcal.models import DateRange, PlannerConfig
    from rmcal.planner.generator import generate_planner
    from rmcal.state import get_meeting_notes_calendar_ids, get_selected_calendar_ids

    if not is_available():
        click.echo("ERROR: macOS EventKit not available.")
        sys.exit(1)

    calendar_ids = get_selected_calendar_ids()
    if calendar_ids is None:
        click.echo("ERROR: No calendar selection saved.")
        click.echo("Run 'rmcal' interactively first to pick your calendars.")
        sys.exit(1)

    if not calendar_ids:
        click.echo("ERROR: All calendars were deselected. Run 'rmcal' to reconfigure.")
        sys.exit(1)

    # Compute date range
    start = ctx.obj["start"]
    end = ctx.obj["end"]
    if start is None:
        today = date.today()
        start = today.replace(day=1)
    if end is None:
        year = start.year + (start.month + 11) // 12
        month = (start.month + 11) % 12 + 1
        end = date(year, month, 1) - timedelta(days=1)

    dr = DateRange(start=start, end=end)
    click.echo(f"[rmcal] Date range: {dr.start} -> {dr.end}")

    # Fetch events
    events = fetch_macos_events(dr, calendar_ids=calendar_ids)
    click.echo(f"[rmcal] Found {len(events)} events")

    # Generate PDF
    output = ctx.obj["output"]
    output.parent.mkdir(parents=True, exist_ok=True)
    config = PlannerConfig(date_range=dr)
    meeting_notes_ids = get_meeting_notes_calendar_ids()
    pdf_path = generate_planner(
        config, events, output_path=output,
        meeting_notes_calendar_ids=meeting_notes_ids,
    )
    click.echo(f"[rmcal] Generated {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} KB)")

    # Upload to cloud
    if ctx.obj["upload"]:
        from rmcal.remarkable.cloud import RemarkableCloud
        from rmcal.state import get_cloud_doc_id, save_cloud_doc_id

        with RemarkableCloud() as cloud:
            if not cloud.is_authenticated:
                click.echo("[rmcal] ERROR: Not authenticated. Run 'rmcal register' first.")
                sys.exit(1)

            document_name = ctx.obj["name"]
            saved_id = get_cloud_doc_id()
            if saved_id:
                existing = cloud.find_document_by_id(saved_id)
                if existing:
                    click.echo("[rmcal] Updating existing document...")
                    cloud.update_document(existing, pdf_path)
                    click.echo("[rmcal] Updated successfully")
                else:
                    click.echo("[rmcal] Previous doc not found, uploading new...")
                    doc_id = cloud.upload_new_document(document_name, pdf_path)
                    save_cloud_doc_id(doc_id)
                    click.echo(f"[rmcal] Uploaded as {doc_id}")
            else:
                click.echo(f"[rmcal] Uploading new document '{document_name}'...")
                doc_id = cloud.upload_new_document(document_name, pdf_path)
                save_cloud_doc_id(doc_id)
                click.echo(f"[rmcal] Uploaded as {doc_id}")

    click.echo("[rmcal] Done!")


@cli.command()
@click.option("--output", "-o", type=click.Path(path_type=Path), default=None,
              help="Output PDF path (default: ./planner.pdf)")
@click.pass_context
def generate(ctx: click.Context, output: Path | None) -> None:
    """Generate PDF planner without uploading."""
    from rmcal.calendar.macos import fetch_macos_events, is_available
    from rmcal.models import DateRange, PlannerConfig
    from rmcal.planner.generator import generate_planner
    from rmcal.state import get_meeting_notes_calendar_ids, get_selected_calendar_ids

    if not is_available():
        click.echo("ERROR: macOS EventKit not available.")
        sys.exit(1)

    calendar_ids = get_selected_calendar_ids()
    if calendar_ids is None:
        click.echo("ERROR: No calendar selection saved.")
        click.echo("Run 'rmcal' interactively first to pick your calendars.")
        sys.exit(1)

    start = ctx.obj["start"]
    end = ctx.obj["end"]
    if start is None:
        today = date.today()
        start = today.replace(day=1)
    if end is None:
        year = start.year + (start.month + 11) // 12
        month = (start.month + 11) % 12 + 1
        end = date(year, month, 1) - timedelta(days=1)

    dr = DateRange(start=start, end=end)
    events = fetch_macos_events(dr, calendar_ids=calendar_ids)
    click.echo(f"Found {len(events)} events")

    out = output or Path("planner.pdf")
    config = PlannerConfig(date_range=dr)
    meeting_notes_ids = get_meeting_notes_calendar_ids()
    pdf_path = generate_planner(
        config, events, output_path=out,
        meeting_notes_calendar_ids=meeting_notes_ids,
    )
    click.echo(f"Generated: {pdf_path} ({pdf_path.stat().st_size / 1024:.0f} KB)")


@cli.group()
def daemon() -> None:
    """Manage the auto-sync background daemon."""
    pass


@daemon.command("install")
@click.pass_context
def daemon_install(ctx: click.Context) -> None:
    """Install launchd daemon for 15-minute auto-sync."""
    from rmcal.daemon import install_daemon, get_daemon_log_path, PLIST_NAME, PLIST_PATH

    install_daemon(document_name=ctx.obj["name"])
    click.echo(f"Installed launchd plist: {PLIST_PATH}")
    click.echo("Daemon started! It will sync every 5 minutes.")
    click.echo(f"Logs: {get_daemon_log_path()}")
    click.echo()
    click.echo("To stop:  rmcal daemon uninstall")
    click.echo(f"To check: launchctl list | grep {PLIST_NAME}")


@daemon.command("uninstall")
def daemon_uninstall() -> None:
    """Remove the auto-sync daemon."""
    from rmcal.daemon import is_daemon_installed, uninstall_daemon

    if is_daemon_installed():
        uninstall_daemon()
        click.echo("Daemon stopped and removed.")
    else:
        click.echo("No daemon installed.")


@daemon.command("status")
def daemon_status() -> None:
    """Check if the auto-sync daemon is running."""
    from rmcal.daemon import is_daemon_installed, is_daemon_running, get_daemon_log_path

    if not is_daemon_installed():
        click.echo("Auto-sync daemon: not installed")
        click.echo("Run 'rmcal daemon install' to enable.")
        return

    if is_daemon_running():
        click.echo("Auto-sync daemon: running (every 5 min)")
    else:
        click.echo("Auto-sync daemon: installed but not running")

    click.echo(f"Log: {get_daemon_log_path()}")


if __name__ == "__main__":
    cli()
