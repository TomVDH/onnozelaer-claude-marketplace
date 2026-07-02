#!/usr/bin/env python3
"""Adjudant sitrep — ELI5 orientation briefing.

Read-only. Answers the "I've been away, catch me up" question: what were we
doing, what's done, where the vault is, and where best to start. Emits JSON for
Claude to render as four plain-language lines (see reference/sitrep.md).

Distinct from check.py: `check` reports schema/compliance state; `sitrep` reports
momentum and the single next action. It reuses check's snapshot primitives and the
shared handoff-freshness layer rather than re-deriving anything.

CLI:
    python3 sitrep.py --project-dir PATH [--vault-dir PATH] [--out FILE]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import sys
from pathlib import Path
from typing import Any, Optional

from _handoff_freshness import (
    age_hours,
    fmt_age,
    latest_today_activity,
    parse_next_line,
    traffic_light,
)
from _vault_walk import smart_project_dir
from check import (
    _folder_counts,
    _latest_dream_signal,
    _most_recent_dated,
    _read_brief,
)


def _next_step(project_dir: Path) -> Optional[str]:
    """The single NEXT action from _handoff.md, if any (read-only)."""
    handoff = project_dir / "_handoff.md"
    if not handoff.is_file():
        return None
    try:
        return parse_next_line(handoff.read_text(errors="replace"))
    except OSError:
        return None


def run_sitrep(
    project_dir: Path,
    vault_path: Optional[Path] = None,
    now: Optional[_dt.datetime] = None,
) -> dict[str, Any]:
    """Compose a read-only orientation snapshot. `now` is injectable for tests."""
    now = now or _dt.datetime.now()

    brief = _read_brief(project_dir)
    counts = _folder_counts(project_dir)

    activity = latest_today_activity(project_dir / ".remember")
    hours = age_hours(activity, now)
    freshness = {
        "light": traffic_light(hours),
        "age": fmt_age(hours),
        "last_activity": activity.isoformat(timespec="minutes") if activity else None,
    }

    whats_done = {
        "last_session": _most_recent_dated(project_dir / "sessions"),
        "last_decision": _most_recent_dated(project_dir / "decisions"),
        "counts": counts,
    }

    return {
        "project": brief,
        "vault_path": str(vault_path) if vault_path else None,
        "purpose": brief.get("title") if brief.get("present") else None,
        "freshness": freshness,
        "were_doing": freshness["last_activity"],
        "whats_done": whats_done,
        "next_step": _next_step(project_dir),
        "open_signals": _latest_dream_signal(project_dir),
    }


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sitrep.py",
        description="Adjudant sitrep — ELI5 orientation briefing (read-only).",
    )
    parser.add_argument("--project-dir", default=".", help="Project root (default: cwd)")
    parser.add_argument("--vault-dir", help="Vault root (informational; auto-resolved otherwise)")
    parser.add_argument("--out", help="Write JSON to FILE instead of stdout")
    args = parser.parse_args(argv)

    project_dir, vault_hint = smart_project_dir(args.project_dir)
    if not project_dir.is_dir():
        if (Path(args.project_dir).expanduser() / ".claude" / "adjudant").is_file():
            print(
                f"error: breadcrumb at {args.project_dir}/.claude/adjudant points to "
                f"vault project {project_dir} which doesn't exist. Run /adjudant connect "
                f"to create it.",
                file=sys.stderr,
            )
        else:
            print(f"error: project-dir not found: {project_dir}", file=sys.stderr)
        return 1

    vault_path = Path(args.vault_dir).expanduser() if args.vault_dir else vault_hint
    report = run_sitrep(project_dir, vault_path)

    payload = json.dumps(report, indent=2, default=str)
    if args.out:
        Path(args.out).expanduser().write_text(payload + "\n")
        print(f"[sitrep] wrote {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
