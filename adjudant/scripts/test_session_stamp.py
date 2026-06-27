"""Tests for adjudant/scripts/_session_stamp.py.

The session-id stamping primitives used by the SessionStart + PostToolUse hooks:
  - add_to_session_id_list  → `session_id:` (list) on session notes
  - stamp_source_session    → `source_session:` (scalar) on authored files
"""

import tempfile
import unittest
from pathlib import Path

from _session_stamp import add_to_session_id_list, stamp_source_session

UUID = "11111111-2222-3333-4444-555555555555"
UUID2 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"


def _w(p: Path, text: str) -> Path:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


# ============================================================
# add_to_session_id_list
# ============================================================


class TestSessionIdList(unittest.TestCase):

    def test_inline_empty_list_gets_first_item_as_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "2026-06-01.md",
                   "---\ntype: session\nsession_id: []\ntags:\n  - session\n---\n\n## Log\n")
            self.assertTrue(add_to_session_id_list(f, UUID))
            t = f.read_text()
            self.assertIn(f"session_id:\n  - {UUID}", t)
            self.assertNotIn("session_id: []", t)
            self.assertIn("## Log", t)  # body preserved

    def test_missing_field_is_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "s.md", "---\ntype: session\ntags:\n  - session\n---\n\nbody\n")
            self.assertTrue(add_to_session_id_list(f, UUID))
            self.assertIn(f"session_id:\n  - {UUID}", f.read_text())

    def test_appends_to_existing_block_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "s.md",
                   f"---\ntype: session\nsession_id:\n  - {UUID}\n---\n\nbody\n")
            self.assertTrue(add_to_session_id_list(f, UUID2))
            t = f.read_text()
            self.assertIn(f"  - {UUID}", t)
            self.assertIn(f"  - {UUID2}", t)

    def test_idempotent_when_already_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "s.md",
                   f"---\ntype: session\nsession_id:\n  - {UUID}\n---\n\nbody\n")
            self.assertFalse(add_to_session_id_list(f, UUID))

    def test_inline_list_with_items_converts_to_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "s.md",
                   f"---\ntype: session\nsession_id: [{UUID}]\n---\n\nbody\n")
            self.assertTrue(add_to_session_id_list(f, UUID2))
            t = f.read_text()
            self.assertIn("session_id:\n", t)
            self.assertIn(f"  - {UUID}", t)
            self.assertIn(f"  - {UUID2}", t)
            self.assertNotIn("[", t.split("---")[1])  # no inline bracket left in fm

    def test_safe_skip_no_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "s.md", "no frontmatter here\n")
            self.assertFalse(add_to_session_id_list(f, UUID))
            self.assertEqual(f.read_text(), "no frontmatter here\n")

    def test_safe_skip_empty_uuid(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "s.md", "---\ntype: session\nsession_id: []\n---\n\nb\n")
            self.assertFalse(add_to_session_id_list(f, ""))

    def test_safe_skip_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(add_to_session_id_list(Path(tmp) / "nope.md", UUID))


# ============================================================
# stamp_source_session
# ============================================================


class TestSourceSession(unittest.TestCase):

    def test_stamps_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "decisions" / "2026-06-01-x.md",
                   "---\ntype: decision\nstatus: active\n---\n\n## Decision\n")
            self.assertTrue(stamp_source_session(f, UUID))
            t = f.read_text()
            self.assertIn(f"source_session: {UUID}", t)
            self.assertIn("## Decision", t)  # body intact

    def test_idempotent_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "decisions" / "d.md",
                   f"---\ntype: decision\nsource_session: {UUID}\n---\n\nbody\n")
            self.assertFalse(stamp_source_session(f, UUID2))
            self.assertNotIn(UUID2, f.read_text())  # never overwrite

    def test_skips_session_notes(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "sessions" / "2026-06-01.md", "---\ntype: session\n---\n\nlog\n")
            self.assertFalse(stamp_source_session(f, UUID))

    def test_skips_excluded_filenames(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("_handoff.md", "_index.md", "_iteration.md", "_index-projects.md"):
                f = _w(Path(tmp) / name, "---\ntype: handoff\n---\n\nbody\n")
                self.assertFalse(stamp_source_session(f, UUID), name)

    def test_safe_skip_no_frontmatter(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "notes" / "n.md", "plain text, no fm\n")
            self.assertFalse(stamp_source_session(f, UUID))

    def test_safe_skip_empty_uuid(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = _w(Path(tmp) / "notes" / "n.md", "---\ntype: note\n---\n\nbody\n")
            self.assertFalse(stamp_source_session(f, ""))

    def test_safe_skip_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(stamp_source_session(Path(tmp) / "notes" / "nope.md", UUID))


if __name__ == "__main__":
    unittest.main()
