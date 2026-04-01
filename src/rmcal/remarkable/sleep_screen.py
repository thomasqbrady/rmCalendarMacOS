"""Generate and upload a sleep screen showing today's events."""

from __future__ import annotations

import tempfile
from datetime import date, datetime, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from rmcal.i18n.translations import month_name, weekday_name
from rmcal.models import Device, Event, PlannerConfig, RemarkableConfig
from rmcal.remarkable.ssh import RemarkableSSH

# Device screen resolutions
SCREEN_SIZES = {
    Device.RM2: (1404, 1872),
    Device.PAPER_PRO: (1620, 2160),
}

SLEEP_SCREEN_PATH = "/usr/share/remarkable/suspended.png"


def update_sleep_screen(
    rm_config: RemarkableConfig,
    planner_config: PlannerConfig,
    events: list[Event],
) -> None:
    """Generate and upload a sleep screen with today's events."""
    today = date.today()
    today_events = [
        ev
        for ev in events
        if (ev.start.date() if isinstance(ev.start, datetime) else ev.start) == today
    ]

    img_path = _generate_sleep_screen(planner_config, today, today_events)

    with RemarkableSSH(rm_config) as ssh:
        ssh.upload_file(img_path, SLEEP_SCREEN_PATH)


def _generate_sleep_screen(
    config: PlannerConfig,
    today: date,
    events: list[Event],
) -> Path:
    """Generate the sleep screen PNG image."""
    width, height = SCREEN_SIZES.get(config.device, SCREEN_SIZES[Device.RM2])
    img = Image.new("L", (width, height), 255)  # Grayscale, white background
    draw = ImageDraw.Draw(img)

    # Use default font (Pillow built-in) — no external font files needed
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 48)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 32)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 26)
    except OSError:
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()

    lang = config.language
    margin = 80
    y = margin

    # Date header
    weekday = weekday_name(lang, today.weekday())
    month_str = month_name(lang, today.month)
    header = f"{weekday}, {month_str} {today.day}"
    draw.text((margin, y), header, fill=0, font=font_large)
    y += 80

    # Separator line
    draw.line([(margin, y), (width - margin, y)], fill=128, width=2)
    y += 30

    if not events:
        draw.text((margin, y), "No events today", fill=128, font=font_medium)
    else:
        all_day = [e for e in events if e.all_day]
        timed = sorted([e for e in events if not e.all_day], key=lambda e: e.start)

        # All-day events
        for ev in all_day:
            draw.text((margin, y), f"▪ {ev.display_name}", fill=0, font=font_medium)
            y += 50
            if ev.location:
                draw.text((margin + 30, y), ev.location, fill=128, font=font_small)
                y += 40

        if all_day and timed:
            y += 20

        # Timed events
        for ev in timed:
            time_str = _format_time(ev.start, config.time_format.value)
            end_str = _format_time(ev.end, config.time_format.value)
            draw.text((margin, y), f"{time_str}", fill=128, font=font_medium)
            draw.text((margin + 150, y), ev.display_name, fill=0, font=font_medium)
            y += 50
            if ev.location:
                draw.text((margin + 150, y), ev.location, fill=128, font=font_small)
                y += 40

            if y > height - margin - 100:
                remaining = len(timed) - timed.index(ev) - 1
                if remaining > 0:
                    draw.text((margin, y), f"+{remaining} more events", fill=128, font=font_small)
                break

    # Save to temp file
    tmp = Path(tempfile.mktemp(suffix=".png"))
    img.save(tmp)
    return tmp


def _format_time(dt: datetime, fmt: str) -> str:
    """Format a datetime as a time string."""
    if fmt == "12h":
        hour = dt.hour
        minute = dt.minute
        ampm = "am" if hour < 12 else "pm"
        if hour == 0:
            hour = 12
        elif hour > 12:
            hour -= 12
        if minute:
            return f"{hour}:{minute:02d}{ampm}"
        return f"{hour}{ampm}"
    return f"{dt.hour:02d}:{dt.minute:02d}"
