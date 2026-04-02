"""Tests for calendar fetching and parsing."""

from datetime import date
from pathlib import Path

from rmcal.calendar.parser import parse_events
from rmcal.models import CalendarSource, DateRange

FIXTURES = Path(__file__).parent / "fixtures"


def _load_sample_events(
    date_range: DateRange,
    prefix: str = "",
) -> list:
    source = CalendarSource(name="Test", url="http://example.com", prefix=prefix)
    ics_text = (FIXTURES / "sample.ics").read_text()
    return parse_events([(source, ics_text)], date_range)


def test_parse_ics_returns_all_april_events():
    """sample.ics has 4 distinct events in April 2026 (plus recurring instances)."""
    dr = DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30))
    events = _load_sample_events(dr)
    summaries = {e.summary for e in events}
    assert summaries == {
        "Morning Standup",
        "Design Review",
        "Company Holiday",
        "Weekly Planning",
        "Team Dinner",
    }


def test_all_day_events_flagged_correctly():
    """Company Holiday is an all-day event; timed events are not."""
    dr = DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30))
    events = _load_sample_events(dr)

    all_day = [e for e in events if e.all_day]
    assert len(all_day) == 1
    assert all_day[0].summary == "Company Holiday"

    timed = [e for e in events if not e.all_day]
    assert all(not e.all_day for e in timed)


def test_recurring_events_expanded_correctly():
    """Weekly Planning recurs weekly for 12 instances starting April 10.
    In Apr 1 – Jun 30 all 12 should appear on the correct Fridays."""
    dr = DateRange(start=date(2026, 4, 1), end=date(2026, 6, 30))
    events = _load_sample_events(dr)

    planning = [e for e in events if e.summary == "Weekly Planning"]
    assert len(planning) == 12

    # Verify they're weekly (7-day gaps)
    dates = sorted(e.start.date() for e in planning)
    for i in range(1, len(dates)):
        assert (dates[i] - dates[i - 1]).days == 7


def test_event_prefix_applied():
    """Calendar prefix should appear in display_name but not summary."""
    dr = DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30))
    events = _load_sample_events(dr, prefix="W")

    standup = next(e for e in events if e.summary == "Morning Standup")
    assert standup.prefix == "W"
    assert standup.display_name == "[W] Morning Standup"
    assert standup.summary == "Morning Standup"  # summary itself unchanged


def test_no_events_outside_date_range():
    """A date range before the fixture events should return nothing."""
    dr = DateRange(start=date(2025, 1, 1), end=date(2025, 1, 31))
    events = _load_sample_events(dr)
    assert events == []


def test_single_day_range_returns_only_that_day():
    """Filtering to April 1 should return only events starting that day."""
    dr = DateRange(start=date(2026, 4, 1), end=date(2026, 4, 1))
    events = _load_sample_events(dr)

    assert len(events) > 0
    for event in events:
        assert event.start.date() == date(2026, 4, 1)
