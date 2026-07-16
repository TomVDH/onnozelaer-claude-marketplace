#!/usr/bin/env python3
"""Adjudant shelf: project lifecycle manager (verb #11).

list:    read-only status table of every project across zones, with the
         machine suggestion (active/stale axis only) beside the declared state.
preview: plan one transition; writes {vault}/.adjudant-shelf-preview/.
apply:   execute the transition (brief status + dated status-log line +
         zone folder move + vault-wide wikilink prefix rewrite +
         projects/_index.md row refresh). Backs up every modified file first.

CLI:
    python3 shelf.py list    (--project-dir PATH | --vault-dir PATH) [--stale-days N] [--today YYYY-MM-DD]
    python3 shelf.py preview (--project-dir PATH | --vault-dir PATH) --slug SLUG --to STATE [--reason TEXT]
    python3 shelf.py apply   (--project-dir PATH | --vault-dir PATH) --slug SLUG --to STATE [--reason TEXT]

--project-dir points at the code project root (breadcrumb flow); --vault-dir
names the vault directly. Machines never call apply without a prior preview.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from _cost import breadcrumb_int
from _vault_walk import (
    DEFAULT_SKIP,
    DEFAULT_STALE_DAYS,
    PROJECT_STATUS_VALUES,
    ZONE_FOR_STATUS,
    VaultUnresolvableError,
    enumerate_projects_all_zones,
    find_project_dir,
    parse_frontmatter,
    resolve_vault,
    smart_project_dir,
    suggest_status,
    zone_matches_status,
    zone_of,
)
from connect import (
    count_non_index_files,
    newest_session_date,
    upsert_projects_index_row,
)

PREVIEW_DIR = ".adjudant-shelf-preview"
BACKUP_DIR = ".adjudant-shelf-backup"
STATUS_LOG_HEADING = "## Status log"


def _resolve_vault_dir(project_dir_arg: str, vault_dir_arg: Optional[str]) -> Path:
    """Vault root from --vault-dir, the breadcrumb flow, or an upward walk."""
    if vault_dir_arg:
        v = Path(vault_dir_arg).expanduser().resolve()
        if v.is_dir():
            return v
        raise VaultUnresolvableError(f"--vault-dir not found: {v}")
    _scan_dir, hint = smart_project_dir(project_dir_arg)
    if hint:
        return hint
    arg = Path(project_dir_arg).expanduser().resolve()
    v = resolve_vault(arg)
    if v:
        return v
    raise VaultUnresolvableError(
        f"cannot resolve a vault from {project_dir_arg}; pass --vault-dir")


def run_list(vault: Path, stale_days: int, today: date) -> dict[str, Any]:
    """Read-only lifecycle table across all zones."""
    rows: list[dict[str, Any]] = []
    for slug, pdir, zone in enumerate_projects_all_zones(vault):
        fm, _ = parse_frontmatter((pdir / "brief.md").read_text(errors="replace"))
        declared = fm.fields.get("status")
        declared = declared if isinstance(declared, str) else None
        sug = suggest_status(declared, pdir, today, stale_days)
        rows.append({
            "slug": slug,
            "zone": zone,
            "zone_matches": zone_matches_status(declared, zone),
            **sug,
        })
    return {"vault": str(vault), "stale_after_days": stale_days, "projects": rows}


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shelf.py",
        description="Adjudant shelf: project lifecycle (list / preview / apply).")
    parser.add_argument("phase", choices=["list", "preview", "apply"])
    parser.add_argument("--project-dir", default=".",
                        help="Code project root, breadcrumb flow (default: cwd)")
    parser.add_argument("--vault-dir", help="Vault root (bypasses breadcrumb)")
    parser.add_argument("--slug", help="Project slug (preview/apply)")
    parser.add_argument("--to", dest="to_state", help="Target state (preview/apply)")
    parser.add_argument("--reason", help="Optional reason recorded in the status log")
    parser.add_argument("--stale-days", type=int,
                        help="Override stale_after_days (list)")
    parser.add_argument("--today", help="YYYY-MM-DD override (testing/determinism)")
    args = parser.parse_args(argv)

    try:
        vault = _resolve_vault_dir(args.project_dir, args.vault_dir)
    except VaultUnresolvableError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    today = date.fromisoformat(args.today) if args.today else date.today()

    if args.phase == "list":
        stale_days = args.stale_days or breadcrumb_int(
            Path(args.project_dir).expanduser().resolve(),
            "stale_after_days", DEFAULT_STALE_DAYS)
        print(json.dumps(run_list(vault, stale_days, today), indent=2))
        return 0

    # preview / apply: implemented in Task 8
    print("error: preview/apply not yet implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(cli_main())
