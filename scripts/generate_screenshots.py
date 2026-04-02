#!/usr/bin/env python3
"""Generate screenshot PDFs for the README using realistic fake calendar data.

Produces three single-page PDFs (day view, week view, meeting notes) that can
be converted to PNGs for embedding in the README.

Usage:
    python scripts/generate_screenshots.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# Ensure src/ is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from reportlab.pdfgen.canvas import Canvas

from rmcal.models import DateRange, Event, PlannerConfig
from rmcal.planner.layouts import day, week
from rmcal.planner.layouts.meeting_notes import render_meeting_notes_page
from rmcal.planner.navigation import NavigationRegistry
from rmcal.planner.styles import PageLayout, get_page_size

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "screenshots"

# Use a Monday so the week view looks good
DEMO_DATE = date(2026, 4, 6)  # Monday

# --- Fake events ---

WORK_CAL = "Work"
PERSONAL_CAL = "Personal"
TEAM_CAL = "Design"

WORK_ID = "work-cal-id"
PERSONAL_ID = "personal-cal-id"
TEAM_ID = "design-cal-id"

ALL_CAL_IDS = {WORK_ID, PERSONAL_ID, TEAM_ID}


def _ev(
    summary: str,
    d: date,
    start_h: int,
    start_m: int,
    end_h: int,
    end_m: int,
    cal: str = WORK_CAL,
    cal_id: str = WORK_ID,
    location: str | None = None,
    attendees: tuple[str, ...] = (),
    all_day: bool = False,
) -> Event:
    return Event(
        summary=summary,
        start=datetime(d.year, d.month, d.day, start_h, start_m, tzinfo=timezone.utc),
        end=datetime(d.year, d.month, d.day, end_h, end_m, tzinfo=timezone.utc),
        all_day=all_day,
        location=location,
        calendar_name=cal,
        calendar_id=cal_id,
        attendees=attendees,
    )


def make_events() -> list[Event]:
    """Create a realistic week of calendar data."""
    mon = DEMO_DATE
    tue = mon + timedelta(days=1)
    wed = mon + timedelta(days=2)
    thu = mon + timedelta(days=3)
    fri = mon + timedelta(days=4)

    events = [
        # --- Monday ---
        _ev("Sprint Planning", mon, 9, 0, 10, 0,
            attendees=("alice@acme.co", "bob@acme.co", "carol@acme.co", "dave@acme.co")),
        _ev("1:1 with Sarah", mon, 10, 30, 11, 0),
        _ev("Lunch with Jamie", mon, 12, 0, 13, 0, PERSONAL_CAL, PERSONAL_ID,
            location="Elm Street Cafe"),
        _ev("API Review", mon, 14, 0, 15, 0,
            attendees=("alice@acme.co", "frank@acme.co")),
        _ev("Yoga", mon, 17, 30, 18, 30, PERSONAL_CAL, PERSONAL_ID,
            location="Downtown Studio"),

        # --- Tuesday ---
        _ev("Team Standup", tue, 9, 0, 9, 30),
        _ev("Design Review", tue, 10, 0, 11, 0, TEAM_CAL, TEAM_ID,
            attendees=("nina@acme.co", "omar@acme.co", "pat@acme.co"),
            location="Room 4B"),
        _ev("Product Sync", tue, 10, 30, 11, 30,  # overlaps Design Review
            attendees=("alice@acme.co", "quinn@acme.co")),
        _ev("Deep Work Block", tue, 13, 0, 16, 0),
        _ev("Piano Lesson", tue, 18, 0, 19, 0, PERSONAL_CAL, PERSONAL_ID),

        # --- Wednesday ---
        _ev("Team Standup", wed, 9, 0, 9, 30),
        _ev("Customer Demo", wed, 11, 0, 12, 0,
            attendees=("alice@acme.co", "bob@acme.co", "client@partner.io"),
            location="Zoom"),
        _ev("Dentist", wed, 14, 0, 15, 0, PERSONAL_CAL, PERSONAL_ID,
            location="234 Oak Avenue"),
        _ev("Architecture Working Group", wed, 15, 30, 16, 30, TEAM_CAL, TEAM_ID,
            attendees=("alice@acme.co", "frank@acme.co", "nina@acme.co")),

        # --- Thursday ---
        _ev("Team Standup", thu, 9, 0, 9, 30),
        _ev("Board Prep", thu, 10, 0, 11, 30,
            attendees=("alice@acme.co", "ceo@acme.co")),
        _ev("Investor Call", thu, 13, 0, 14, 0,
            attendees=("alice@acme.co", "ceo@acme.co", "cfo@acme.co"),
            location="Conference Room A"),
        _ev("UX Critique", thu, 14, 30, 15, 30, TEAM_CAL, TEAM_ID,
            attendees=("nina@acme.co", "omar@acme.co")),
        _ev("Run Club", thu, 17, 0, 18, 0, PERSONAL_CAL, PERSONAL_ID),

        # --- Friday ---
        _ev("Team Standup", fri, 9, 0, 9, 30),
        _ev("Sprint Retro", fri, 10, 0, 11, 0,
            attendees=("alice@acme.co", "bob@acme.co", "carol@acme.co", "dave@acme.co")),
        _ev("Lunch & Learn", fri, 12, 0, 13, 0, TEAM_CAL, TEAM_ID,
            location="Kitchen"),
        _ev("Weekly Review", fri, 14, 0, 14, 30),

        # All-day events
        Event(summary="Alice out of office", start=datetime(wed.year, wed.month, wed.day, 0, 0, tzinfo=timezone.utc),
              end=datetime(wed.year, wed.month, wed.day, 23, 59, tzinfo=timezone.utc),
              all_day=True, calendar_name=WORK_CAL, calendar_id=WORK_ID),
        Event(summary="Earth Day", start=datetime(thu.year, thu.month, thu.day, 0, 0, tzinfo=timezone.utc),
              end=datetime(thu.year, thu.month, thu.day, 23, 59, tzinfo=timezone.utc),
              all_day=True, calendar_name=PERSONAL_CAL, calendar_id=PERSONAL_ID),
    ]
    return events


def _config() -> PlannerConfig:
    return PlannerConfig(
        date_range=DateRange(start=DEMO_DATE, end=DEMO_DATE + timedelta(days=6)),
    )


def _generate_full_planner(events: list[Event]) -> tuple[Path, dict[str, int]]:
    """Generate the full planner PDF and return (path, manifest)."""
    from rmcal.planner.generator import generate_planner
    config = _config()
    out = OUTPUT_DIR / "full_planner.pdf"
    return generate_planner(
        config, events, output_path=out,
        meeting_notes_calendar_ids=ALL_CAL_IDS,
    )


def _extract_page(full_pdf: Path, page_index: int, out_name: str) -> Path:
    """Extract a single page from a PDF."""
    from pypdf import PdfReader, PdfWriter
    reader = PdfReader(str(full_pdf))
    writer = PdfWriter()
    writer.add_page(reader.pages[page_index])
    out = OUTPUT_DIR / out_name
    with open(out, "wb") as f:
        writer.write(f)
    return out


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    events = make_events()

    # Generate the full planner (all links resolve correctly)
    full_pdf, manifest = _generate_full_planner(events)
    print(f"Generated full planner: {full_pdf}")

    # Tuesday day view (has concurrent events)
    tue = DEMO_DATE + timedelta(days=1)
    day_bm = f"day-{tue.isoformat()}"
    day_page = manifest[day_bm]
    day_pdf = _extract_page(full_pdf, day_page, "day-view.pdf")
    print(f"Extracted day view (page {day_page}): {day_pdf}")

    # Week view
    iso = DEMO_DATE.isocalendar()
    week_bm = f"week-{iso[0]}-W{iso[1]:02d}"
    week_page = manifest[week_bm]
    week_pdf = _extract_page(full_pdf, week_page, "week-view.pdf")
    print(f"Extracted week view (page {week_page}): {week_pdf}")

    # Meeting notes — Sprint Planning (Monday, first meeting)
    meeting_bm = f"meeting-{DEMO_DATE.isoformat()}-0"
    meeting_page = manifest[meeting_bm]
    meeting_pdf = _extract_page(full_pdf, meeting_page, "meeting-notes.pdf")
    print(f"Extracted meeting notes (page {meeting_page}): {meeting_pdf}")

    # Clean up full planner
    full_pdf.unlink()

    # Convert to PNG
    print("\nConverting to PNG...")
    import subprocess
    for name in ["day-view", "week-view", "meeting-notes"]:
        pdf = OUTPUT_DIR / f"{name}.pdf"
        png = OUTPUT_DIR / f"{name}.png"
        subprocess.run([
            "sips", "-s", "format", "png",
            str(pdf), "--out", str(png),
            "--resampleWidth", "800",
        ], capture_output=True)
        pdf.unlink()
        print(f"  {png}")

    print(f"\nDone! Screenshots in {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
