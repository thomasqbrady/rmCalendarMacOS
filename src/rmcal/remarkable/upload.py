"""Upload PDF to reMarkable with annotation preservation."""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from pathlib import Path

from rmcal.models import DateRange, RemarkableConfig
from rmcal.remarkable.ssh import XOCHITL_DIR, RemarkableSSH

STATE_DIR = Path("~/.config/rmcal").expanduser()
STATE_FILE = STATE_DIR / "state.json"


def upload_planner(
    config: RemarkableConfig,
    pdf_path: Path,
    date_range: DateRange,
    force: bool = False,
) -> None:
    """Upload a planner PDF to the reMarkable tablet.

    Preserves handwritten annotations on subsequent uploads by:
    - Reusing the same document UUID
    - Keeping existing .rm annotation files untouched
    - Reusing existing page UUIDs in the .content pages array
    """
    with RemarkableSSH(config) as ssh:
        existing = _find_existing_document(ssh, config.document_name)

        if existing:
            # Check date range hasn't changed (would break annotation mapping)
            _check_date_range(date_range, force)
            _update_existing(ssh, existing, pdf_path, config)
        else:
            _upload_new(ssh, pdf_path, config)
            _save_state(date_range)

        ssh.restart_xochitl()


def _find_existing_document(ssh: RemarkableSSH, document_name: str) -> str | None:
    """Find an existing document UUID by visible name.

    Returns the UUID string or None.
    """
    try:
        files = ssh.listdir(XOCHITL_DIR)
    except FileNotFoundError:
        return None

    for filename in files:
        if not filename.endswith(".metadata"):
            continue

        doc_uuid = filename[: -len(".metadata")]
        try:
            content = ssh.read_file(f"{XOCHITL_DIR}/{filename}")
            metadata = json.loads(content)
        except Exception:
            continue

        if (
            metadata.get("visibleName") == document_name
            and metadata.get("type") == "DocumentType"
            and not metadata.get("deleted", False)
        ):
            return doc_uuid

    return None


def _update_existing(
    ssh: RemarkableSSH,
    doc_uuid: str,
    pdf_path: Path,
    config: RemarkableConfig,
) -> None:
    """Update an existing document, preserving annotations."""
    # Read existing .content
    content_path = f"{XOCHITL_DIR}/{doc_uuid}.content"
    content = json.loads(ssh.read_file(content_path))
    existing_pages = content.get("pages", [])

    # Count pages in the new PDF
    new_page_count = _count_pdf_pages(pdf_path)

    # Build new pages array: reuse existing page UUIDs, add new ones if needed
    new_pages = []
    for i in range(new_page_count):
        if i < len(existing_pages):
            new_pages.append(existing_pages[i])
        else:
            new_pages.append(str(uuid.uuid4()))

    # Replace the PDF
    ssh.upload_file(pdf_path, f"{XOCHITL_DIR}/{doc_uuid}.pdf")

    # Update .content
    content["pages"] = new_pages
    content["pageCount"] = new_page_count
    ssh.write_file(content_path, json.dumps(content))

    # Update timestamp in .metadata
    metadata_path = f"{XOCHITL_DIR}/{doc_uuid}.metadata"
    metadata = json.loads(ssh.read_file(metadata_path))
    metadata["lastModified"] = str(int(time.time() * 1000))
    metadata["version"] = metadata.get("version", 0) + 1
    ssh.write_file(metadata_path, json.dumps(metadata))


def _upload_new(
    ssh: RemarkableSSH,
    pdf_path: Path,
    config: RemarkableConfig,
) -> None:
    """Upload a brand new document."""
    doc_uuid = str(uuid.uuid4())
    page_count = _count_pdf_pages(pdf_path)
    pages = [str(uuid.uuid4()) for _ in range(page_count)]
    now_ms = str(int(time.time() * 1000))

    # Upload PDF
    ssh.upload_file(pdf_path, f"{XOCHITL_DIR}/{doc_uuid}.pdf")

    # Create .metadata
    metadata = {
        "deleted": False,
        "lastModified": now_ms,
        "lastOpened": now_ms,
        "lastOpenedPage": 0,
        "metadatamodified": False,
        "modified": False,
        "parent": config.folder or "",
        "pinned": False,
        "synced": False,
        "type": "DocumentType",
        "version": 1,
        "visibleName": config.document_name,
    }
    ssh.write_file(f"{XOCHITL_DIR}/{doc_uuid}.metadata", json.dumps(metadata))

    # Create .content
    content = {
        "extraMetadata": {},
        "fileType": "pdf",
        "fontName": "",
        "lastOpenedPage": 0,
        "lineHeight": -1,
        "margins": 100,
        "orientation": "portrait",
        "pageCount": page_count,
        "pages": pages,
        "textScale": 1,
        "transform": {
            "m11": 1, "m12": 0, "m13": 0,
            "m21": 0, "m22": 1, "m23": 0,
            "m31": 0, "m32": 0, "m33": 1,
        },
    }
    ssh.write_file(f"{XOCHITL_DIR}/{doc_uuid}.content", json.dumps(content))

    # Create required directories
    ssh.mkdir(f"{XOCHITL_DIR}/{doc_uuid}")
    ssh.mkdir(f"{XOCHITL_DIR}/{doc_uuid}.thumbnails")
    ssh.mkdir(f"{XOCHITL_DIR}/{doc_uuid}.highlights")


def _count_pdf_pages(pdf_path: Path) -> int:
    """Count pages in a PDF file using pypdf."""
    try:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        return len(reader.pages)
    except ImportError:
        # Fallback: use reportlab's page count if pypdf not available
        # This is a rough estimate based on file parsing
        # In practice, we know the page count from generation
        raise RuntimeError(
            "pypdf is required for page counting. Install with: pip install pypdf"
        )


def _check_date_range(date_range: DateRange, force: bool) -> None:
    """Check if the date range has changed since the last upload.

    If it has, annotations won't align with the new pages.
    """
    if force:
        return

    state = _load_state()
    if state is None:
        return

    old_hash = state.get("date_range_hash")
    new_hash = date_range.hash_key
    if old_hash and old_hash != new_hash:
        raise RuntimeError(
            f"Date range has changed (was {old_hash}, now {new_hash}). "
            f"Annotations won't align with new pages. "
            f"Use --force to upload anyway (annotations will be misaligned), "
            f"or delete the existing document first."
        )


def _load_state() -> dict | None:
    """Load the local state file."""
    if not STATE_FILE.exists():
        return None
    return json.loads(STATE_FILE.read_text())


def _save_state(date_range: DateRange) -> None:
    """Save the current state."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {"date_range_hash": date_range.hash_key}
    STATE_FILE.write_text(json.dumps(state))
