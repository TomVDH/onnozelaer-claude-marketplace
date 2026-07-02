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

    (plugin / ".claude-plugin").mkdir(parents=True)
    (plugin / ".claude-plugin" / "plugin.json").write_text(
        json.dumps({"name": "adjudant", "version": version}, indent=2) + "\n")

    (plugin / "scripts").mkdir(parents=True)
    (plugin / "scripts" / "command-metadata.json").write_text(
        json.dumps({"name": "adjudant", "version": version,
                    "verbs": [{"name": v} for v in verbs]}, indent=2) + "\n")

    for h in ("source", ".claude", ".gemini"):
        d = plugin / h / "skills"
        d.mkdir(parents=True)
        (d / "adjudant").symlink_to(Path("../../skills/adjudant"))

    (root / ".claude-plugin").mkdir(parents=True)
    (root / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"plugins": [{"name": "adjudant", "version": version}]}, indent=2) + "\n")

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


if __name__ == "__main__":
    unittest.main()
