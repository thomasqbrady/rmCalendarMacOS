#!/usr/bin/env python3
"""Run this script directly in Terminal to grant calendar access.

macOS requires an interactive terminal session to show the permission dialog.
After granting access, the rmcal CLI will work without prompting again.
"""

import sys
import threading

try:
    from EventKit import EKEntityTypeEvent, EKEventStore
    from Foundation import NSDate, NSRunLoop, NSDefaultRunLoopMode
except ImportError:
    print("pyobjc-framework-EventKit not installed.")
    print("Run: pip install pyobjc-framework-EventKit")
    sys.exit(1)


def main():
    store = EKEventStore.alloc().init()

    status = EKEventStore.authorizationStatusForEntityType_(EKEntityTypeEvent)
    status_names = {0: "Not Determined", 1: "Restricted", 2: "Authorized (legacy)", 3: "Full Access", 4: "Write Only"}
    print(f"Current calendar access status: {status_names.get(status, status)}")

    if status in (2, 3):
        print("Already have calendar access!")
        _show_calendars(store)
        return

    print("Requesting calendar access... (you should see a macOS permission dialog)")

    result = threading.Event()
    granted_flag = [False]

    def handler(granted, error):
        granted_flag[0] = granted
        if error:
            print(f"Error: {error.localizedDescription()}")
        result.set()

    try:
        store.requestFullAccessToEventsWithCompletion_(handler)
    except AttributeError:
        store.requestAccessToEntityType_completion_(EKEntityTypeEvent, handler)

    result.wait(timeout=120)

    if granted_flag[0]:
        print("Calendar access granted!")
        _show_calendars(store)
    else:
        print("Calendar access denied.")
        print("Go to System Settings > Privacy & Security > Calendars")
        print("and enable access for Terminal (or your Python installation).")


def _show_calendars(store):
    from EventKit import EKEntityTypeEvent
    calendars = store.calendarsForEntityType_(EKEntityTypeEvent)
    print(f"\nFound {len(calendars)} calendars:")
    for cal in calendars:
        print(f"  - {cal.title()}")

    # Show a few upcoming events
    from datetime import datetime, timezone, timedelta
    now = datetime.now(tz=timezone.utc)
    start_ts = now.timestamp()
    end_ts = (now + timedelta(days=14)).timestamp()
    ns_start = NSDate.dateWithTimeIntervalSince1970_(start_ts)
    ns_end = NSDate.dateWithTimeIntervalSince1970_(end_ts)

    predicate = store.predicateForEventsWithStartDate_endDate_calendars_(
        ns_start, ns_end, calendars
    )
    events = store.eventsMatchingPredicate_(predicate)

    if events:
        print(f"\nNext 2 weeks: {len(events)} events")
        for ev in events[:15]:
            start = datetime.fromtimestamp(ev.startDate().timeIntervalSince1970(), tz=timezone.utc)
            if ev.isAllDay():
                time_str = start.strftime("%b %d (all day)")
            else:
                time_str = start.strftime("%b %d %H:%M")
            cal_name = ev.calendar().title() if ev.calendar() else "?"
            print(f"  {time_str} - {ev.title()} [{cal_name}]")
        if len(events) > 15:
            print(f"  ... and {len(events) - 15} more")
    else:
        print("\nNo events in the next 2 weeks.")


if __name__ == "__main__":
    main()
