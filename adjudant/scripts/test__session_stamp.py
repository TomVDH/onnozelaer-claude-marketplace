"""Tests for _session_stamp.py — session_id list + source_session scalar."""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _session_stamp import add_to_session_id_list, stamp_source_session

UUID1 = "2ada03ff-687f-4a82-9e1f-1234567890ab"
UUID2 = "abcd1234-5678-90ef-1234-567890abcdef"


class TestSessionIdList(unittest.TestCase):

    def _session(self, tmp: Path, frontmatter: str) -> Path:
        f = tmp / "2026-06-26.md"
        f.write_text(f"---\n{frontmatter}---\n\n> intent\n\n## Log\n")
        return f

    def test_creates_session_id_block_when_field_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._session(Path(tmp), "type: session\ndate: 2026-06-26\ntags:\n  - session\n")
            self.assertTrue(add_to_session_id_list(f, UUID1))
            text = f.read_text()
            self.assertIn("session_id:", text)
            self.assertIn(f"  - {UUID1}", text)
            # Body preserved
            self.assertIn("## Log", text)
            self.assertIn("> intent", text)

    def test_fills_inline_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._session(Path(tmp), "type: session\nsession_id: []\ntags:\n  - session\n")
            self.assertTrue(add_to_session_id_list(f, UUID1))
            text = f.read_text()
            self.assertIn(f"  - {UUID1}", text)
            self.assertNotIn("session_id: []", text)

    def test_appends_to_existing_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._session(Path(tmp), f"type: session\nsession_id:\n  - {UUID1}\ntags:\n  - session\n")
            self.assertTrue(add_to_session_id_list(f, UUID2))
            text = f.read_text()
            self.assertIn(f"  - {UUID1}", text)
            self.assertIn(f"  - {UUID2}", text)

    def test_idempotent_when_uuid_already_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._session(Path(tmp), f"type: session\nsession_id:\n  - {UUID1}\ntags:\n  - session\n")
            before = f.read_text()
            self.assertFalse(add_to_session_id_list(f, UUID1))
            self.assertEqual(f.read_text(), before)

    def test_inline_list_with_items_converts_to_block(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._session(Path(tmp), f"type: session\nsession_id: [{UUID1}]\ntags:\n  - session\n")
            self.assertTrue(add_to_session_id_list(f, UUID2))
            text = f.read_text()
            self.assertIn("session_id:\n", text)
            self.assertIn(f"  - {UUID1}", text)
            self.assertIn(f"  - {UUID2}", text)
            self.assertNotIn("[", text.split("---")[1])  # no inline bracket left in fm

    def test_refuses_empty_uuid(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._session(Path(tmp), "type: session\ntags:\n  - session\n")
            self.assertFalse(add_to_session_id_list(f, ""))

    def test_no_frontmatter_safe_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "bare.md"
            f.write_text("plain markdown, no frontmatter\n")
            self.assertFalse(add_to_session_id_list(f, UUID1))

    def test_missing_file_safe_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(add_to_session_id_list(Path(tmp) / "nope.md", UUID1))


class TestSourceSessionStamp(unittest.TestCase):

    def _decision(self, tmp: Path, name: str = "2026-06-26-pick-x.md") -> Path:
        d = tmp / "decisions"
        d.mkdir()
        f = d / name
        f.write_text(
            "---\ntype: decision\nproject: \"[[projects/x/brief|x]]\"\n"
            "status: active\ntags:\n  - decision\n---\n\n## Decision\n\nBody.\n"
        )
        return f

    def test_stamps_decision_with_source_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._decision(Path(tmp))
            self.assertTrue(stamp_source_session(f, UUID1))
            text = f.read_text()
            self.assertIn(f"source_session: {UUID1}", text)
            # Blank line before body preserved
            self.assertIn("---\n\n## Decision", text)

    def test_idempotent_when_already_stamped(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = self._decision(Path(tmp))
            self.assertTrue(stamp_source_session(f, UUID1))
            before = f.read_text()
            self.assertFalse(stamp_source_session(f, UUID2))
            self.assertEqual(f.read_text(), before)

    def test_skips_session_note_in_sessions_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp) / "sessions"
            d.mkdir()
            f = d / "2026-06-26.md"
            f.write_text("---\ntype: session\ntags:\n  - session\n---\nbody\n")
            self.assertFalse(stamp_source_session(f, UUID1))

    def test_skips_handoff_and_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name in ("_handoff.md", "_index.md", "_index-projects.md", "_iteration.md"):
                f = Path(tmp) / name
                f.write_text(f"---\ntype: x\n---\nbody\n")
                self.assertFalse(stamp_source_session(f, UUID1), f"should skip {name}")

    def test_no_frontmatter_safe_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "decisions" / "no-fm.md"
            f.parent.mkdir()
            f.write_text("plain markdown, no frontmatter\n")
            self.assertFalse(stamp_source_session(f, UUID1))

    def test_empty_uuid_safe_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "notes" / "n.md"
            f.parent.mkdir()
            f.write_text("---\ntype: note\n---\n\nbody\n")
            self.assertFalse(stamp_source_session(f, ""))

    def test_missing_file_safe_skip(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertFalse(stamp_source_session(Path(tmp) / "notes" / "nope.md", UUID1))

    def test_preserves_existing_fields_and_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "notes" / "n.md"
            f.parent.mkdir()
            f.write_text(
                "---\ntype: note\nproject: \"[[projects/x/brief|x]]\"\n"
                "tags:\n  - note\n---\n\n# Title\n\nLine 1\nLine 2\n"
            )
            self.assertTrue(stamp_source_session(f, UUID1))
            text = f.read_text()
            for line in ("type: note", "project: \"[[projects/x/brief|x]]\"",
                         "tags:", "  - note", "# Title", "Line 1", "Line 2"):
                self.assertIn(line, text)
            self.assertIn(f"source_session: {UUID1}", text)


if __name__ == "__main__":
    unittest.main()
