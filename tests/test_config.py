"""Tests for configuration loading."""

from datetime import date
from pathlib import Path

import pytest

from rmcal.config import _normalize_url, _parse_config
from rmcal.models import Language, PageSize, WeekStart


def test_parse_minimal_config():
    """Test parsing a config with minimal required fields."""
    raw = {
        "planner": {
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
        },
    }
    config = _parse_config(raw)
    assert config.planner.date_range.start == date(2026, 1, 1)
    assert config.planner.date_range.end == date(2026, 12, 31)
    assert config.planner.language == Language.EN
    assert config.planner.page_size == PageSize.A4
    assert config.planner.week_start == WeekStart.MONDAY


def test_parse_full_config():
    """Test parsing a full config with all fields."""
    raw = {
        "planner": {
            "start_date": "2026-01-01",
            "end_date": "2026-12-31",
            "page_size": "letter",
            "device": "paper_pro",
            "week_start": "sunday",
            "time_format": "12h",
            "day_start_hour": 8,
            "day_end_hour": 20,
            "handedness": "left",
            "language": "fr",
        },
        "calendars": [
            {"name": "Work", "url": "https://example.com/cal.ics", "prefix": "W"},
            {"name": "Personal", "url": "webcal://example.com/personal.ics"},
        ],
        "remarkable": {
            "host": "192.168.1.100",
            "auth": "mypassword",
            "document_name": "My Planner",
        },
        "sleep_screen": {"enabled": True},
    }
    config = _parse_config(raw)
    assert config.planner.language == Language.FR
    assert config.planner.page_size == PageSize.LETTER
    assert len(config.calendars) == 2
    assert config.calendars[0].prefix == "W"
    assert config.calendars[1].url == "https://example.com/personal.ics"
    assert config.remarkable.host == "192.168.1.100"
    assert config.sleep_screen.enabled is True


def test_normalize_webcal_url():
    """Test webcal:// to https:// conversion."""
    assert _normalize_url("webcal://example.com/cal.ics") == "https://example.com/cal.ics"
    assert _normalize_url("https://example.com/cal.ics") == "https://example.com/cal.ics"


def test_auto_date_range():
    """Test auto date range calculation."""
    raw = {"planner": {"start_date": "auto", "end_date": "auto"}}
    config = _parse_config(raw)
    today = date.today()
    assert config.planner.date_range.start.day == 1
    assert config.planner.date_range.start.month == today.month


def test_invalid_date_range():
    """Test that end before start raises error."""
    raw = {
        "planner": {
            "start_date": "2026-12-31",
            "end_date": "2026-01-01",
        },
    }
    with pytest.raises(ValueError, match="must be after"):
        _parse_config(raw)
