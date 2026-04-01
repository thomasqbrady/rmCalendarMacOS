"""Week view layout — 7-day time-slot grid with events."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from rmcal.i18n.translations import weekday_short, month_name_short, label
from rmcal.models import Event, PlannerConfig, WeekStart
from rmcal.planner.navigation import NavigationRegistry
from rmcal.planner.styles import (
    BLACK,
    GRAY,
    LIGHT_GRAY,
    VERY_LIGHT_GRAY,
    BODY_SIZE,
    HEADER_SIZE,
    SMALL_SIZE,
    SUBTITLE_SIZE,
    TINY_SIZE,
    THIN,
    HAIRLINE,
    MEDIUM,
    PageLayout,
    get_font,
)


def assign_pages(
    nav: NavigationRegistry,
    start_page: int,
    config: PlannerConfig,
) -> int:
    """Assign page numbers for all week pages."""
    page = start_page
    for week_start in _iter_weeks(config):
        iso = week_start.isocalendar()
        nav.register(nav.bm_week(iso[0], iso[1]), page)
        page += 1
    return page


def render(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    events: list[Event],
    layout: PageLayout,
    meeting_events: list[Event] | None = None,
) -> None:
    """Render all week pages."""
    for week_start in _iter_weeks(config):
        _render_week_page(c, nav, config, layout, events, week_start, meeting_events)
        c.showPage()


def _render_week_page(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    events: list[Event],
    week_start: date,
    meeting_events: list[Event] | None = None,
) -> None:
    lang = config.language
    font = get_font(lang)
    font_bold = get_font(lang, bold=True)

    iso = week_start.isocalendar()
    week_num = iso[1]
    year = iso[0]

    # Bookmark
    c.bookmarkPage(nav.bm_week(year, week_num))

    # Title: "Week 13, March 2026"
    month_label = month_name_short(lang, week_start.month)
    title = f"{label(lang, 'week')} {week_num}, {month_label} {week_start.year}"
    c.setFont(font_bold, SUBTITLE_SIZE)
    c.setFillColorRGB(*BLACK)
    title_y = layout.content_top - SUBTITLE_SIZE
    c.drawString(layout.content_x, title_y, title)

    # Nav: back to month
    month_bm = nav.bm_month(week_start.year, week_start.month)
    if nav.get_page(month_bm) is not None:
        c.setFont(font, SMALL_SIZE)
        c.setFillColorRGB(*GRAY)
        nav_text = month_label
        nav_x = layout.content_right - c.stringWidth(nav_text, font, SMALL_SIZE)
        c.drawString(nav_x, title_y, nav_text)
        tw = c.stringWidth(nav_text, font, SMALL_SIZE)
        c.linkAbsolute(nav_text, month_bm, (nav_x - 1, title_y - 1, nav_x + tw + 1, title_y + SMALL_SIZE + 1))

    # Week prev/next arrows
    _draw_week_arrows(c, nav, config, layout, week_start, title_y, font_bold)

    days = [week_start + timedelta(days=i) for i in range(7)]

    # All-day events banner
    all_day_events = _get_all_day_events(events, days)
    banner_height = max(len(all_day_events), 1) * (SMALL_SIZE + 1 * mm) + 2 * mm
    banner_top = title_y - 8 * mm
    banner_bottom = banner_top - banner_height

    if all_day_events:
        c.setFillColorRGB(*VERY_LIGHT_GRAY)
        c.rect(layout.content_x, banner_bottom, layout.content_width, banner_height, fill=1, stroke=0)
        c.setFont(font, SMALL_SIZE)
        c.setFillColorRGB(*BLACK)
        ady = banner_top - SMALL_SIZE - 1 * mm
        for ev in all_day_events[:5]:
            c.drawString(layout.content_x + 2 * mm, ady, ev.display_name)
            ady -= SMALL_SIZE + 1 * mm

    # Day columns with time slots
    col_w = layout.content_width / 7
    grid_top = banner_bottom - 6 * mm
    grid_bottom = layout.content_bottom

    hours = list(range(config.day_start_hour, config.day_end_hour + 1))
    num_hours = len(hours)
    row_h = (grid_top - grid_bottom) / num_hours

    # Day headers
    header_y = banner_bottom - 2 * mm
    c.setFont(font_bold, SMALL_SIZE)
    for i, d in enumerate(days):
        cx = layout.content_x + i * col_w + col_w / 2
        day_label = f"{weekday_short(lang, d.weekday())} {d.day}"
        c.setFillColorRGB(*BLACK)
        c.drawCentredString(cx, header_y, day_label)

        # Clickable link to day view
        day_bm = nav.bm_day(d)
        if nav.get_page(day_bm) is not None:
            tw = c.stringWidth(day_label, font_bold, SMALL_SIZE)
            c.linkAbsolute(
                day_label, day_bm,
                (cx - tw / 2 - 1, header_y - 1, cx + tw / 2 + 1, header_y + SMALL_SIZE + 1),
            )

    # Time slot grid
    c.setStrokeColorRGB(*LIGHT_GRAY)
    c.setLineWidth(HAIRLINE)

    for h_idx, hour in enumerate(hours):
        y = grid_top - h_idx * row_h

        # Horizontal line
        c.line(layout.content_x, y, layout.content_right, y)

        # Hour label
        c.setFont(font, TINY_SIZE)
        c.setFillColorRGB(*GRAY)
        hour_label = _format_hour_12(hour)
        c.drawString(layout.content_x - 1 * mm, y - TINY_SIZE, hour_label)

    # Vertical column dividers
    for i in range(1, 7):
        x = layout.content_x + i * col_w
        c.line(x, grid_top, x, grid_bottom)

    # Place timed events
    timed_events = _get_timed_events(events, days)
    for ev in timed_events:
        ev_date = ev.start.date() if isinstance(ev.start, datetime) else ev.start
        day_idx = (ev_date - week_start).days
        if not 0 <= day_idx < 7:
            continue

        col_x = layout.content_x + day_idx * col_w + 1 * mm
        ev_w = col_w - 2 * mm

        # Calculate vertical position from time
        start_hour = ev.start.hour + ev.start.minute / 60.0
        end_hour = ev.end.hour + ev.end.minute / 60.0 if ev.end else start_hour + 1

        start_offset = max(0, start_hour - config.day_start_hour)
        end_offset = min(num_hours, end_hour - config.day_start_hour)

        ev_top = grid_top - start_offset * row_h
        ev_bottom = grid_top - end_offset * row_h
        ev_height = ev_top - ev_bottom

        if ev_height < TINY_SIZE:
            continue

        # Event background
        c.setFillColorRGB(*VERY_LIGHT_GRAY)
        c.rect(col_x, ev_bottom, ev_w, ev_height, fill=1, stroke=0)

        # Event text
        c.setFont(font, TINY_SIZE)
        c.setFillColorRGB(*BLACK)
        text = ev.display_name
        max_chars = int(ev_w / (TINY_SIZE * 0.5))
        if len(text) > max_chars:
            text = text[: max_chars - 1] + "…"
        text_y = ev_top - TINY_SIZE - 0.5 * mm
        if text_y >= ev_bottom:
            c.drawString(col_x + 0.5 * mm, text_y, text)

            # Link to meeting notes page if one exists
            if meeting_events:
                from rmcal.planner.layouts.meeting_notes import get_day_meetings
                day_meetings = get_day_meetings(meeting_events, ev_date)
                if ev in day_meetings:
                    idx = day_meetings.index(ev)
                    mn_bm = nav.bm_meeting_note(ev_date, idx)
                    if nav.get_page(mn_bm) is not None:
                        c.linkAbsolute(
                            text, mn_bm,
                            (col_x, ev_bottom, col_x + ev_w, ev_top),
                        )


def _iter_weeks(config: PlannerConfig):
    """Iterate over week start dates within the date range."""
    dr = config.date_range
    # Find the first week start on or before dr.start
    d = dr.start
    if config.week_start == WeekStart.MONDAY:
        d -= timedelta(days=d.weekday())  # Back to Monday
    else:
        d -= timedelta(days=(d.weekday() + 1) % 7)  # Back to Sunday

    while d <= dr.end:
        # Only include weeks that overlap the date range
        week_end = d + timedelta(days=6)
        if week_end >= dr.start and d <= dr.end:
            yield d
        d += timedelta(days=7)


def _get_all_day_events(events: list[Event], days: list[date]) -> list[Event]:
    """Get all-day events for the given week."""
    day_set = set(days)
    result = []
    for ev in events:
        if not ev.all_day:
            continue
        ev_date = ev.start.date() if isinstance(ev.start, datetime) else ev.start
        if ev_date in day_set:
            result.append(ev)
    return result


def _get_timed_events(events: list[Event], days: list[date]) -> list[Event]:
    """Get timed (non-all-day) events for the given week."""
    day_set = set(days)
    result = []
    for ev in events:
        if ev.all_day:
            continue
        ev_date = ev.start.date() if isinstance(ev.start, datetime) else ev.start
        if ev_date in day_set:
            result.append(ev)
    return result


def _draw_week_arrows(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    week_start: date,
    y: float,
    font_bold: str,
) -> None:
    """Draw prev/next week arrows."""
    prev_start = week_start - timedelta(days=7)
    prev_iso = prev_start.isocalendar()
    prev_bm = nav.bm_week(prev_iso[0], prev_iso[1])
    if nav.get_page(prev_bm) is not None:
        c.setFont(font_bold, BODY_SIZE)
        c.setFillColorRGB(*GRAY)
        x = layout.content_right - 30 * mm
        c.drawString(x, y, "<")
        tw = c.stringWidth("<", font_bold, BODY_SIZE)
        c.linkAbsolute("prev", prev_bm, (x - 1, y - 1, x + tw + 1, y + BODY_SIZE + 1))

    next_start = week_start + timedelta(days=7)
    next_iso = next_start.isocalendar()
    next_bm = nav.bm_week(next_iso[0], next_iso[1])
    if nav.get_page(next_bm) is not None:
        c.setFont(font_bold, BODY_SIZE)
        c.setFillColorRGB(*GRAY)
        x = layout.content_right - 20 * mm
        c.drawString(x, y, ">")
        tw = c.stringWidth(">", font_bold, BODY_SIZE)
        c.linkAbsolute("next", next_bm, (x - 1, y - 1, x + tw + 1, y + BODY_SIZE + 1))


def _format_hour_12(hour: int) -> str:
    """Format an hour in 12-hour format."""
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"
