"""Tests for scripts/bump_plugin_version.py — one-shot version lockstep."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bump_plugin_version import bump, _set_json_version


def _w(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _make_tree(root: Path, plugin: str = "demo", version: str = "0.1.0") -> None:
    """Minimal marketplace layout with all four lockstep files at `version`."""
    _w(root / plugin / ".claude-plugin" / "plugin.json",
       json.dumps({"name": plugin, "version": version, "keywords": ["a", "b"]}, indent=2) + "\n")
    _w(root / plugin / "scripts" / "command-metadata.json",
       json.dumps({"name": plugin, "version": version, "verbs": []}, indent=2) + "\n")
    _w(root / plugin / "skills" / plugin / "SKILL.md",
       f"---\nname: {plugin}\nversion: {version}\nuser-invocable: true\n---\n\n# {plugin}\n")
    _w(root / ".claude-plugin" / "marketplace.json",
       json.dumps({"plugins": [{"name": plugin, "version": version, "source": f"./{plugin}"}]}, indent=2) + "\n")


class TestSemverValidation(unittest.TestCase):

    def test_rejects_bad_versions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_tree(root)
            for bad in ("1.2", "v1.2.3", "1.2.3.4", "abc", "1.2.x"):
                with self.assertRaises(ValueError, msg=bad):
                    bump("demo", bad, root=root)

    def test_accepts_semver_with_prerelease(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_tree(root)
            changed = bump("demo", "1.2.3-rc.1", root=root)
            self.assertTrue(changed)


class TestBump(unittest.TestCase):

    def test_writes_all_lockstep_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_tree(root, version="0.1.0")
            changed = bump("demo", "0.2.0", root=root)
            self.assertEqual(len(changed), 4)
            self.assertEqual(json.loads((root / "demo" / ".claude-plugin" / "plugin.json").read_text())["version"], "0.2.0")
            self.assertEqual(json.loads((root / "demo" / "scripts" / "command-metadata.json").read_text())["version"], "0.2.0")
            self.assertIn("version: 0.2.0", (root / "demo" / "skills" / "demo" / "SKILL.md").read_text())
            mk = json.loads((root / ".claude-plugin" / "marketplace.json").read_text())
            self.assertEqual(mk["plugins"][0]["version"], "0.2.0")

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_tree(root, version="0.1.0")
            bump("demo", "0.2.0", root=root)
            self.assertEqual(bump("demo", "0.2.0", root=root), [])  # second call is a no-op

    def test_round_trip_preserves_key_order_and_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_tree(root, version="0.1.0")
            before = json.loads((root / "demo" / ".claude-plugin" / "plugin.json").read_text())
            bump("demo", "0.2.0", root=root)
            after = json.loads((root / "demo" / ".claude-plugin" / "plugin.json").read_text())
            self.assertEqual(list(before.keys()), list(after.keys()))  # order intact
            self.assertEqual(after["name"], before["name"])
            self.assertEqual(after["keywords"], before["keywords"])  # untouched field survives

    def test_unknown_plugin_in_marketplace_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_tree(root, plugin="demo")
            # plugin dir exists but is not listed in marketplace.json
            (root / "orphan" / ".claude-plugin").mkdir(parents=True)
            (root / "orphan" / ".claude-plugin" / "plugin.json").write_text('{"name": "orphan", "version": "0.1.0"}\n')
            with self.assertRaises(KeyError):
                bump("orphan", "0.2.0", root=root)

    def test_missing_plugin_dir_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_tree(root)
            with self.assertRaises(KeyError):
                bump("nonexistent", "0.2.0", root=root)


class TestSetJsonVersion(unittest.TestCase):

    def test_absent_file_returns_false(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(_set_json_version(Path(tmp) / "nope.json", "1.0.0"))


if __name__ == "__main__":
    unittest.main()
