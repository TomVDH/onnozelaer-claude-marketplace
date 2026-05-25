#!/usr/bin/env python3
"""Adjudant validators — fail-the-build drift defense.

Run from the plugin root (adjudant/). Exit 0 on pass, 1 on any failure.

Validators:
  1. harness-parity         — .claude/skills/adjudant and .gemini/skills/adjudant resolve to source/
  2. templates-tag-schema   — no deprecated tags (#ob/, #cabinet/) in any template
  3. claude-md-imports-agents — templates/CLAUDE.md starts with @AGENTS.md
  4. template-coverage      — every file-type in vault-standards has a matching template
  5. command-metadata-coherence — verbs in command-metadata.json match SKILL.md router
  6. plugin-version-set     — .claude-plugin/plugin.json has a non-empty version
"""

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "source" / "skills" / "adjudant"
TEMPLATES = SOURCE / "templates"
REFERENCE = SOURCE / "reference"
HARNESS_DIRS = [ROOT / ".claude" / "skills" / "adjudant", ROOT / ".gemini" / "skills" / "adjudant"]

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
    for h in HARNESS_DIRS:
        if not h.is_symlink():
            r.add_fail(name, f"{h.relative_to(ROOT)} is not a symlink")
            return
        try:
            resolved = h.resolve()
            if resolved != SOURCE.resolve():
                r.add_fail(
                    name,
                    f"{h.relative_to(ROOT)} resolves to {resolved}, expected {SOURCE.resolve()}",
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
    skill_file = SOURCE / "SKILL.md"
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


def main() -> int:
    print(f"adjudant validators — running from {ROOT}")
    r = Result()
    validate_harness_parity(r)
    validate_templates_tag_schema(r)
    validate_claude_md_imports_agents(r)
    validate_template_coverage(r)
    validate_command_metadata_coherence(r)
    validate_plugin_version_set(r)
    return r.report()


if __name__ == "__main__":
    sys.exit(main())
