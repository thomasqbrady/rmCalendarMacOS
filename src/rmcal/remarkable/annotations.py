"""Annotation preservation across syncs.

Maps page UUIDs between old and new document versions using bookmark-based
page manifests, so handwritten annotations stay on the correct page even
when meetings are added or removed.

Orphaned annotations (pages that no longer exist in the new PDF) are
preserved by inserting blank carrier pages at the position where the
original page would have appeared.
"""

from __future__ import annotations

import json
import re
import uuid as uuid_mod
from pathlib import Path


def compute_page_mapping(
    old_manifest: dict[str, int],
    new_manifest: dict[str, int],
    new_page_count: int,
    old_uuids: list[str],
) -> tuple[list[str], list[int]]:
    """Compute new page UUIDs and blank page insertion points.

    Compares old and new page manifests (bookmark→page_index) to:
    1. Reuse UUIDs for pages whose bookmark still exists
    2. Identify orphaned bookmarks and insert blank carrier pages

    Args:
        old_manifest: Previous sync's bookmark→page_index mapping.
        new_manifest: Current sync's bookmark→page_index mapping.
        new_page_count: Number of pages in the newly generated PDF.
        old_uuids: Page UUIDs from the existing .content file.

    Returns:
        (final_uuids, blank_insert_indices) where:
        - final_uuids: UUID list for the final document (including blanks)
        - blank_insert_indices: sorted page indices (in the final doc)
          where blank pages should be inserted
    """
    # Invert old manifest: page_index → bookmark
    old_idx_to_bm: dict[int, str] = {v: k for k, v in old_manifest.items()}

    # Find orphaned bookmarks (exist in old but not new) that have annotations
    # We can't know which pages have annotations from here, so we preserve
    # ALL orphaned pages — blank pages are cheap.
    orphaned: list[tuple[str, int]] = []  # (bookmark, old_page_index)
    for bm, old_idx in old_manifest.items():
        if bm not in new_manifest and old_idx < len(old_uuids):
            orphaned.append((bm, old_idx))

    # Determine insertion point for each orphan: right after the related page
    # in the new document. E.g. "meeting-2026-04-02-0" → after "day-2026-04-02".
    insertions: list[tuple[int, str, str]] = []  # (new_insert_after, bookmark, old_uuid)
    for bm, old_idx in orphaned:
        insert_after = _find_insertion_point(bm, new_manifest)
        old_uuid = old_uuids[old_idx]
        insertions.append((insert_after, bm, old_uuid))

    # Sort insertions by position (stable sort preserves order for same position)
    insertions.sort(key=lambda x: x[0])

    # Build the final UUID list:
    # Start with the new document's pages, mapping bookmarks to old UUIDs
    new_bm_to_old_uuid: dict[str, str] = {}
    for bm, old_idx in old_manifest.items():
        if bm in new_manifest and old_idx < len(old_uuids):
            new_bm_to_old_uuid[bm] = old_uuids[old_idx]

    # Invert new manifest for lookup
    new_idx_to_bm: dict[int, str] = {v: k for k, v in new_manifest.items()}

    base_uuids: list[str] = []
    for i in range(new_page_count):
        bm = new_idx_to_bm.get(i)
        if bm and bm in new_bm_to_old_uuid:
            base_uuids.append(new_bm_to_old_uuid[bm])
        else:
            base_uuids.append(str(uuid_mod.uuid4()))

    # Now splice in blank pages for orphans
    # Work backwards through insertion points so indices don't shift
    blank_insert_indices: list[int] = []
    final_uuids = list(base_uuids)

    # Group insertions by position to maintain order
    offset = 0
    for insert_after, bm, old_uuid in insertions:
        # insert_after is a new-manifest page index; adjust for prior insertions
        pos = insert_after + 1 + offset
        final_uuids.insert(pos, old_uuid)
        blank_insert_indices.append(pos)
        offset += 1

    return final_uuids, sorted(blank_insert_indices)


def _find_insertion_point(bookmark: str, new_manifest: dict[str, int]) -> int:
    """Find where an orphaned page should be inserted in the new document.

    Uses bookmark naming conventions:
    - "meeting-2026-04-02-0" → insert after "day-2026-04-02"
    - "day-2026-04-02" → insert after previous day or its week
    - Other → insert at end
    """
    # Meeting notes → after the day page
    m = re.match(r"meeting-(\d{4}-\d{2}-\d{2})-\d+", bookmark)
    if m:
        day_bm = f"day-{m.group(1)}"
        if day_bm in new_manifest:
            # Insert after the day page and any existing meeting notes for that day
            day_idx = new_manifest[day_bm]
            # Find the last page associated with this day
            max_idx = day_idx
            for bm, idx in new_manifest.items():
                if bm.startswith(f"meeting-{m.group(1)}-") and idx > max_idx:
                    max_idx = idx
            return max_idx

    # Day page → after previous day
    m = re.match(r"day-(\d{4}-\d{2}-\d{2})", bookmark)
    if m:
        from datetime import date, timedelta
        d = date.fromisoformat(m.group(1))
        prev_day_bm = f"day-{(d - timedelta(days=1)).isoformat()}"
        if prev_day_bm in new_manifest:
            return new_manifest[prev_day_bm]

    # Fallback: insert at the end
    if new_manifest:
        return max(new_manifest.values())
    return 0


def insert_blank_pages(pdf_path: Path, insert_indices: list[int]) -> Path:
    """Insert blank pages into a PDF at the specified indices.

    Modifies the PDF in-place and returns the same path.
    """
    if not insert_indices:
        return pdf_path

    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(str(pdf_path))
    writer = PdfWriter()

    # Get page dimensions from the first page
    first_page = reader.pages[0]
    width = first_page.mediabox.width
    height = first_page.mediabox.height

    # Build the final page list
    insert_set = set(insert_indices)
    src_idx = 0
    for final_idx in range(len(reader.pages) + len(insert_indices)):
        if final_idx in insert_set:
            # Insert a blank page
            writer.add_blank_page(width=width, height=height)
        else:
            writer.add_page(reader.pages[src_idx])
            src_idx += 1

    with open(pdf_path, "wb") as f:
        writer.write(f)

    return pdf_path


def build_content_json(
    page_uuids: list[str],
    existing_content: dict | None = None,
) -> dict:
    """Build a .content JSON structure with the given page UUIDs.

    Preserves non-page fields from existing_content if provided.
    """
    base = existing_content or {}
    return {
        "extraMetadata": base.get("extraMetadata", {}),
        "fileType": "pdf",
        "fontName": base.get("fontName", ""),
        "lastOpenedPage": base.get("lastOpenedPage", 0),
        "lineHeight": base.get("lineHeight", -1),
        "margins": base.get("margins", 100),
        "orientation": base.get("orientation", "portrait"),
        "pageCount": len(page_uuids),
        "pages": page_uuids,
        "textScale": base.get("textScale", 1),
        "transform": base.get("transform", {
            "m11": 1, "m12": 0, "m13": 0,
            "m21": 0, "m22": 1, "m23": 0,
            "m31": 0, "m32": 0, "m33": 1,
        }),
    }
