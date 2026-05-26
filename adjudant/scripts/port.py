#!/usr/bin/env python3
"""Adjudant port verb — migrate legacy projects to adjudant compliance.

Run from the project root (or via `python3 adjudant/scripts/port.py`).
Detects project flavor (X/Y/Z) or port phase (preview/applied) and
dispatches accordingly. See docs/superpowers/specs/2026-05-26-adjudant-port-verb-design.md.
"""

import os
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


def create_backup(project_root: Path, files_to_backup: list[Path]) -> Path:
    """Create .adjudant-port-backup/{ISO-8601-basic-Z-timestamp}/ and copy
    each existing file into it with `.legacy` suffix. Returns the backup dir."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_dir = project_root / ".adjudant-port-backup" / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)

    for rel in files_to_backup:
        src = project_root / rel
        if not src.is_file():
            continue
        dst_name = src.name + ".legacy"
        shutil.copy2(src, backup_dir / dst_name)

    return backup_dir


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


def render_breadcrumb(vault_path: Path, vault_name: str, slug: str, mode: str) -> str:
    """Render the .claude/adjudant breadcrumb content. Plain `key: value` lines."""
    return (
        f"vault_path: {vault_path}\n"
        f"vault_name: {vault_name}\n"
        f"slug: {slug}\n"
        f"mode: {mode}\n"
    )


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


def generate_preview_y(
    project_root: Path,
    vault_path: Path,
    project_type: str,
    project_name: str,
) -> None:
    """For Flavor Y: parse legacy files, run OB mapping, write preview dir."""
    preview_dir = project_root / ".adjudant-port-preview"
    preview_dir.mkdir(exist_ok=True)

    slug = _parse_breadcrumb_field(project_root / ".claude" / "obsidian-bridge", "slug") or project_root.name
    vault_name = vault_path.name

    agents_legacy = project_root / "AGENTS.md"
    claude_legacy = project_root / "CLAUDE.md"

    ob_sections = parse_markdown_sections(agents_legacy.read_text()) if agents_legacy.is_file() else {}
    claude_sections = parse_markdown_sections(claude_legacy.read_text()) if claude_legacy.is_file() else {}

    mapped = map_ob_sections(ob_sections)

    claude_body = mapped["claude_md_body"]
    for heading, body in claude_sections.items():
        if claude_body:
            claude_body += "\n\n"
        claude_body += f"## {heading.title()}\n\n{body}"
        mapped["decisions"] += f'- Legacy CLAUDE.md "## {heading}" → Kept in CLAUDE.md (legacy claude content)\n'

    agents_out = render_agents_md(
        project_name=project_name,
        slug=slug,
        project_type=project_type,
        what_this_is=mapped["what_this_is"],
        conventions=mapped["conventions"],
        where_things_live_extra_rows=mapped["where_things_live_extra_rows"],
        from_legacy=mapped["from_legacy"],
    )
    claude_out = render_claude_md(claude_specific_body=claude_body)
    breadcrumb_out = render_breadcrumb(vault_path=vault_path, vault_name=vault_name, slug=slug, mode="project")

    (preview_dir / "AGENTS.md.proposed").write_text(agents_out)
    (preview_dir / "CLAUDE.md.proposed").write_text(claude_out)
    (preview_dir / "breadcrumb.proposed").write_text(breadcrumb_out)

    vault_changes = _y_vault_changes(vault_path, slug, project_type)
    (preview_dir / "vault-changes.txt").write_text("\n".join(vault_changes) + "\n")

    summary = _render_summary(
        flavor="Y",
        vault_path=vault_path,
        slug=slug,
        decisions=mapped["decisions"],
        vault_changes=vault_changes,
    )
    (preview_dir / "summary.md").write_text(summary)


def _y_vault_changes(vault_path: Path, slug: str, project_type: str) -> list[str]:
    """Return list of vault change operations as strings, one per line.
    Format: "ACTION:path1[:path2]" where ACTION is RENAME, CREATE, ARCHIVE, REPLACE, REGEN, UPDATE-ROW."""
    proj = vault_path / "projects" / slug
    changes = []
    refs = proj / "refs"
    if refs.is_dir():
        changes.append(f"RENAME:{refs}:{proj / 'references'}")
    iterations = proj / "iterations"
    if iterations.is_dir():
        changes.append(f"ARCHIVE:{iterations}:{vault_path / 'legacy' / 'iterations' / slug}")
    for sub in ("tasks", "images"):
        if not (proj / sub).is_dir():
            changes.append(f"CREATE:{proj / sub}")
    if (proj / "brief.md").is_file():
        changes.append(f"REPLACE:{proj / 'brief.md'}")
    changes.append(f"REGEN:{proj / '_index.md'}")
    changes.append(f"UPDATE-ROW:{vault_path / 'projects' / '_index.md'}:{slug}")
    return changes


def _capitalise_heading_in_decisions(decisions: str) -> str:
    """Capitalise the first letter of heading names inside '## <name>' patterns in decisions log.
    Leaves the rest of each word lowercase (e.g. 'vault rules' → 'Vault rules')."""
    return re.sub(
        r'"## ([^"]+)"',
        lambda m: f'"## {m.group(1)[0].upper() + m.group(1)[1:]}"',
        decisions,
    )


def _render_summary(flavor: str, vault_path: Path, slug: str, decisions: str, vault_changes: list[str]) -> str:
    """Render the summary.md content for the preview dir."""
    from datetime import datetime
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    vault_changes_table = "\n".join(f"| `{change}` |" for change in vault_changes)
    decisions_display = _capitalise_heading_in_decisions(decisions)
    return f"""# Port preview summary

Generated: {timestamp} · Flavor: {flavor} ({"obsidian-bridge legacy" if flavor == "Y" else "see flavor"})
Vault: {vault_path}/projects/{slug}

## File changes (project side)
| File | Action |
|---|---|
| AGENTS.md | Replace (merged) |
| CLAUDE.md | Replace (merged) |
{"| .claude/obsidian-bridge | Remove (migrated to .claude/adjudant) |" if flavor == "Y" else ""}
| .claude/adjudant | Create |
| .gitignore | Append (.adjudant-port-*) |

## Vault changes
| Operation |
|---|
{vault_changes_table}

## Merge decisions
{decisions_display or "(none)"}

To apply: re-run `/adjudant:adjudant port`.
To discard: delete `.adjudant-port-preview/` and start over.
"""


def generate_preview_x(
    project_root: Path,
    vault_path: Path,
    slug: str,
    project_type: str,
    project_name: str,
) -> None:
    """For Flavor X: fresh-scaffold using templates only. No legacy parsing."""
    preview_dir = project_root / ".adjudant-port-preview"
    preview_dir.mkdir(exist_ok=True)
    vault_name = vault_path.name

    agents_out = render_agents_md(
        project_name=project_name,
        slug=slug,
        project_type=project_type,
        what_this_is="",
        conventions="",
        where_things_live_extra_rows="",
        from_legacy="",
    )
    claude_out = render_claude_md(claude_specific_body="")
    breadcrumb_out = render_breadcrumb(vault_path=vault_path, vault_name=vault_name, slug=slug, mode="project")

    (preview_dir / "AGENTS.md.proposed").write_text(agents_out)
    (preview_dir / "CLAUDE.md.proposed").write_text(claude_out)
    (preview_dir / "breadcrumb.proposed").write_text(breadcrumb_out)

    proj = vault_path / "projects" / slug
    subfolders = _project_type_subfolders(project_type)
    vault_changes = [f"CREATE:{proj / sub}" for sub in subfolders]
    vault_changes.append(f"CREATE:{proj / 'brief.md'}")
    vault_changes.append(f"REGEN:{proj / '_index.md'}")
    vault_changes.append(f"UPDATE-ROW:{vault_path / 'projects' / '_index.md'}:{slug}")
    (preview_dir / "vault-changes.txt").write_text("\n".join(vault_changes) + "\n")

    summary = _render_summary(
        flavor="X",
        vault_path=vault_path,
        slug=slug,
        decisions="(no legacy content — fresh scaffold)\n",
        vault_changes=vault_changes,
    )
    (preview_dir / "summary.md").write_text(summary)


def _project_type_subfolders(project_type: str) -> list[str]:
    """Per spec, vault-standards.md per-type subfolder defaults."""
    base = {
        "coding":    ["decisions", "notes", "tasks", "references", "sessions", "images"],
        "plugin":    ["decisions", "notes", "tasks", "references", "sessions", "images", "releases"],
        "knowledge": ["notes", "sources", "references", "sessions"],
        "tinkerage": ["sessions"],
    }
    return base.get(project_type, ["sessions"])


def generate_preview_z_scaffold(
    project_root: Path,
    vault_path: Path,
    slug: str,
    project_type: str,
    project_name: str,
) -> None:
    """For Flavor Z: scaffold the preview dir but leave AGENTS.md.proposed
    and CLAUDE.md.proposed as TODO placeholders. Claude fills them in via
    the AI classifier instructions in reference/port.md.

    Also copies legacy AGENTS.md and CLAUDE.md into the preview dir as
    legacy-AGENTS.md / legacy-CLAUDE.md for Claude's reference.
    """
    preview_dir = project_root / ".adjudant-port-preview"
    preview_dir.mkdir(exist_ok=True)
    vault_name = vault_path.name

    for name in ("AGENTS.md", "CLAUDE.md"):
        src = project_root / name
        if src.is_file():
            (preview_dir / f"legacy-{name}").write_text(src.read_text())

    placeholder = "TODO: Claude AI classifier fills this. See reference/port.md for instructions.\n"
    (preview_dir / "AGENTS.md.proposed").write_text(placeholder)
    (preview_dir / "CLAUDE.md.proposed").write_text(placeholder)

    breadcrumb_out = render_breadcrumb(vault_path=vault_path, vault_name=vault_name, slug=slug, mode="project")
    (preview_dir / "breadcrumb.proposed").write_text(breadcrumb_out)

    proj = vault_path / "projects" / slug
    subfolders = _project_type_subfolders(project_type)
    vault_changes = [f"CREATE:{proj / sub}" for sub in subfolders]
    if not (proj / "brief.md").is_file():
        vault_changes.append(f"CREATE:{proj / 'brief.md'}")
    vault_changes.append(f"REGEN:{proj / '_index.md'}")
    vault_changes.append(f"UPDATE-ROW:{vault_path / 'projects' / '_index.md'}:{slug}")
    (preview_dir / "vault-changes.txt").write_text("\n".join(vault_changes) + "\n")

    summary = _render_summary(
        flavor="Z",
        vault_path=vault_path,
        slug=slug,
        decisions="(AI classifier decisions appended by Claude during preview phase)\n",
        vault_changes=vault_changes,
    )
    (preview_dir / "summary.md").write_text(summary)


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
