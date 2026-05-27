"""Tests for adjudant/scripts/check.py."""

import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from check import run_check, _read_brief, _folder_counts, _most_recent_dated, _handoff_info, _latest_dream_signal


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestReadBrief(unittest.TestCase):

    def test_brief_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "brief.md",
                "---\ntype: project\nslug: test\nproject_type: coding\nstatus: active\n---\n\n# Test Project\n\nBody.")
            brief = _read_brief(root)
            self.assertTrue(brief["present"])
            self.assertEqual(brief["slug"], "test")
            self.assertEqual(brief["project_type"], "coding")
            self.assertEqual(brief["status"], "active")
            self.assertEqual(brief["title"], "Test Project")

    def test_brief_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(_read_brief(Path(tmp))["present"])


class TestFolderCounts(unittest.TestCase):

    def test_counts_non_index_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "decisions").mkdir()
            (root / "decisions" / "_index.md").write_text("# idx")
            (root / "decisions" / "2026-05-26-a.md").write_text("a")
            (root / "decisions" / "2026-05-27-b.md").write_text("b")
            counts = _folder_counts(root)
            self.assertEqual(counts["decisions"], 2)

    def test_missing_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            counts = _folder_counts(Path(tmp))
            self.assertEqual(counts, {})


class TestMostRecentDated(unittest.TestCase):

    def test_finds_max(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for d in ["2026-05-26", "2026-05-28", "2026-05-27"]:
                (root / f"{d}.md").write_text("x")
            self.assertEqual(_most_recent_dated(root), "2026-05-28")

    def test_empty_returns_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(_most_recent_dated(Path(tmp)))

    def test_ignores_non_dated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "no-date.md").write_text("x")
            (root / "2026-05-26.md").write_text("y")
            self.assertEqual(_most_recent_dated(root), "2026-05-26")


class TestHandoffInfo(unittest.TestCase):

    def test_handoff_present_with_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "_handoff.md", "---\ntype: handoff\nupdated: 2026-05-25\n---\n\nbody")
            info = _handoff_info(root)
            self.assertTrue(info["present"])
            self.assertEqual(info["updated"], "2026-05-25")
            self.assertIsInstance(info["stale_hours"], float)

    def test_handoff_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(_handoff_info(Path(tmp))["present"])


class TestLatestDreamSignal(unittest.TestCase):

    def test_picks_most_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "dreams").mkdir()
            (root / "dreams" / "2026-05-20.md").write_text("# old")
            (root / "dreams" / "2026-05-26.md").write_text("# new\n**90 drift items**")
            sig = _latest_dream_signal(root)
            self.assertEqual(sig["date"], "2026-05-26")
            self.assertEqual(sig["drift_items"], 90)

    def test_no_dreams_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(_latest_dream_signal(Path(tmp))["present"])


class TestRunCheck(unittest.TestCase):

    def test_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "brief.md",
                "---\ntype: project\nslug: test\nproject_type: coding\nstatus: active\n---\n\n# Test\n")
            _write(root / "_handoff.md", "---\ntype: handoff\nupdated: 2026-05-25\n---\nbody")
            (root / "decisions").mkdir()
            (root / "decisions" / "2026-05-26-a.md").write_text("---\ntype: decision\n---\n")
            (root / "sessions").mkdir()
            (root / "sessions" / "2026-05-26.md").write_text("---\ntype: session\n---\n")
            report = run_check(root)
            self.assertEqual(report["project"]["slug"], "test")
            self.assertEqual(report["counts"]["decisions"], 1)
            self.assertEqual(report["recent"]["last_decision"], "2026-05-26")
            self.assertTrue(report["handoff"]["present"])


if __name__ == "__main__":
    unittest.main()
