"""PDF planner generation orchestrator."""

from __future__ import annotations

import tempfile
from pathlib import Path

from reportlab.pdfgen.canvas import Canvas

from rmcal.models import Event, Handedness, Language, PlannerConfig
from rmcal.planner.layouts import day, month, week, year
from rmcal.planner.navigation import NavigationRegistry
from rmcal.planner.styles import PageLayout, get_page_size, register_cjk_fonts


def _filter_meeting_events(
    events: list[Event],
    meeting_notes_calendar_ids: set[str],
) -> list[Event]:
    """Filter events to only non-all-day events from meeting notes calendars."""
    return [
        e for e in events
        if not e.all_day and e.calendar_id in meeting_notes_calendar_ids
    ]


def generate_planner(
    config: PlannerConfig,
    events: list[Event],
    output_path: Path | None = None,
    meeting_notes_calendar_ids: set[str] | None = None,
) -> Path:
    """Generate a complete PDF planner.

    Uses a two-pass approach:
    1. Assign deterministic page numbers to all views
    2. Render all pages with correct cross-page navigation links

    Returns the path to the generated PDF.
    """
    if config.language == Language.JA:
        register_cjk_fonts()

    if output_path is None:
        output_path = Path(tempfile.mkdtemp()) / "planner.pdf"

    output_path.parent.mkdir(parents=True, exist_ok=True)

    nav = NavigationRegistry()
    layout = PageLayout(
        page_size=config.page_size,
        handedness_right=(config.handedness == Handedness.RIGHT),
    )
    page_size = get_page_size(config.page_size)

    # Filter meeting events
    meeting_events: list[Event] | None = None
    if meeting_notes_calendar_ids:
        meeting_events = _filter_meeting_events(events, meeting_notes_calendar_ids)
        if not meeting_events:
            meeting_events = None

    # Pass 1: Assign page numbers (deterministic ordering)
    page = 0
    page = year.assign_pages(nav, page, config)
    page = month.assign_pages(nav, page, config)
    page = week.assign_pages(nav, page, config)
    page = day.assign_pages(nav, page, config, meeting_events)

    total_pages = page

    # Pass 2: Render all pages
    c = Canvas(str(output_path), pagesize=page_size)
    c.setTitle("rmCalendar")
    c.setAuthor("rmCalendar")

    year.render(c, nav, config, events, layout)
    month.render(c, nav, config, events, layout, meeting_events)
    week.render(c, nav, config, events, layout, meeting_events)
    day.render(c, nav, config, events, layout, meeting_events)

    c.save()

    return output_path


def count_pages(
    config: PlannerConfig,
    events: list[Event] | None = None,
    meeting_notes_calendar_ids: set[str] | None = None,
) -> int:
    """Count the total number of pages that will be generated.

    Used for annotation preservation — the page count must be deterministic.
    """
    nav = NavigationRegistry()

    meeting_events: list[Event] | None = None
    if events and meeting_notes_calendar_ids:
        meeting_events = _filter_meeting_events(events, meeting_notes_calendar_ids)
        if not meeting_events:
            meeting_events = None

    page = 0
    page = year.assign_pages(nav, page, config)
    page = month.assign_pages(nav, page, config)
    page = week.assign_pages(nav, page, config)
    page = day.assign_pages(nav, page, config, meeting_events)
    return page
