#!/usr/bin/env python3
"""Adjudant validators — fail-the-build drift defense.

Run from the plugin root (adjudant/). Exit 0 on pass, 1 on any failure.

Validators:
  1. harness-parity         — source/, .claude/, .gemini/ skill paths all resolve to skills/adjudant
  2. templates-tag-schema   — no deprecated tags (#ob/, #cabinet/) in any template
  3. claude-md-imports-agents — templates/CLAUDE.md starts with @AGENTS.md
  4. template-coverage      — every file-type in vault-standards has a matching template
  5. command-metadata-coherence — verbs in command-metadata.json match SKILL.md router
  6. plugin-version-set     — .claude-plugin/plugin.json has a non-empty version
  7. port-preview-coherence  — if preview dir exists, has all required files
  8. port-backup-integrity   — backup dirs have at least one .legacy file
  9. gitignore-includes-port-dirs — .gitignore lists port dirs if either exists
 10. version-consistency     — plugin.json / command-metadata.json / SKILL.md (+ marketplace when present) versions all match
 11. tidy-preview-coherence  — if tidy preview dir exists, has summary.md + changes.json + files/
 12. tidy-backup-integrity   — tidy backup dirs have at least one .legacy file
 13. gitignore-includes-tidy-dirs — .gitignore lists tidy dirs if either exists
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CANONICAL = ROOT / "skills" / "adjudant"
TEMPLATES = CANONICAL / "templates"
REFERENCE = CANONICAL / "reference"
HARNESS_DIRS = [
    ROOT / "source" / "skills" / "adjudant",
    ROOT / ".claude" / "skills" / "adjudant",
    ROOT / ".gemini" / "skills" / "adjudant",
]

# File types that must have a matching template (per vault-standards List A)
FILE_TYPES_REQUIRING_TEMPLATE = {
    "decision": "decision.md",
    "session": "session.md",
    "note": "note.md",
    "doc": "doc.md",
    "handoff": "handoff.md",
    "source": "source.md",
    "iteration": "iteration.md",
    "release": "release.md",
    "dream-report": "dream-report.md",
    # project has 4 variants
    "project": [
        "project-brief-coding.md",
        "project-brief-knowledge.md",
        "project-brief-plugin.md",
        "project-brief-tinkerage.md",
    ],
    # index has 2 variants
    "index": ["_index-projects.md", "_index-collection.md"],
    # vault-home is special
    "vault-home": "home.md",
}

DEPRECATED_TAG_PATTERNS = [
    re.compile(r"#ob/"),
    re.compile(r"#cabinet/"),
    re.compile(r"^\s*-\s+ob/", re.MULTILINE),
    re.compile(r"^\s*-\s+cabinet/", re.MULTILINE),
]


class Result:
    def __init__(self):
        self.failures: list[str] = []
        self.passes: list[str] = []

    def add_pass(self, name: str) -> None:
        self.passes.append(name)

    def add_fail(self, name: str, detail: str) -> None:
        self.failures.append(f"{name}: {detail}")

    def report(self) -> int:
        for name in self.passes:
            print(f"  ✓ {name}")
        for failure in self.failures:
            print(f"  ✗ {failure}")
        if self.failures:
            print(f"\nFAIL — {len(self.failures)} validator(s) failed")
            return 1
        print(f"\nPASS — {len(self.passes)} validator(s) green")
        return 0


def validate_harness_parity(r: Result) -> None:
    name = "harness-parity"
    if not CANONICAL.is_dir() or CANONICAL.is_symlink():
        r.add_fail(name, f"skills/adjudant must be a real directory (the canonical skill location)")
        return
    for h in HARNESS_DIRS:
        if not h.is_symlink():
            r.add_fail(name, f"{h.relative_to(ROOT)} is not a symlink")
            return
        try:
            resolved = h.resolve()
            if resolved != CANONICAL.resolve():
                r.add_fail(
                    name,
                    f"{h.relative_to(ROOT)} resolves to {resolved}, expected {CANONICAL.resolve()}",
                )
                return
        except OSError as e:
            r.add_fail(name, f"{h.relative_to(ROOT)}: {e}")
            return
    r.add_pass(name)


def validate_templates_tag_schema(r: Result) -> None:
    name = "templates-tag-schema"
    if not TEMPLATES.is_dir():
        r.add_fail(name, f"{TEMPLATES.relative_to(ROOT)} not found")
        return
    offenders: list[str] = []
    for f in TEMPLATES.glob("*.md"):
        text = f.read_text()
        for pat in DEPRECATED_TAG_PATTERNS:
            if pat.search(text):
                offenders.append(f"{f.relative_to(ROOT)} matches {pat.pattern}")
    if offenders:
        r.add_fail(name, "deprecated tags found: " + "; ".join(offenders))
        return
    r.add_pass(name)


def validate_claude_md_imports_agents(r: Result) -> None:
    name = "claude-md-imports-agents"
    f = TEMPLATES / "CLAUDE.md"
    if not f.exists():
        r.add_fail(name, "templates/CLAUDE.md missing")
        return
    lines = f.read_text().splitlines()
    first_nonempty = next((ln.strip() for ln in lines if ln.strip()), "")
    if first_nonempty != "@AGENTS.md":
        r.add_fail(name, f"first non-empty line is {first_nonempty!r}, expected '@AGENTS.md'")
        return
    r.add_pass(name)


def validate_template_coverage(r: Result) -> None:
    name = "template-coverage"
    missing: list[str] = []
    for file_type, template in FILE_TYPES_REQUIRING_TEMPLATE.items():
        templates = template if isinstance(template, list) else [template]
        for t in templates:
            if not (TEMPLATES / t).exists():
                missing.append(f"type {file_type!r} → {t}")
    if missing:
        r.add_fail(name, "missing templates: " + "; ".join(missing))
        return
    r.add_pass(name)


def validate_command_metadata_coherence(r: Result) -> None:
    name = "command-metadata-coherence"
    meta_file = ROOT / "adjudant" / "scripts" / "command-metadata.json"
    if not meta_file.exists():
        # Try local-relative if running inside adjudant/
        meta_file = ROOT / "scripts" / "command-metadata.json"
    skill_file = CANONICAL / "SKILL.md"
    if not meta_file.exists() or not skill_file.exists():
        r.add_fail(name, f"missing {meta_file} or {skill_file}")
        return
    try:
        meta = json.loads(meta_file.read_text())
    except json.JSONDecodeError as e:
        r.add_fail(name, f"command-metadata.json invalid: {e}")
        return
    meta_verbs = {v["name"] for v in meta.get("verbs", [])}
    skill_text = skill_file.read_text()
    # Verbs in SKILL.md router table (rough match: lines starting with `| \`verb\` |`)
    skill_verbs = set(re.findall(r"\|\s+`(\w+)`\s+\|\s+`reference/", skill_text))
    if meta_verbs != skill_verbs:
        only_meta = meta_verbs - skill_verbs
        only_skill = skill_verbs - meta_verbs
        detail = []
        if only_meta:
            detail.append(f"in metadata not SKILL.md: {only_meta}")
        if only_skill:
            detail.append(f"in SKILL.md not metadata: {only_skill}")
        r.add_fail(name, "; ".join(detail))
        return
    r.add_pass(name)


def validate_plugin_version_set(r: Result) -> None:
    name = "plugin-version-set"
    f = ROOT / ".claude-plugin" / "plugin.json"
    if not f.exists():
        r.add_fail(name, f"{f.relative_to(ROOT)} missing")
        return
    try:
        data = json.loads(f.read_text())
    except json.JSONDecodeError as e:
        r.add_fail(name, f"plugin.json invalid: {e}")
        return
    version = data.get("version", "")
    if not version:
        r.add_fail(name, "version field empty or missing")
        return
    r.add_pass(name)


PORT_PREVIEW_REQUIRED = ["AGENTS.md.proposed", "CLAUDE.md.proposed", "breadcrumb.proposed", "vault-changes.txt", "summary.md"]


def validate_port_preview_coherence(r: Result) -> None:
    name = "port-preview-coherence"
    preview = ROOT / ".adjudant-port-preview"
    if not preview.is_dir():
        r.add_pass(name)
        return
    missing = [f for f in PORT_PREVIEW_REQUIRED if not (preview / f).is_file()]
    if missing:
        r.add_fail(name, f"preview dir missing required files: {missing}")
        return
    r.add_pass(name)


def validate_port_backup_integrity(r: Result) -> None:
    name = "port-backup-integrity"
    backup_root = ROOT / ".adjudant-port-backup"
    if not backup_root.is_dir():
        r.add_pass(name)
        return
    for subdir in backup_root.iterdir():
        if subdir.is_dir():
            entries = list(subdir.iterdir())
            if not entries:
                continue  # empty backup dir (e.g. fresh X-flavor port) is fine
            has_legacy = any(f.name.endswith(".legacy") for f in entries)
            if not has_legacy:
                r.add_fail(name, f"backup dir {subdir.name} has non-.legacy files but no .legacy: {[f.name for f in entries]}")
                return
    r.add_pass(name)


def validate_gitignore_includes_port_dirs(r: Result) -> None:
    name = "gitignore-includes-port-dirs"
    preview = ROOT / ".adjudant-port-preview"
    backup = ROOT / ".adjudant-port-backup"
    if not preview.is_dir() and not backup.is_dir():
        r.add_pass(name)
        return
    gi = ROOT / ".gitignore"
    if not gi.is_file():
        r.add_fail(name, "port directories exist but .gitignore is missing")
        return
    text = gi.read_text()
    required = []
    if preview.is_dir():
        required.append(".adjudant-port-preview/")
    if backup.is_dir():
        required.append(".adjudant-port-backup/")
    missing = [e for e in required if e not in text]
    if missing:
        r.add_fail(name, f".gitignore missing entries: {missing}")
        return
    r.add_pass(name)


TIDY_PREVIEW_REQUIRED = ["summary.md", "changes.json"]


def validate_tidy_preview_coherence(r: Result) -> None:
    name = "tidy-preview-coherence"
    preview = ROOT / ".adjudant-tidy-preview"
    if not preview.is_dir():
        r.add_pass(name)
        return
    missing = [f for f in TIDY_PREVIEW_REQUIRED if not (preview / f).is_file()]
    if missing:
        r.add_fail(name, f"tidy preview dir missing required files: {missing}")
        return
    if not (preview / "files").is_dir():
        r.add_fail(name, "tidy preview dir missing files/ subdir")
        return
    r.add_pass(name)


def validate_tidy_backup_integrity(r: Result) -> None:
    name = "tidy-backup-integrity"
    backup_root = ROOT / ".adjudant-tidy-backup"
    if not backup_root.is_dir():
        r.add_pass(name)
        return
    for subdir in backup_root.iterdir():
        if subdir.is_dir():
            # walk recursively because tidy backup mirrors project structure
            files = [p for p in subdir.rglob("*") if p.is_file()]
            if not files:
                # Empty backup dirs are not failure (could be the initial mkdir before any copy)
                continue
            has_legacy = any(p.name.endswith(".legacy") for p in files)
            if not has_legacy:
                r.add_fail(name, f"tidy backup dir {subdir.name} has files but no .legacy: {[p.name for p in files]}")
                return
    r.add_pass(name)


def validate_gitignore_includes_tidy_dirs(r: Result) -> None:
    name = "gitignore-includes-tidy-dirs"
    preview = ROOT / ".adjudant-tidy-preview"
    backup = ROOT / ".adjudant-tidy-backup"
    if not preview.is_dir() and not backup.is_dir():
        r.add_pass(name)
        return
    gi = ROOT / ".gitignore"
    if not gi.is_file():
        # Try parent (when running from inside adjudant/)
        gi = ROOT.parent / ".gitignore"
    if not gi.is_file():
        r.add_fail(name, "tidy directories exist but .gitignore is missing")
        return
    text = gi.read_text()
    required = []
    if preview.is_dir():
        required.append(".adjudant-tidy-preview/")
    if backup.is_dir():
        required.append(".adjudant-tidy-backup/")
    missing = [e for e in required if e not in text]
    if missing:
        r.add_fail(name, f".gitignore missing entries: {missing}")
        return
    r.add_pass(name)


def validate_version_consistency(r: Result) -> None:
    name = "version-consistency"
    versions: dict[str, str] = {}
    # In-plugin sources (always present)
    try:
        versions["plugin.json"] = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text()).get("version", "")
        versions["command-metadata.json"] = json.loads((ROOT / "scripts" / "command-metadata.json").read_text()).get("version", "")
    except (json.JSONDecodeError, OSError) as e:
        r.add_fail(name, f"could not read a version source: {e}")
        return
    skill_file = CANONICAL / "SKILL.md"
    m = re.search(r"^version:\s*(\S+)", skill_file.read_text(), re.M) if skill_file.exists() else None
    versions["SKILL.md"] = m.group(1) if m else ""
    # marketplace.json lives in the parent repo — only check when present (standalone installs won't have it)
    mk = ROOT.parent / ".claude-plugin" / "marketplace.json"
    if mk.is_file():
        try:
            entry = next((p for p in json.loads(mk.read_text()).get("plugins", []) if p.get("name") == "adjudant"), None)
            if entry is not None:
                versions["marketplace.json"] = entry.get("version", "")
        except json.JSONDecodeError:
            pass
    empties = [k for k, v in versions.items() if not v]
    if empties:
        r.add_fail(name, f"missing/empty version in: {empties}")
        return
    if len(set(versions.values())) != 1:
        r.add_fail(name, f"version mismatch: {versions}")
        return
    r.add_pass(name)


def main() -> int:
    print(f"adjudant validators — running from {ROOT}")
    r = Result()
    validate_harness_parity(r)
    validate_templates_tag_schema(r)
    validate_claude_md_imports_agents(r)
    validate_template_coverage(r)
    validate_command_metadata_coherence(r)
    validate_plugin_version_set(r)
    validate_port_preview_coherence(r)
    validate_port_backup_integrity(r)
    validate_gitignore_includes_port_dirs(r)
    validate_version_consistency(r)
    validate_tidy_preview_coherence(r)
    validate_tidy_backup_integrity(r)
    validate_gitignore_includes_tidy_dirs(r)
    return r.report()


if __name__ == "__main__":
    sys.exit(main())
