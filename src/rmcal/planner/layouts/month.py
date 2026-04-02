"""Month view layout — calendar grid with event summaries."""

from __future__ import annotations

import calendar
from datetime import date, datetime, timezone

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from rmcal.i18n.translations import month_name, weekday_short, label
from rmcal.models import Event, PlannerConfig, Handedness
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
    THIN,
    HAIRLINE,
    MEDIUM,
    PageLayout,
    get_font,
    get_calendar_stripe,
)


def assign_pages(
    nav: NavigationRegistry,
    start_page: int,
    config: PlannerConfig,
) -> int:
    """Assign page numbers for all month pages."""
    page = start_page
    dr = config.date_range
    year, month = dr.start.year, dr.start.month
    end_year, end_month = dr.end.year, dr.end.month

    while (year, month) <= (end_year, end_month):
        nav.register(nav.bm_month(year, month), page)
        page += 1
        month += 1
        if month > 12:
            month = 1
            year += 1
    return page


def render(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    events: list[Event],
    layout: PageLayout,
    meeting_events: list[Event] | None = None,
) -> None:
    """Render all month pages."""
    dr = config.date_range
    year, month = dr.start.year, dr.start.month
    end_year, end_month = dr.end.year, dr.end.month

    while (year, month) <= (end_year, end_month):
        _render_month_page(c, nav, config, layout, events, year, month, meeting_events)
        c.showPage()
        month += 1
        if month > 12:
            month = 1
            year += 1


def _render_month_page(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    events: list[Event],
    year: int,
    month: int,
    meeting_events: list[Event] | None = None,
) -> None:
    lang = config.language
    font = get_font(lang)
    font_bold = get_font(lang, bold=True)

    # Bookmark
    c.bookmarkPage(nav.bm_month(year, month))

    # Title: "March 2026"
    title = f"{month_name(lang, month)} {year}"
    c.setFont(font_bold, SUBTITLE_SIZE)
    c.setFillColorRGB(*BLACK)
    title_y = layout.content_top - SUBTITLE_SIZE
    c.drawString(layout.content_x, title_y, title)

    # Navigation: back to year
    year_bm = nav.bm_year(year)
    _draw_nav_link(c, layout, nav, year_bm, str(year), title_y, font, BODY_SIZE)

    # Prev/Next month arrows
    _draw_month_arrows(c, nav, config, layout, year, month, title_y, font_bold)

    # Weekday headers
    first_weekday = 0 if config.week_start.value == "monday" else 6
    header_y = title_y - 10 * mm
    col_w = layout.content_width / 7

    c.setFont(font_bold, SMALL_SIZE)
    c.setFillColorRGB(*GRAY)
    for i in range(7):
        day_idx = (i + first_weekday) % 7
        cx = layout.content_x + i * col_w + col_w / 2
        c.drawCentredString(cx, header_y, weekday_short(lang, day_idx))

    # Calendar grid
    cal = calendar.Calendar(firstweekday=first_weekday)
    weeks = cal.monthdayscalendar(year, month)
    num_weeks = len(weeks)

    grid_top = header_y - 4 * mm
    grid_height = grid_top - layout.content_bottom
    row_h = grid_height / num_weeks

    # Get events for this month
    month_events = _get_month_events(events, year, month)

    for week_idx, week in enumerate(weeks):
        row_top = grid_top - week_idx * row_h
        row_bottom = row_top - row_h

        # Grid lines
        c.setStrokeColorRGB(*LIGHT_GRAY)
        c.setLineWidth(HAIRLINE)
        c.line(layout.content_x, row_bottom, layout.content_right, row_bottom)

        for i, day in enumerate(week):
            cell_x = layout.content_x + i * col_w
            if day == 0:
                continue

            # Day number
            c.setFont(font_bold, BODY_SIZE)
            c.setFillColorRGB(*BLACK)
            day_x = cell_x + 2 * mm
            day_y = row_top - BODY_SIZE - 1 * mm
            c.drawString(day_x, day_y, str(day))

            # Clickable link to day view
            day_date = date(year, month, day)
            day_bm = nav.bm_day(day_date)
            if nav.get_page(day_bm) is not None:
                tw = c.stringWidth(str(day), font_bold, BODY_SIZE)
                c.linkAbsolute(
                    str(day), day_bm,
                    (day_x - 1, day_y - 1, day_x + tw + 1, day_y + BODY_SIZE + 1),
                )

            # Event summaries (up to 3 per cell)
            day_events = month_events.get(day, [])
            event_y = day_y - SMALL_SIZE - 2 * mm
            max_events = min(3, int((day_y - row_bottom - BODY_SIZE - 3 * mm) / (SMALL_SIZE + 1 * mm)))

            c.setFont(font, SMALL_SIZE)
            for ev_idx, ev in enumerate(day_events[:max_events]):
                if event_y < row_bottom + 1 * mm:
                    break
                c.setFillColorRGB(*get_calendar_stripe(ev.calendar_name))
                # Truncate event name to fit cell
                ev_text = _truncate_text(c, ev.display_name, col_w - 4 * mm, font, SMALL_SIZE)
                c.drawString(cell_x + 2 * mm, event_y, ev_text)

                # Link to meeting notes page if one exists
                if meeting_events and not ev.all_day:
                    from rmcal.planner.layouts.meeting_notes import get_day_meetings
                    day_meetings = get_day_meetings(meeting_events, day_date)
                    if ev in day_meetings:
                        idx = day_meetings.index(ev)
                        mn_bm = nav.bm_meeting_note(day_date, idx)
                        if nav.get_page(mn_bm) is not None:
                            tw = c.stringWidth(ev_text, font, SMALL_SIZE)
                            c.linkAbsolute(
                                ev_text, mn_bm,
                                (cell_x + 2 * mm - 1, event_y - 1, cell_x + 2 * mm + tw + 1, event_y + SMALL_SIZE + 1),
                            )

                event_y -= SMALL_SIZE + 1 * mm

            if len(day_events) > max_events:
                c.setFillColorRGB(*GRAY)
                c.drawString(cell_x + 2 * mm, event_y, f"+{len(day_events) - max_events} more")

        # Week number on the side
        # Find the first non-zero day in this week to get ISO week number
        first_day = next((d for d in week if d > 0), None)
        if first_day:
            d = date(year, month, first_day)
            iso_week = d.isocalendar()[1]
            week_bm = nav.bm_week(year, iso_week)
            wk_label = f"W{iso_week}"
            wk_y = row_top - row_h / 2
            c.setFont(font, SMALL_SIZE)
            c.setFillColorRGB(*GRAY)

            if config.handedness.value == "right":
                wk_x = layout.nav_x + 3 * mm
            else:
                wk_x = layout.nav_x + 3 * mm

            c.drawString(wk_x, wk_y, wk_label)
            if nav.get_page(week_bm) is not None:
                tw = c.stringWidth(wk_label, font, SMALL_SIZE)
                c.linkAbsolute(
                    wk_label, week_bm,
                    (wk_x - 1, wk_y - 1, wk_x + tw + 1, wk_y + SMALL_SIZE + 1),
                )

    # Vertical grid lines
    c.setStrokeColorRGB(*LIGHT_GRAY)
    c.setLineWidth(HAIRLINE)
    for i in range(1, 7):
        x = layout.content_x + i * col_w
        c.line(x, grid_top, x, grid_top - num_weeks * row_h)


# Import here to avoid circular
from rmcal.planner.styles import TINY_SIZE


def _get_month_events(
    events: list[Event], year: int, month: int
) -> dict[int, list[Event]]:
    """Group events by day of month."""
    result: dict[int, list[Event]] = {}
    for ev in events:
        ev_date = ev.start.date() if isinstance(ev.start, datetime) else ev.start
        if ev_date.year == year and ev_date.month == month:
            result.setdefault(ev_date.day, []).append(ev)
    return result


def _sanitize(text: str) -> str:
    """Replace characters that Helvetica cannot render with safe alternatives."""
    import unicodedata

    out: list[str] = []
    for ch in text:
        # Replace control characters (newlines, tabs, etc.) with space
        if unicodedata.category(ch).startswith("C"):
            out.append(" ")
            continue
        try:
            ch.encode("latin-1")
            out.append(ch)
        except UnicodeEncodeError:
            cat = unicodedata.category(ch)
            if cat.startswith("P") or cat.startswith("S") or cat.startswith("Z"):
                out.append(" ")
            else:
                decomposed = unicodedata.normalize("NFKD", ch)
                safe = decomposed.encode("latin-1", "ignore").decode("latin-1")
                out.append(safe if safe else "")
    return "".join(out)


def _truncate_text(
    c: Canvas, text: str, max_width: float, font: str, size: float
) -> str:
    """Sanitize and truncate text to fit within max_width, adding ellipsis if needed."""
    text = _sanitize(text)
    if c.stringWidth(text, font, size) <= max_width:
        return text
    for i in range(len(text) - 1, 0, -1):
        truncated = text[:i] + "..."
        if c.stringWidth(truncated, font, size) <= max_width:
            return truncated
    return "..."


def _draw_nav_link(
    c: Canvas,
    layout: PageLayout,
    nav: NavigationRegistry,
    bookmark: str,
    text: str,
    y: float,
    font: str,
    size: float,
) -> None:
    """Draw a navigation link at the right edge of the content area."""
    page = nav.get_page(bookmark)
    if page is None:
        return
    c.setFont(font, size)
    c.setFillColorRGB(*GRAY)
    tw = c.stringWidth(text, font, size)
    x = layout.content_right - tw
    c.drawString(x, y, text)
    c.linkAbsolute(text, bookmark, (x - 1, y - 1, x + tw + 1, y + size + 1))


def _draw_month_arrows(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    year: int,
    month: int,
    y: float,
    font_bold: str,
) -> None:
    """Draw prev/next month navigation arrows."""
    # Previous month
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    prev_bm = nav.bm_month(prev_year, prev_month)
    if nav.get_page(prev_bm) is not None:
        c.setFont(font_bold, HEADER_SIZE)
        c.setFillColorRGB(*GRAY)
        arrow = "<"
        x = layout.content_right - 35 * mm
        c.drawString(x, y, arrow)
        tw = c.stringWidth(arrow, font_bold, HEADER_SIZE)
        c.linkAbsolute(arrow, prev_bm, (x - 1, y - 1, x + tw + 1, y + HEADER_SIZE + 1))

    # Next month
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    next_bm = nav.bm_month(next_year, next_month)
    if nav.get_page(next_bm) is not None:
        c.setFont(font_bold, HEADER_SIZE)
        c.setFillColorRGB(*GRAY)
        arrow = ">"
        x = layout.content_right - 22 * mm
        c.drawString(x, y, arrow)
        tw = c.stringWidth(arrow, font_bold, HEADER_SIZE)
        c.linkAbsolute(arrow, next_bm, (x - 1, y - 1, x + tw + 1, y + HEADER_SIZE + 1))
