"""Smoke tests for the bash hooks (session-start.sh / sessionend.sh).

Cross-machine parity regressions: legacy `key=value` breadcrumbs and
`~`-prefixed vault paths must resolve (they used to silently no-op).
"""

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks" / "scripts"


def _run(script: str, project: Path, home: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["HOME"] = str(home)
    env.pop("CLAUDE_PLUGIN_ROOT", None)  # exercise the pure-bash path
    return subprocess.run(
        ["bash", str(HOOKS / script)],
        env=env, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=10,
    )


class TestSessionStartHook(unittest.TestCase):

    def _project(self, tmp: Path, breadcrumb: str) -> tuple[Path, Path]:
        home = tmp / "home"
        project = tmp / "code"
        vault = home / "vault"
        (vault / "projects" / "demo").mkdir(parents=True)
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "adjudant").write_text(breadcrumb.format(vault=vault))
        return project, home

    def test_colon_breadcrumb_resolves(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._project(Path(tmp), "vault_path: {vault}\nslug: demo\n")
            r = _run("session-start.sh", project, home)
            self.assertEqual(r.returncode, 0)
            self.assertIn("Vault:", r.stdout)

    def test_legacy_equals_breadcrumb_resolves(self):
        # Pre-v0.4.0 `key=value` — the Python hooks accepted it, bash did not.
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._project(Path(tmp), "vault_path={vault}\nslug=demo\n")
            r = _run("session-start.sh", project, home)
            self.assertEqual(r.returncode, 0)
            self.assertIn("Vault:", r.stdout)

    def test_tilde_vault_path_expands(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._project(Path(tmp), "vault_path: ~/vault\nslug: demo\n")
            r = _run("session-start.sh", project, home)
            self.assertEqual(r.returncode, 0)
            self.assertIn("Vault:", r.stdout)

    def test_stale_vault_path_silently_noops(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._project(Path(tmp), "vault_path: /nope/nowhere\nslug: demo\n")
            r = _run("session-start.sh", project, home)
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, "")  # no context block, no crash


class TestSessionEndHook(unittest.TestCase):

    def test_stale_vault_never_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"; home.mkdir()
            project = Path(tmp) / "code"
            (project / ".claude").mkdir(parents=True)
            (project / ".claude" / "adjudant").write_text(
                f"vault_path: {tmp}/gone/vault\nslug: demo\n")
            r = _run("sessionend.sh", project, home)
            self.assertEqual(r.returncode, 0)
            self.assertFalse((Path(tmp) / "gone").exists())

    def test_tilde_vault_appends_session_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            sessions = home / "vault" / "projects" / "demo" / "sessions"
            sessions.mkdir(parents=True)
            from datetime import date
            session_file = sessions / f"{date.today().isoformat()}.md"
            session_file.write_text("## Log\n")
            project = Path(tmp) / "code"
            (project / ".claude").mkdir(parents=True)
            (project / ".claude" / "adjudant").write_text("vault_path: ~/vault\nslug: demo\n")
            r = _run("sessionend.sh", project, home)
            self.assertEqual(r.returncode, 0)
            self.assertIn("session ended", session_file.read_text())


if __name__ == "__main__":
    unittest.main()
