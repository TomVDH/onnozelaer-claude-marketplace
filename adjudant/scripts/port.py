#!/usr/bin/env python3
"""Adjudant port verb — migrate legacy projects to adjudant compliance.

Run from the project root (or via `python3 adjudant/scripts/port.py`).
Detects project flavor (X/Y/Z) or port phase (preview/applied) and
dispatches accordingly. See docs/superpowers/specs/2026-05-26-adjudant-port-verb-design.md.
"""

import os
import re
from pathlib import Path
from typing import Optional


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


def resolve_vault_path(project_root: Path) -> Optional[Path]:
    """Resolve the vault path for this project per spec resolution order:
    1. OB_VAULT env var
    2. .claude/adjudant breadcrumb (vault_path: field)
    3. .claude/obsidian-bridge breadcrumb (vault: field)
    4. Walk parent dirs for Home.md with `type: vault-home` frontmatter
    5. Return None (caller must prompt)
    """
    env = os.environ.get("OB_VAULT")
    if env:
        return Path(env)

    adj_breadcrumb = project_root / ".claude" / "adjudant"
    if adj_breadcrumb.is_file():
        path = _parse_breadcrumb_field(adj_breadcrumb, "vault_path")
        if path:
            return Path(path)

    ob_breadcrumb = project_root / ".claude" / "obsidian-bridge"
    if ob_breadcrumb.is_file():
        path = _parse_breadcrumb_field(ob_breadcrumb, "vault")
        if path:
            return Path(path)

    return _walk_up_for_vault_home(project_root)


def _parse_breadcrumb_field(path: Path, field: str) -> Optional[str]:
    """Parse a simple `key: value` breadcrumb file. Returns the value of `field` or None."""
    for line in path.read_text().splitlines():
        m = re.match(rf"^\s*{re.escape(field)}\s*:\s*(.+?)\s*$", line)
        if m:
            return m.group(1)
    return None


def _walk_up_for_vault_home(start: Path) -> Optional[Path]:
    """Walk parent dirs looking for Home.md with `type: vault-home` in frontmatter."""
    current = start
    seen = set()
    while True:
        resolved = current.resolve()
        if resolved in seen or resolved == resolved.parent:
            break
        seen.add(resolved)
        home = current / "Home.md"
        if home.is_file():
            text = home.read_text()
            fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
            if fm_match and re.search(r"^\s*type\s*:\s*vault-home\s*$", fm_match.group(1), re.MULTILINE):
                return current
        current = current.parent
    return None


def parse_markdown_sections(text: str) -> dict[str, str]:
    """Parse a markdown file into a dict of {lowercased-heading-text: body}.

    Captures ## and ### headings. Heading text is normalized: lowercased,
    leading/trailing whitespace stripped. Body is everything until the next
    heading at the same or higher level.

    The # (h1) title is ignored. Content before any ## heading is discarded.
    """
    sections: dict[str, str] = {}
    current_key: Optional[str] = None
    current_body: list[str] = []

    for line in text.splitlines():
        heading_match = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if heading_match:
            if current_key is not None:
                sections[current_key] = "\n".join(current_body).strip()
            current_key = heading_match.group(2).strip().lower()
            current_body = []
        elif current_key is not None:
            current_body.append(line)

    if current_key is not None:
        sections[current_key] = "\n".join(current_body).strip()

    return sections


OB_SECTION_MAPPING = {
    "working tree":          ("where_things_live_extra_rows", None),
    "stack":                 ("conventions",                  None),
    "stack and tools":       ("conventions",                  None),
    "vault rules":           (None,                           "DROPPED — now in vault-standards.md (single source of truth)"),
    "vault layout":          (None,                           "DROPPED — now in vault-standards.md (single source of truth)"),
    "claude instructions":   ("claude_md_body",               None),
    "claude-specific":       ("claude_md_body",               None),
    "conventions":           ("conventions",                  None),
    "project rules":         ("conventions",                  None),
    "what this is":          ("what_this_is",                 None),
    "purpose":               ("what_this_is",                 None),
    "overview":              ("what_this_is",                 None),
}


def map_ob_sections(ob_sections: dict[str, str]) -> dict[str, str]:
    """Apply the OB → adjudant mapping. Input keys are lowercased headings.

    Returns a dict with these slots:
      - what_this_is: prose for the "What this is" section
      - conventions: prose for the "Conventions" section
      - where_things_live_extra_rows: rows to append to the standard table
      - claude_md_body: content moved to CLAUDE.md (under @AGENTS.md)
      - from_legacy: unmatched headings, appended to AGENTS.md at end
      - decisions: log of all mapping decisions (for summary.md)
    """
    result = {
        "what_this_is": "",
        "conventions": "",
        "where_things_live_extra_rows": "",
        "claude_md_body": "",
        "from_legacy": "",
        "decisions": "",
    }

    for heading, body in ob_sections.items():
        slot, dropped_reason = OB_SECTION_MAPPING.get(heading, (None, None))

        if dropped_reason:
            result["decisions"] += f'- OB "## {heading}" → {dropped_reason}\n'
        elif slot is None:
            # Unmatched
            result["from_legacy"] += f"### {heading}\n\n{body}\n\n"
            result["decisions"] += f'- OB "## {heading}" → "## From legacy AGENTS.md" section at end (no template match)\n'
        else:
            if result[slot]:
                result[slot] += "\n\n"
            result[slot] += body
            result["decisions"] += f'- OB "## {heading}" → adjudant "{slot}" (deterministic OB mapping)\n'

    return result


def render_agents_md(
    project_name: str,
    slug: str,
    project_type: str,
    what_this_is: str,
    conventions: str,
    where_things_live_extra_rows: str,
    from_legacy: str,
) -> str:
    """Render a complete AGENTS.md from inputs. Matches templates/AGENTS.md shape."""
    extra = f"\n{where_things_live_extra_rows}" if where_things_live_extra_rows else ""
    body = f"""# {project_name}

`{slug}` · type: `{project_type}` · vault: [[projects/{slug}/brief|{slug}]]

> One-line purpose of this project.

## What this is

{what_this_is or "{Two to four sentences. Why this project exists, who it's for, what success looks like.}"}

## Where things live

| | |
|---|---|
| Working tree | (this folder) |
| Canonical context | [[projects/{slug}/brief]] |
| Decisions | [[projects/{slug}/decisions]] |
| Sessions | [[projects/{slug}/sessions]] |
| Handoff | [[projects/{slug}/_handoff]] |{extra}

## Conventions

{conventions or "{Project-specific guardrails. Add as they're decided. Examples: stack choices, naming rules, forbidden commands, deploy paths.}"}

## Vault is canonical

When asked "is X documented?" or "do we know Y?", check the vault first — repos document code, the vault documents decisions and context. Use the `adjudant` skill to read/write vault files.

## Claude-specific overrides

Live in `CLAUDE.md` next to this file. CLAUDE.md `@`-imports this file.
"""
    if from_legacy.strip():
        body += f"\n## From legacy AGENTS.md\n\n{from_legacy.rstrip()}\n"
    return body


def render_claude_md(claude_specific_body: str) -> str:
    """Render CLAUDE.md from the template + optional claude-specific body."""
    extra = f"\n{claude_specific_body.rstrip()}\n" if claude_specific_body.strip() else ""
    return f"""@AGENTS.md

# Claude-specific overrides

Project context, conventions, vault references, and working-files index live in `AGENTS.md` (imported above). Any agent — Claude, Gemini, Codex, Cursor — reads from there.

This file is for **Claude Code-specific overrides only**:
- Slash-command behavior hints
- Plugin/skill invocation preferences
- Claude-only tool guidance (e.g., specific `Bash` allowlists)

**If you're about to add generic project context here, move it to `AGENTS.md` instead.**
{extra}"""


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
