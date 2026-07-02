"""Tests for adjudant/scripts/validate.py — the drift-defense validators.

Each test builds a minimal temp plugin tree and monkeypatches validate.py's
module-level path anchors (ROOT / CANONICAL / TEMPLATES / REFERENCE / HARNESS_DIRS)
to point at it, then drives one validator and inspects the Result.
"""

import json
import tempfile
import unittest
from pathlib import Path

import validate
from validate import Result


def _build(root: Path, *, version: str = "1.0.0", verbs=("connect", "check")) -> Path:
    """Lay out a minimal, valid adjudant plugin tree under `root`. Returns the
    plugin dir (what ROOT should be patched to). marketplace.json lives at
    root/.claude-plugin (i.e. ROOT.parent), matching the real layout."""
    plugin = root / "adjudant"
    canonical = plugin / "skills" / "adjudant"
    (canonical / "templates").mkdir(parents=True)
    (canonical / "reference").mkdir(parents=True)

    rows = "\n".join(f"| `{v}` | `reference/{v}.md` | desc |" for v in verbs)
    (canonical / "SKILL.md").write_text(
        f"---\nname: adjudant\nversion: {version}\n---\n\n"
        f"| Verb | Loads | Purpose |\n|---|---|---|\n{rows}\n"
    )

    for v in verbs:
        (canonical / "reference" / f"{v}.md").write_text(f"# /adjudant {v}\n")

    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "adjudant", "version": version,
                    "description": f"verbs: {', '.join(verbs)}"}, indent=2) + "\n")
    (plugin / "README.md").write_text(f"# adjudant\n\nverbs: {', '.join(verbs)}\n")

    (plugin / "scripts").mkdir(parents=True)
    (plugin / "scripts" / "command-metadata.json").write_text(
        json.dumps({"name": "adjudant", "version": version,
                    "verbs": [{"name": v, "reference": f"reference/{v}.md"} for v in verbs]},
                   indent=2) + "\n")

    for h in ("source", ".claude", ".gemini"):
        d = plugin / h / "skills"
        d.mkdir(parents=True)
        (d / "adjudant").symlink_to(Path("../../skills/adjudant"))

    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "adjudant", "version": version,
                                 "description": f"verbs: {', '.join(verbs)}"}]}, indent=2) + "\n")

    return plugin


class _PatchedTree(unittest.TestCase):
    """Base: build a valid tree in a temp dir and point validate.* at it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        root = Path(self._tmp.name)
        self.plugin = _build(root)
        self._orig = {k: getattr(validate, k)
                      for k in ("ROOT", "CANONICAL", "TEMPLATES", "REFERENCE", "HARNESS_DIRS")}
        validate.ROOT = self.plugin
        validate.CANONICAL = self.plugin / "skills" / "adjudant"
        validate.TEMPLATES = validate.CANONICAL / "templates"
        validate.REFERENCE = validate.CANONICAL / "reference"
        validate.HARNESS_DIRS = [self.plugin / h / "skills" / "adjudant"
                                 for h in ("source", ".claude", ".gemini")]

    def tearDown(self):
        for k, v in self._orig.items():
            setattr(validate, k, v)
        self._tmp.cleanup()


class TestHarnessParity(_PatchedTree):

    def test_passes_when_symlinks_resolve(self):
        r = Result()
        validate.validate_harness_parity(r)
        self.assertEqual(r.failures, [])

    def test_fails_when_one_harness_is_real_dir(self):
        # Replace the .claude symlink with a real directory
        link = self.plugin / ".claude" / "skills" / "adjudant"
        link.unlink()
        link.mkdir()
        r = Result()
        validate.validate_harness_parity(r)
        self.assertTrue(any("harness-parity" in f for f in r.failures))


class TestVersionConsistency(_PatchedTree):

    def test_passes_at_lockstep(self):
        r = Result()
        validate.validate_version_consistency(r)
        self.assertEqual(r.failures, [])

    def test_fails_on_single_file_mismatch(self):
        pj = self.plugin / ".claude-plugin" / "plugin.json"
        pj.write_text(json.dumps({"name": "adjudant", "version": "9.9.9"}) + "\n")
        r = Result()
        validate.validate_version_consistency(r)
        self.assertTrue(any("version-consistency" in f for f in r.failures))


class TestTidyBackupIntegrity(_PatchedTree):
    """This is the validator the A1 fix repairs — it must now actually fail."""

    def test_passes_with_legacy_file(self):
        d = self.plugin / ".adjudant-tidy-backup" / "proj" / "notes"
        d.mkdir(parents=True)
        (d / "n.md.legacy").write_text("old\n")
        r = Result()
        validate.validate_tidy_backup_integrity(r)
        self.assertEqual(r.failures, [])

    def test_fails_when_files_but_no_legacy(self):
        d = self.plugin / ".adjudant-tidy-backup" / "proj"
        d.mkdir(parents=True)
        (d / "note.md").write_text("not a backup\n")
        r = Result()
        validate.validate_tidy_backup_integrity(r)
        self.assertTrue(any("tidy-backup-integrity" in f for f in r.failures),
                        "expected tidy-backup-integrity to fail on a dir with no .legacy files")

    def test_passes_on_empty_backup_dir(self):
        (self.plugin / ".adjudant-tidy-backup" / "proj").mkdir(parents=True)
        r = Result()
        validate.validate_tidy_backup_integrity(r)
        self.assertEqual(r.failures, [])


class TestReferenceFilesExist(_PatchedTree):

    def test_passes_when_all_references_exist(self):
        r = Result()
        validate.validate_reference_files_exist(r)
        self.assertEqual(r.failures, [])

    def test_fails_when_a_reference_file_is_missing(self):
        (self.plugin / "skills" / "adjudant" / "reference" / "check.md").unlink()
        r = Result()
        validate.validate_reference_files_exist(r)
        self.assertTrue(any("reference-files-exist" in f for f in r.failures))


class TestVerbSurfaceParity(_PatchedTree):

    def test_passes_when_all_surfaces_know_all_verbs(self):
        r = Result()
        validate.validate_verb_surface_parity(r)
        self.assertEqual(r.failures, [])

    def test_fails_when_readme_missing_a_verb(self):
        (self.plugin / "README.md").write_text("# adjudant\n\nverbs: connect\n")  # no 'check'
        r = Result()
        validate.validate_verb_surface_parity(r)
        self.assertTrue(any("README.md missing verbs" in f for f in r.failures))

    def test_fails_on_wrong_spelled_out_verb_count(self):
        # The escape class this validator exists for: "nine verbs" surviving a
        # verb addition. Fixture has 2 verbs; claim nine.
        (self.plugin / "README.md").write_text("# adjudant\n\nnine verbs: connect, check\n")
        r = Result()
        validate.validate_verb_surface_parity(r)
        self.assertTrue(any("says 'nine verbs' but metadata has 2" in f for f in r.failures))


class TestCommandMetadataCoherence(_PatchedTree):

    def test_passes_when_verbs_match(self):
        r = Result()
        validate.validate_command_metadata_coherence(r)
        self.assertEqual(r.failures, [])

    def test_fails_when_metadata_has_extra_verb(self):
        meta = self.plugin / "scripts" / "command-metadata.json"
        data = json.loads(meta.read_text())
        data["verbs"].append({"name": "ghost"})  # not in SKILL.md router
        meta.write_text(json.dumps(data) + "\n")
        r = Result()
        validate.validate_command_metadata_coherence(r)
        self.assertTrue(any("command-metadata-coherence" in f for f in r.failures))


class TestTemplatesTagSchema(_PatchedTree):

    def test_passes_when_no_deprecated_tags(self):
        (validate.TEMPLATES / "note.md").write_text("---\ntags:\n  - note\n---\n")
        r = Result()
        validate.validate_templates_tag_schema(r)
        self.assertEqual(r.failures, [])

    def test_fails_on_deprecated_ob_tag(self):
        (validate.TEMPLATES / "note.md").write_text("---\ntags:\n  - ob/note\n---\n#ob/note\n")
        r = Result()
        validate.validate_templates_tag_schema(r)
        self.assertTrue(any("templates-tag-schema" in f for f in r.failures))


class TestClaudeMdImportsAgents(_PatchedTree):

    def test_passes_when_first_line_is_import(self):
        (validate.TEMPLATES / "CLAUDE.md").write_text("\n@AGENTS.md\n\n# Overrides\n")
        r = Result()
        validate.validate_claude_md_imports_agents(r)
        self.assertEqual(r.failures, [])

    def test_fails_on_wrong_first_line(self):
        (validate.TEMPLATES / "CLAUDE.md").write_text("# CLAUDE\n@AGENTS.md\n")
        r = Result()
        validate.validate_claude_md_imports_agents(r)
        self.assertTrue(any("claude-md-imports-agents" in f for f in r.failures))

    def test_fails_when_missing(self):
        r = Result()
        validate.validate_claude_md_imports_agents(r)
        self.assertTrue(any("claude-md-imports-agents" in f for f in r.failures))


class TestTemplateCoverage(_PatchedTree):

    def _provision_all(self):
        for template in validate.FILE_TYPES_REQUIRING_TEMPLATE.values():
            for t in (template if isinstance(template, list) else [template]):
                (validate.TEMPLATES / t).write_text("---\n---\n")

    def test_passes_when_all_templates_present(self):
        self._provision_all()
        r = Result()
        validate.validate_template_coverage(r)
        self.assertEqual(r.failures, [])

    def test_fails_when_one_missing(self):
        self._provision_all()
        (validate.TEMPLATES / "decision.md").unlink()
        r = Result()
        validate.validate_template_coverage(r)
        self.assertTrue(any("decision" in f for f in r.failures))


class TestPluginVersionSet(_PatchedTree):

    def test_passes_with_version(self):
        r = Result()
        validate.validate_plugin_version_set(r)
        self.assertEqual(r.failures, [])

    def test_fails_on_empty_version(self):
        pj = self.plugin / ".claude-plugin" / "plugin.json"
        pj.write_text(json.dumps({"name": "adjudant", "version": ""}) + "\n")
        r = Result()
        validate.validate_plugin_version_set(r)
        self.assertTrue(any("plugin-version-set" in f for f in r.failures))


class TestPortPreviewCoherence(_PatchedTree):

    def test_passes_when_no_preview_dir(self):
        r = Result()
        validate.validate_port_preview_coherence(r)
        self.assertEqual(r.failures, [])

    def test_fails_when_preview_incomplete(self):
        d = self.plugin / ".adjudant-port-preview"
        d.mkdir()
        (d / "summary.md").write_text("x")
        r = Result()
        validate.validate_port_preview_coherence(r)
        self.assertTrue(any("port-preview-coherence" in f for f in r.failures))

    def test_passes_when_preview_complete(self):
        d = self.plugin / ".adjudant-port-preview"
        d.mkdir()
        for f in validate.PORT_PREVIEW_REQUIRED:
            (d / f).write_text("x")
        r = Result()
        validate.validate_port_preview_coherence(r)
        self.assertEqual(r.failures, [])


class TestPortBackupIntegrity(_PatchedTree):

    def test_passes_with_legacy_files(self):
        d = self.plugin / ".adjudant-port-backup" / "20260101T000000Z"
        d.mkdir(parents=True)
        (d / "AGENTS.md.legacy").write_text("x")
        r = Result()
        validate.validate_port_backup_integrity(r)
        self.assertEqual(r.failures, [])

    def test_fails_on_non_legacy_only_dir(self):
        d = self.plugin / ".adjudant-port-backup" / "20260101T000000Z"
        d.mkdir(parents=True)
        (d / "stray.md").write_text("x")
        r = Result()
        validate.validate_port_backup_integrity(r)
        self.assertTrue(any("port-backup-integrity" in f for f in r.failures))


class TestGitignoreValidators(_PatchedTree):

    def test_port_dirs_require_active_entries(self):
        (self.plugin / ".adjudant-port-preview").mkdir()
        # Commented-out entry must NOT satisfy the check (old substring bug)
        (self.plugin / ".gitignore").write_text("# .adjudant-port-preview/\n")
        r = Result()
        validate.validate_gitignore_includes_port_dirs(r)
        self.assertTrue(any("gitignore-includes-port-dirs" in f for f in r.failures))

    def test_port_dirs_pass_with_entry(self):
        (self.plugin / ".adjudant-port-preview").mkdir()
        (self.plugin / ".gitignore").write_text(".adjudant-port-preview/\n")
        r = Result()
        validate.validate_gitignore_includes_port_dirs(r)
        self.assertEqual(r.failures, [])

    def test_port_dirs_fall_back_to_parent_gitignore(self):
        (self.plugin / ".adjudant-port-preview").mkdir()
        (self.plugin.parent / ".gitignore").write_text(".adjudant-port-preview/\n")
        r = Result()
        validate.validate_gitignore_includes_port_dirs(r)
        self.assertEqual(r.failures, [])

    def test_tidy_dirs_negated_entry_fails(self):
        (self.plugin / ".adjudant-tidy-preview").mkdir()
        (self.plugin / ".gitignore").write_text("!.adjudant-tidy-preview/\n")
        r = Result()
        validate.validate_gitignore_includes_tidy_dirs(r)
        self.assertTrue(any("gitignore-includes-tidy-dirs" in f for f in r.failures))

    def test_tidy_dirs_pass_with_entry(self):
        (self.plugin / ".adjudant-tidy-preview").mkdir()
        (self.plugin / ".gitignore").write_text(".adjudant-tidy-preview/\n")
        r = Result()
        validate.validate_gitignore_includes_tidy_dirs(r)
        self.assertEqual(r.failures, [])


class TestTidyPreviewCoherence(_PatchedTree):

    def test_passes_when_no_dir(self):
        r = Result()
        validate.validate_tidy_preview_coherence(r)
        self.assertEqual(r.failures, [])

    def test_fails_when_incomplete(self):
        d = self.plugin / ".adjudant-tidy-preview"
        d.mkdir()
        (d / "summary.md").write_text("x")
        r = Result()
        validate.validate_tidy_preview_coherence(r)
        self.assertTrue(any("tidy-preview-coherence" in f for f in r.failures))

    def test_passes_when_complete(self):
        d = self.plugin / ".adjudant-tidy-preview"
        d.mkdir()
        (d / "summary.md").write_text("x")
        (d / "changes.json").write_text("{}")
        (d / "files").mkdir()
        r = Result()
        validate.validate_tidy_preview_coherence(r)
        self.assertEqual(r.failures, [])


class TestSkillFrontmatterVersion(_PatchedTree):

    def test_body_version_line_not_picked_up(self):
        # A body line starting `version:` must not shadow the frontmatter value
        skill = self.plugin / "skills" / "adjudant" / "SKILL.md"
        skill.write_text(
            "---\nname: adjudant\nversion: 1.0.0\n---\n\n"
            "# adjudant\n\nversion: 9.9.9 is mentioned in prose here\n"
            "| `connect` | `reference/connect.md` | d |\n"
            "| `check` | `reference/check.md` | d |\n"
        )
        self.assertEqual(validate._skill_frontmatter_version(skill), "1.0.0")


if __name__ == "__main__":
    unittest.main()
