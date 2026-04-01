"""Read calendar events directly from macOS Calendar via EventKit."""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from rmcal.models import DateRange, Event


@dataclass(frozen=True)
class MacCalendar:
    """A macOS calendar with its name and unique ID."""

    title: str
    calendar_id: str
    source: str  # e.g. "iCloud", "Google", "Local"


def is_available() -> bool:
    """Check if macOS EventKit is available."""
    if sys.platform != "darwin":
        return False
    try:
        import EventKit  # noqa: F401

        return True
    except ImportError:
        return False


def _get_store():
    """Get an authorized EKEventStore, or raise PermissionError."""
    from EventKit import EKEventStore

    store = EKEventStore.alloc().init()
    granted = _request_access(store)
    if not granted:
        raise PermissionError(
            "Calendar access denied. Grant access in "
            "System Settings > Privacy & Security > Calendars."
        )
    return store


def list_macos_calendars() -> list[MacCalendar]:
    """List all available macOS calendars.

    Requests permission if not yet granted.
    """
    from EventKit import EKEntityTypeEvent

    store = _get_store()
    calendars = store.calendarsForEntityType_(EKEntityTypeEvent)

    result: list[MacCalendar] = []
    for cal in calendars:
        source_name = ""
        src = cal.source()
        if src:
            source_name = str(src.title())

        result.append(
            MacCalendar(
                title=str(cal.title()),
                calendar_id=str(cal.calendarIdentifier()),
                source=source_name,
            )
        )

    result.sort(key=lambda c: (c.source, c.title))
    return result


def fetch_macos_events(
    date_range: DateRange,
    calendar_ids: set[str] | None = None,
) -> list[Event]:
    """Fetch events from macOS calendars within the date range.

    Args:
        date_range: The date range to fetch events for.
        calendar_ids: If provided, only include events from these calendar IDs.
                      If None, include all calendars.
    """
    from EventKit import EKEntityTypeEvent
    from Foundation import NSDate

    store = _get_store()

    # Build date range as NSDate
    start_ts = datetime.combine(date_range.start, datetime.min.time(), tzinfo=timezone.utc).timestamp()
    end_ts = datetime.combine(date_range.end, datetime.max.time(), tzinfo=timezone.utc).timestamp()

    ns_start = NSDate.dateWithTimeIntervalSince1970_(start_ts)
    ns_end = NSDate.dateWithTimeIntervalSince1970_(end_ts)

    # Filter calendars if IDs are specified
    all_calendars = store.calendarsForEntityType_(EKEntityTypeEvent)
    if calendar_ids is not None:
        calendars = [c for c in all_calendars if str(c.calendarIdentifier()) in calendar_ids]
        if not calendars:
            return []
    else:
        calendars = all_calendars

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        ns_start, ns_end, calendars
    )
    ek_events = store.eventsMatchingPredicate_(predicate)

    if ek_events is None:
        return []

    # Convert to our Event model
    events: list[Event] = []
    for ek_ev in ek_events:
        summary = ek_ev.title() or "(No title)"
        all_day = bool(ek_ev.isAllDay())

        start_dt = _nsdate_to_datetime(ek_ev.startDate())
        end_dt = _nsdate_to_datetime(ek_ev.endDate())

        location = ek_ev.location()
        if location:
            location = str(location)
        else:
            location = None

        cal_name = ""
        cal_id = ""
        cal = ek_ev.calendar()
        if cal:
            cal_name = str(cal.title())
            cal_id = str(cal.calendarIdentifier())

        attendee_names: list[str] = []
        ek_attendees = ek_ev.attendees()
        if ek_attendees:
            for att in ek_attendees:
                name = att.name()
                if name:
                    attendee_names.append(str(name))

        events.append(
            Event(
                summary=str(summary),
                start=start_dt,
                end=end_dt,
                all_day=all_day,
                location=location,
                calendar_name=cal_name,
                calendar_id=cal_id,
                attendees=tuple(attendee_names),
            )
        )

    events.sort(key=lambda e: (e.start, e.end, e.summary))
    return events


def _request_access(store) -> bool:
    """Request calendar access, blocking until the user responds."""
    from EventKit import EKEntityTypeEvent, EKEventStore

    status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)

    # Already authorized
    # EKAuthorizationStatusAuthorized = 2, EKAuthorizationStatusFullAccess = 3
    if status in (2, 3):
        return True

    # Request access using a threading event to block until completion
    result = threading.Event()
    granted_flag = [False]

    def handler(granted, error):
        granted_flag[0] = granted
        result.set()

    # Try the modern API first (macOS Ventura+), fall back to legacy
    try:
        store.requestFullAccessToEventsWithCompletion_(handler)
    except AttributeError:
        store.requestAccessToEntityType_completion_(EKEntityTypeEvent, handler)

    result.wait(timeout=120)
    return granted_flag[0]


def _nsdate_to_datetime(nsdate) -> datetime:
    """Convert an NSDate to a Python datetime in local timezone."""
    timestamp = nsdate.timeIntervalSince1970()
    return datetime.fromtimestamp(timestamp).astimezone()
