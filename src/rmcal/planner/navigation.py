"""Cross-page link registry for PDF navigation."""

from __future__ import annotations

from datetime import date


class NavigationRegistry:
    """Tracks page numbers for bookmark-based navigation between planner views."""

    def __init__(self) -> None:
        self._page_index: dict[str, int] = {}

    def register(self, bookmark: str, page_number: int) -> None:
        """Register a page with a bookmark name."""
        self._page_index[bookmark] = page_number

    def get_page(self, bookmark: str) -> int | None:
        """Get the page number for a bookmark."""
        return self._page_index.get(bookmark)

    @property
    def total_pages(self) -> int:
        if not self._page_index:
            return 0
        return max(self._page_index.values()) + 1

    @property
    def page_manifest(self) -> dict[str, int]:
        """Return a copy of the bookmark→page_index mapping."""
        return dict(self._page_index)

    # Bookmark name generators — deterministic naming scheme

    @staticmethod
    def bm_year(year: int) -> str:
        return f"year-{year}"

    @staticmethod
    def bm_month(year: int, month: int) -> str:
        return f"month-{year}-{month:02d}"

    @staticmethod
    def bm_week(year: int, week: int) -> str:
        return f"week-{year}-W{week:02d}"

    @staticmethod
    def bm_day(d: date) -> str:
        return f"day-{d.isoformat()}"

    @staticmethod
    def bm_meeting_note(d: date, event_index: int) -> str:
        return f"meeting-{d.isoformat()}-{event_index}"
