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
    breadcrumb = project_dir / ".claude" / "adjudant"
    if not breadcrumb.exists():
        return {}
    info = {}
    for line in breadcrumb.read_text().splitlines():
        if "=" in line:
            k, v = line.split("=", 1)
            info[k.strip()] = v.strip()
    return info


def sync_handoff(project_dir: Path, vault: Path, slug: str, today: str, ts: str) -> None:
    remember = project_dir / ".remember" / "remember.md"
    if not remember.exists():
        return

    handoff = vault / "projects" / slug / "_handoff.md"
    body = remember.read_text()

    header = (
        "---\n"
        "type: handoff\n"
        f'project: "[[projects/{slug}/brief|{slug}]]"\n'
        f"updated: {today}\n"
        "source: remember\n"
        "tags:\n"
        "  - handoff\n"
        "---\n"
    )

    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        f"{header}\n"
        f"# Handoff — {slug}\n\n"
        f"*Mirrored from `.remember/remember.md` on {today} {ts}.*\n\n"
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

    # 1. Append pause marker
    session_file = vault / "projects" / slug / "sessions" / f"{today}.md"
    if session_file.exists():
        with session_file.open("a") as f:
            f.write(f"- {ts} · paused (compaction)\n")

    # 2. Sync handoff
    sync_handoff(project_dir, vault, slug, today, ts)

    return 0


if __name__ == "__main__":
    sys.exit(main())
