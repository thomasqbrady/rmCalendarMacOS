"""Tests for persistent state management."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from rmcal.state import (
    clear_cloud_doc_id,
    get_cloud_doc_id,
    get_meeting_notes_calendar_ids,
    get_selected_calendar_ids,
    load_state,
    save_cloud_doc_id,
    save_meeting_notes_calendar_ids,
    save_selected_calendar_ids,
    save_state,
)


class TestState:
    """All state tests use a temporary directory to avoid touching real config."""

    def _patch_state_file(self, tmp_path: Path):
        state_file = tmp_path / "state.json"
        return (
            patch("rmcal.state.STATE_FILE", state_file),
            patch("rmcal.state.STATE_DIR", tmp_path),
        )

    def test_load_empty_state(self, tmp_path: Path):
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            assert load_state() == {}

    def test_save_and_load_roundtrip(self, tmp_path: Path):
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            save_state({"key": "value"})
            assert load_state() == {"key": "value"}

    def test_calendar_ids_none_when_never_set(self, tmp_path: Path):
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            assert get_selected_calendar_ids() is None

    def test_save_and_get_calendar_ids(self, tmp_path: Path):
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            save_selected_calendar_ids({"cal-a", "cal-b"})
            result = get_selected_calendar_ids()
            assert result == {"cal-a", "cal-b"}

    def test_cloud_doc_id_lifecycle(self, tmp_path: Path):
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            assert get_cloud_doc_id() is None

            save_cloud_doc_id("doc-123")
            assert get_cloud_doc_id() == "doc-123"

            clear_cloud_doc_id()
            assert get_cloud_doc_id() is None

    def test_clear_cloud_doc_id_when_not_set(self, tmp_path: Path):
        """Clearing a non-existent key should not raise."""
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            clear_cloud_doc_id()  # Should not raise
            assert get_cloud_doc_id() is None

    def test_meeting_notes_ids_none_when_never_set(self, tmp_path: Path):
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            assert get_meeting_notes_calendar_ids() is None

    def test_save_and_get_meeting_notes_ids(self, tmp_path: Path):
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            save_meeting_notes_calendar_ids({"cal-x"})
            assert get_meeting_notes_calendar_ids() == {"cal-x"}

    def test_multiple_keys_coexist(self, tmp_path: Path):
        """Setting one key should not clobber another."""
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            save_selected_calendar_ids({"cal-a"})
            save_cloud_doc_id("doc-1")
            save_meeting_notes_calendar_ids({"cal-b"})

            assert get_selected_calendar_ids() == {"cal-a"}
            assert get_cloud_doc_id() == "doc-1"
            assert get_meeting_notes_calendar_ids() == {"cal-b"}

    def test_handles_corrupted_state_file(self, tmp_path: Path):
        p1, p2 = self._patch_state_file(tmp_path)
        with p1, p2:
            (tmp_path / "state.json").write_text("not valid json{{{")
            assert load_state() == {}
