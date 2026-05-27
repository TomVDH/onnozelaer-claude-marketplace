"""Tests for adjudant/scripts/sync.py."""

import tempfile
import unittest
from pathlib import Path

from sync import (
    find_remember_source,
    mirror_handoff,
    refresh_brief_updated,
    refresh_projects_index_row,
    run_sync,
)


def _w(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _connected_setup(tmp: Path, slug: str = "p") -> tuple[Path, Path]:
    """Create a code project + connected vault."""
    proj = tmp / "code"; proj.mkdir()
    vault = tmp / "vault"; vault.mkdir()
    (vault / "Home.md").write_text("---\ntype: vault-home\n---\n")
    (vault / "projects").mkdir()
    (vault / "projects" / slug).mkdir()
    _w(vault / "projects" / slug / "brief.md",
       f"---\ntype: project\nproject_type: coding\nslug: {slug}\nstatus: active\nupdated: 2026-05-01\n---\n\n# Test\n")
    (vault / "projects" / slug / "sessions").mkdir()
    _w(proj / ".claude" / "adjudant",
       f"vault_path: {vault}\nvault_name: vault\nslug: {slug}\nmode: project\n")
    return proj, vault


# ============================================================
# Brief refresh
# ============================================================


class TestRefreshBriefUpdated(unittest.TestCase):

    def test_bumps_existing_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief = Path(tmp) / "brief.md"
            brief.write_text("---\nupdated: 2026-05-01\n---\nbody")
            r = refresh_brief_updated(brief, "2026-05-27")
            self.assertEqual(r, "bumped")
            self.assertIn("updated: 2026-05-27", brief.read_text())

    def test_unchanged_when_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief = Path(tmp) / "brief.md"
            brief.write_text("---\nupdated: 2026-05-27\n---\nbody")
            r = refresh_brief_updated(brief, "2026-05-27")
            self.assertEqual(r, "unchanged")

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(refresh_brief_updated(Path(tmp) / "nope.md", "2026-05-27"), "missing")


# ============================================================
# Handoff mirror
# ============================================================


class TestFindRememberSource(unittest.TestCase):

    def test_prefers_remember_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            _w(proj / ".remember" / "remember.md", "canonical")
            _w(proj / ".remember" / "now.md", "fallback")
            self.assertEqual(find_remember_source(proj).name, "remember.md")

    def test_falls_back_to_now_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            _w(proj / ".remember" / "now.md", "fallback")
            self.assertEqual(find_remember_source(proj).name, "now.md")

    def test_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(find_remember_source(Path(tmp)))


class TestMirrorHandoff(unittest.TestCase):

    def test_creates_handoff_from_remember(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "code"; proj.mkdir()
            _w(proj / ".remember" / "now.md", "current state\n")
            handoff = Path(tmp) / "_handoff.md"
            r = mirror_handoff(proj, handoff, "p", "2026-05-27")
            self.assertEqual(r, "mirrored")
            content = handoff.read_text()
            self.assertIn("type: handoff", content)
            self.assertIn("updated: 2026-05-27", content)
            self.assertIn("current state", content)

    def test_no_source_when_remember_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "code"; proj.mkdir()
            handoff = Path(tmp) / "_handoff.md"
            r = mirror_handoff(proj, handoff, "p", "2026-05-27")
            self.assertEqual(r, "no-source")


# ============================================================
# Projects index row refresh
# ============================================================


class TestRefreshProjectsIndexRow(unittest.TestCase):

    def test_updates_row_with_current_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, vault = _connected_setup(Path(tmp), "p")
            # Add a session + a decision
            _w(vault / "projects" / "p" / "sessions" / "2026-05-27.md", "---\ntype: session\n---\n")
            (vault / "projects" / "p" / "decisions").mkdir()
            _w(vault / "projects" / "p" / "decisions" / "2026-05-27-x.md", "---\ntype: decision\n---\n")
            r = refresh_projects_index_row(vault, "p")
            self.assertIn(r, ("inserted", "created-index", "updated"))
            text = (vault / "projects" / "_index.md").read_text()
            self.assertIn("p/brief", text)
            self.assertIn("2026-05-27", text)


# ============================================================
# End-to-end run_sync
# ============================================================


class TestRunSyncEndToEnd(unittest.TestCase):

    def test_full_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, vault = _connected_setup(Path(tmp), "p")
            _w(proj / ".remember" / "now.md", "live state body\n")
            summary = run_sync(proj)
            # All three steps should produce useful outputs
            self.assertEqual(summary["slug"], "p")
            self.assertEqual(summary["steps"]["brief_refresh"], "bumped")
            self.assertEqual(summary["steps"]["handoff_mirror"], "mirrored")
            self.assertIn(summary["steps"]["projects_index_row"], ("inserted", "created-index", "updated"))
            # Handoff actually exists with the body
            handoff_content = (vault / "projects" / "p" / "_handoff.md").read_text()
            self.assertIn("live state body", handoff_content)

    def test_unconnected_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No breadcrumb
            with self.assertRaises(RuntimeError):
                run_sync(Path(tmp))


if __name__ == "__main__":
    unittest.main()
