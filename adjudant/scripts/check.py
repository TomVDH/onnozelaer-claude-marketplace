#!/usr/bin/env python3
"""Adjudant check — quick project status snapshot.

Read-only. Reads brief.md frontmatter + folder counts + recent activity
+ handoff freshness + latest dream drift signal. Emits JSON for Claude
to render as a 3-section summary.

CLI:
    python3 check.py --project-dir PATH [--vault-dir PATH] [--out FILE]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from _cost import breadcrumb_int, cost_block, read_threshold, stat_walk
from _vault_walk import (
    DEFAULT_STALE_DAYS, parse_frontmatter, resolve_vault, smart_project_dir,
    suggest_status, zone_matches_status, zone_of, VaultUnresolvableError,
)


def _read_brief(project_dir: Path) -> dict[str, Any]:
    """Read brief.md frontmatter + first heading."""
    brief = project_dir / "brief.md"
    if not brief.is_file():
        return {"present": False}
    text = brief.read_text(errors="replace")
    fm, body = parse_frontmatter(text)
    title = None
    for line in body.split("\n"):
        line = line.strip()
        if line.startswith("# "):
            title = line[2:].strip()
            break
    return {
        "present": True,
        "title": title,
        "slug": fm.fields.get("slug"),
        "project_type": fm.fields.get("project_type"),
        "status": fm.fields.get("status"),
        "codename": fm.fields.get("codename"),
        "created": fm.fields.get("created"),
        "updated": fm.fields.get("updated"),
    }


def _folder_counts(project_dir: Path) -> dict[str, int]:
    """Count non-index .md files per common folder."""
    counts: dict[str, int] = {}
    for folder in ["decisions", "sessions", "dreams", "notes", "tasks", "references", "sources", "releases"]:
        d = project_dir / folder
        if not d.is_dir():
            continue
        counts[folder] = sum(
            1 for f in d.iterdir()
            if f.is_file() and f.suffix == ".md" and f.name != "_index.md"
        )
    return counts


def _most_recent_dated(folder: Path, *, pattern: re.Pattern = re.compile(r"^(\d{4}-\d{2}-\d{2})")) -> Optional[str]:
    """Return the most recent YYYY-MM-DD prefix among .md files in folder."""
    if not folder.is_dir():
        return None
    dates = []
    for f in folder.iterdir():
        if not f.is_file() or f.suffix != ".md":
            continue
        m = pattern.match(f.stem)
        if m:
            dates.append(m.group(1))
    return max(dates) if dates else None


def _handoff_info(project_dir: Path) -> dict[str, Any]:
    """Read _handoff.md frontmatter for `updated:`."""
    handoff = project_dir / "_handoff.md"
    if not handoff.is_file():
        return {"present": False}
    text = handoff.read_text(errors="replace")
    fm, _ = parse_frontmatter(text)
    updated = fm.fields.get("updated")
    info: dict[str, Any] = {"present": True, "updated": updated}
    if updated:
        try:
            # Accept YYYY-MM-DD or full ISO. `updated:` is written with local
            # dates (sync/hooks use datetime.now()), so bare dates and naive
            # timestamps are interpreted as LOCAL time — not UTC midnight,
            # which skewed staleness by the UTC offset (even negative).
            if re.match(r"^\d{4}-\d{2}-\d{2}$", str(updated)):
                dt = datetime.fromisoformat(str(updated) + "T00:00:00")
            else:
                dt = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
            if dt.tzinfo is not None:
                dt = dt.astimezone().replace(tzinfo=None)  # aware → local naive
            stale_hours = (datetime.now() - dt).total_seconds() / 3600.0
            info["stale_hours"] = round(stale_hours, 1)
        except (ValueError, TypeError):
            info["stale_hours"] = None
    return info


_DRIFT_HEADER_RE = re.compile(r"(\d+)\s+(?:distinct\s+)?drift\s+items?", re.IGNORECASE)


def _latest_dream_signal(project_dir: Path) -> dict[str, Any]:
    """Find the most recent dream report and try to parse drift_items from it."""
    dreams = project_dir / "dreams"
    if not dreams.is_dir():
        return {"present": False}
    # Dream reports are written as {YYYY-MM-DD}-dream.md (reference/dream.md);
    # bare {YYYY-MM-DD}.md accepted for hand-authored reports.
    candidates = sorted(
        (f for f in dreams.iterdir() if f.is_file() and re.match(r"^\d{4}-\d{2}-\d{2}(-dream)?\.md$", f.name)),
        reverse=True,
    )
    if not candidates:
        return {"present": False}
    latest = candidates[0]
    info: dict[str, Any] = {"present": True, "file": latest.name, "date": latest.name[:10]}
    try:
        text = latest.read_text(errors="replace")
        m = _DRIFT_HEADER_RE.search(text)
        if m:
            info["drift_items"] = int(m.group(1))
    except OSError:
        pass
    return info


def run_check(project_dir: Path, code_root: Optional[Path] = None,
              today: Optional[date] = None) -> dict[str, Any]:
    brief = _read_brief(project_dir)
    counts = _folder_counts(project_dir)
    recent = {
        "last_session": _most_recent_dated(project_dir / "sessions"),
        "last_decision": _most_recent_dated(project_dir / "decisions"),
        "last_dream": _most_recent_dated(project_dir / "dreams"),
    }
    handoff = _handoff_info(project_dir)
    drift_signal = _latest_dream_signal(project_dir)
    stale_days = breadcrumb_int(code_root, "stale_after_days", DEFAULT_STALE_DAYS)
    sug = suggest_status(
        brief.get("status") if brief.get("present") else None,
        project_dir, today or date.today(), stale_days)
    zone = zone_of(project_dir)
    status = {**sug, "zone": zone,
              "zone_matches": zone_matches_status(brief.get("status"), zone)}
    return {
        "project": brief,
        "counts": counts,
        "recent": recent,
        "handoff": handoff,
        "drift_signal": drift_signal,
        "status": status,
    }


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check.py",
        description="Adjudant check — quick status snapshot (read-only).",
    )
    parser.add_argument("--project-dir", default=".", help="Project root (default: cwd)")
    parser.add_argument("--vault-dir", help="Vault root (currently informational only)")
    parser.add_argument("--out", help="Write JSON to FILE instead of stdout")
    parser.add_argument("--estimate-only", action="store_true",
                        help="Print only the cost block (stat-only walk) and exit")
    args = parser.parse_args(argv)

    try:
        project_dir, _vault_hint = smart_project_dir(args.project_dir)
    except VaultUnresolvableError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    if not project_dir.is_dir():
        # Breadcrumb resolved to a vault project that doesn't exist yet
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

    code_root = Path(args.project_dir).expanduser().resolve()
    files, n_bytes = stat_walk(project_dir)
    cost = cost_block(files, n_bytes, read_threshold(code_root))
    if args.estimate_only:
        print(json.dumps({"cost": cost}, indent=2))
        return 0

    report = run_check(project_dir, code_root=code_root)
    report["cost"] = cost

    payload = json.dumps(report, indent=2, default=str)
    if args.out:
        Path(args.out).expanduser().write_text(payload + "\n")
        print(f"[check] wrote {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
