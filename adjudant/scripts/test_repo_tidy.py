"""Tests for repo_tidy symlink repair (preview -> apply, idempotent)."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repo_tidy as rt
from test_repo_walk import _make_plugin


class TestRepoTidy(unittest.TestCase):

    def _adopted_with_missing_link(self, root: Path) -> Path:
        _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
        (root / "alpha" / ".gemini" / "skills" / "alpha").unlink()  # missing
        return root

    def test_detect_finds_missing_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._adopted_with_missing_link(Path(tmp))
            reps = rt.detect_repairs(root)
            self.assertEqual(len(reps), 1)
            self.assertEqual(reps[0]["harness"], ".gemini")

    def test_clean_repo_no_repairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            self.assertEqual(rt.detect_repairs(root), [])

    def test_non_adopted_plugin_not_repaired(self):
        # skills present but ZERO harness symlinks -> not adopted -> left alone
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=False)
            self.assertEqual(rt.detect_repairs(root), [])

    def test_preview_then_apply_repairs_and_backs_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._adopted_with_missing_link(Path(tmp))
            preview = rt.write_preview(root, rt.detect_repairs(root))
            self.assertTrue((preview / "summary.md").is_file())
            self.assertTrue((preview / "changes.json").is_file())
            self.assertTrue((preview / "files").is_dir())
            # live still broken before apply
            self.assertFalse((root / "alpha" / ".gemini" / "skills" / "alpha").is_symlink())
            backup = rt.apply_preview(root)
            link = root / "alpha" / ".gemini" / "skills" / "alpha"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), (root / "alpha" / "skills" / "alpha").resolve())
            self.assertTrue(backup.is_dir())
            self.assertFalse((root / rt.PREVIEW_DIR_NAME).exists())  # preview consumed

    def test_idempotent_second_detect_empty_after_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._adopted_with_missing_link(Path(tmp))
            rt.write_preview(root, rt.detect_repairs(root))
            rt.apply_preview(root)
            self.assertEqual(rt.detect_repairs(root), [])


if __name__ == "__main__":
    unittest.main()
