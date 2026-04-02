"""Meeting notes page layout — dedicated page per meeting with header and lined notes area."""

from __future__ import annotations

from datetime import date, datetime

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

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
    TINY_SIZE,
    THIN,
    HAIRLINE,
    PageLayout,
    get_font,
)


def render_meeting_notes_page(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    d: date,
    event: Event,
    event_index: int,
) -> None:
    """Render a single meeting notes page."""
    lang = config.language
    font = get_font(lang)
    font_bold = get_font(lang, bold=True)

    # Bookmark
    c.bookmarkPage(nav.bm_meeting_note(d, event_index))

    y = layout.content_top

    # --- Time, date, duration (small gray) ---
    time_str = _format_time_range(event)
    date_str = _format_date(d)
    duration_str = _format_duration(event)
    meta_line = f"{time_str}  ·  {date_str}  ·  {duration_str}"

    c.setFont(font, SMALL_SIZE)
    c.setFillColorRGB(*GRAY)
    y -= SMALL_SIZE
    c.drawString(layout.content_x, y, meta_line)

    # --- Meeting name (large bold) ---
    y -= HEADER_SIZE + 4 * mm
    c.setFont(font_bold, HEADER_SIZE)
    c.setFillColorRGB(*BLACK)
    # Truncate if too long for page width
    name = _sanitize(event.display_name)
    max_width = layout.content_right - layout.content_x
    while c.stringWidth(name, font_bold, HEADER_SIZE) > max_width and len(name) > 10:
        name = name[:-4] + "..."
    c.drawString(layout.content_x, y, name)

    # --- Attendees (small gray) ---
    if event.attendees:
        y -= SMALL_SIZE + 3 * mm
        c.setFont(font, SMALL_SIZE)
        c.setFillColorRGB(*GRAY)
        attendee_str = _format_attendees(event.attendees, c, font, SMALL_SIZE, max_width)
        c.drawString(layout.content_x, y, _sanitize(attendee_str))

    # --- Location (tiny gray, if present) ---
    if event.location:
        y -= TINY_SIZE + 2 * mm
        c.setFont(font, TINY_SIZE)
        c.setFillColorRGB(*GRAY)
        loc = _sanitize(event.location)
        while c.stringWidth(loc, font, TINY_SIZE) > max_width and len(loc) > 10:
            loc = loc[:-4] + "..."
        c.drawString(layout.content_x, y, loc)

    # --- Horizontal rule ---
    y -= 4 * mm
    c.setStrokeColorRGB(*LIGHT_GRAY)
    c.setLineWidth(THIN)
    c.line(layout.content_x, y, layout.content_right, y)

    # --- Back to day link ---
    y -= TINY_SIZE + 2 * mm
    c.setFont(font, TINY_SIZE)
    c.setFillColorRGB(*GRAY)
    day_bm = nav.bm_day(d)
    day_page = nav.get_page(day_bm)
    if day_page is not None:
        link_text = f"< Back to {d.strftime('%b %d')}"
        c.drawString(layout.content_x, y, link_text)
        tw = c.stringWidth(link_text, font, TINY_SIZE)
        c.linkAbsolute(
            link_text, day_bm,
            (layout.content_x, y - 1 * mm, layout.content_x + tw, y + TINY_SIZE),
        )

    # --- Lined notes area ---
    notes_top = y - 4 * mm
    line_spacing = 7 * mm
    c.setStrokeColorRGB(*VERY_LIGHT_GRAY)
    c.setLineWidth(HAIRLINE)
    line_y = notes_top
    while line_y > layout.content_bottom:
        c.line(layout.content_x, line_y, layout.content_right, line_y)
        line_y -= line_spacing


def get_day_meetings(events: list[Event], d: date) -> list[Event]:
    """Get non-all-day meetings for a specific day, sorted by start time."""
    result = []
    for ev in events:
        if ev.all_day:
            continue
        ev_date = ev.start.date() if isinstance(ev.start, datetime) else ev.start
        if ev_date == d:
            result.append(ev)
    result.sort(key=lambda e: (e.start, e.end, e.summary))
    return result


def _format_time_range(event: Event) -> str:
    """Format event time range in 12-hour format."""
    start = event.start
    end = event.end
    s = start.strftime("%-I:%M %p")
    e = end.strftime("%-I:%M %p")
    return f"{s} – {e}"


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


def _format_date(d: date) -> str:
    """Format date as 'April 2, 2026'."""
    return d.strftime("%B %-d, %Y")


def _format_duration(event: Event) -> str:
    """Format event duration humanely."""
    delta = event.end - event.start
    total_minutes = int(delta.total_seconds() / 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60

    if hours == 0:
        return f"{minutes} min"
    elif minutes == 0:
        return f"{hours} hr" if hours == 1 else f"{hours} hrs"
    else:
        h = f"{hours} hr" if hours == 1 else f"{hours} hrs"
        return f"{h} {minutes} min"


def _format_attendees(
    attendees: tuple[str, ...],
    c: Canvas,
    font: str,
    size: float,
    max_width: float,
) -> str:
    """Format attendee list, truncating if too long."""
    max_show = 8
    if len(attendees) <= max_show:
        text = ", ".join(attendees)
    else:
        text = ", ".join(attendees[:max_show]) + f" + {len(attendees) - max_show} more"

    # Truncate if still too wide
    while c.stringWidth(text, font, size) > max_width and len(text) > 20:
        text = text[:-4] + "..."
    return text
