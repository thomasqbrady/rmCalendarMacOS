"""Tests for reMarkable upload logic (mocked SSH)."""

import json
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

try:
    from rmcal.remarkable.upload import _check_date_range, _find_existing_document
    from rmcal.models import DateRange, RemarkableConfig
except ImportError:
    pytest.skip("paramiko not installed (SSH upload tests)", allow_module_level=True)



def test_check_date_range_no_state():
    """No saved state should not raise."""
    with patch("rmcal.remarkable.upload._load_state", return_value=None):
        _check_date_range(DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31)), force=False)


def test_check_date_range_same():
    """Same date range should not raise."""
    dr = DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31))
    state = {"date_range_hash": dr.hash_key}
    with patch("rmcal.remarkable.upload._load_state", return_value=state):
        _check_date_range(dr, force=False)


def test_check_date_range_changed():
    """Changed date range should raise without force."""
    old = DateRange(start=date(2026, 1, 1), end=date(2026, 6, 30))
    new = DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31))
    state = {"date_range_hash": old.hash_key}
    with patch("rmcal.remarkable.upload._load_state", return_value=state):
        with pytest.raises(RuntimeError, match="Date range has changed"):
            _check_date_range(new, force=False)


def test_check_date_range_force():
    """Changed date range should not raise with force."""
    old = DateRange(start=date(2026, 1, 1), end=date(2026, 6, 30))
    new = DateRange(start=date(2026, 1, 1), end=date(2026, 12, 31))
    state = {"date_range_hash": old.hash_key}
    with patch("rmcal.remarkable.upload._load_state", return_value=state):
        _check_date_range(new, force=True)  # Should not raise


def test_find_existing_document():
    """Test finding a document by name in mocked SSH."""
    mock_ssh = MagicMock()
    mock_ssh.listdir.return_value = [
        "abc-123.metadata",
        "abc-123.content",
        "def-456.metadata",
    ]

    def read_file(path):
        if "abc-123.metadata" in path:
            return json.dumps({
                "visibleName": "rmCalendar",
                "type": "DocumentType",
                "deleted": False,
            })
        if "def-456.metadata" in path:
            return json.dumps({
                "visibleName": "Other Doc",
                "type": "DocumentType",
                "deleted": False,
            })
        raise FileNotFoundError(path)

    mock_ssh.read_file.side_effect = read_file

    result = _find_existing_document(mock_ssh, "rmCalendar")
    assert result == "abc-123"


def test_find_nonexistent_document():
    """Test that searching for a missing document returns None."""
    mock_ssh = MagicMock()
    mock_ssh.listdir.return_value = ["abc-123.metadata"]
    mock_ssh.read_file.return_value = json.dumps({
        "visibleName": "Other Doc",
        "type": "DocumentType",
        "deleted": False,
    })

    result = _find_existing_document(mock_ssh, "rmCalendar")
    assert result is None
