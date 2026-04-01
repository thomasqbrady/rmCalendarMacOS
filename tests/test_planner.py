"""Tests for PDF planner generation."""

from datetime import date, datetime, timezone
from pathlib import Path

from rmcal.models import (
    DateRange,
    Event,
    PlannerConfig,
    WeekStart,
)
from rmcal.planner.generator import count_pages, generate_planner
from rmcal.planner.navigation import NavigationRegistry


def test_page_count_deterministic():
    """Page count must be identical for the same date range across runs."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31)),
    )
    count1 = count_pages(config)
    count2 = count_pages(config)
    assert count1 == count2
    assert count1 > 0


def test_page_count_includes_all_views():
    """Verify page count includes year, months, weeks, and days."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31)),
    )
    total = count_pages(config)
    # 1 year + 12 months + ~52 weeks + 365 days
    assert total > 400


def test_page_count_week_start_affects_count():
    """Different week start days may produce different week counts."""
    config_mon = PlannerConfig(
        date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31)),
        week_start=WeekStart.MONDAY,
    )
    config_sun = PlannerConfig(
        date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31)),
        week_start=WeekStart.SUNDAY,
    )
    count_mon = count_pages(config_mon)
    count_sun = count_pages(config_sun)
    # Both should have roughly the same number of pages
    assert abs(count_mon - count_sun) <= 2


def test_navigation_registry():
    """Test that NavigationRegistry tracks bookmarks correctly."""
    nav = NavigationRegistry()
    nav.register(nav.bm_year(2026), 0)
    nav.register(nav.bm_month(2026, 1), 1)
    nav.register(nav.bm_day(date(2026, 1, 15)), 50)

    assert nav.get_page(nav.bm_year(2026)) == 0
    assert nav.get_page(nav.bm_month(2026, 1)) == 1
    assert nav.get_page(nav.bm_day(date(2026, 1, 15))) == 50
    assert nav.get_page("nonexistent") is None


def test_generate_pdf(tmp_path: Path):
    """Test that PDF generation produces a valid file."""
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
        Event(
            summary="All Day Event",
            start=datetime(2026, 4, 20, 0, 0, tzinfo=timezone.utc),
            end=datetime(2026, 4, 21, 0, 0, tzinfo=timezone.utc),
            all_day=True,
            calendar_name="Test",
        ),
    ]

    output = tmp_path / "test_planner.pdf"
    result = generate_planner(config, events, output_path=output)

    assert result.exists()
    assert result.stat().st_size > 0

    # Verify with pypdf
    from pypdf import PdfReader

    reader = PdfReader(str(result))
    expected = count_pages(config)
    assert len(reader.pages) == expected


def test_generate_pdf_with_no_events(tmp_path: Path):
    """Test PDF generation with no events."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 7)),
    )
    output = tmp_path / "empty_planner.pdf"
    result = generate_planner(config, [], output_path=output)

    assert result.exists()
    assert result.stat().st_size > 0
