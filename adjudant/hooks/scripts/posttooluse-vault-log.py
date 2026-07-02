#!/usr/bin/env python3
"""PostToolUse hook for adjudant.

Two mechanical jobs on every new Write under {vault}/projects/{slug}/:

  1. Append a `- HH:MM · Decision|Added: [[link]]` entry to today's session log.
  2. Stamp `source_session: <uuid>` into the new file's frontmatter so the
     conversation that authored it is one hop away — not a grep through
     transcripts. Session notes / _handoff / _index files are excluded.

Fires only on Write (not Edit/MultiEdit, which typically modify existing files).
Both stamping passes are best-effort and fail-closed.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Shared stamping primitives live in <plugin>/scripts/. Mirror precompact's
# bootstrap pattern; degrade gracefully so a missing helper never crashes the hook.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from _session_stamp import stamp_source_session
    _STAMP = True
except Exception:  # pragma: no cover - defensive
    _STAMP = False

    def stamp_source_session(*_a, **_k):  # type: ignore
        return False

try:
    from _vault_walk import _candidate_vault_paths
except Exception:  # pragma: no cover - defensive
    def _candidate_vault_paths(_name):  # type: ignore
        return []


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

    vault = Path(vault_path).expanduser()
    if not vault.is_dir():
        # Cross-machine fallback: vault_name against standard locations
        vault = next(
            (c for c in _candidate_vault_paths(info.get("vault_name", "")) if c.is_dir()),
            None,
        ) if info.get("vault_name") else None
        if vault is None:
            return 0  # stale breadcrumb — fail closed, never log to a phantom path
    project_root = vault / "projects" / slug

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input", {})
    file_path_str = tool_input.get("file_path") or tool_input.get("path")
    session_id = (payload.get("session_id") or "").strip()
    if not file_path_str:
        return 0

    file_path = Path(file_path_str)
    try:
        rel = file_path.relative_to(project_root)
    except ValueError:
        return 0

    # Only act on NEW files (Write tool, not Edit/MultiEdit)
    if tool_name != "Write":
        return 0

    today = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%H:%M")
    session_file = project_root / "sessions" / f"{today}.md"

    parts = rel.parts
    if not parts:
        return 0

    # --- Job 1: append a session-log entry (if a session note exists for today) ---
    if session_file.exists():
        is_decision = parts[0] == "decisions"
        label = "Decision" if is_decision else "Added"
        link = f"[[projects/{slug}/{'/'.join(parts)}]]"
        try:
            with session_file.open("a") as f:
                f.write(f"- {ts} · {label}: {link}\n")
        except OSError:
            pass  # log-write failure must not block job 2

    # --- Job 2: stamp source_session on the new file. The stamping primitive
    # itself decides what's eligible (skips session notes, _handoff, _index,
    # files without frontmatter, files already stamped). Best-effort. ---
    if session_id and _STAMP:
        try:
            stamp_source_session(file_path, session_id)
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
