"""reMarkable Cloud API client (tectonic / sync v3-v4 protocol).

Based on reverse-engineering from rmapi-js (erikbrinkman/rmapi-js).
Handles device registration, authentication, document listing, upload, and replacement.
"""

from __future__ import annotations

import base64
import hashlib
import json
import struct
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

import httpx

AUTH_HOST = "https://webapp-prod.cloud.remarkable.engineering"
RAW_HOST = "https://eu.tectonic.remarkable.com"
UPLOAD_HOST = "https://internal.cloud.remarkable.com"

TOKEN_FILE = Path("~/.config/rmcal/remarkable_token.json").expanduser()

# Index format constants
SCHEMA_VERSION = 3
DOC_TYPE = 80000000
FILE_TYPE = 0
DELIMITER = ":"


def _crc32c(data: bytes) -> str:
    """Compute CRC32C checksum and return as base64."""
    try:
        import crc32c as _crc32c_mod
        crc = _crc32c_mod.crc32c(data)
    except ImportError:
        # Pure-python fallback using the crc32c table
        crc = _crc32c_pure(data)
    buf = struct.pack(">I", crc & 0xFFFFFFFF)
    return base64.b64encode(buf).decode()


def _crc32c_pure(data: bytes) -> int:
    """Pure-python CRC32C (Castagnoli) implementation."""
    crc = 0xFFFFFFFF
    poly = 0x82F63B78
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 1:
                crc = (crc >> 1) ^ poly
            else:
                crc >>= 1
    return crc ^ 0xFFFFFFFF


@dataclass
class RawEntry:
    """An entry in a document or root index."""

    hash: str
    entry_type: int  # DOC_TYPE (80000000) or FILE_TYPE (0)
    entry_id: str  # document UUID or filename
    subfiles: int = 0
    size: int = 0

    def line(self) -> str:
        return f"{self.hash}:{self.entry_type}:{self.entry_id}:{self.subfiles}:{self.size}"

    @staticmethod
    def parse(line: str) -> RawEntry:
        parts = line.strip().split(":")
        return RawEntry(
            hash=parts[0],
            entry_type=int(parts[1]),
            entry_id=parts[2],
            subfiles=int(parts[3]) if len(parts) > 3 else 0,
            size=int(parts[4]) if len(parts) > 4 else 0,
        )


@dataclass
class CloudDocument:
    """A document in the reMarkable Cloud."""

    doc_id: str
    doc_hash: str
    visible_name: str
    parent: str = ""
    doc_type: str = "DocumentType"
    file_entries: list[RawEntry] = field(default_factory=list)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _hash_entries_v3(entries: list[RawEntry]) -> str:
    """Compute schema v3 collection hash: SHA-256 of concatenated binary hashes."""
    sorted_entries = sorted(entries, key=lambda e: e.entry_id)
    hasher = hashlib.sha256()
    for e in sorted_entries:
        hasher.update(bytes.fromhex(e.hash))
    return hasher.hexdigest()


class RemarkableCloud:
    """Client for the reMarkable Cloud API (tectonic protocol)."""

    def __init__(self) -> None:
        self._device_token: str | None = None
        self._user_token: str | None = None
        self._client = httpx.Client(timeout=60, follow_redirects=True)
        self._load_tokens()

    @property
    def is_authenticated(self) -> bool:
        return self._device_token is not None

    def register_device(self, code: str) -> None:
        """Register this app as a device using a one-time code."""
        device_id = str(uuid.uuid4())
        resp = self._client.post(
            f"{AUTH_HOST}/token/json/2/device/new",
            json={
                "code": code,
                "deviceDesc": "desktop-windows",
                "deviceID": device_id,
            },
            headers={"Authorization": "Bearer"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"Device registration failed (HTTP {resp.status_code}): {resp.text}"
            )
        self._device_token = resp.text
        self._save_tokens()
        self._refresh_user_token()

    def _refresh_user_token(self) -> None:
        if not self._device_token:
            raise RuntimeError("Not authenticated. Run 'register' first.")
        resp = self._client.post(
            f"{AUTH_HOST}/token/json/2/user/new",
            headers={"Authorization": f"Bearer {self._device_token}"},
        )
        if resp.status_code != 200:
            raise RuntimeError(
                f"User token refresh failed (HTTP {resp.status_code}): {resp.text}"
            )
        self._user_token = resp.text
        self._save_tokens()

    def _auth_headers(self) -> dict[str, str]:
        if not self._user_token:
            self._refresh_user_token()
        return {"Authorization": f"Bearer {self._user_token}"}

    def _authed_request(
        self, method: str, url: str, retry_auth: bool = True, **kwargs
    ) -> httpx.Response:
        headers = {**self._auth_headers(), **kwargs.pop("headers", {})}
        resp = self._client.request(method, url, headers=headers, **kwargs)
        if resp.status_code == 401 and retry_auth:
            self._refresh_user_token()
            headers = {**self._auth_headers(), **kwargs.pop("headers", {})}
            resp = self._client.request(method, url, headers=headers, **kwargs)
        return resp

    # --- Low-level blob operations (tectonic protocol) ---

    def _get_root_hash(self) -> tuple[str, int, int]:
        """Get root hash, generation, and schema version."""
        resp = self._authed_request("GET", f"{RAW_HOST}/sync/v4/root")
        resp.raise_for_status()
        data = resp.json()
        return data["hash"], data["generation"], data.get("schemaVersion", 3)

    def _get_blob(self, blob_hash: str) -> bytes:
        """Download a blob by hash."""
        resp = self._authed_request("GET", f"{RAW_HOST}/sync/v3/files/{blob_hash}")
        resp.raise_for_status()
        return resp.content

    def _put_blob(self, blob_hash: str, data: bytes, filename: str = "") -> None:
        """Upload a blob by hash."""
        crc = _crc32c(data)
        headers = {
            "rm-filename": filename or blob_hash,
            "x-goog-hash": f"crc32c={crc}",
        }
        resp = self._authed_request(
            "PUT", f"{RAW_HOST}/sync/v3/files/{blob_hash}",
            content=data, headers=headers,
        )
        resp.raise_for_status()

    def _put_root_hash(self, root_hash: str, generation: int) -> tuple[str, int]:
        """Update the root hash. Returns (new_hash, new_generation)."""
        resp = self._authed_request(
            "PUT", f"{RAW_HOST}/sync/v3/root",
            content=json.dumps({
                "hash": root_hash,
                "generation": generation,
                "broadcast": True,
            }).encode(),
        )
        if resp.status_code == 409 or b"precondition failed" in resp.content.lower():
            raise GenerationConflict("Root generation conflict")
        resp.raise_for_status()
        data = resp.json()
        return data["hash"], data["generation"]

    # --- Index parsing ---

    def _parse_entries(self, blob: bytes) -> list[RawEntry]:
        """Parse an index blob into entries."""
        text = blob.decode()
        lines = text.strip().split("\n")
        # Skip schema version line (and optional info line for v4)
        entries = []
        for line in lines[1:]:
            line = line.strip()
            if line:
                parsed = RawEntry.parse(line)
                # Skip v4 info lines (type "0" with id "." at start)
                if parsed.entry_id != ".":
                    entries.append(parsed)
        return entries

    def _build_entries_blob(self, entries: list[RawEntry]) -> bytes:
        """Build an index blob from entries (schema v3)."""
        sorted_entries = sorted(entries, key=lambda e: e.entry_id)
        lines = [f"{SCHEMA_VERSION}\n"]
        for e in sorted_entries:
            lines.append(f"{e.line()}\n")
        return "".join(lines).encode()

    # --- Public API ---

    def upload_simple(self, name: str, pdf_path: Path) -> str:
        """Upload a PDF using the simple upload API. Returns doc ID.

        This is the easiest way to upload a new document — the cloud
        handles creating all the metadata and index entries.
        """
        pdf_data = pdf_path.read_bytes()
        meta = base64.b64encode(
            json.dumps({"file_name": name}).encode()
        ).decode()
        resp = self._authed_request(
            "POST", f"{UPLOAD_HOST}/doc/v2/files",
            content=pdf_data,
            headers={
                "Content-Type": "application/pdf",
                "rm-meta": meta,
                "rm-source": "RoR-Browser",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data["docID"]

    def list_documents(self) -> list[CloudDocument]:
        """List all documents in the cloud."""
        root_hash, _, _ = self._get_root_hash()
        root_blob = self._get_blob(root_hash)
        root_entries = self._parse_entries(root_blob)

        docs = []
        for entry in root_entries:
            if entry.entry_type != DOC_TYPE:
                continue
            try:
                doc_blob = self._get_blob(entry.hash)
                file_entries = self._parse_entries(doc_blob)

                # Find and parse metadata
                metadata = {}
                for f in file_entries:
                    if f.entry_id.endswith(".metadata"):
                        meta_blob = self._get_blob(f.hash)
                        metadata = json.loads(meta_blob)
                        break

                docs.append(CloudDocument(
                    doc_id=entry.entry_id,
                    doc_hash=entry.hash,
                    visible_name=metadata.get("visibleName", ""),
                    parent=metadata.get("parent", ""),
                    doc_type=metadata.get("type", "DocumentType"),
                    file_entries=file_entries,
                ))
            except Exception:
                continue  # Skip docs we can't parse
        return docs

    def find_document(self, name: str) -> CloudDocument | None:
        """Find a document by visible name."""
        for doc in self.list_documents():
            if doc.visible_name == name and doc.doc_type == "DocumentType":
                return doc
        return None

    def find_document_by_id(self, doc_id: str) -> CloudDocument | None:
        """Find a document by ID without downloading all metadata (fast)."""
        root_hash, _, _ = self._get_root_hash()
        root_blob = self._get_blob(root_hash)
        root_entries = self._parse_entries(root_blob)

        for entry in root_entries:
            if entry.entry_id == doc_id:
                doc_blob = self._get_blob(entry.hash)
                file_entries = self._parse_entries(doc_blob)
                # Get metadata for this specific doc
                metadata = {}
                for f in file_entries:
                    if f.entry_id.endswith(".metadata"):
                        meta_blob = self._get_blob(f.hash)
                        metadata = json.loads(meta_blob)
                        break
                return CloudDocument(
                    doc_id=entry.entry_id,
                    doc_hash=entry.hash,
                    visible_name=metadata.get("visibleName", ""),
                    parent=metadata.get("parent", ""),
                    doc_type=metadata.get("type", "DocumentType"),
                    file_entries=file_entries,
                )
        return None

    def upload_new_document(self, name: str, pdf_path: Path, parent: str = "") -> str:
        """Upload a new PDF document. Returns the document ID."""
        # Use the simple API for new uploads
        return self.upload_simple(name, pdf_path)

    def update_document(self, doc: CloudDocument, pdf_path: Path) -> None:
        """Update an existing document's PDF while preserving annotations.

        Replaces the PDF blob, updates metadata, keeps all .rm annotation files.
        """
        max_retries = 5
        for attempt in range(max_retries):
            try:
                self._do_update(doc, pdf_path)
                return
            except GenerationConflict:
                if attempt == max_retries - 1:
                    raise

    def _do_update(self, doc: CloudDocument, pdf_path: Path) -> None:
        """Perform the actual document update."""
        doc_id = doc.doc_id
        pdf_data = pdf_path.read_bytes()

        # Get current root state
        root_hash, generation, schema_version = self._get_root_hash()
        root_blob = self._get_blob(root_hash)
        root_entries = self._parse_entries(root_blob)

        # Re-fetch document entries (may have changed)
        doc_entry = None
        for e in root_entries:
            if e.entry_id == doc_id:
                doc_entry = e
                break
        if not doc_entry:
            raise RuntimeError(f"Document {doc_id} not found in root index")

        doc_blob = self._get_blob(doc_entry.hash)
        file_entries = self._parse_entries(doc_blob)

        # Build new file entries — replace PDF and metadata, keep everything else
        new_file_entries: list[RawEntry] = []

        for f in file_entries:
            if f.entry_id.endswith(".pdf"):
                # Replace PDF
                pdf_hash = _sha256(pdf_data)
                self._put_blob(pdf_hash, pdf_data, f"{doc_id}.pdf")
                new_file_entries.append(RawEntry(
                    hash=pdf_hash, entry_type=FILE_TYPE,
                    entry_id=f.entry_id, size=len(pdf_data),
                ))
            elif f.entry_id.endswith(".metadata"):
                # Update metadata timestamp
                old_meta = json.loads(self._get_blob(f.hash))
                old_meta["lastModified"] = str(int(time.time() * 1000))
                old_meta["version"] = old_meta.get("version", 0) + 1
                meta_bytes = json.dumps(old_meta).encode()
                meta_hash = _sha256(meta_bytes)
                self._put_blob(meta_hash, meta_bytes, f"{doc_id}.metadata")
                new_file_entries.append(RawEntry(
                    hash=meta_hash, entry_type=FILE_TYPE,
                    entry_id=f.entry_id, size=len(meta_bytes),
                ))
            else:
                # Keep annotations, content, pagedata, etc. as-is
                new_file_entries.append(f)

        # Build and upload new document index
        doc_index_blob = self._build_entries_blob(new_file_entries)
        doc_index_hash = _hash_entries_v3(new_file_entries)
        self._put_blob(doc_index_hash, doc_index_blob, f"{doc_id}.docSchema")

        # Update root index
        new_root_entries = [e for e in root_entries if e.entry_id != doc_id]
        new_root_entries.append(RawEntry(
            hash=doc_index_hash, entry_type=DOC_TYPE,
            entry_id=doc_id, subfiles=len(new_file_entries),
        ))

        root_index_blob = self._build_entries_blob(new_root_entries)
        # For schema v3, root hash is also computed from concatenated binary hashes
        new_root_hash = _hash_entries_v3(new_root_entries)
        self._put_blob(new_root_hash, root_index_blob, "root.docSchema")

        # Commit the new root
        self._put_root_hash(new_root_hash, generation)

    def _load_tokens(self) -> None:
        if TOKEN_FILE.exists():
            data = json.loads(TOKEN_FILE.read_text())
            self._device_token = data.get("device_token")
            self._user_token = data.get("user_token")

    def _save_tokens(self) -> None:
        TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        TOKEN_FILE.write_text(json.dumps({
            "device_token": self._device_token,
            "user_token": self._user_token,
        }))

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> RemarkableCloud:
        return self

    def __exit__(self, *args) -> None:
        self.close()


class GenerationConflict(Exception):
    """Raised when the root generation doesn't match (concurrent sync)."""
