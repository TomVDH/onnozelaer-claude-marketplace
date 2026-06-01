#!/usr/bin/env python3
"""PreCompact hook for adjudant.

MECHANICAL ONLY — no model calls. Must finish well inside the 5s hook budget.
Two lanes, both cheap on-disk reads:

  1. Append an enriched pause tombstone to today's vault session log:
       `- HH:MM · paused (compaction) — next: <NEXT line>`
  2. Mirror `.remember/remember.md` (or `now.md`) → vault `_handoff.md`, with a
     freshness header (traffic light · age · NEXT · stale flag).

SessionEnd reuses this with `--sync-only` (no pause marker).

Freshness logic is shared with `/adjudant sync` via `scripts/_handoff_freshness.py`
(single source of truth). The import is best-effort: if it ever fails, the hook
still does its mechanical work — it just omits the freshness header. All vault
I/O fails closed: an offline iCloud vault must never crash the compaction.
"""

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Shared freshness primitives live in <plugin>/scripts/. Bootstrap that onto the
# path (fixed plugin layout) and import; degrade gracefully if unavailable.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from _handoff_freshness import compute_freshness, freshness_header, parse_next_line
    _FRESHNESS = True
except Exception:  # pragma: no cover - defensive: hook must never crash on import
    _FRESHNESS = False

    def parse_next_line(_text):  # type: ignore
        return None

    def compute_freshness(*_a, **_k):  # type: ignore
        return ("", "", None, False)

    def freshness_header(*_a, **_k):  # type: ignore
        return ""


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
    fresh = freshness_header(light, age_str, next_line, stale)
    fresh_block = f"{fresh}\n\n" if fresh else ""

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
        f"{fresh_block}"
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
