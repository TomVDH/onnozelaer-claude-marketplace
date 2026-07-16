"""Tests for adjudant/scripts/shelf.py."""

import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from shelf import cli_main as shelf_cli, run_list


def _mk_project(vault: Path, slug: str, zone: str = "", status: str = "active",
                sessions: list = ()) -> Path:
    pdir = vault / "projects" / zone / slug if zone else vault / "projects" / slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "brief.md").write_text(
        f"---\ntype: project\nslug: {slug}\nproject_type: coding\nstatus: {status}\n"
        f"created: 2026-01-01\nupdated: 2026-01-01\ntags:\n  - project\n---\n\n# {slug}\n")
    if sessions:
        (pdir / "sessions").mkdir(exist_ok=True)
        for d in sessions:
            (pdir / "sessions" / f"{d}.md").write_text("---\ntype: session\n---\n")
    return pdir


class TestRunList(unittest.TestCase):

    def test_lists_all_zones_with_suggestions(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "hot", sessions=["2026-07-15"])
            _mk_project(vault, "quiet", sessions=["2026-03-01"])
            _mk_project(vault, "cold", zone="_fridge", status="fridge")
            _mk_project(vault, "shipped", zone="_archive", status="done")
            out = run_list(vault, stale_days=30, today=date(2026, 7, 16))
            rows = {r["slug"]: r for r in out["projects"]}
            self.assertEqual(set(rows), {"hot", "quiet", "cold", "shipped"})
            self.assertIsNone(rows["hot"]["suggested"])
            self.assertEqual(rows["quiet"]["suggested"], "stale")
            self.assertEqual(rows["cold"]["zone"], "_fridge")
            self.assertTrue(rows["cold"]["zone_matches"])
            self.assertTrue(rows["shipped"]["zone_matches"])

    def test_zone_mismatch_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "misfiled", status="dead")  # dead but in living zone
            out = run_list(vault, stale_days=30, today=date(2026, 7, 16))
            self.assertFalse(out["projects"][0]["zone_matches"])


class TestListCli(unittest.TestCase):

    def test_cli_list_via_vault_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "p", sessions=["2026-07-10"])
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = shelf_cli(["list", "--vault-dir", str(vault),
                                "--today", "2026-07-16"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["projects"][0]["slug"], "p")
            self.assertEqual(payload["stale_after_days"], 30)


if __name__ == "__main__":
    unittest.main()
