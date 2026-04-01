"""Configuration loading from TOML files."""

from __future__ import annotations

import tomllib
from datetime import date
from pathlib import Path

from rmcal.models import (
    AppConfig,
    CalendarSource,
    DateRange,
    Device,
    Handedness,
    Language,
    PageSize,
    PlannerConfig,
    RemarkableConfig,
    SleepScreenConfig,
    TimeFormat,
    WeekStart,
)

DEFAULT_CONFIG_PATH = Path("~/.config/rmcal/config.toml").expanduser()


def load_config(path: Path | None = None) -> AppConfig:
    """Load configuration from a TOML file."""
    config_path = path or DEFAULT_CONFIG_PATH
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Copy config.example.toml to {config_path} and edit it."
        )

    with open(config_path, "rb") as f:
        raw = tomllib.load(f)

    return _parse_config(raw)


def _parse_config(raw: dict) -> AppConfig:
    planner_raw = raw.get("planner", {})
    date_range = _parse_date_range(planner_raw)

    planner = PlannerConfig(
        date_range=date_range,
        page_size=PageSize(planner_raw.get("page_size", "A4")),
        device=Device(planner_raw.get("device", "rm2")),
        week_start=WeekStart(planner_raw.get("week_start", "monday")),
        time_format=TimeFormat(planner_raw.get("time_format", "24h")),
        day_start_hour=planner_raw.get("day_start_hour", 7),
        day_end_hour=planner_raw.get("day_end_hour", 22),
        handedness=Handedness(planner_raw.get("handedness", "right")),
        language=Language(planner_raw.get("language", "en")),
    )

    calendars = [
        CalendarSource(
            name=cal["name"],
            url=_normalize_url(cal["url"]),
            prefix=cal.get("prefix", ""),
        )
        for cal in raw.get("calendars", [])
    ]

    rm_raw = raw.get("remarkable", {})
    remarkable = RemarkableConfig(
        host=rm_raw.get("host", "10.11.99.1"),
        user=rm_raw.get("user", "root"),
        auth=rm_raw.get("auth", ""),
        folder=rm_raw.get("folder", ""),
        document_name=rm_raw.get("document_name", "rmCalendarMacOS Planner"),
    )

    ss_raw = raw.get("sleep_screen", {})
    sleep_screen = SleepScreenConfig(enabled=ss_raw.get("enabled", False))

    return AppConfig(
        planner=planner,
        calendars=calendars,
        remarkable=remarkable,
        sleep_screen=sleep_screen,
    )


def _parse_date_range(planner_raw: dict) -> DateRange:
    start_str = planner_raw.get("start_date", "auto")
    end_str = planner_raw.get("end_date", "auto")

    if start_str == "auto":
        today = date.today()
        start = today.replace(day=1)
    else:
        start = date.fromisoformat(start_str)

    if end_str == "auto":
        # 12 months from start
        year = start.year + (start.month + 11) // 12
        month = (start.month + 11) % 12 + 1
        end = date(year, month, 1) - __import__("datetime").timedelta(days=1)
    else:
        end = date.fromisoformat(end_str)

    if end <= start:
        raise ValueError(f"end_date ({end}) must be after start_date ({start})")

    return DateRange(start=start, end=end)


def _normalize_url(url: str) -> str:
    """Convert webcal:// URLs to https://."""
    if url.startswith("webcal://"):
        return "https://" + url[len("webcal://"):]
    return url
