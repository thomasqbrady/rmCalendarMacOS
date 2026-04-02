"""Day view layout — detailed daily schedule with events and notes area."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from rmcal.i18n.translations import weekday_name, month_name, label
from rmcal.models import Event, PlannerConfig
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
    get_calendar_fill,
    get_calendar_stripe,
)


def assign_pages(
    nav: NavigationRegistry,
    start_page: int,
    config: PlannerConfig,
    meeting_events: list[Event] | None = None,
) -> int:
    """Assign page numbers for all day pages and their meeting notes pages."""
    from rmcal.planner.layouts.meeting_notes import get_day_meetings

    page = start_page
    d = config.date_range.start
    while d <= config.date_range.end:
        nav.register(nav.bm_day(d), page)
        page += 1
        # Meeting notes pages for this day
        if meeting_events:
            day_meetings = get_day_meetings(meeting_events, d)
            for idx in range(len(day_meetings)):
                nav.register(nav.bm_meeting_note(d, idx), page)
                page += 1
        d += timedelta(days=1)
    return page


def render(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    events: list[Event],
    layout: PageLayout,
    meeting_events: list[Event] | None = None,
) -> None:
    """Render all day pages and their meeting notes pages."""
    from rmcal.planner.layouts.meeting_notes import get_day_meetings, render_meeting_notes_page

    d = config.date_range.start
    while d <= config.date_range.end:
        day_events = _get_day_events(events, d)
        _render_day_page(c, nav, config, layout, d, day_events, meeting_events)
        c.showPage()
        # Render meeting notes pages for this day
        if meeting_events:
            day_meetings = get_day_meetings(meeting_events, d)
            for idx, event in enumerate(day_meetings):
                render_meeting_notes_page(c, nav, config, layout, d, event, idx)
                c.showPage()
        d += timedelta(days=1)


def _render_day_page(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    d: date,
    events: list[Event],
    meeting_events: list[Event] | None = None,
) -> None:
    lang = config.language
    font = get_font(lang)
    font_bold = get_font(lang, bold=True)

    # Bookmark
    c.bookmarkPage(nav.bm_day(d))

    # Title: "Wednesday, March 25, 2026"
    weekday = weekday_name(lang, d.weekday())
    month_str = month_name(lang, d.month)
    title = f"{weekday}, {month_str} {d.day}, {d.year}"
    c.setFont(font_bold, SUBTITLE_SIZE)
    c.setFillColorRGB(*BLACK)
    title_y = layout.content_top - SUBTITLE_SIZE
    c.drawString(layout.content_x, title_y, title)

    # Navigation: back to month, back to week
    nav_y = title_y
    _draw_day_nav(c, nav, config, layout, d, nav_y, font, font_bold)

    # Prev/Next day arrows
    _draw_day_arrows(c, nav, config, layout, d, title_y, font_bold)

    # Separate all-day and timed events
    all_day = [e for e in events if e.all_day]
    timed = [e for e in events if not e.all_day]

    # All-day events section
    section_y = title_y - 10 * mm
    if all_day:
        c.setFont(font_bold, SMALL_SIZE)
        c.setFillColorRGB(*GRAY)
        c.drawString(layout.content_x, section_y, label(lang, "all_day"))
        section_y -= SMALL_SIZE + 2 * mm

        c.setFont(font, BODY_SIZE)
        for ev in all_day:
            c.setFillColorRGB(*BLACK)
            c.drawString(layout.content_x + 3 * mm, section_y, ev.display_name)
            if ev.location:
                c.setFillColorRGB(*GRAY)
                c.setFont(font, SMALL_SIZE)
                c.drawString(layout.content_x + 3 * mm, section_y - SMALL_SIZE - 1 * mm, ev.location)
                section_y -= SMALL_SIZE + 1 * mm
                c.setFont(font, BODY_SIZE)
            section_y -= BODY_SIZE + 2 * mm

        section_y -= 2 * mm

    # Time-slot schedule
    hours = list(range(config.day_start_hour, config.day_end_hour + 1))
    num_hours = len(hours)

    # Reserve bottom 25% for notes area
    notes_height = (section_y - layout.content_bottom) * 0.25
    grid_bottom = layout.content_bottom + notes_height + 5 * mm
    grid_top = section_y
    row_h = (grid_top - grid_bottom) / num_hours

    time_col_w = 14 * mm
    event_x = layout.content_x + time_col_w
    event_w = layout.content_width - time_col_w

    for h_idx, hour in enumerate(hours):
        y = grid_top - h_idx * row_h

        # Hour label
        c.setFont(font, SMALL_SIZE)
        c.setFillColorRGB(*GRAY)
        hour_label = _format_hour_12(hour)
        c.drawRightString(layout.content_x + time_col_w - 2 * mm, y - SMALL_SIZE, hour_label)

        # Horizontal line
        c.setStrokeColorRGB(*LIGHT_GRAY)
        c.setLineWidth(HAIRLINE)
        c.line(event_x, y, layout.content_right, y)

        # Half-hour dashed line
        half_y = y - row_h / 2
        if half_y > grid_bottom:
            c.setDash(1, 2)
            c.line(event_x, half_y, layout.content_right, half_y)
            c.setDash()

    # Bottom line of grid
    c.line(event_x, grid_bottom, layout.content_right, grid_bottom)

    # Place timed events
    tiles = _compute_tile_columns(timed)
    for ev in timed:
        start_hour = ev.start.hour + ev.start.minute / 60.0
        end_hour = ev.end.hour + ev.end.minute / 60.0

        start_offset = max(0, start_hour - config.day_start_hour)
        end_offset = min(num_hours, end_hour - config.day_start_hour)

        ev_top = grid_top - start_offset * row_h
        ev_bottom = grid_top - end_offset * row_h
        ev_height = ev_top - ev_bottom

        if ev_height < SMALL_SIZE:
            ev_height = SMALL_SIZE + 2 * mm
            ev_bottom = ev_top - ev_height

        # Tile placement for concurrent events
        tile_col, tile_total = tiles.get(id(ev), (0, 1))
        tile_w = (event_w - 2 * mm) / tile_total
        ev_x = event_x + 1 * mm + tile_col * tile_w
        ev_w_actual = tile_w - 0.5 * mm

        # Event background
        c.setFillColorRGB(*get_calendar_fill(ev.calendar_name))
        c.rect(ev_x, ev_bottom, ev_w_actual, ev_height, fill=1, stroke=0)

        # Colored left-border stripe
        c.setStrokeColorRGB(*get_calendar_stripe(ev.calendar_name))
        c.setLineWidth(MEDIUM)
        c.line(ev_x, ev_bottom, ev_x, ev_top)

        available_w = ev_w_actual - 4 * mm
        text_x = ev_x + 2 * mm
        time_str = _format_time(ev.start, config.time_format.value)
        end_str = _format_time(ev.end, config.time_format.value)
        time_text = f"{time_str} – {end_str}"

        # Always show the event name — it's the most important element.
        # Layout priority: name > time > location.
        line1_y = ev_top - SMALL_SIZE - 1 * mm
        line2_y = ev_top - SMALL_SIZE - BODY_SIZE - 2 * mm
        line3_y = line2_y - SMALL_SIZE - 1 * mm

        name_text = _sanitize(ev.display_name)
        name_text = _truncate(c, name_text, available_w, font_bold, BODY_SIZE)

        if line2_y >= ev_bottom + 1 * mm:
            # Enough room for time on line 1, name on line 2
            c.setFont(font, SMALL_SIZE)
            c.setFillColorRGB(*GRAY)
            c.drawString(text_x, line1_y, time_text)

            c.setFont(font_bold, BODY_SIZE)
            c.setFillColorRGB(*BLACK)
            c.drawString(text_x, line2_y, name_text)

            # Location on line 3 if it fits
            if ev.location and line3_y >= ev_bottom + 1 * mm:
                loc_text = _sanitize(ev.location)
                loc_text = _truncate(c, loc_text, available_w, font, SMALL_SIZE)
                c.setFont(font, SMALL_SIZE)
                c.setFillColorRGB(*GRAY)
                c.drawString(text_x, line3_y, loc_text)
        else:
            # Only room for one line — show name (shrink if needed)
            size = BODY_SIZE
            if c.stringWidth(name_text, font_bold, size) > available_w:
                size = SMALL_SIZE
                name_text = _truncate(c, _sanitize(ev.display_name), available_w, font_bold, size)
            c.setFont(font_bold, size)
            c.setFillColorRGB(*BLACK)
            c.drawString(text_x, line1_y, name_text)

        # Link to meeting notes page if one exists
        if meeting_events:
            from rmcal.planner.layouts.meeting_notes import get_day_meetings
            day_meetings = get_day_meetings(meeting_events, d)
            if ev in day_meetings:
                idx = day_meetings.index(ev)
                mn_bm = nav.bm_meeting_note(d, idx)
                if nav.get_page(mn_bm) is not None:
                    c.linkAbsolute(
                        name_text, mn_bm,
                        (ev_x, ev_bottom, ev_x + ev_w_actual, ev_top),
                    )

    # Notes area
    notes_top = grid_bottom - 5 * mm
    c.setFont(font_bold, SMALL_SIZE)
    c.setFillColorRGB(*GRAY)
    c.drawString(layout.content_x, notes_top, label(lang, "notes"))

    # Ruled lines for notes
    notes_line_y = notes_top - SMALL_SIZE - 3 * mm
    line_spacing = 7 * mm
    c.setStrokeColorRGB(*VERY_LIGHT_GRAY)
    c.setLineWidth(HAIRLINE)
    while notes_line_y > layout.content_bottom:
        c.line(layout.content_x, notes_line_y, layout.content_right, notes_line_y)
        notes_line_y -= line_spacing


def _compute_tile_columns(timed: list[Event]) -> dict[int, tuple[int, int]]:
    """Compute column assignments for overlapping timed events.

    Returns a dict mapping id(event) to (col_index, total_cols) so that
    concurrent events can be placed side-by-side.
    """
    if not timed:
        return {}

    # Sort by start time
    sorted_events = sorted(timed, key=lambda e: e.start)

    # Greedy column assignment
    # columns[col] = end time of the last event placed in that column
    columns: list[datetime] = []
    col_assignment: dict[int, int] = {}

    for ev in sorted_events:
        placed = False
        for col_idx, col_end in enumerate(columns):
            if ev.start >= col_end:
                columns[col_idx] = ev.end
                col_assignment[id(ev)] = col_idx
                placed = True
                break
        if not placed:
            col_assignment[id(ev)] = len(columns)
            columns.append(ev.end)

    # Group transitively overlapping events
    # Two events overlap if one starts before the other ends
    groups: list[list[Event]] = []
    for ev in sorted_events:
        if not groups:
            groups.append([ev])
            continue
        last_group = groups[-1]
        group_end = max(e.end for e in last_group)
        if ev.start < group_end:
            last_group.append(ev)
        else:
            groups.append([ev])

    # Build result: all events in a group share the same total_cols
    result: dict[int, tuple[int, int]] = {}
    for group in groups:
        total_cols = max(col_assignment[id(e)] for e in group) + 1
        for e in group:
            result[id(e)] = (col_assignment[id(e)], total_cols)

    return result


def _sanitize(text: str) -> str:
    """Replace characters that Helvetica cannot render with safe alternatives."""
    import unicodedata

    out: list[str] = []
    for ch in text:
        try:
            ch.encode("latin-1")
            out.append(ch)
        except UnicodeEncodeError:
            # Try a sensible replacement
            cat = unicodedata.category(ch)
            if cat.startswith("P") or cat.startswith("S"):
                out.append(" ")  # punctuation/symbol → space
            elif cat.startswith("Z"):
                out.append(" ")  # whitespace variants
            else:
                # Try NFKD decomposition (e.g. ligatures → ascii)
                decomposed = unicodedata.normalize("NFKD", ch)
                safe = decomposed.encode("latin-1", "ignore").decode("latin-1")
                out.append(safe if safe else "")
    return "".join(out)


def _truncate(c: Canvas, text: str, max_w: float, font: str, size: float) -> str:
    """Truncate text to fit max_w, adding ellipsis if needed."""
    if c.stringWidth(text, font, size) <= max_w:
        return text
    for i in range(len(text) - 1, 0, -1):
        t = text[:i] + "..."
        if c.stringWidth(t, font, size) <= max_w:
            return t
    return "..."


def _get_day_events(events: list[Event], d: date) -> list[Event]:
    """Get events for a specific day."""
    result = []
    for ev in events:
        ev_date = ev.start.date() if isinstance(ev.start, datetime) else ev.start
        if ev_date == d:
            result.append(ev)
    return result


def _draw_day_nav(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    d: date,
    y: float,
    font: str,
    font_bold: str,
) -> None:
    """Draw month and week navigation links."""
    from rmcal.i18n.translations import month_name_short

    lang = config.language

    # Back to month
    month_bm = nav.bm_month(d.year, d.month)
    if nav.get_page(month_bm) is not None:
        month_label = month_name_short(lang, d.month)
        c.setFont(font, BODY_SIZE)
        c.setFillColorRGB(*GRAY)
        x = layout.content_right - c.stringWidth(month_label, font, BODY_SIZE)
        c.drawString(x, y, month_label)
        tw = c.stringWidth(month_label, font, BODY_SIZE)
        c.linkAbsolute(month_label, month_bm, (x - 1, y - 1, x + tw + 1, y + BODY_SIZE + 1))

    # Back to week
    iso = d.isocalendar()
    week_bm = nav.bm_week(iso[0], iso[1])
    if nav.get_page(week_bm) is not None:
        week_label = f"W{iso[1]}"
        c.setFont(font, BODY_SIZE)
        c.setFillColorRGB(*GRAY)
        x = layout.content_right - c.stringWidth(week_label, font, BODY_SIZE) - 25 * mm
        c.drawString(x, y, week_label)
        tw = c.stringWidth(week_label, font, BODY_SIZE)
        c.linkAbsolute(week_label, week_bm, (x - 1, y - 1, x + tw + 1, y + BODY_SIZE + 1))


def _draw_day_arrows(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    d: date,
    y: float,
    font_bold: str,
) -> None:
    """Draw prev/next day arrows."""
    prev_d = d - timedelta(days=1)
    prev_bm = nav.bm_day(prev_d)
    if nav.get_page(prev_bm) is not None:
        c.setFont(font_bold, HEADER_SIZE)
        c.setFillColorRGB(*GRAY)
        x = layout.content_right - 55 * mm
        c.drawString(x, y, "<")
        tw = c.stringWidth("<", font_bold, HEADER_SIZE)
        c.linkAbsolute("prev", prev_bm, (x - 1, y - 1, x + tw + 1, y + HEADER_SIZE + 1))

    next_d = d + timedelta(days=1)
    next_bm = nav.bm_day(next_d)
    if nav.get_page(next_bm) is not None:
        c.setFont(font_bold, HEADER_SIZE)
        c.setFillColorRGB(*GRAY)
        x = layout.content_right - 45 * mm
        c.drawString(x, y, ">")
        tw = c.stringWidth(">", font_bold, HEADER_SIZE)
        c.linkAbsolute("next", next_bm, (x - 1, y - 1, x + tw + 1, y + HEADER_SIZE + 1))


def _format_time(dt: datetime, fmt: str) -> str:
    """Format a datetime as a time string."""
    if fmt == "12h":
        hour = dt.hour
        minute = dt.minute
        ampm = "AM" if hour < 12 else "PM"
        if hour == 0:
            hour = 12
        elif hour > 12:
            hour -= 12
        if minute:
            return f"{hour}:{minute:02d} {ampm}"
        return f"{hour} {ampm}"
    # 24h fallback also uses 12-hour for Helvetica compatibility
    hour = dt.hour
    minute = dt.minute
    ampm = "AM" if hour < 12 else "PM"
    if hour == 0:
        hour = 12
    elif hour > 12:
        hour -= 12
    return f"{hour}:{minute:02d} {ampm}"


def _format_hour_12(hour: int) -> str:
    """Format an hour in 12-hour format."""
    if hour == 0:
        return "12 AM"
    if hour < 12:
        return f"{hour} AM"
    if hour == 12:
        return "12 PM"
    return f"{hour - 12} PM"
