"""Tests for adjudant/scripts/sitrep.py."""

import contextlib
import io
import json as _json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from sitrep import cli_main as sitrep_cli, run_sitrep, _next_step


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
            self.assertEqual(rep["whats_done"]["total_files"], 3)  # session+decision+note
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

    def test_breadcrumb_flow_reads_remember_from_code_root(self):
        # In the real flow the vault project dir and the code root are DIFFERENT
        # directories: .remember/ lives at the code root only. Freshness must
        # come from there, not from the vault dir (regression: always-⚪ bug).
        with tempfile.TemporaryDirectory() as tmp:
            vault_proj = Path(tmp) / "vault" / "projects" / "demo"
            code_root = Path(tmp) / "code"
            self._project(vault_proj)
            _write(code_root / ".remember" / "today-2026-07-02.md", "- 10:30 · wrote code\n")
            now = datetime(2026, 7, 2, 11, 0)
            rep = run_sitrep(vault_proj, now=now, code_root=code_root)
            self.assertEqual(rep["freshness"]["light"], "\U0001f7e2")
            self.assertEqual(rep["freshness"]["age"], "30m")

    def test_status_block_with_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "brief.md",
                "---\ntype: project\nslug: t\nproject_type: coding\nstatus: active\n---\n\n# T\n")
            (root / "sessions").mkdir()
            (root / "sessions" / "2026-01-01.md").write_text("---\ntype: session\n---\n")
            now = datetime(2026, 7, 2, 12, 0)
            rep = run_sitrep(root, now=now)
            self.assertEqual(rep["status"]["declared"], "active")
            self.assertEqual(rep["status"]["suggested"], "stale")
            self.assertIn("zone", rep["status"])
            self.assertIn("zone_matches", rep["status"])

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


class TestSitrepCost(unittest.TestCase):

    def test_estimate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "brief.md").write_text(
                "---\ntype: project\nslug: t\nproject_type: coding\nstatus: active\n---\n\n# T\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = sitrep_cli(["--project-dir", str(root), "--estimate-only"])
            self.assertEqual(rc, 0)
            payload = _json.loads(buf.getvalue())
            self.assertEqual(set(payload), {"cost"})

    def test_normal_run_includes_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "brief.md").write_text(
                "---\ntype: project\nslug: t\nproject_type: coding\nstatus: active\n---\n\n# T\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = sitrep_cli(["--project-dir", str(root)])
            self.assertEqual(rc, 0)
            self.assertIn("cost", _json.loads(buf.getvalue()))


if __name__ == "__main__":
    unittest.main()
