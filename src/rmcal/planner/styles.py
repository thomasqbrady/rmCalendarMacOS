"""E-ink optimized styles, fonts, and dimension constants."""

from __future__ import annotations

from reportlab.lib.pagesizes import A4, letter
from reportlab.lib.units import mm

from rmcal.models import Device, Language, PageSize

# Colors — e-ink optimized (no color, high contrast for gray-scale displays)
BLACK = (0, 0, 0)
WHITE = (1, 1, 1)
GRAY = (0.35, 0.35, 0.35)            # Secondary text — readable on e-ink
LIGHT_GRAY = (0.65, 0.65, 0.65)      # Grid lines — visible but not dominant
VERY_LIGHT_GRAY = (0.85, 0.85, 0.85) # Event backgrounds, subtle fills

# Calendar-specific background fills — well-separated gray levels for e-ink
CALENDAR_FILLS = [
    (0.88, 0.88, 0.88),
    (0.76, 0.76, 0.76),
    (0.82, 0.82, 0.82),
    (0.70, 0.70, 0.70),
    (0.92, 0.92, 0.92),
    (0.64, 0.64, 0.64),
    (0.86, 0.86, 0.86),
    (0.74, 0.74, 0.74),
]


def get_calendar_fill(calendar_name: str) -> tuple[float, float, float]:
    """Return a consistent gray fill for a given calendar name."""
    idx = hash(calendar_name) % len(CALENDAR_FILLS)
    return CALENDAR_FILLS[idx]


# Line weights
HAIRLINE = 0.25
THIN = 0.5
MEDIUM = 1.0
THICK = 1.5

# Font names
FONT_REGULAR = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_LIGHT = "Helvetica"  # ReportLab doesn't ship Helvetica-Light

# CJK font for Japanese
FONT_CJK = "HeiseiKakuGo-W5"

# Font sizes
TITLE_SIZE = 18
SUBTITLE_SIZE = 14
HEADER_SIZE = 11
BODY_SIZE = 9
SMALL_SIZE = 7
TINY_SIZE = 6

# Margins
MARGIN_TOP = 15 * mm
MARGIN_BOTTOM = 10 * mm
MARGIN_OUTER = 12 * mm
MARGIN_INNER = 8 * mm

# Navigation sidebar width
NAV_WIDTH = 18 * mm


def get_page_size(page_size: PageSize) -> tuple[float, float]:
    """Get the page dimensions for the configured page size."""
    if page_size == PageSize.LETTER:
        return letter
    return A4


def get_font(language: Language, bold: bool = False) -> str:
    """Get the appropriate font name for the language."""
    if language == Language.JA:
        return FONT_CJK
    return FONT_BOLD if bold else FONT_REGULAR


def register_cjk_fonts() -> None:
    """Register CJK fonts for Japanese support."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    try:
        pdfmetrics.registerFont(UnicodeCIDFont(FONT_CJK))
    except Exception:
        # CJK fonts may not be available in all environments
        pass


class PageLayout:
    """Computed layout dimensions for a page."""

    def __init__(
        self,
        page_size: PageSize,
        handedness_right: bool = True,
        has_nav: bool = True,
    ):
        w, h = get_page_size(page_size)
        self.page_width = w
        self.page_height = h

        # For right-handed users: nav on left, content on right
        # For left-handed users: nav on right, content on left
        nav_w = NAV_WIDTH if has_nav else 0

        if handedness_right:
            self.nav_x = 0
            self.content_x = nav_w + MARGIN_INNER
            self.content_right = w - MARGIN_OUTER
        else:
            self.nav_x = w - nav_w
            self.content_x = MARGIN_OUTER
            self.content_right = w - nav_w - MARGIN_INNER

        self.nav_width = nav_w
        self.content_width = self.content_right - self.content_x
        self.content_top = h - MARGIN_TOP
        self.content_bottom = MARGIN_BOTTOM
        self.content_height = self.content_top - self.content_bottom
