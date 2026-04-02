"""Tests for PDF planner generation."""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from rmcal.models import (
    DateRange,
    Event,
    PlannerConfig,
    WeekStart,
)
from rmcal.planner.generator import count_pages, generate_planner
from rmcal.planner.navigation import NavigationRegistry


def test_page_count_one_month():
    """April 2026 (30 days) should produce exactly 1 year + 1 month + 5 weeks + 30 days."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30)),
    )
    total = count_pages(config)
    # 1 year + 1 month + 5 weeks (Mar 30 – May 3 covers 5 ISO weeks) + 30 days = 37
    assert total == 37


def test_page_count_full_year():
    """Full year 2026 should produce 1 year + 12 months + 53 weeks + 365 days."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31)),
    )
    total = count_pages(config)
    assert total == 1 + 12 + 53 + 365


def test_page_count_with_meeting_notes():
    """Meeting notes pages add one page per non-all-day meeting event."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 7)),
    )
    events = [
        Event(
            summary="Meeting A",
            start=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
            end=datetime(2026, 4, 2, 11, 0, tzinfo=timezone.utc),
            all_day=False,
            calendar_name="Work",
            calendar_id="cal-1",
        ),
        Event(
            summary="Meeting B",
            start=datetime(2026, 4, 3, 14, 0, tzinfo=timezone.utc),
            end=datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc),
            all_day=False,
            calendar_name="Work",
            calendar_id="cal-1",
        ),
        Event(
            summary="Holiday",
            start=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
            end=datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc),
            all_day=True,
            calendar_name="Work",
            calendar_id="cal-1",
        ),
    ]
    base = count_pages(config)
    with_meetings = count_pages(config, events, meeting_notes_calendar_ids={"cal-1"})
    # Two non-all-day meetings = 2 extra pages (all-day event excluded)
    assert with_meetings == base + 2


def test_week_start_produces_same_component_counts():
    """Monday and Sunday week starts should only differ in week count by at most 1."""
    dr = DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31))
    config_mon = PlannerConfig(date_range=dr, week_start=WeekStart.MONDAY)
    config_sun = PlannerConfig(date_range=dr, week_start=WeekStart.SUNDAY)
    # Both have the same year/month/day pages; only weeks can differ
    diff = abs(count_pages(config_mon) - count_pages(config_sun))
    assert diff <= 1


def test_navigation_registry_stores_and_retrieves():
    nav = NavigationRegistry()
    nav.register(nav.bm_year(2026), 0)
    nav.register(nav.bm_month(2026, 1), 1)
    nav.register(nav.bm_day(date(2026, 1, 15)), 50)

    assert nav.get_page(nav.bm_year(2026)) == 0
    assert nav.get_page(nav.bm_month(2026, 1)) == 1
    assert nav.get_page(nav.bm_day(date(2026, 1, 15))) == 50


def test_navigation_registry_returns_none_for_unknown():
    nav = NavigationRegistry()
    assert nav.get_page("nonexistent") is None


def test_generate_pdf_produces_correct_page_count(tmp_path: Path):
    """Generated PDF must have exactly as many pages as count_pages predicts."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30)),
    )
    events = [
        Event(
            summary="Test Event",
            start=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
            end=datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc),
            all_day=False,
            calendar_name="Test",
        ),
    ]

    output = tmp_path / "test_planner.pdf"
    result = generate_planner(config, events, output_path=output)

    assert result.exists()
    assert result.stat().st_size > 0

    from pypdf import PdfReader
    reader = PdfReader(str(result))
    assert len(reader.pages) == count_pages(config)


def test_generate_pdf_with_no_events(tmp_path: Path):
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 7)),
    )
    output = tmp_path / "empty_planner.pdf"
    result = generate_planner(config, [], output_path=output)

    assert result.exists()
    assert result.stat().st_size > 0

    from pypdf import PdfReader
    reader = PdfReader(str(result))
    assert len(reader.pages) == count_pages(config)
