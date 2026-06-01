#!/usr/bin/env python3
"""PreCompact hook for adjudant.

MECHANICAL ONLY — no model calls. Must finish well inside the 5s hook budget.
Two lanes, both cheap on-disk reads:

  1. Append an enriched pause tombstone to today's vault session log:
       `- HH:MM · paused (compaction) — next: <NEXT line>`
  2. Mirror `.remember/remember.md` (or `now.md`) → vault `_handoff.md`, with a
     freshness header derived from on-disk signals:
       <traffic light> handoff age: <age> · NEXT: <next or "(not set)">
       (+ a STALE warning when session activity is newer than the handoff)

SessionEnd reuses this with `--sync-only` (no pause marker).

Design notes:
  - Freshness is computed from REAL activity (latest `.remember/today-*.md`
    timestamp), not `remember.md` mtime — so it can't be faked by an idle touch.
  - There are NO model calls here. Anything needing judgment (e.g. a smart
    handoff rewrite) belongs in a human-run verb, not this 5s hook.
  - All vault I/O fails closed: an offline/unavailable iCloud vault must never
    crash the compaction.
"""

import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional


# Traffic-light thresholds, in hours
LIGHT_GREEN_MAX_H = 2.0
LIGHT_YELLOW_MAX_H = 8.0

TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
DATE_IN_NAME_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
# `NEXT: ...` in any leading markup form: `NEXT:`, `- NEXT:`, `**NEXT:**`, `## NEXT —`
NEXT_INLINE_RE = re.compile(r"^[\s>#*\-]*\**\s*NEXT\**\s*[:\-–—]\s*(.+?)\s*$", re.IGNORECASE)
# Hook-written session markers — noise, not real activity
SESSION_MARKER_RE = re.compile(r"paused \(compaction\)|session ended", re.IGNORECASE)


def read_breadcrumb(project_dir: Path) -> dict:
    """Read `.claude/adjudant` breadcrumb (`key: value` per line, YAML-ish).

    Format written by connect.py — uses `:` separator. Old `=` format
    (pre-v0.4.0) also tolerated for transition.
    """
    breadcrumb = project_dir / ".claude" / "adjudant"
    if not breadcrumb.exists():
        return {}
    info = {}
    for line in breadcrumb.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sep = ":" if ":" in line else ("=" if "=" in line else None)
        if not sep:
            continue
        k, v = line.split(sep, 1)
        info[k.strip()] = v.strip()
    return info


def find_remember_source(project_dir: Path) -> Optional[Path]:
    """Locate the best `.remember/` file to mirror.

    Priority:
      1. `.remember/remember.md` (canonical per sync runbook)
      2. `.remember/now.md` (newer convention on some machines)
    """
    canonical = project_dir / ".remember" / "remember.md"
    if canonical.is_file():
        return canonical
    now_file = project_dir / ".remember" / "now.md"
    if now_file.is_file():
        return now_file
    return None


# ============================================================
# Freshness primitives (pure — no I/O except where noted)
# ============================================================


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


def latest_today_activity(remember_dir: Path) -> Optional[datetime]:
    """Most recent REAL activity time across `.remember/today-*.md`.

    Date comes from the filename (`today-YYYY-MM-DD.md`) when present, else the
    file mtime; time from the last HH:MM in the file, else the file mtime.
    Returns None if there are no such files.
    """
    try:
        candidates = sorted(remember_dir.glob("today-*.md"))
    except OSError:
        return None
    best: Optional[datetime] = None
    for f in candidates:
        try:
            text = f.read_text(errors="replace")
            mtime = datetime.fromtimestamp(f.stat().st_mtime)
        except OSError:
            continue
        dm = DATE_IN_NAME_RE.search(f.name)
        year, month, day = (int(dm.group(1)), int(dm.group(2)), int(dm.group(3))) if dm else (mtime.year, mtime.month, mtime.day)
        tm = _last_time(text)
        if tm:
            try:
                dt = datetime(year, month, day, tm[0], tm[1])
            except ValueError:
                dt = mtime
        else:
            dt = mtime
        if best is None or dt > best:
            best = dt
    return best


def latest_session_activity(session_file: Path, day: datetime) -> Optional[datetime]:
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
        return datetime(day.year, day.month, day.day, last[0], last[1])
    except ValueError:
        return None


def age_hours(activity: Optional[datetime], now: datetime) -> Optional[float]:
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
            "\n\n\U0001f534 **STALE** — session activity is newer than this "
            "handoff. Rebuild it before trusting NEXT."
        )
    return block


def compute_freshness(
    project_dir: Path,
    source_body: str,
    source: Optional[Path],
    session_file: Path,
    now: datetime,
) -> tuple:
    """Return (light, age_str, next_line, stale) from cheap on-disk signals."""
    activity = latest_today_activity(project_dir / ".remember")
    if activity is None and source is not None:
        try:
            activity = datetime.fromtimestamp(source.stat().st_mtime)
        except OSError:
            activity = None
    hours = age_hours(activity, now)
    next_line = parse_next_line(source_body)
    sess = latest_session_activity(session_file, now)
    stale = bool(activity and sess and sess > activity)
    return traffic_light(hours), fmt_age(hours), next_line, stale


# ============================================================
# Actions
# ============================================================


def sync_handoff(project_dir: Path, vault: Path, slug: str, today: str, ts: str, now: datetime) -> None:
    """Mirror the remember source → `_handoff.md` with a freshness header. Fails closed."""
    source = find_remember_source(project_dir)
    if source is None:
        return
    try:
        body = source.read_text(errors="replace")
    except OSError:
        return
    source_name = source.name

    session_file = vault / "projects" / slug / "sessions" / f"{today}.md"
    light, age_str, next_line, stale = compute_freshness(project_dir, body, source, session_file, now)

    header = (
        "---\n"
        "type: handoff\n"
        f'project: "[[projects/{slug}/brief|{slug}]]"\n'
        f"updated: {today}\n"
        f"source: {source.stem}\n"
        "tags:\n"
        "  - handoff\n"
        "---\n"
    )

    content = (
        f"{header}\n"
        f"# Handoff — {slug}\n\n"
        f"{freshness_header(light, age_str, next_line, stale)}\n\n"
        f"*Mirrored from `.remember/{source_name}` on {today} {ts}.*\n\n"
        f"---\n\n"
        f"{body}\n"
    )

    try:
        handoff = vault / "projects" / slug / "_handoff.md"
        handoff.parent.mkdir(parents=True, exist_ok=True)
        handoff.write_text(content)
    except OSError:
        return


def append_pause_marker(project_dir: Path, session_file: Path, ts: str) -> None:
    """Append the enriched `paused (compaction)` tombstone. Fails closed."""
    next_line = None
    source = find_remember_source(project_dir)
    if source is not None:
        try:
            next_line = parse_next_line(source.read_text(errors="replace"))
        except OSError:
            next_line = None
    marker = f"- {ts} · paused (compaction)"
    if next_line:
        marker += f" — next: {next_line}"
    try:
        if session_file.exists():
            with session_file.open("a") as f:
                f.write(marker + "\n")
    except OSError:
        return


def main() -> int:
    project_dir_str = os.environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir_str:
        return 0

    project_dir = Path(project_dir_str)
    info = read_breadcrumb(project_dir)
    vault_path = info.get("vault_path", "")
    slug = info.get("slug", "")
    if not vault_path or not slug:
        return 0

    vault = Path(vault_path)
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    ts = now.strftime("%H:%M")

    # SessionEnd reuses this script with --sync-only: skip the pause marker
    # (the session ended; it did not pause for compaction).
    sync_only = "--sync-only" in sys.argv[1:]

    if not sync_only:
        session_file = vault / "projects" / slug / "sessions" / f"{today}.md"
        append_pause_marker(project_dir, session_file, ts)

    sync_handoff(project_dir, vault, slug, today, ts, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
