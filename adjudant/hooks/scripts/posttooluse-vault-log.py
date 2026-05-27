#!/usr/bin/env python3
"""PostToolUse hook for adjudant.

Appends an entry to today's session log when a NEW file is written under
{vault}/projects/{slug}/. Fires only on Write (not Edit/MultiEdit, which
typically modify existing files).
"""

import json
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


def main() -> int:
    project_dir = os.environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir:
        return 0

    info = read_breadcrumb(Path(project_dir))
    vault_path = info.get("vault_path", "")
    slug = info.get("slug", "")
    if not vault_path or not slug:
        return 0

    vault = Path(vault_path)
    project_root = vault / "projects" / slug

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    file_path_str = tool_input.get("file_path") or tool_input.get("path")
    if not file_path_str:
        return 0

    file_path = Path(file_path_str)
    try:
        rel = file_path.relative_to(project_root)
    except ValueError:
        return 0

    # Only log NEW files (Write tool, not Edit/MultiEdit)
    if tool_name != "Write":
        return 0

    today = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%H:%M")
    session_file = project_root / "sessions" / f"{today}.md"
    if not session_file.exists():
        return 0

    parts = rel.parts
    if not parts:
        return 0

    is_decision = parts[0] == "decisions"
    label = "Decision" if is_decision else "Added"
    link = f"[[projects/{slug}/{'/'.join(parts)}]]"
    entry = f"- {ts} · {label}: {link}\n"

    with session_file.open("a") as f:
        f.write(entry)

    return 0


if __name__ == "__main__":
    sys.exit(main())
