#!/usr/bin/env python3
"""Adjudant sync — push current project state to the vault.

Three locked features (per reference/sync.md):
  1. Brief refresh — update brief.md frontmatter `updated:` field
  2. Handoff mirror — copy `.remember/remember.md` (or `.remember/now.md`
     fallback) body into `_handoff.md`, preserving handoff frontmatter
  3. Project-row refresh — update `{vault}/projects/_index.md` row counts
     for this project

CLI:
    python3 sync.py --project-dir PATH

`--project-dir` is the CODE project root (with `.claude/adjudant` breadcrumb).
Auto-resolves the vault project location via the breadcrumb.

Idempotent. Re-running produces identical effects given identical inputs.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from _vault_walk import (
    parse_breadcrumb,
    parse_frontmatter,
    resolve_project_from_cwd,
)
from connect import (
    count_non_index_files,
    newest_session_date,
    upsert_projects_index_row,
)


# ============================================================
# Step 1: brief refresh
# ============================================================


def refresh_brief_updated(brief_path: Path, today: str) -> str:
    """Update brief.md frontmatter `updated:` field. Returns 'bumped' / 'unchanged' / 'missing'."""
    if not brief_path.is_file():
        return "missing"
    text = brief_path.read_text(errors="replace")
    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return "no-frontmatter"
    close_idx = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            close_idx = i
            break
    if close_idx is None:
        return "unparseable-frontmatter"
    changed = False
    for i in range(1, close_idx):
        m = re.match(r"^(updated\s*:\s*).*$", lines[i])
        if m:
            new_line = f"{m.group(1)}{today}"
            if lines[i] != new_line:
                lines[i] = new_line
                changed = True
            break
    if changed:
        brief_path.write_text("\n".join(lines))
        return "bumped"
    return "unchanged"


# ============================================================
# Step 2: handoff mirror
# ============================================================


HANDOFF_FRONTMATTER_TEMPLATE = (
    "---\n"
    "type: handoff\n"
    "project: \"[[projects/{slug}/brief|{slug}]]\"\n"
    "updated: {today}\n"
    "tags:\n"
    "  - handoff\n"
    "---\n\n"
)


def find_remember_source(project_root: Path) -> Optional[Path]:
    """Return the best `.remember/` file to mirror into handoff body.

    Priority:
      1. `.remember/remember.md` (canonical per sync runbook)
      2. `.remember/now.md` (newer convention used on this machine)

    Returns None if neither exists.
    """
    canonical = project_root / ".remember" / "remember.md"
    if canonical.is_file():
        return canonical
    now_file = project_root / ".remember" / "now.md"
    if now_file.is_file():
        return now_file
    return None


def mirror_handoff(
    project_root: Path,
    handoff_path: Path,
    slug: str,
    today: str,
) -> str:
    """Copy remember/now body into handoff body (frontmatter regenerated).

    Returns: 'mirrored' / 'no-source' / 'unchanged'.
    """
    source = find_remember_source(project_root)
    if not source:
        return "no-source"

    body = source.read_text(errors="replace").rstrip() + "\n"
    new_content = HANDOFF_FRONTMATTER_TEMPLATE.format(slug=slug, today=today) + body

    if handoff_path.is_file():
        # Preserve existing frontmatter if user-customised, only update body + updated:
        existing = handoff_path.read_text(errors="replace")
        fm, _ = parse_frontmatter(existing)
        if fm.has_block:
            # Surgically update the `updated:` field and replace body
            lines = existing.split("\n")
            close_idx = next((i for i in range(1, len(lines)) if lines[i].rstrip() == "---"), None)
            if close_idx is not None:
                for i in range(1, close_idx):
                    m = re.match(r"^(updated\s*:\s*).*$", lines[i])
                    if m:
                        lines[i] = f"{m.group(1)}{today}"
                        break
                new_content = "\n".join(lines[: close_idx + 1]) + "\n\n" + body
        if new_content.rstrip() == existing.rstrip():
            return "unchanged"

    handoff_path.write_text(new_content)
    return "mirrored"


# ============================================================
# Step 3: project-row refresh (delegates to connect.upsert_projects_index_row)
# ============================================================


def refresh_projects_index_row(vault_path: Path, slug: str) -> str:
    proj_dir = vault_path / "projects" / slug
    if not proj_dir.is_dir():
        return "project-missing"
    brief_path = proj_dir / "brief.md"
    if not brief_path.is_file():
        return "brief-missing"
    fm, _ = parse_frontmatter(brief_path.read_text(errors="replace"))
    project_type = fm.fields.get("project_type") or "coding"
    status = fm.fields.get("status") or "active"
    decisions_n = count_non_index_files(proj_dir / "decisions")
    sessions_n = count_non_index_files(proj_dir / "sessions")
    last_session = newest_session_date(proj_dir / "sessions")
    return upsert_projects_index_row(
        vault_path, slug, project_type, status, decisions_n, sessions_n, last_session
    )


# ============================================================
# Top-level run
# ============================================================


def run_sync(project_root: Path) -> dict[str, Any]:
    ctx = resolve_project_from_cwd(project_root)
    if ctx is None:
        raise RuntimeError(
            f"no .claude/adjudant breadcrumb at {project_root} (run /adjudant connect first)"
        )
    if not ctx.vault_project_dir.is_dir():
        raise RuntimeError(
            f"vault project dir missing: {ctx.vault_project_dir} (run /adjudant connect)"
        )

    today = datetime.now().strftime("%Y-%m-%d")
    summary: dict[str, Any] = {
        "project_root": str(project_root),
        "vault_path": str(ctx.vault_path),
        "slug": ctx.slug,
        "today": today,
        "steps": {},
    }

    brief_path = ctx.vault_project_dir / "brief.md"
    handoff_path = ctx.vault_project_dir / "_handoff.md"

    summary["steps"]["brief_refresh"] = refresh_brief_updated(brief_path, today)
    summary["steps"]["handoff_mirror"] = mirror_handoff(
        project_root, handoff_path, ctx.slug, today
    )
    summary["steps"]["projects_index_row"] = refresh_projects_index_row(ctx.vault_path, ctx.slug)

    return summary


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sync.py",
        description="Adjudant sync — push project state to the vault.",
    )
    parser.add_argument("--project-dir", default=".",
                        help="Code project root with .claude/adjudant breadcrumb (default: cwd)")
    args = parser.parse_args(argv)

    project_root = Path(args.project_dir).expanduser().resolve()
    if not project_root.is_dir():
        print(f"error: project-dir not found: {project_root}", file=sys.stderr)
        return 1

    try:
        summary = run_sync(project_root)
    except RuntimeError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    print(f"[sync] {summary['slug']}: "
          f"brief={summary['steps']['brief_refresh']}, "
          f"handoff={summary['steps']['handoff_mirror']}, "
          f"row={summary['steps']['projects_index_row']}",
          file=sys.stderr)

    print(json.dumps(summary, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
