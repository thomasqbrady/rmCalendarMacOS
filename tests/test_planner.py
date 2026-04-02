"""Tests for PDF planner generation."""

from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from rmcal.models import (
    DateRange,
    Event,
    PlannerConfig,
    WeekStart,
)
from rmcal.planner.generator import count_pages, generate_planner
from rmcal.planner.navigation import NavigationRegistry
from rmcal.planner.layouts.week import (
    _compute_tile_columns as week_tile_columns,
)
from rmcal.planner.layouts.day import (
    _compute_tile_columns as day_tile_columns,
)
from rmcal.planner.styles import get_calendar_fill, get_calendar_stripe, CALENDAR_COLORS


def test_page_count_one_month():
    """April 2026 (30 days) should produce exactly 1 year + 1 month + 5 weeks + 30 days."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30)),
    )
    total = count_pages(config)
    # 1 year + 1 month + 5 weeks (Mar 30 – May 3 covers 5 ISO weeks) + 30 days = 37
    assert total == 37


def test_page_count_full_year():
    """Full year 2026 should produce 1 year + 12 months + 53 weeks + 365 days."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31)),
    )
    total = count_pages(config)
    assert total == 1 + 12 + 53 + 365


def test_page_count_with_meeting_notes():
    """Meeting notes pages add one page per non-all-day meeting event."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 7)),
    )
    events = [
        Event(
            summary="Meeting A",
            start=datetime(2026, 4, 2, 10, 0, tzinfo=timezone.utc),
            end=datetime(2026, 4, 2, 11, 0, tzinfo=timezone.utc),
            all_day=False,
            calendar_name="Work",
            calendar_id="cal-1",
        ),
        Event(
            summary="Meeting B",
            start=datetime(2026, 4, 3, 14, 0, tzinfo=timezone.utc),
            end=datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc),
            all_day=False,
            calendar_name="Work",
            calendar_id="cal-1",
        ),
        Event(
            summary="Holiday",
            start=datetime(2026, 4, 5, 0, 0, tzinfo=timezone.utc),
            end=datetime(2026, 4, 6, 0, 0, tzinfo=timezone.utc),
            all_day=True,
            calendar_name="Work",
            calendar_id="cal-1",
        ),
    ]
    base = count_pages(config)
    with_meetings = count_pages(config, events, meeting_notes_calendar_ids={"cal-1"})
    # Two non-all-day meetings = 2 extra pages (all-day event excluded)
    assert with_meetings == base + 2


def test_week_start_produces_same_component_counts():
    """Monday and Sunday week starts should only differ in week count by at most 1."""
    dr = DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31))
    config_mon = PlannerConfig(date_range=dr, week_start=WeekStart.MONDAY)
    config_sun = PlannerConfig(date_range=dr, week_start=WeekStart.SUNDAY)
    # Both have the same year/month/day pages; only weeks can differ
    diff = abs(count_pages(config_mon) - count_pages(config_sun))
    assert diff <= 1


def test_navigation_registry_stores_and_retrieves():
    nav = NavigationRegistry()
    nav.register(nav.bm_year(2026), 0)
    nav.register(nav.bm_month(2026, 1), 1)
    nav.register(nav.bm_day(date(2026, 1, 15)), 50)

    assert nav.get_page(nav.bm_year(2026)) == 0
    assert nav.get_page(nav.bm_month(2026, 1)) == 1
    assert nav.get_page(nav.bm_day(date(2026, 1, 15))) == 50


def test_navigation_registry_returns_none_for_unknown():
    nav = NavigationRegistry()
    assert nav.get_page("nonexistent") is None


def test_generate_pdf_produces_correct_page_count(tmp_path: Path):
    """Generated PDF must have exactly as many pages as count_pages predicts."""
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 30)),
    )
    events = [
        Event(
            summary="Test Event",
            start=datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc),
            end=datetime(2026, 4, 15, 11, 0, tzinfo=timezone.utc),
            all_day=False,
            calendar_name="Test",
        ),
    ]

    output = tmp_path / "test_planner.pdf"
    result, manifest = generate_planner(config, events, output_path=output)

    assert result.exists()
    assert result.stat().st_size > 0
    assert isinstance(manifest, dict)
    assert len(manifest) > 0

    from pypdf import PdfReader
    reader = PdfReader(str(result))
    assert len(reader.pages) == count_pages(config)


def test_generate_pdf_with_no_events(tmp_path: Path):
    config = PlannerConfig(
        date_range=DateRange(start=date(2026, 4, 1), end=date(2026, 4, 7)),
    )
    output = tmp_path / "empty_planner.pdf"
    result, manifest = generate_planner(config, [], output_path=output)

    assert result.exists()
    assert result.stat().st_size > 0
    assert isinstance(manifest, dict)

    from pypdf import PdfReader
    reader = PdfReader(str(result))
    assert len(reader.pages) == count_pages(config)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ev(hour_start: int, hour_end: int, summary: str = "E", cal: str = "Work") -> Event:
    """Create a timed event on a fixed day with the given hour range."""
    return Event(
        summary=summary,
        start=datetime(2026, 4, 15, hour_start, 0, tzinfo=timezone.utc),
        end=datetime(2026, 4, 15, hour_end, 0, tzinfo=timezone.utc),
        all_day=False,
        calendar_name=cal,
    )


# ---------------------------------------------------------------------------
# Tile-column tests (both week.py and day.py implementations)
# ---------------------------------------------------------------------------

class TestTileColumns:
    """Tests for the _compute_tile_columns algorithm in week and day layouts."""

    def _run_both(self, events):
        """Run both implementations and assert they agree."""
        w = week_tile_columns(events)
        d = day_tile_columns(events)
        # Both should assign the same (col, total) per event
        for ev in events:
            assert w[id(ev)] == d[id(ev)], (
                f"Mismatch for {ev.summary}: week={w[id(ev)]}, day={d[id(ev)]}"
            )
        return w

    def test_empty_input(self):
        assert week_tile_columns([]) == {}
        assert day_tile_columns([]) == {}

    def test_single_event_gets_one_column(self):
        ev = _ev(9, 10)
        result = self._run_both([ev])
        assert result[id(ev)] == (0, 1)

    def test_non_overlapping_events_get_one_column_each(self):
        a = _ev(9, 10, "A")
        b = _ev(11, 12, "B")
        result = self._run_both([a, b])
        assert result[id(a)] == (0, 1)
        assert result[id(b)] == (0, 1)

    def test_two_concurrent_events_tile_into_two_columns(self):
        a = _ev(9, 11, "A")
        b = _ev(10, 12, "B")
        result = self._run_both([a, b])
        assert result[id(a)][1] == 2  # total_cols = 2
        assert result[id(b)][1] == 2
        # They must be in different columns
        assert result[id(a)][0] != result[id(b)][0]

    def test_three_way_overlap(self):
        a = _ev(9, 12, "A")
        b = _ev(10, 13, "B")
        c = _ev(11, 14, "C")
        result = self._run_both([a, b, c])
        cols = {result[id(a)][0], result[id(b)][0], result[id(c)][0]}
        assert len(cols) == 3  # each in a unique column
        assert result[id(a)][1] == 3
        assert result[id(b)][1] == 3
        assert result[id(c)][1] == 3

    def test_partial_chain_overlap(self):
        """A overlaps B, B overlaps C, but A does NOT overlap C.

        They form one transitive group so all share the same total_cols.
        Only 2 columns are needed (A and C can share a column).
        """
        a = _ev(9, 11, "A")
        b = _ev(10, 13, "B")
        c = _ev(12, 14, "C")
        result = self._run_both([a, b, c])
        # All in the same group
        assert result[id(a)][1] == result[id(b)][1] == result[id(c)][1]
        # A ends before C starts → they can reuse the same column
        assert result[id(a)][1] == 2
        assert result[id(a)][0] == result[id(c)][0]  # A and C share column 0

    def test_mixed_overlapping_and_solo(self):
        """Two overlapping events + one solo later = two separate groups."""
        a = _ev(9, 11, "A")
        b = _ev(10, 12, "B")
        solo = _ev(14, 15, "Solo")
        result = self._run_both([a, b, solo])
        assert result[id(a)][1] == 2
        assert result[id(b)][1] == 2
        assert result[id(solo)] == (0, 1)  # independent group

    def test_back_to_back_events_do_not_overlap(self):
        """Events where one ends exactly when the next starts are NOT concurrent."""
        a = _ev(9, 10, "A")
        b = _ev(10, 11, "B")
        result = self._run_both([a, b])
        # Both should be in column 0 with total 1 (separate groups)
        assert result[id(a)] == (0, 1)
        assert result[id(b)] == (0, 1)


# ---------------------------------------------------------------------------
# Calendar fill tests
# ---------------------------------------------------------------------------

class TestCalendarColors:
    def test_fill_same_name_returns_same_color(self):
        assert get_calendar_fill("Work") == get_calendar_fill("Work")

    def test_stripe_same_name_returns_same_color(self):
        assert get_calendar_stripe("Work") == get_calendar_stripe("Work")

    def test_different_names_may_differ(self):
        """At least two of three distinct names should produce different fills."""
        fills = {get_calendar_fill(n) for n in ["Work", "Personal", "Holidays"]}
        assert len(fills) >= 2

    def test_fill_and_stripe_are_different(self):
        """Fill (pastel) should differ from stripe (saturated) for same calendar."""
        assert get_calendar_fill("Work") != get_calendar_stripe("Work")

    def test_returned_values_within_0_1_range(self):
        for name in ["A", "B", "Calendar", "日本語"]:
            r, g, b = get_calendar_fill(name)
            assert 0.0 <= r <= 1.0
            assert 0.0 <= g <= 1.0
            assert 0.0 <= b <= 1.0
            r, g, b = get_calendar_stripe(name)
            assert 0.0 <= r <= 1.0
            assert 0.0 <= g <= 1.0
            assert 0.0 <= b <= 1.0


# ---------------------------------------------------------------------------
# Annotation preservation tests
# ---------------------------------------------------------------------------

from rmcal.remarkable.annotations import (
    compute_page_mapping,
    _find_insertion_point,
    build_content_json,
)


class TestAnnotationPreservation:
    """Tests for bookmark-based page UUID remapping."""

    def test_identical_manifests_reuse_all_uuids(self):
        """When nothing changes, all UUIDs are reused."""
        manifest = {"year-2026": 0, "month-2026-04": 1, "day-2026-04-01": 2}
        old_uuids = ["uuid-0", "uuid-1", "uuid-2"]
        final, blanks = compute_page_mapping(manifest, manifest, 3, old_uuids)
        assert final == old_uuids
        assert blanks == []

    def test_added_page_gets_new_uuid(self):
        """A new page in the new manifest gets a fresh UUID."""
        old = {"day-2026-04-01": 0, "day-2026-04-02": 1}
        new = {"day-2026-04-01": 0, "day-2026-04-02": 1, "day-2026-04-03": 2}
        old_uuids = ["uuid-0", "uuid-1"]
        final, blanks = compute_page_mapping(old, new, 3, old_uuids)
        assert final[0] == "uuid-0"
        assert final[1] == "uuid-1"
        assert final[2] != "uuid-0" and final[2] != "uuid-1"  # new UUID
        assert blanks == []

    def test_removed_meeting_creates_blank_after_day(self):
        """Deleting a meeting inserts a blank page after the day page."""
        old = {
            "day-2026-04-02": 0,
            "meeting-2026-04-02-0": 1,
            "day-2026-04-03": 2,
        }
        new = {
            "day-2026-04-02": 0,
            "day-2026-04-03": 1,
        }
        old_uuids = ["uuid-day2", "uuid-meeting", "uuid-day3"]
        final, blanks = compute_page_mapping(old, new, 2, old_uuids)
        # The orphaned meeting page should be inserted after day-2026-04-02
        assert blanks == [1]
        assert "uuid-meeting" in final
        # day-2026-04-02 keeps its UUID
        assert final[0] == "uuid-day2"
        # The meeting's blank carrier is at position 1
        assert final[1] == "uuid-meeting"
        # day-2026-04-03 keeps its UUID
        assert final[2] == "uuid-day3"

    def test_multiple_orphans_same_day(self):
        """Multiple meeting notes deleted from the same day."""
        old = {
            "day-2026-04-02": 0,
            "meeting-2026-04-02-0": 1,
            "meeting-2026-04-02-1": 2,
            "day-2026-04-03": 3,
        }
        new = {
            "day-2026-04-02": 0,
            "day-2026-04-03": 1,
        }
        old_uuids = ["uuid-day2", "uuid-m0", "uuid-m1", "uuid-day3"]
        final, blanks = compute_page_mapping(old, new, 2, old_uuids)
        assert len(blanks) == 2
        assert "uuid-m0" in final
        assert "uuid-m1" in final
        assert final[0] == "uuid-day2"
        # Both orphans inserted after day-2026-04-02, before day-2026-04-03
        assert final[-1] == "uuid-day3"

    def test_no_old_manifest_produces_all_new_uuids(self):
        """First sync — no old manifest means all fresh UUIDs."""
        new = {"day-2026-04-01": 0}
        final, blanks = compute_page_mapping({}, new, 1, [])
        assert len(final) == 1
        assert blanks == []


class TestFindInsertionPoint:
    """Tests for _find_insertion_point bookmark parsing."""

    def test_meeting_inserts_after_day(self):
        manifest = {"day-2026-04-02": 5, "day-2026-04-03": 6}
        assert _find_insertion_point("meeting-2026-04-02-0", manifest) == 5

    def test_meeting_inserts_after_last_existing_meeting(self):
        manifest = {
            "day-2026-04-02": 5,
            "meeting-2026-04-02-0": 6,
            "day-2026-04-03": 7,
        }
        # Should insert after the existing meeting-0, not after the day
        assert _find_insertion_point("meeting-2026-04-02-1", manifest) == 6

    def test_day_inserts_after_previous_day(self):
        manifest = {"day-2026-04-01": 3, "day-2026-04-03": 5}
        assert _find_insertion_point("day-2026-04-02", manifest) == 3

    def test_unknown_bookmark_inserts_at_end(self):
        manifest = {"day-2026-04-01": 0, "day-2026-04-02": 1}
        assert _find_insertion_point("unknown-bookmark", manifest) == 1


class TestBuildContentJson:
    def test_basic_structure(self):
        uuids = ["a", "b", "c"]
        content = build_content_json(uuids)
        assert content["pageCount"] == 3
        assert content["pages"] == ["a", "b", "c"]
        assert content["fileType"] == "pdf"

    def test_preserves_existing_fields(self):
        existing = {"lastOpenedPage": 5, "margins": 200}
        content = build_content_json(["a"], existing)
        assert content["lastOpenedPage"] == 5
        assert content["margins"] == 200
        assert content["pageCount"] == 1
