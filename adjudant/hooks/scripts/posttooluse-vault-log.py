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

# Shared primitives live in <plugin>/scripts/. Mirror precompact's bootstrap
# pattern, one guard per module: a broken or mid-sync module must only degrade
# ITS OWN capability, never shadow a sibling import that succeeded.
try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
except Exception:  # pragma: no cover - defensive
    pass

try:
    from _session_stamp import stamp_source_session
    _STAMP = True
except Exception:  # pragma: no cover - degrade: log without stamping
    _STAMP = False

    def stamp_source_session(*_a, **_k):  # type: ignore
        return False

try:
    from _vault_walk import resolve_vault
    _RESOLVER = True
except Exception:  # pragma: no cover - degrade: breadcrumb vault_path only
    _RESOLVER = False

    def resolve_vault(_project_root, _env_vault=None):  # type: ignore
        return None


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
    slug = info.get("slug", "")
    if not slug:
        return 0

    # Same 5-step resolve_vault chain as the verbs and the other hooks, so
    # every hook writes to the SAME vault. Degraded mode (broken _vault_walk):
    # honor a locally-valid vault_path only.
    vault = resolve_vault(Path(project_dir))
    if vault is None and not _RESOLVER:
        # Degraded mode keeps the shell hooks' precedence: OB_VAULT first,
        # then a locally-valid vault_path (same-vault invariant).
        ob = os.environ.get("OB_VAULT", "")
        p = Path(ob).expanduser() if ob else None
        if p is None or not p.is_dir():
            vault_path = info.get("vault_path", "")
            p = Path(vault_path).expanduser() if vault_path else None
        vault = p if (p is not None and p.is_dir()) else None
    if vault is None or not vault.is_dir():
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
        # Resolve both sides so a symlinked or differently-normalized Write
        # path (~/Obsidian/V → iCloud, `..` segments) still matches the vault.
        rel = file_path.resolve().relative_to(project_root.resolve())
    except (ValueError, OSError):
        return 0

    # Only act on NEW files (Write tool, not Edit/MultiEdit)
    if tool_name != "Write":
        return 0

    now = datetime.now()  # single clock read: date and time can't straddle midnight
    today = now.strftime("%Y-%m-%d")
    ts = now.strftime("%H:%M")
    # Today's note — or the latest existing one when the session straddles
    # midnight (the new day's note appears at the next SessionStart).
    session_file = project_root / "sessions" / f"{today}.md"
    if not session_file.exists():
        try:
            # digit classes, not ?: a stray abcd-ef-gh.md must never win
            candidates = sorted((project_root / "sessions").glob(
                "[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md"))
        except OSError:
            candidates = []
        if candidates:
            session_file = candidates[-1]

    parts = rel.parts
    if not parts:
        return 0

    # --- Job 1: append a session-log entry (if a session note exists) ---
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
    # A PostToolUse hook must never surface as a tool failure: whatever goes
    # wrong (future logic error, exotic I/O failure), exit 0.
    try:
        sys.exit(main())
    except Exception:  # pragma: no cover - last-resort guard
        sys.exit(0)
