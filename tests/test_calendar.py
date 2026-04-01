"""Tests for calendar fetching and parsing."""

from datetime import date
from pathlib import Path

from rmcal.calendar.parser import parse_events
from rmcal.models import CalendarSource, DateRange

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_ics_events():
    """Test parsing events from a sample ICS file."""
    source = CalendarSource(name="Test", url="http://example.com", prefix="T")
    ics_text = (FIXTURES / "sample.ics").read_text()
    date_range = DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30))

    events = parse_events([(source, ics_text)], date_range)

    assert len(events) > 0
    # Check we got the Morning Standup
    summaries = [e.summary for e in events]
    assert "Morning Standup" in summaries
    assert "Design Review" in summaries
    assert "Company Holiday" in summaries
    assert "Team Dinner" in summaries


def test_parse_all_day_events():
    """Test that all-day events are parsed correctly."""
    source = CalendarSource(name="Test", url="http://example.com")
    ics_text = (FIXTURES / "sample.ics").read_text()
    date_range = DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30))

    events = parse_events([(source, ics_text)], date_range)

    all_day = [e for e in events if e.all_day]
    assert len(all_day) >= 1
    assert any(e.summary == "Company Holiday" for e in all_day)


def test_parse_recurring_events():
    """Test that recurring events are expanded."""
    source = CalendarSource(name="Test", url="http://example.com")
    ics_text = (FIXTURES / "sample.ics").read_text()
    # Use a wider range to capture recurring instances
    date_range = DateRange(start=date(2026, 4, 1), end=date(2026, 6, 30))

    events = parse_events([(source, ics_text)], date_range)

    planning_events = [e for e in events if e.summary == "Weekly Planning"]
    # Should have multiple instances of the recurring event
    assert len(planning_events) >= 4


def test_parse_event_prefix():
    """Test that calendar prefix is applied to events."""
    source = CalendarSource(name="Work", url="http://example.com", prefix="W")
    ics_text = (FIXTURES / "sample.ics").read_text()
    date_range = DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30))

    events = parse_events([(source, ics_text)], date_range)

    standup = next(e for e in events if e.summary == "Morning Standup")
    assert standup.prefix == "W"
    assert standup.display_name == "[W] Morning Standup"


def test_parse_empty_calendar():
    """Test parsing a calendar with no events in range."""
    source = CalendarSource(name="Test", url="http://example.com")
    ics_text = (FIXTURES / "sample.ics").read_text()
    date_range = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))

    events = parse_events([(source, ics_text)], date_range)
    assert len(events) == 0


def test_date_range_filtering():
    """Test that events outside the date range are excluded."""
    source = CalendarSource(name="Test", url="http://example.com")
    ics_text = (FIXTURES / "sample.ics").read_text()
    # Only April 1
    date_range = DateRange(start=date(2026, 4, 1), end=date(2026, 4, 1))

    events = parse_events([(source, ics_text)], date_range)

    for event in events:
        ev_date = event.start.date()
        assert ev_date == date(2026, 4, 1)
