"""Tests for repo_scan detectors + run_scan."""
import contextlib
import io
import json
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repo_scan as rs
from test_repo_walk import _make_plugin, _marketplace, _write


class TestRepoScan(unittest.TestCase):

    def test_clean_repo_zero_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            _marketplace(root, [("alpha", "1.0.0")])
            _write(root / "AGENTS.md", "# r\n")
            _write(root / "CLAUDE.md", "@AGENTS.md\n")
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertEqual(report["summary"]["drift_items"], 0)

    def test_version_mismatch_counts_as_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.1", skills=False)
            _marketplace(root, [("alpha", "1.0.0")])  # registry behind
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertTrue(report["version_coherence"]["mismatches"])
            self.assertGreaterEqual(report["summary"]["drift_items"], 1)

    def test_broken_symlink_on_adopted_plugin_is_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            _marketplace(root, [("alpha", "1.0.0")])
            (root / "alpha" / ".gemini" / "skills" / "alpha").unlink()  # missing
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertGreaterEqual(report["summary"]["drift_items"], 1)
            self.assertTrue(report["symlink_integrity"]["issues"])

    def test_skillless_plugin_not_symlink_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "beta", "1.0.0", skills=False)
            _marketplace(root, [("beta", "1.0.0")])
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertEqual(report["symlink_integrity"]["issues"], [])

    def test_registration_gap_is_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=False)
            _make_plugin(root, "ghost", "1.0.0", skills=False)  # not in marketplace
            _marketplace(root, [("alpha", "1.0.0")])
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertIn("ghost", str(report["registration"]))
            self.assertGreaterEqual(report["summary"]["drift_items"], 1)

    def test_context_files_informational_not_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=False)
            _marketplace(root, [("alpha", "1.0.0")])
            _write(root / "AGENTS.md", "# r\n")
            _write(root / "CLAUDE.md", "@AGENTS.md\n")
            # plugin has no per-plugin AGENTS/CLAUDE — must NOT add drift
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertEqual(report["summary"]["drift_items"], 0)

    def test_report_is_json_serializable(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            _marketplace(root, [("alpha", "1.0.0")])
            report = rs.run_scan(root, today=date(2026, 7, 7))
            json.loads(json.dumps(report, default=str))


class TestRepoScanCost(unittest.TestCase):

    def _project(self, root: Path) -> None:
        _write(root / "README.md", "# repo\n" + "x" * 4000)
        _write(root / "scripts" / "helper.py", "# helper\nprint('hi')\n")
        _write(root / "data" / "config.json", "{}\n")

    def test_estimate_only_is_cost_only_and_stat_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = rs.cli_main(["--project-dir", str(root), "--estimate-only"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(set(payload), {"cost"})
            self.assertEqual(payload["cost"]["files"], 3)

    def test_normal_run_includes_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = rs.cli_main(["--project-dir", str(root), "--today", "2026-07-07"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertIn("cost", payload)
            self.assertIn("summary", payload)


if __name__ == "__main__":
    unittest.main()
