"""Parse ICS data into Event models."""

from __future__ import annotations

from datetime import date, datetime, timezone

import recurring_ical_events
from icalendar import Calendar

from rmcal.models import CalendarSource, DateRange, Event


def parse_events(
    ics_data: list[tuple[CalendarSource, str]],
    date_range: DateRange,
) -> list[Event]:
    """Parse all ICS data into a sorted list of Events within the date range."""
    events: list[Event] = []
    for source, ics_text in ics_data:
        events.extend(_parse_single_calendar(source, ics_text, date_range))
    events.sort(key=lambda e: (e.start, e.end, e.summary))
    return events


def _parse_single_calendar(
    source: CalendarSource,
    ics_text: str,
    date_range: DateRange,
) -> list[Event]:
    """Parse a single ICS feed into Events."""
    cal = Calendar.from_ical(ics_text)

    # Use recurring_ical_events to expand recurring events within range
    start_dt = datetime.combine(date_range.start, datetime.min.time(), tzinfo=timezone.utc)
    end_dt = datetime.combine(date_range.end, datetime.max.time(), tzinfo=timezone.utc)
    recurring = recurring_ical_events.of(cal).between(start_dt, end_dt)

    events: list[Event] = []
    for component in recurring:
        if component.name != "VEVENT":
            continue

        dtstart = component.get("DTSTART")
        dtend = component.get("DTEND")
        if dtstart is None:
            continue

        start_val = dtstart.dt if hasattr(dtstart, "dt") else dtstart
        end_val = dtend.dt if dtend and hasattr(dtend, "dt") else dtend

        all_day = isinstance(start_val, date) and not isinstance(start_val, datetime)

        if all_day:
            start_datetime = datetime.combine(start_val, datetime.min.time(), tzinfo=timezone.utc)
            if end_val:
                end_datetime = datetime.combine(end_val, datetime.min.time(), tzinfo=timezone.utc)
            else:
                end_datetime = start_datetime
        else:
            start_datetime = _ensure_local(start_val)
            end_datetime = _ensure_local(end_val) if end_val else start_datetime

        summary = str(component.get("SUMMARY", ""))
        location = component.get("LOCATION")
        if location:
            location = str(location)

        events.append(
            Event(
                summary=summary,
                start=start_datetime,
                end=end_datetime,
                all_day=all_day,
                location=location,
                calendar_name=source.name,
                prefix=source.prefix,
            )
        )

    return events


def _ensure_local(dt: datetime | date) -> datetime:
    """Convert a datetime to local timezone for correct display."""
    if isinstance(dt, datetime):
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc).astimezone()
        return dt.astimezone()
    return datetime.combine(dt, datetime.min.time(), tzinfo=timezone.utc).astimezone()
