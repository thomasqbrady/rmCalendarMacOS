"""Tests for the reMarkable Cloud API client (v3/v4 schema support)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from rmcal.remarkable.cloud import (
    CloudDocument,
    DOC_TYPE,
    FILE_TYPE,
    GenerationConflict,
    RawEntry,
    RemarkableCloud,
    _build_entries_blob,
    _hash_blob_v4,
    _hash_entries_v3,
    _is_doc_entry,
    _root_entry_type,
    _sha256,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_entry(entry_id: str = "test.pdf", size: int = 100) -> RawEntry:
    """Create a RawEntry with a deterministic hash."""
    h = hashlib.sha256(entry_id.encode()).hexdigest()
    return RawEntry(hash=h, entry_type=FILE_TYPE, entry_id=entry_id, subfiles=0, size=size)


def _sample_file_entries() -> list[RawEntry]:
    """Build a small set of file entries representing a document."""
    return [
        _make_entry("doc-uuid.pdf", 5000),
        _make_entry("doc-uuid.metadata", 200),
        _make_entry("doc-uuid.content", 50),
    ]


def _make_cloud() -> RemarkableCloud:
    """Create a RemarkableCloud without loading tokens."""
    with patch.object(RemarkableCloud, "_load_tokens"):
        return RemarkableCloud()


# ---------------------------------------------------------------------------
# RawEntry
# ---------------------------------------------------------------------------

class TestRawEntry:
    def test_line_roundtrip(self):
        entry = RawEntry(hash="abc123", entry_type=DOC_TYPE, entry_id="my-doc", subfiles=3, size=1024)
        parsed = RawEntry.parse(entry.line())
        assert parsed.hash == "abc123"
        assert parsed.entry_type == DOC_TYPE
        assert parsed.entry_id == "my-doc"
        assert parsed.subfiles == 3
        assert parsed.size == 1024

    def test_parse_three_fields_defaults_optional(self):
        entry = RawEntry.parse("abcdef:0:test.pdf")
        assert entry.hash == "abcdef"
        assert entry.entry_type == 0
        assert entry.entry_id == "test.pdf"
        assert entry.subfiles == 0
        assert entry.size == 0

    def test_parse_all_five_fields(self):
        entry = RawEntry.parse("abcdef:80000000:doc-id:5:2048")
        assert entry.entry_type == DOC_TYPE
        assert entry.entry_id == "doc-id"
        assert entry.subfiles == 5
        assert entry.size == 2048

    def test_parse_non_numeric_type_defaults_to_zero(self):
        """v4 summary lines have '.' as the type field — should not crash."""
        entry = RawEntry.parse("0:.:2:1024")
        assert entry.entry_type == 0


# ---------------------------------------------------------------------------
# Hash functions — tested against precomputed golden values
# ---------------------------------------------------------------------------

# Golden values computed from _sample_file_entries() — if the hash algorithm
# changes, these must be intentionally updated.
V3_GOLDEN_HASH = "963f9ac7952205f5d6b074f6c5ec40dc5e4a5eabb26cab3227500bba4a8a190e"
V4_GOLDEN_HASH = "e4d54f57877bca32a0bdbd954275268e19cc4ec427c2bbc10bc59712011fd02d"


class TestHashFunctions:
    def test_v3_hash_matches_golden(self):
        assert _hash_entries_v3(_sample_file_entries()) == V3_GOLDEN_HASH

    def test_v3_hash_order_independent(self):
        """v3 hash sorts by entry_id internally, so input order doesn't matter."""
        entries = _sample_file_entries()
        assert _hash_entries_v3(entries) == _hash_entries_v3(list(reversed(entries)))

    def test_v4_hash_matches_golden(self):
        blob = _build_entries_blob(_sample_file_entries(), schema=4)
        assert _hash_blob_v4(blob) == V4_GOLDEN_HASH

    def test_v3_and_v4_hashes_differ(self):
        """Same entries must produce different hashes under v3 vs v4 algorithms."""
        entries = _sample_file_entries()
        v3 = _hash_entries_v3(entries)
        v4 = _hash_blob_v4(_build_entries_blob(entries, schema=4))
        assert v3 != v4

    def test_v3_hash_changes_when_entry_changes(self):
        entries_a = [_make_entry("a.pdf", 100)]
        entries_b = [_make_entry("b.pdf", 100)]
        assert _hash_entries_v3(entries_a) != _hash_entries_v3(entries_b)


# ---------------------------------------------------------------------------
# Index blob building
# ---------------------------------------------------------------------------

class TestBuildEntriesBlob:
    def test_v3_starts_with_version_then_entries(self):
        entries = [_make_entry("b.pdf", 200), _make_entry("a.pdf", 100)]
        blob = _build_entries_blob(entries, schema=3)
        lines = blob.decode().strip().split("\n")
        assert lines[0] == "3"
        assert len(lines) == 3  # version + 2 entries

    def test_v3_entries_sorted_by_id(self):
        entries = [_make_entry("z.pdf"), _make_entry("a.pdf"), _make_entry("m.pdf")]
        blob = _build_entries_blob(entries, schema=3)
        lines = blob.decode().strip().split("\n")
        parsed = [RawEntry.parse(line) for line in lines[1:]]
        ids = [e.entry_id for e in parsed]
        assert ids == ["a.pdf", "m.pdf", "z.pdf"]

    def test_v4_has_summary_line_with_correct_counts(self):
        entries = [_make_entry("b.pdf", 200), _make_entry("a.pdf", 100)]
        blob = _build_entries_blob(entries, schema=4)
        lines = blob.decode().strip().split("\n")
        assert lines[0] == "4"
        # Summary line: 0:.:count:totalSize
        assert lines[1] == "0:.:2:300"
        assert len(lines) == 4  # version + summary + 2 entries

    def test_v4_empty_entries(self):
        blob = _build_entries_blob([], schema=4)
        lines = blob.decode().strip().split("\n")
        assert lines[0] == "4"
        assert lines[1] == "0:.:0:0"


# ---------------------------------------------------------------------------
# Entry type helpers
# ---------------------------------------------------------------------------

class TestEntryTypeHelpers:
    def test_root_entry_type_v3_is_doc_type(self):
        assert _root_entry_type(3) == DOC_TYPE

    def test_root_entry_type_v4_is_file_type(self):
        assert _root_entry_type(4) == FILE_TYPE

    def test_root_entry_type_future_versions_use_file_type(self):
        assert _root_entry_type(5) == FILE_TYPE
        assert _root_entry_type(10) == FILE_TYPE

    def test_is_doc_entry_accepts_both_types(self):
        assert _is_doc_entry(RawEntry(hash="a", entry_type=DOC_TYPE, entry_id="x")) is True
        assert _is_doc_entry(RawEntry(hash="a", entry_type=FILE_TYPE, entry_id="x")) is True


# ---------------------------------------------------------------------------
# Index parsing
# ---------------------------------------------------------------------------

class TestParseEntries:
    def test_parse_v3_index(self):
        blob = b"3\nabc:80000000:doc-1:3:0\ndef:80000000:doc-2:5:0\n"
        entries = _make_cloud()._parse_entries(blob)
        assert len(entries) == 2
        assert entries[0].entry_id == "doc-1"
        assert entries[0].entry_type == DOC_TYPE
        assert entries[1].entry_id == "doc-2"

    def test_parse_v4_index_filters_summary_line(self):
        blob = b"4\n0:.:2:1024\nabc:0:doc-1:3:500\ndef:0:doc-2:5:524\n"
        entries = _make_cloud()._parse_entries(blob)
        assert len(entries) == 2
        assert entries[0].entry_id == "doc-1"
        assert entries[1].entry_id == "doc-2"

    def test_parse_empty_index(self):
        assert _make_cloud()._parse_entries(b"3\n") == []

    def test_detect_schema_from_blob(self):
        cloud = _make_cloud()
        assert cloud._detect_schema_from_blob(b"3\nabc:0:doc:0:0\n") == 3
        assert cloud._detect_schema_from_blob(b"4\n0:.:1:100\n") == 4


# ---------------------------------------------------------------------------
# hash_index dispatching
# ---------------------------------------------------------------------------

class TestHashIndex:
    def test_v3_uses_entry_hash_algorithm(self):
        cloud = _make_cloud()
        entries = _sample_file_entries()
        blob = _build_entries_blob(entries, schema=3)
        assert cloud._hash_index(entries, blob, schema=3) == V3_GOLDEN_HASH

    def test_v4_uses_content_hash_algorithm(self):
        cloud = _make_cloud()
        entries = _sample_file_entries()
        blob = _build_entries_blob(entries, schema=4)
        assert cloud._hash_index(entries, blob, schema=4) == V4_GOLDEN_HASH


# ---------------------------------------------------------------------------
# find_document_by_id — deleted/trashed detection
# ---------------------------------------------------------------------------

class TestFindDocumentById:
    def _mock_find(self, metadata: dict) -> CloudDocument | None:
        """Set up mocks for find_document_by_id with given metadata."""
        cloud = _make_cloud()
        doc_id = "test-doc-id"
        meta_hash = "metahash123"
        meta_blob = json.dumps(metadata).encode()

        root_blob = f"3\nrootdochash:80000000:{doc_id}:1:0\n".encode()
        doc_blob = f"3\n{meta_hash}:0:{doc_id}.metadata:0:{len(meta_blob)}\n".encode()

        def get_blob(h):
            if h == "roothash":
                return root_blob
            if h == "rootdochash":
                return doc_blob
            if h == meta_hash:
                return meta_blob
            raise RuntimeError(f"Unknown hash: {h}")

        cloud._get_root_hash = MagicMock(return_value=("roothash", 1, 3))
        cloud._get_blob = MagicMock(side_effect=get_blob)

        return cloud.find_document_by_id(doc_id)

    def test_finds_normal_document(self):
        doc = self._mock_find({
            "visibleName": "My Doc",
            "type": "DocumentType",
            "parent": "",
            "deleted": False,
        })
        assert doc is not None
        assert doc.visible_name == "My Doc"
        assert doc.doc_id == "test-doc-id"

    def test_returns_none_for_deleted(self):
        doc = self._mock_find({
            "visibleName": "Deleted Doc",
            "type": "DocumentType",
            "parent": "",
            "deleted": True,
        })
        assert doc is None

    def test_returns_none_for_trashed(self):
        doc = self._mock_find({
            "visibleName": "Trashed Doc",
            "type": "DocumentType",
            "parent": "trash",
            "deleted": False,
        })
        assert doc is None

    def test_returns_none_for_missing_doc(self):
        cloud = _make_cloud()
        root_blob = b"3\nroothash:80000000:other-doc:1:0\n"
        cloud._get_root_hash = MagicMock(return_value=("roothash", 1, 3))
        cloud._get_blob = MagicMock(return_value=root_blob)
        assert cloud.find_document_by_id("nonexistent-id") is None


# ---------------------------------------------------------------------------
# _do_update — v3 vs v4 integration
# ---------------------------------------------------------------------------

class TestDoUpdate:
    def _run_update(self, schema_version: int, tmp_path: Path) -> dict:
        """Run _do_update with mocked blobs and capture what gets uploaded.

        Returns a dict of {filename: (hash, data)} for all put_blob calls.
        """
        cloud = _make_cloud()
        doc_id = "test-doc-uuid"

        pdf_path = tmp_path / "test.pdf"
        pdf_data = b"%PDF-1.4 test content"
        pdf_path.write_bytes(pdf_data)

        old_pdf_hash = _sha256(b"old pdf content")
        old_meta = {
            "visibleName": "Test Doc",
            "lastModified": "1000000",
            "version": 1,
            "type": "DocumentType",
            "parent": "",
            "deleted": False,
        }
        old_meta_bytes = json.dumps(old_meta).encode()
        old_meta_hash = _sha256(old_meta_bytes)
        annotation_hash = _sha256(b"annotation data")

        file_entries = [
            RawEntry(hash=old_pdf_hash, entry_type=FILE_TYPE, entry_id=f"{doc_id}.pdf", size=100),
            RawEntry(hash=old_meta_hash, entry_type=FILE_TYPE, entry_id=f"{doc_id}.metadata", size=len(old_meta_bytes)),
            RawEntry(hash=annotation_hash, entry_type=FILE_TYPE, entry_id=f"{doc_id}/page1.rm", size=50),
        ]

        doc_entry_type = _root_entry_type(schema_version)
        doc_index_blob = _build_entries_blob(file_entries, schema_version)
        if schema_version >= 4:
            doc_index_hash = _hash_blob_v4(doc_index_blob)
        else:
            doc_index_hash = _hash_entries_v3(file_entries)

        root_entries = [
            RawEntry(hash=doc_index_hash, entry_type=doc_entry_type, entry_id=doc_id, subfiles=3),
        ]
        root_index_blob = _build_entries_blob(root_entries, schema_version)

        uploaded: dict[str, tuple[str, bytes]] = {}

        def mock_get_blob(h):
            if h == "root-hash":
                return root_index_blob
            if h == doc_index_hash:
                return doc_index_blob
            if h == old_meta_hash:
                return old_meta_bytes
            raise RuntimeError(f"Unexpected blob fetch: {h}")

        def mock_put_blob(h, data, filename="", schema=3):
            uploaded[filename] = (h, data)

        cloud._get_root_hash = MagicMock(return_value=("root-hash", 42, schema_version))
        cloud._get_blob = MagicMock(side_effect=mock_get_blob)
        cloud._put_blob = MagicMock(side_effect=mock_put_blob)
        cloud._put_root_hash = MagicMock(return_value=("new-root", 43))

        doc = CloudDocument(
            doc_id=doc_id,
            doc_hash=doc_index_hash,
            visible_name="Test Doc",
            file_entries=file_entries,
        )
        cloud._do_update(doc, pdf_path)

        # Verify generation was passed through
        cloud._put_root_hash.assert_called_once()
        assert cloud._put_root_hash.call_args[0][1] == 42

        return uploaded

    def _get_uploaded_doc_index(self, uploaded: dict) -> bytes:
        """Extract the doc index blob from uploaded files."""
        keys = [k for k in uploaded if k.endswith(".docSchema") and k != "root.docSchema"]
        assert len(keys) == 1
        return uploaded[keys[0]][1]

    def _get_uploaded_root_index(self, uploaded: dict) -> bytes:
        return uploaded["root.docSchema"][1]

    def test_v3_update_produces_v3_index(self, tmp_path: Path):
        uploaded = self._run_update(3, tmp_path)
        doc_blob = self._get_uploaded_doc_index(uploaded)
        root_blob = self._get_uploaded_root_index(uploaded)

        # Both start with v3
        assert doc_blob.startswith(b"3\n")
        assert root_blob.startswith(b"3\n")

        # Root doc entry uses DOC_TYPE
        root_entries = _make_cloud()._parse_entries(root_blob)
        assert len(root_entries) == 1
        assert root_entries[0].entry_type == DOC_TYPE

    def test_v4_update_produces_v4_index(self, tmp_path: Path):
        uploaded = self._run_update(4, tmp_path)
        doc_blob = self._get_uploaded_doc_index(uploaded)
        root_blob = self._get_uploaded_root_index(uploaded)

        # Both start with v4
        assert doc_blob.startswith(b"4\n")
        assert root_blob.startswith(b"4\n")

        # Root doc entry uses FILE_TYPE
        root_entries = _make_cloud()._parse_entries(root_blob)
        assert len(root_entries) == 1
        assert root_entries[0].entry_type == FILE_TYPE

    def test_v4_hash_equals_content_hash_of_blob(self, tmp_path: Path):
        """v4 hashes must be SHA-256 of the serialized blob itself."""
        uploaded = self._run_update(4, tmp_path)

        for filename in ("root.docSchema",):
            blob_hash, blob_data = uploaded[filename]
            assert blob_hash == _sha256(blob_data), f"{filename} hash mismatch"

        doc_key = [k for k in uploaded if k.endswith(".docSchema") and k != "root.docSchema"][0]
        doc_hash, doc_data = uploaded[doc_key]
        assert doc_hash == _sha256(doc_data)

    def test_v3_hash_differs_from_content_hash(self, tmp_path: Path):
        """v3 uses hash-of-hashes, NOT content hash of the blob."""
        uploaded = self._run_update(3, tmp_path)
        doc_key = [k for k in uploaded if k.endswith(".docSchema") and k != "root.docSchema"][0]
        doc_hash, doc_data = uploaded[doc_key]
        assert doc_hash != _sha256(doc_data)

    def test_preserves_annotation_files(self, tmp_path: Path):
        """Annotation .rm files must appear in the new index but not be re-uploaded."""
        uploaded = self._run_update(3, tmp_path)
        doc_blob = self._get_uploaded_doc_index(uploaded)
        doc_entries = _make_cloud()._parse_entries(doc_blob)

        # Annotation entry is preserved in the index
        annotation_entries = [e for e in doc_entries if e.entry_id.endswith(".rm")]
        assert len(annotation_entries) == 1
        assert annotation_entries[0].entry_id == "test-doc-uuid/page1.rm"

        # Annotation was NOT re-uploaded (only pdf, metadata, and 2 schema blobs)
        uploaded_filenames = set(uploaded.keys())
        assert not any(f.endswith(".rm") for f in uploaded_filenames)

    def test_metadata_version_incremented(self, tmp_path: Path):
        uploaded = self._run_update(3, tmp_path)
        meta_files = [k for k in uploaded if k.endswith(".metadata")]
        assert len(meta_files) == 1
        meta = json.loads(uploaded[meta_files[0]][1])
        assert meta["version"] == 2  # Was 1, now 2

    def test_pdf_blob_uploaded_with_new_content(self, tmp_path: Path):
        uploaded = self._run_update(3, tmp_path)
        pdf_files = [k for k in uploaded if k.endswith(".pdf")]
        assert len(pdf_files) == 1
        pdf_data = uploaded[pdf_files[0]][1]
        assert pdf_data == b"%PDF-1.4 test content"


# ---------------------------------------------------------------------------
# _put_blob content-type handling
# ---------------------------------------------------------------------------

class TestPutBlobContentType:
    """Verify v4 sets text/plain Content-Type on schema blobs by inspecting
    the headers dict built inside _put_blob, not httpx internals."""

    def _capture_put_blob_headers(self, filename: str, schema: int) -> dict:
        """Call _put_blob and capture the headers passed to _authed_request."""
        cloud = _make_cloud()
        captured = {}

        def mock_authed_request(method, url, **kwargs):
            captured.update(kwargs.get("headers", {}))
            resp = MagicMock()
            resp.status_code = 200
            resp.raise_for_status = MagicMock()
            return resp

        cloud._user_token = "test"
        cloud._authed_request = mock_authed_request
        cloud._put_blob("testhash", b"test data", filename, schema=schema)
        return captured

    def test_v4_schema_blob_has_text_plain_content_type(self):
        headers = self._capture_put_blob_headers("root.docSchema", schema=4)
        assert headers.get("content-type") == "text/plain; charset=UTF-8"

    def test_v3_schema_blob_has_no_content_type_override(self):
        headers = self._capture_put_blob_headers("root.docSchema", schema=3)
        assert "content-type" not in headers

    def test_v4_pdf_blob_has_no_content_type_override(self):
        headers = self._capture_put_blob_headers("doc.pdf", schema=4)
        assert "content-type" not in headers


# ---------------------------------------------------------------------------
# upload_simple status code handling
# ---------------------------------------------------------------------------

class TestUploadSimple:
    def _mock_upload(self, status_code: int, body: dict | str) -> RemarkableCloud:
        cloud = _make_cloud()
        cloud._user_token = "test-token"
        resp = MagicMock()
        resp.status_code = status_code
        if isinstance(body, dict):
            resp.json.return_value = body
        else:
            resp.text = body
        cloud._authed_request = MagicMock(return_value=resp)
        return cloud

    def test_accepts_200(self, tmp_path: Path):
        cloud = self._mock_upload(200, {"docID": "new-doc-id"})
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF test")
        assert cloud.upload_simple("Test", pdf) == "new-doc-id"

    def test_accepts_201(self, tmp_path: Path):
        cloud = self._mock_upload(201, {"docID": "new-doc-id"})
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF test")
        assert cloud.upload_simple("Test", pdf) == "new-doc-id"

    def test_rejects_500(self, tmp_path: Path):
        cloud = self._mock_upload(500, "Internal Server Error")
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF test")
        with pytest.raises(RuntimeError, match="Upload failed"):
            cloud.upload_simple("Test", pdf)

    def test_rejects_missing_doc_id(self, tmp_path: Path):
        cloud = self._mock_upload(200, {"hash": "abc123"})
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF test")
        with pytest.raises(RuntimeError, match="missing docID"):
            cloud.upload_simple("Test", pdf)


# ---------------------------------------------------------------------------
# Generation conflict retry
# ---------------------------------------------------------------------------

class TestUpdateRetry:
    def test_retries_on_generation_conflict(self, tmp_path: Path):
        cloud = _make_cloud()
        call_count = 0

        def mock_do_update(doc, pdf_path, old_manifest=None, new_manifest=None):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise GenerationConflict("conflict")

        cloud._do_update = MagicMock(side_effect=mock_do_update)
        doc = CloudDocument(doc_id="test", doc_hash="abc", visible_name="Test")
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF test")

        cloud.update_document(doc, pdf)
        assert call_count == 3

    def test_raises_after_max_retries(self, tmp_path: Path):
        cloud = _make_cloud()
        cloud._do_update = MagicMock(side_effect=GenerationConflict("conflict"))
        doc = CloudDocument(doc_id="test", doc_hash="abc", visible_name="Test")
        pdf = tmp_path / "test.pdf"
        pdf.write_bytes(b"%PDF test")

        with pytest.raises(GenerationConflict):
            cloud.update_document(doc, pdf)
        assert cloud._do_update.call_count == 5
