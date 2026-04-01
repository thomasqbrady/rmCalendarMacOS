"""Shared data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum


class Language(StrEnum):
    EN = "en"
    FR = "fr"
    ES = "es"
    IT = "it"
    DE = "de"
    JA = "ja"


class WeekStart(StrEnum):
    MONDAY = "monday"
    SUNDAY = "sunday"


class TimeFormat(StrEnum):
    H24 = "24h"
    H12 = "12h"


class Handedness(StrEnum):
    LEFT = "left"
    RIGHT = "right"


class PageSize(StrEnum):
    A4 = "A4"
    LETTER = "letter"


class Device(StrEnum):
    RM2 = "rm2"
    PAPER_PRO = "paper_pro"


@dataclass(frozen=True)
class Event:
    """A single calendar event."""

    summary: str
    start: datetime
    end: datetime
    all_day: bool
    location: str | None = None
    calendar_name: str = ""
    calendar_id: str = ""
    prefix: str = ""
    attendees: tuple[str, ...] = ()

    @property
    def display_name(self) -> str:
        if self.prefix:
            return f"[{self.prefix}] {self.summary}"
        return self.summary


@dataclass(frozen=True)
class CalendarSource:
    """A calendar ICS feed configuration."""

    name: str
    url: str
    prefix: str = ""


@dataclass(frozen=True)
class DateRange:
    """A date range for planner generation."""

    start: date
    end: date

    @property
    def hash_key(self) -> str:
        """Stable hash for detecting range changes (annotation preservation)."""
        return f"{self.start.isoformat()}:{self.end.isoformat()}"


@dataclass(frozen=True)
class PlannerConfig:
    """Configuration for planner generation."""

    date_range: DateRange
    page_size: PageSize = PageSize.A4
    device: Device = Device.RM2
    week_start: WeekStart = WeekStart.MONDAY
    time_format: TimeFormat = TimeFormat.H24
    day_start_hour: int = 7
    day_end_hour: int = 22
    handedness: Handedness = Handedness.RIGHT
    language: Language = Language.EN


@dataclass(frozen=True)
class RemarkableConfig:
    """Configuration for reMarkable connection."""

    host: str = "10.11.99.1"
    user: str = "root"
    auth: str = ""  # password or path to SSH key
    folder: str = ""  # parent folder UUID on device
    document_name: str = "rmCalendar"


@dataclass(frozen=True)
class SleepScreenConfig:
    """Configuration for sleep screen generation."""

    enabled: bool = False


@dataclass
class AppConfig:
    """Top-level application configuration."""

    planner: PlannerConfig
    calendars: list[CalendarSource] = field(default_factory=list)
    remarkable: RemarkableConfig = field(default_factory=RemarkableConfig)
    sleep_screen: SleepScreenConfig = field(default_factory=SleepScreenConfig)
