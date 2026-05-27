#!/usr/bin/env python3
"""PreCompact hook for adjudant.

1. Append a pause marker to today's session log.
2. Mirror .remember/remember.md to vault _handoff.md (sync action).
"""

import os
import sys
from datetime import datetime
from pathlib import Path


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


def find_remember_source(project_dir: Path) -> Path:
    """Locate the best `.remember/` file to mirror.

    Priority:
      1. `.remember/remember.md` (canonical per sync runbook)
      2. `.remember/now.md` (newer convention on some machines)

    Returns the chosen Path or None.
    """
    canonical = project_dir / ".remember" / "remember.md"
    if canonical.is_file():
        return canonical
    now_file = project_dir / ".remember" / "now.md"
    if now_file.is_file():
        return now_file
    return None


def sync_handoff(project_dir: Path, vault: Path, slug: str, today: str, ts: str) -> None:
    source = find_remember_source(project_dir)
    if source is None:
        return

    handoff = vault / "projects" / slug / "_handoff.md"
    body = source.read_text()
    source_name = source.name  # 'remember.md' or 'now.md'

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

    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        f"{header}\n"
        f"# Handoff — {slug}\n\n"
        f"*Mirrored from `.remember/{source_name}` on {today} {ts}.*\n\n"
        f"---\n\n"
        f"{body}\n"
    )


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
    today = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%H:%M")

    # SessionEnd reuses this script for the handoff sync only. With --sync-only
    # we skip the pause marker — the session ended, it did not pause for compaction.
    sync_only = "--sync-only" in sys.argv[1:]

    # 1. Append pause marker (PreCompact only)
    if not sync_only:
        session_file = vault / "projects" / slug / "sessions" / f"{today}.md"
        if session_file.exists():
            with session_file.open("a") as f:
                f.write(f"- {ts} · paused (compaction)\n")

    # 2. Sync handoff
    sync_handoff(project_dir, vault, slug, today, ts)

    return 0


if __name__ == "__main__":
    sys.exit(main())
