#!/usr/bin/env python3
"""Adjudant vault-walk primitives.

Shared module for dream/check/tidy. Stdlib-only. Read-only.

Public API:
    parse_frontmatter(text) -> (Frontmatter, body)
    extract_wikilinks(body) -> list[Wikilink]
    extract_inline_tags(body) -> list[str]
    extract_markdown_md_links(body) -> list[(text, path, line)]
    walk_project(root) -> Iterator[VaultFile]
    build_vault_index(vault_root) -> set[str]
    resolve_wikilink(target, index) -> bool
    parse_breadcrumb(project_root) -> Optional[dict]
    resolve_vault(project_root, env_vault=None) -> Optional[Path]
    is_bucket_d_tag(tag, project_slug=None) -> bool

Schema constants (single source of truth, imported by dream + tidy):
    BUCKET_A_TYPES, BUCKET_B_MIGRATIONS, BUCKET_D_TAG_PREFIXES,
    BUCKET_D_TAG_EXACT, VAGUE_TOPICAL_TAGS, CREW_NAMES,
    PROJECT_TYPE_DEFAULT_FOLDERS, AUTO_CREATED_FOLDERS, INDEX_EXEMPT_FOLDERS

CLI smoke-test mode (read-only, the module never writes):
    python3 _vault_walk.py --project-dir PATH [--vault-dir PATH] [--json]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterator, Optional


# ============================================================
# Frontmatter parsing — minimal YAML (stdlib only, mirrors port.py regex approach)
# ============================================================


@dataclass
class Frontmatter:
    raw: str = ""
    fields: dict[str, Any] = field(default_factory=dict)
    parse_error: Optional[str] = None
    has_block: bool = False


def parse_frontmatter(text: str) -> tuple[Frontmatter, str]:
    """Extract YAML frontmatter from a markdown file. Returns (fm, body).

    Recognizes the standard `---\\n...\\n---\\n` opening.
    """
    fm = Frontmatter()
    if not text.startswith("---"):
        return fm, text

    lines = text.split("\n")
    if not lines or lines[0].rstrip() != "---":
        return fm, text

    close_idx: Optional[int] = None
    for i in range(1, len(lines)):
        if lines[i].rstrip() == "---":
            close_idx = i
            break

    if close_idx is None:
        fm.parse_error = "frontmatter block missing closing ---"
        return fm, text

    fm.has_block = True
    fm.raw = "\n".join(lines[1:close_idx])
    body = "\n".join(lines[close_idx + 1:])
    fm.fields = _parse_minimal_yaml(fm.raw)
    return fm, body


_KEY_RE = re.compile(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$")
_LIST_ITEM_RE = re.compile(r"^(\s+)-\s+(.*)$")


def _parse_minimal_yaml(text: str) -> dict[str, Any]:
    """Tiny YAML parser. Handles:
      - key: value
      - key: "quoted" or 'quoted'
      - key:
          - list_item
          - list_item
      - # comments
      - null/~/empty values (preserved as None to allow drift detection)

    Does NOT handle: nested mappings, multi-line scalars, flow style,
    anchors. Unknown shapes are recorded as raw string.
    """
    result: dict[str, Any] = {}
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            i += 1
            continue
        m = _KEY_RE.match(line)
        if not m:
            i += 1
            continue
        key = m.group(1)
        rest = m.group(2).strip()

        # Strip trailing comments OUTSIDE quotes (cheap heuristic)
        if rest and not (rest.startswith('"') or rest.startswith("'")):
            rest = re.sub(r"\s+#.*$", "", rest)

        if rest == "":
            # Possible list block
            items: list[str] = []
            j = i + 1
            while j < len(lines):
                ln = lines[j]
                if ln.strip() == "" or ln.strip().startswith("#"):
                    j += 1
                    continue
                m2 = _LIST_ITEM_RE.match(ln)
                if m2:
                    items.append(_strip_quotes(m2.group(2).strip()))
                    j += 1
                else:
                    break
            if items:
                result[key] = items
                i = j
                continue
            else:
                result[key] = None
                i += 1
                continue

        # Single-line value
        # Preserve literal "null"/"~" as the string so drift detection can flag it,
        # rather than coercing to Python None.
        result[key] = _strip_quotes(rest)
        i += 1
    return result


def _strip_quotes(s: str) -> str:
    if len(s) >= 2 and ((s[0] == '"' and s[-1] == '"') or (s[0] == "'" and s[-1] == "'")):
        return s[1:-1]
    return s


# ============================================================
# Wikilinks & inline tags
# ============================================================


@dataclass
class Wikilink:
    target: str
    alias: Optional[str]
    heading: Optional[str]
    line: int
    raw: str


WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")
ALIAS_SEP_RE = re.compile(r"\\?\|")  # | or \|, both alias separators
TAG_RE = re.compile(r"(?:^|[\s,()])#([A-Za-z][\w/-]*)")
MD_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+\.md(?:#[^)\s]*)?)\)")
URL_RE = re.compile(r"https?://\S+")


def extract_wikilinks(body: str) -> list[Wikilink]:
    """All [[...]] in body, skipping code blocks (fenced + 4-space indented)."""
    links: list[Wikilink] = []
    in_fenced = False
    for lineno, line in enumerate(body.split("\n"), start=1):
        ls = line.lstrip()
        if ls.startswith("```"):
            in_fenced = not in_fenced
            continue
        if in_fenced:
            continue
        # 4-space indented code block heuristic: skip when line begins with 4+ spaces
        # but only if it's not a list continuation. Safe minimum: skip if starts with
        # exactly 4+ spaces AND doesn't have a `-`/`*`/`+` as the first non-space char.
        if line.startswith("    ") and line.lstrip()[:1] not in ("-", "*", "+", "|", "["):
            continue
        for m in WIKILINK_RE.finditer(line):
            inner = m.group(1)
            parts = ALIAS_SEP_RE.split(inner, maxsplit=1)
            target_full = parts[0].strip()
            alias = parts[1].strip() if len(parts) > 1 else None
            heading: Optional[str] = None
            target = target_full
            if "#" in target:
                target, heading = target.split("#", 1)
                target = target.strip()
                heading = heading.strip()
            links.append(Wikilink(
                target=target,
                alias=alias,
                heading=heading,
                line=lineno,
                raw=m.group(0),
            ))
    return links


def extract_inline_tags(body: str) -> list[str]:
    """Inline #tags in body, skipping code blocks and URLs."""
    out: list[str] = []
    in_fenced = False
    for line in body.split("\n"):
        ls = line.lstrip()
        if ls.startswith("```"):
            in_fenced = not in_fenced
            continue
        if in_fenced:
            continue
        if line.startswith("    "):
            continue
        cleaned = URL_RE.sub("", line)
        for m in TAG_RE.finditer(cleaned):
            out.append(m.group(1))
    return out


def extract_markdown_md_links(body: str) -> list[tuple[str, str, int]]:
    """[text](path.md) occurrences (potential wikilink-form violations)."""
    out: list[tuple[str, str, int]] = []
    in_fenced = False
    for lineno, line in enumerate(body.split("\n"), start=1):
        ls = line.lstrip()
        if ls.startswith("```"):
            in_fenced = not in_fenced
            continue
        if in_fenced:
            continue
        for m in MD_LINK_RE.finditer(line):
            out.append((m.group(1), m.group(2), lineno))
    return out


# ============================================================
# VaultFile + walker
# ============================================================


@dataclass
class VaultFile:
    path: Path
    rel_path: Path
    frontmatter: Frontmatter
    body: str
    tags_frontmatter: list[str]
    tags_inline: list[str]
    wikilinks: list[Wikilink]
    markdown_md_links: list[tuple[str, str, int]]

    @property
    def tags(self) -> list[str]:
        return self.tags_frontmatter + self.tags_inline

    @property
    def file_type(self) -> Optional[str]:
        t = self.frontmatter.fields.get("type")
        return t if isinstance(t, str) else None


DEFAULT_SKIP: tuple[str, ...] = (".git", "node_modules", "__pycache__", ".obsidian", ".trash")


def walk_project(
    root: Path,
    *,
    skip: tuple[str, ...] = DEFAULT_SKIP,
    include_legacy: bool = False,
) -> Iterator[VaultFile]:
    """Yield VaultFile for every .md in root, recursively.

    By default skips .git, node_modules, etc. `_legacy/` is also skipped
    unless `include_legacy=True` is passed (legacy files often have
    intentional historical drift we don't want to flag in routine ops).
    """
    skip_set = set(skip)
    if not include_legacy:
        skip_set.add("_legacy")

    for f in sorted(root.rglob("*.md")):
        rel = f.relative_to(root)
        if any(part in skip_set for part in rel.parts):
            continue
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        fm, body = parse_frontmatter(text)
        fm_tags_raw = fm.fields.get("tags")
        fm_tags: list[str] = []
        if isinstance(fm_tags_raw, list):
            fm_tags = [str(t) for t in fm_tags_raw if t]
        elif isinstance(fm_tags_raw, str) and fm_tags_raw.strip():
            fm_tags = [fm_tags_raw.strip()]
        yield VaultFile(
            path=f,
            rel_path=rel,
            frontmatter=fm,
            body=body,
            tags_frontmatter=fm_tags,
            tags_inline=extract_inline_tags(body),
            wikilinks=extract_wikilinks(body),
            markdown_md_links=extract_markdown_md_links(body),
        )


# ============================================================
# Vault index for wikilink resolution
# ============================================================


def build_vault_index(vault_root: Path) -> set[str]:
    """All resolvable wikilink target forms across the vault.

    Includes:
      - relative path with extension
      - relative path without extension
      - bare basename (Obsidian default match if unique)
    Spans .md, .canvas, .base.
    """
    index: set[str] = set()
    for ext in ("md", "canvas", "base"):
        for f in vault_root.rglob(f"*.{ext}"):
            try:
                rel = f.relative_to(vault_root)
            except ValueError:
                continue
            s = str(rel)
            index.add(s)
            index.add(s[: -(len(ext) + 1)])  # strip `.ext`
            index.add(f.stem)
            index.add(f.name)
    return index


def resolve_wikilink(target: str, index: set[str]) -> bool:
    """True if target resolves in the vault index.

    Tries (in order): exact path, path+.md, basename, basename+.md.
    The basename fallback matches Obsidian's default resolution: `[[foo]]`
    resolves to any `foo.md` anywhere in the vault.
    """
    if not target:
        return False
    if target in index:
        return True
    if (target + ".md") in index:
        return True
    # Basename fallback (Obsidian default resolution)
    base = target.replace("\\", "/").rstrip("/").split("/")[-1]
    if base != target:
        if base in index:
            return True
        if (base + ".md") in index:
            return True
    return False


# ============================================================
# Breadcrumb + vault resolution (port.py patterns)
# ============================================================


def parse_breadcrumb(project_root: Path) -> Optional[dict]:
    """Read .claude/adjudant breadcrumb (key:value, one per line)."""
    bc = project_root / ".claude" / "adjudant"
    if not bc.is_file():
        return None
    out: dict[str, str] = {}
    for line in bc.read_text().splitlines():
        m = re.match(r"^\s*([A-Za-z_][\w-]*)\s*:\s*(.+?)\s*$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def resolve_vault(
    project_root: Path,
    env_vault: Optional[str] = None,
) -> Optional[Path]:
    """4-step resolution: env → .claude/adjudant → .claude/obsidian-bridge → walk up."""
    # 1. Env var override
    if env_vault:
        p = Path(env_vault).expanduser()
        if p.is_dir():
            return p

    # 2. adjudant breadcrumb
    bc = parse_breadcrumb(project_root)
    if bc and "vault_path" in bc:
        p = Path(bc["vault_path"]).expanduser()
        if p.is_dir():
            return p

    # 3. legacy OB breadcrumb
    ob = project_root / ".claude" / "obsidian-bridge"
    if ob.is_file():
        for line in ob.read_text().splitlines():
            m = re.match(r"^\s*vault\s*:\s*(.+?)\s*$", line)
            if m:
                p = Path(m.group(1)).expanduser()
                if p.is_dir():
                    return p

    # 4. Walk up for Home.md
    cur = project_root.resolve()
    while cur != cur.parent:
        home = cur / "Home.md"
        if home.is_file():
            try:
                text = home.read_text(errors="replace")
                if re.search(r"^type:\s*vault-home", text, re.MULTILINE):
                    return cur
            except OSError:
                pass
        cur = cur.parent
    return None


# ============================================================
# Schema constants — single source of truth (imported by dream + tidy)
# ============================================================


BUCKET_A_TYPES: frozenset[str] = frozenset({
    "decision", "session", "note", "doc", "project", "handoff",
    "index", "iteration", "release", "source", "dream-report",
})
BUCKET_A_TYPES_PLUS_HOME: frozenset[str] = BUCKET_A_TYPES | {"vault-home"}

# Bucket B — custom file types migrated from cabinet/*
BUCKET_B_MIGRATIONS: dict[str, str] = {
    "cabinet/recon": "recon-item",
    "cabinet/portal-concept": "portal-concept",
    "cabinet/preview": "preview",
    "cabinet/asset-index": "index",
    "cabinet/dev-doc": "doc",
    "cabinet/decision": "decision",
}

# Bucket D — tags to drop entirely
BUCKET_D_TAG_PREFIXES: tuple[str, ...] = ("ob/",)

VAGUE_TOPICAL_TAGS: frozenset[str] = frozenset({
    "architecture", "architecture-lockin", "architecture-source",
    "frontend", "cms", "moc", "toolbox", "scheduler",
    "campaign-request", "flow-c", "nightly", "hubspot",
    "reconciler",
})

CREW_NAMES: frozenset[str] = frozenset({
    "bostrol", "kevijntje", "henske", "jonasty",
})

# Project-type tag form is forbidden — it lives in frontmatter `project_type:`
PROJECT_TYPE_TAGS: frozenset[str] = frozenset({
    "type/coding", "type/knowledge", "type/plugin", "type/tinkerage",
})

BUCKET_D_TAG_EXACT: frozenset[str] = VAGUE_TOPICAL_TAGS | CREW_NAMES | PROJECT_TYPE_TAGS

# Other cabinet/* tags — drop unless in BUCKET_B_MIGRATIONS keys
_BUCKET_B_KEYS = frozenset(BUCKET_B_MIGRATIONS.keys())

# Per-project_type folder defaults (must align with vault-standards.md §5)
PROJECT_TYPE_DEFAULT_FOLDERS: dict[str, dict[str, list[str]]] = {
    "coding": {
        "with_index": ["decisions", "notes", "tasks", "references"],
        "no_index": ["sessions", "images"],
    },
    "plugin": {
        "with_index": ["decisions", "notes", "tasks", "references", "releases"],
        "no_index": ["sessions", "images"],
    },
    "knowledge": {
        "with_index": ["notes", "sources", "references"],
        "no_index": ["sessions"],
    },
    "tinkerage": {
        "with_index": [],
        "no_index": ["sessions"],
    },
}

AUTO_CREATED_FOLDERS: frozenset[str] = frozenset({"dreams", "canvases", "bases"})
INDEX_EXEMPT_FOLDERS: frozenset[str] = frozenset({
    "sessions", "images", "assets", "previews", "iterations", "_archive",
})


def is_bucket_d_tag(tag: str, project_slug: Optional[str] = None) -> bool:
    """Return True if tag should be dropped per Bucket D."""
    # ob/* prefix
    if any(tag.startswith(p) for p in BUCKET_D_TAG_PREFIXES):
        return True
    # cabinet/* — drop unless in Bucket B migrations
    if tag.startswith("cabinet/") and tag not in _BUCKET_B_KEYS:
        return True
    # Exact match (vague topicals, crew, project-type tags)
    if tag in BUCKET_D_TAG_EXACT:
        return True
    # Project-slug self-tag and slug/* / slug-* variants
    if project_slug:
        if tag == project_slug:
            return True
        if tag.startswith(project_slug + "/"):
            return True
        if tag.startswith(project_slug + "-"):
            return True
    return False


def is_bucket_b_migration(tag: str) -> Optional[str]:
    """If tag is a Bucket B migration source, return the target tag; else None."""
    return BUCKET_B_MIGRATIONS.get(tag)


# ============================================================
# CLI smoke-test (read-only — the module never writes)
# ============================================================


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="_vault_walk.py",
        description="Vault-walk primitives — read-only smoke test.",
    )
    parser.add_argument("--project-dir", required=True, help="Project root to walk")
    parser.add_argument("--vault-dir", help="Vault root for wikilink resolution")
    parser.add_argument("--include-legacy", action="store_true", help="Walk into _legacy/")
    parser.add_argument("--json", action="store_true", help="Emit JSON instead of human format")
    args = parser.parse_args(argv)

    project_dir = Path(args.project_dir).expanduser().resolve()
    vault_dir = Path(args.vault_dir).expanduser().resolve() if args.vault_dir else None

    if not project_dir.is_dir():
        print(f"error: --project-dir not found: {project_dir}", file=sys.stderr)
        return 1

    files = list(walk_project(project_dir, include_legacy=args.include_legacy))
    parse_errors = [
        {"file": str(f.rel_path), "error": f.frontmatter.parse_error}
        for f in files if f.frontmatter.parse_error
    ]
    no_fm = [str(f.rel_path) for f in files if not f.frontmatter.has_block]

    tag_counter: Counter[str] = Counter()
    for f in files:
        for t in f.tags:
            tag_counter[t] += 1

    type_counter: Counter[str] = Counter()
    for f in files:
        t = f.file_type
        if t:
            type_counter[t] += 1

    total_wl = sum(len(f.wikilinks) for f in files)
    broken_wl = 0
    md_link_violations = sum(len(f.markdown_md_links) for f in files)
    if vault_dir and vault_dir.is_dir():
        idx = build_vault_index(vault_dir)
        for f in files:
            for wl in f.wikilinks:
                if not resolve_wikilink(wl.target, idx):
                    broken_wl += 1

    output: dict[str, Any] = {
        "project_dir": str(project_dir),
        "vault_dir": str(vault_dir) if vault_dir else None,
        "files_scanned": len(files),
        "files_no_frontmatter": no_fm[:10],
        "parse_errors": parse_errors[:10],
        "tag_inventory_top30": tag_counter.most_common(30),
        "type_inventory": type_counter.most_common(),
        "wikilinks_total": total_wl,
        "wikilinks_broken": broken_wl,
        "markdown_md_link_violations": md_link_violations,
    }

    if args.json:
        print(json.dumps(output, indent=2, default=str))
    else:
        print(f"project:        {project_dir}")
        print(f"vault:          {vault_dir or '(not specified)'}")
        print(f"files:          {len(files)}")
        print(f"no frontmatter: {len(no_fm)}")
        print(f"parse errors:   {len(parse_errors)}")
        print(f"wikilinks:      {total_wl} total, {broken_wl} broken")
        print(f"md-link violations: {md_link_violations}")
        if type_counter:
            print(f"\ntype inventory:")
            for t, n in type_counter.most_common():
                marker = " " if t in BUCKET_A_TYPES_PLUS_HOME else "*"
                print(f"  {marker} {n:4}  {t}")
        if tag_counter:
            print(f"\ntop 30 tags:")
            for tag, n in tag_counter.most_common(30):
                print(f"  {n:4}  {tag}")
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
