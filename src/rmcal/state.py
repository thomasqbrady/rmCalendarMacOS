"""Persistent state: saved calendar selection, date range hash, etc."""

from __future__ import annotations

import json
from pathlib import Path

STATE_DIR = Path("~/.config/rmcal").expanduser()
STATE_FILE = STATE_DIR / "state.json"


def load_state() -> dict:
    """Load the saved state."""
    if not STATE_FILE.exists():
        return {}
    try:
        return json.loads(STATE_FILE.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state: dict) -> None:
    """Save state to disk."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2))


def get_selected_calendar_ids() -> set[str] | None:
    """Get the saved calendar selection. Returns None if never configured."""
    state = load_state()
    ids = state.get("selected_calendar_ids")
    if ids is None:
        return None
    return set(ids)


def save_selected_calendar_ids(ids: set[str]) -> None:
    """Save the calendar selection."""
    state = load_state()
    state["selected_calendar_ids"] = sorted(ids)
    save_state(state)


def get_date_range_hash() -> str | None:
    """Get the saved date range hash."""
    return load_state().get("date_range_hash")


def save_date_range_hash(hash_key: str) -> None:
    """Save the date range hash."""
    state = load_state()
    state["date_range_hash"] = hash_key
    save_state(state)


def get_cloud_doc_id() -> str | None:
    """Get the saved reMarkable Cloud document ID."""
    return load_state().get("cloud_doc_id")


def save_cloud_doc_id(doc_id: str) -> None:
    """Save the reMarkable Cloud document ID."""
    state = load_state()
    state["cloud_doc_id"] = doc_id
    save_state(state)


def clear_cloud_doc_id() -> None:
    """Clear the saved reMarkable Cloud document ID."""
    state = load_state()
    state.pop("cloud_doc_id", None)
    save_state(state)


def get_meeting_notes_calendar_ids() -> set[str] | None:
    """Get the saved meeting notes calendar selection. Returns None if never configured."""
    state = load_state()
    ids = state.get("meeting_notes_calendar_ids")
    if ids is None:
        return None
    return set(ids)


def save_meeting_notes_calendar_ids(ids: set[str]) -> None:
    """Save the meeting notes calendar selection."""
    state = load_state()
    state["meeting_notes_calendar_ids"] = sorted(ids)
    save_state(state)


def get_page_manifest() -> dict[str, int] | None:
    """Get the saved page manifest (bookmark→page_index mapping)."""
    return load_state().get("page_manifest")


def save_page_manifest(manifest: dict[str, int]) -> None:
    """Save the page manifest for annotation preservation across syncs."""
    state = load_state()
    state["page_manifest"] = manifest
    save_state(state)
