#!/usr/bin/env python3
"""Shared handoff-freshness primitives for adjudant.

Pure functions (stdlib only, read-only) used by BOTH the PreCompact hook
(`hooks/scripts/precompact.py`) and the `/adjudant sync` verb (`sync.py`) so
the freshness header they write stays identical and can't drift.

Freshness is computed from REAL activity (latest `.remember/today-*.md`
timestamp), not a touchable mtime, so an idle `touch` can't fake it.
"""

from __future__ import annotations

import datetime as _dt
import re
from pathlib import Path
from typing import Optional


# Traffic-light thresholds, in hours
LIGHT_GREEN_MAX_H = 2.0
LIGHT_YELLOW_MAX_H = 8.0

TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
DATE_IN_NAME_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
# `NEXT: ...` in any leading markup form: `NEXT:`, `- NEXT:`, `**NEXT:**`, `## NEXT —`.
# A plain hyphen only counts as the separator after whitespace, so compound
# prose like "Next-day retry logic…" is not misread as a NEXT directive.
NEXT_INLINE_RE = re.compile(r"^[\s>#*\-]*\**\s*NEXT\**\s*(?::|[–—]|\s[-–—])\s*(.+?)\s*$", re.IGNORECASE)
# Hook-written session markers — noise, not real activity
SESSION_MARKER_RE = re.compile(r"paused \(compaction\)|session ended", re.IGNORECASE)


def parse_next_line(text: str) -> Optional[str]:
    """Extract the handoff's single NEXT action. Priority:
      1. an inline `NEXT: ...` line (any leading markup / bold)
      2. the first non-empty line under a `## NEXT` heading
    Returns the trimmed action text, or None if there's no NEXT.
    """
    lines = text.splitlines()
    for ln in lines:
        m = NEXT_INLINE_RE.match(ln)
        if m:
            val = m.group(1).strip().strip("*").strip()
            if val:
                return val[:200]
    in_next = False
    for ln in lines:
        h = re.match(r"^#{1,6}\s+(.*\S)\s*$", ln)
        if h:
            in_next = h.group(1).strip().upper().startswith("NEXT")
            continue
        if in_next:
            s = ln.strip()
            if not s:
                continue
            s = re.sub(r"^[-*+]\s+", "", s)
            s = re.sub(r"^\[[ xX]\]\s*", "", s)
            if s:
                return s[:200]
    return None


def _last_time(text: str) -> Optional[tuple]:
    """The last HH:MM appearing in text, as (hour, minute)."""
    times = TIME_RE.findall(text)
    if not times:
        return None
    h, m = times[-1]
    return int(h), int(m)


def latest_today_activity(remember_dir: Path) -> Optional[_dt.datetime]:
    """Most recent REAL activity time across `.remember/today-*.md`.

    Date comes from the filename (`today-YYYY-MM-DD.md`) when present, else the
    file mtime; time from the last HH:MM in the file, else the file mtime.
    Returns None if there are no such files.
    """
    try:
        candidates = sorted(remember_dir.glob("today-*.md"))
    except OSError:
        return None
    best: Optional[_dt.datetime] = None
    for f in candidates:
        try:
            text = f.read_text(errors="replace")
            mtime = _dt.datetime.fromtimestamp(f.stat().st_mtime)
        except OSError:
            continue
        dm = DATE_IN_NAME_RE.search(f.name)
        year, month, day = (int(dm.group(1)), int(dm.group(2)), int(dm.group(3))) if dm else (mtime.year, mtime.month, mtime.day)
        tm = _last_time(text)
        if tm:
            try:
                dt = _dt.datetime(year, month, day, tm[0], tm[1])
            except ValueError:
                dt = mtime
        else:
            dt = mtime
        if best is None or dt > best:
            best = dt
    return best


def latest_session_activity(session_file: Path, day: _dt.datetime) -> Optional[_dt.datetime]:
    """Latest non-marker `- HH:MM · …` time in the vault session note for `day`.

    Hook tombstones (paused/ended) are skipped — they aren't real work.
    """
    try:
        text = session_file.read_text(errors="replace")
    except OSError:
        return None
    last = None
    for ln in text.splitlines():
        if SESSION_MARKER_RE.search(ln):
            continue
        tm = _last_time(ln)
        if tm:
            last = tm
    if last is None:
        return None
    try:
        return _dt.datetime(day.year, day.month, day.day, last[0], last[1])
    except ValueError:
        return None


def age_hours(activity: Optional[_dt.datetime], now: _dt.datetime) -> Optional[float]:
    if activity is None:
        return None
    return max((now - activity).total_seconds() / 3600.0, 0.0)


def traffic_light(hours: Optional[float]) -> str:
    if hours is None:
        return "⚪"  # white circle — age unknown
    if hours < LIGHT_GREEN_MAX_H:
        return "\U0001f7e2"  # green
    if hours < LIGHT_YELLOW_MAX_H:
        return "\U0001f7e1"  # yellow
    return "\U0001f534"  # red


def fmt_age(hours: Optional[float]) -> str:
    if hours is None:
        return "unknown"
    if hours < 1:
        return f"{int(round(hours * 60))}m"
    if hours < 48:
        return f"{int(round(hours))}h"
    return f"{int(round(hours / 24))}d"


def freshness_header(light: str, age_str: str, next_line: Optional[str], stale: bool) -> str:
    """The glanceable freshness block placed at the top of `_handoff.md`."""
    next_disp = next_line if next_line else "(not set)"
    block = f"{light} **handoff age: {age_str}** · NEXT: {next_disp}"
    if stale:
        block += (
            "\n\n\U0001f534 **STALE**: session activity is newer than this "
            "handoff. Rebuild it before trusting NEXT."
        )
    return block


def compute_freshness(
    project_dir: Path,
    source_body: str,
    source: Optional[Path],
    session_file: Path,
    now: _dt.datetime,
) -> tuple:
    """Return (light, age_str, next_line, stale) from cheap on-disk signals."""
    activity = latest_today_activity(project_dir / ".remember")
    if activity is None and source is not None:
        try:
            activity = _dt.datetime.fromtimestamp(source.stat().st_mtime)
        except OSError:
            activity = None
    hours = age_hours(activity, now)
    next_line = parse_next_line(source_body)
    sess = latest_session_activity(session_file, now)
    stale = bool(activity and sess and sess > activity)
    return traffic_light(hours), fmt_age(hours), next_line, stale
