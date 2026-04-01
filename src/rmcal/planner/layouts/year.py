"""Year overview layout — 12 mini-calendar grids on one page."""

from __future__ import annotations

import calendar
from datetime import date

from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas

from rmcal.i18n.translations import month_name_short, weekday_letter
from rmcal.models import Event, PlannerConfig, Handedness
from rmcal.planner.navigation import NavigationRegistry
from rmcal.planner.styles import (
    BLACK,
    FONT_BOLD,
    FONT_REGULAR,
    GRAY,
    LIGHT_GRAY,
    BODY_SIZE,
    SMALL_SIZE,
    TINY_SIZE,
    TITLE_SIZE,
    THIN,
    HAIRLINE,
    PageLayout,
    get_font,
)


def assign_pages(
    nav: NavigationRegistry,
    start_page: int,
    config: PlannerConfig,
) -> int:
    """Assign page numbers for year overview pages. Returns next available page."""
    # One page per year that appears in the date range
    page = start_page
    for year in range(config.date_range.start.year, config.date_range.end.year + 1):
        nav.register(nav.bm_year(year), page)
        page += 1
    return page


def render(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    events: list[Event],
    layout: PageLayout,
) -> None:
    """Render year overview pages."""
    for year in range(config.date_range.start.year, config.date_range.end.year + 1):
        _render_year_page(c, nav, config, layout, year)
        c.showPage()


def _render_year_page(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    year: int,
) -> None:
    """Render a single year overview page."""
    lang = config.language
    font = get_font(lang)
    font_bold = get_font(lang, bold=True)

    # Bookmark for navigation
    bm = nav.bm_year(year)
    c.bookmarkPage(bm)

    # Title
    c.setFont(font_bold, TITLE_SIZE)
    c.setFillColorRGB(*BLACK)
    title_y = layout.content_top - TITLE_SIZE
    c.drawString(layout.content_x, title_y, str(year))

    # Grid: 3 columns x 4 rows of mini-calendars
    cols = 3
    rows = 4
    grid_top = title_y - 12 * mm
    grid_left = layout.content_x
    cell_w = layout.content_width / cols
    cell_h = (grid_top - layout.content_bottom) / rows

    week_start_offset = 0 if config.week_start.value == "monday" else 6

    for month_idx in range(12):
        col = month_idx % cols
        row = month_idx // cols
        x = grid_left + col * cell_w
        y = grid_top - row * cell_h

        month_num = month_idx + 1
        _render_mini_month(
            c, nav, config, layout, x, y, cell_w, cell_h,
            year, month_num, week_start_offset, lang, font, font_bold,
        )


def _render_mini_month(
    c: Canvas,
    nav: NavigationRegistry,
    config: PlannerConfig,
    layout: PageLayout,
    x: float,
    y: float,
    w: float,
    h: float,
    year: int,
    month: int,
    week_start_offset: int,
    lang,
    font: str,
    font_bold: str,
) -> None:
    """Render a single mini-month calendar within the year grid."""
    padding = 3 * mm
    inner_x = x + padding
    inner_w = w - 2 * padding
    col_w = inner_w / 7

    # Month name (clickable link to month view)
    month_label = month_name_short(lang, month)
    name_y = y - 4 * mm
    c.setFont(font_bold, BODY_SIZE)
    c.setFillColorRGB(*BLACK)
    c.drawString(inner_x, name_y, month_label)

    # Create clickable link to month page
    month_bm = nav.bm_month(year, month)
    month_page = nav.get_page(month_bm)
    if month_page is not None:
        c.linkAbsolute(
            month_label,
            month_bm,
            (inner_x, name_y - 2, inner_x + c.stringWidth(month_label, font_bold, BODY_SIZE), name_y + BODY_SIZE),
        )

    # Weekday headers
    header_y = name_y - 5 * mm
    c.setFont(font, TINY_SIZE)
    c.setFillColorRGB(*GRAY)
    for i in range(7):
        day_idx = (i + week_start_offset) % 7
        letter = weekday_letter(lang, day_idx)
        cx = inner_x + i * col_w + col_w / 2
        c.drawCentredString(cx, header_y, letter)

    # Day numbers
    c.setFont(font, TINY_SIZE)
    cal = calendar.Calendar(firstweekday=(0 if week_start_offset == 0 else 6))
    row_y = header_y - 4 * mm

    for week in cal.monthdayscalendar(year, month):
        for i, day in enumerate(week):
            if day == 0:
                continue
            cx = inner_x + i * col_w + col_w / 2
            c.setFillColorRGB(*BLACK)
            c.drawCentredString(cx, row_y, str(day))

            # Clickable link to day view
            day_date = date(year, month, day)
            day_bm = nav.bm_day(day_date)
            day_page = nav.get_page(day_bm)
            if day_page is not None:
                tw = c.stringWidth(str(day), font, TINY_SIZE)
                c.linkAbsolute(
                    str(day),
                    day_bm,
                    (cx - tw / 2 - 1, row_y - 1, cx + tw / 2 + 1, row_y + TINY_SIZE + 1),
                )

        row_y -= 3.5 * mm
