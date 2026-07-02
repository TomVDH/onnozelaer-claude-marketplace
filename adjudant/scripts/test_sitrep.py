"""Tests for adjudant/scripts/sitrep.py."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sitrep import run_sitrep, _next_step


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


class TestNextStep(unittest.TestCase):

    def test_next_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "_handoff.md", "---\nupdated: 2026-07-02\n---\n\nNEXT: wire up the sitrep verb\n")
            self.assertEqual(_next_step(root), "wire up the sitrep verb")

    def test_next_absent_when_no_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(_next_step(Path(tmp)))

    def test_next_none_when_no_next_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "_handoff.md", "---\nupdated: 2026-07-02\n---\n\nJust some prose, no marker.\n")
            self.assertIsNone(_next_step(root))


class TestRunSitrep(unittest.TestCase):

    def _project(self, root: Path) -> None:
        _write(root / "brief.md",
               "---\ntype: project\nslug: demo\nproject_type: coding\nstatus: active\n---\n\n# Demo Project\n\nBody.")
        _write(root / "_handoff.md", "---\nupdated: 2026-07-02\n---\n\nNEXT: ship v0.10.0\n")
        _write(root / "sessions" / "2026-07-01.md", "# session\n")
        _write(root / "decisions" / "2026-06-30-pick-approach.md", "# decision\n")
        _write(root / "notes" / "idea.md", "# note\n")

    def test_populated_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            _write(root / ".remember" / "today-2026-07-02.md", "- 09:00 · started work\n- 10:30 · wrote code\n")
            now = datetime(2026, 7, 2, 11, 0)  # 30m after last activity
            rep = run_sitrep(root, vault_path=Path("/vault/demo"), now=now)

            self.assertEqual(rep["purpose"], "Demo Project")
            self.assertEqual(rep["vault_path"], "/vault/demo")
            self.assertEqual(rep["next_step"], "ship v0.10.0")
            self.assertEqual(rep["whats_done"]["last_session"], "2026-07-01")
            self.assertEqual(rep["whats_done"]["last_decision"], "2026-06-30")
            self.assertEqual(rep["whats_done"]["counts"]["notes"], 1)
            # 30 minutes → green light
            self.assertEqual(rep["freshness"]["light"], "\U0001f7e2")
            self.assertEqual(rep["freshness"]["age"], "30m")

    def test_stale_activity_turns_light_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            _write(root / ".remember" / "today-2026-07-01.md", "- 09:00 · old work\n")
            now = datetime(2026, 7, 2, 18, 0)  # >8h later
            rep = run_sitrep(root, now=now)
            self.assertEqual(rep["freshness"]["light"], "\U0001f534")  # red

    def test_missing_handoff_yields_null_next(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "brief.md", "---\ntype: project\nslug: demo\n---\n\n# Demo\n")
            now = datetime(2026, 7, 2, 12, 0)
            rep = run_sitrep(root, now=now)
            self.assertIsNone(rep["next_step"])

    def test_empty_project_no_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            now = datetime(2026, 7, 2, 12, 0)
            rep = run_sitrep(root, now=now)
            self.assertFalse(rep["project"]["present"])
            self.assertIsNone(rep["purpose"])
            self.assertIsNone(rep["were_doing"])
            self.assertEqual(rep["freshness"]["light"], "⚪")  # white — age unknown
            self.assertEqual(rep["whats_done"]["counts"], {})


if __name__ == "__main__":
    unittest.main()
