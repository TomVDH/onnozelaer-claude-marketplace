#!/usr/bin/env python3
"""Adjudant port verb — migrate legacy projects to adjudant compliance.

Run from the project root (or via `python3 adjudant/scripts/port.py`).
Detects project flavor (X/Y/Z) or port phase (preview/applied) and
dispatches accordingly. See docs/superpowers/specs/2026-05-26-adjudant-port-verb-design.md.
"""

from pathlib import Path


_TEMPLATE_SENTINEL_LINES = (
    "# {Project Name}",
    "`{slug}` · type: `{coding|knowledge|plugin|tinkerage}` · vault: [[projects/{slug}/brief|{slug}]]",
)


def _looks_like_template(path: Path) -> bool:
    """Return True if the file's first 5 non-empty lines match the AGENTS.md
    template sentinels (placeholders intact). Used to distinguish a project
    that has just been scaffolded by `connect` from one that's been authored."""
    if not path.is_file():
        return False
    lines = [ln.strip() for ln in path.read_text().splitlines() if ln.strip()][:5]
    return all(sentinel in lines for sentinel in _TEMPLATE_SENTINEL_LINES)


def detect_flavor(project_root: Path) -> str:
    """Detect the legacy flavor or port phase of a project.

    Returns: "X", "Y", "Z", "preview", or "applied".
    Order matters — preview/applied are checked before legacy markers.
    """
    if (project_root / ".adjudant-port-preview").is_dir():
        return "preview"

    if (project_root / ".adjudant-port-backup").is_dir() and _is_adjudant_compliant(project_root):
        return "applied"

    if (project_root / ".claude" / "obsidian-bridge").is_file():
        return "Y"

    agents = project_root / "AGENTS.md"
    claude = project_root / "CLAUDE.md"
    if agents.is_file() and not _looks_like_template(agents):
        return "Z"
    if claude.is_file() and claude.read_text().strip() and \
            next((ln.strip() for ln in claude.read_text().splitlines() if ln.strip()), "") != "@AGENTS.md":
        return "Z"

    return "X"


def _is_adjudant_compliant(project_root: Path) -> bool:
    """Project is compliant if all four hold:
    1. breadcrumb at .claude/adjudant exists
    2. AGENTS.md exists
    3. CLAUDE.md exists and starts with `@AGENTS.md`
    4. no .claude/obsidian-bridge breadcrumb lingering
    """
    if not (project_root / ".claude" / "adjudant").is_file():
        return False
    if not (project_root / "AGENTS.md").is_file():
        return False
    claude_md = project_root / "CLAUDE.md"
    if not claude_md.is_file():
        return False
    first_line = next(
        (ln.strip() for ln in claude_md.read_text().splitlines() if ln.strip()),
        "",
    )
    if first_line != "@AGENTS.md":
        return False
    if (project_root / ".claude" / "obsidian-bridge").exists():
        return False
    return True
