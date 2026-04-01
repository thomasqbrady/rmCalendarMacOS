"""Fetch ICS calendar feeds."""

from __future__ import annotations

import httpx

from rmcal.models import CalendarSource


def fetch_all_calendars(
    sources: list[CalendarSource],
    timeout: float = 30.0,
) -> list[tuple[CalendarSource, str]]:
    """Fetch ICS data from all calendar sources.

    Returns list of (source, ics_text) tuples.
    """
    results: list[tuple[CalendarSource, str]] = []
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        for source in sources:
            ics_text = _fetch_ics(client, source)
            results.append((source, ics_text))
    return results


def _fetch_ics(client: httpx.Client, source: CalendarSource) -> str:
    """Fetch a single ICS feed with retry."""
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            resp = client.get(source.url)
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as e:
            last_error = e
            if attempt < 2:
                import time

                time.sleep(2**attempt)
    raise RuntimeError(
        f"Failed to fetch calendar '{source.name}' from {source.url}: {last_error}"
    )
