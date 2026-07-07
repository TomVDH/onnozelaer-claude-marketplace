"""Smoke tests for the bash hooks (session-start.sh / sessionend.sh /
user-prompt-reminder.sh).

Cross-machine parity regressions: legacy `key=value` breadcrumbs, `~`-prefixed
vault paths, and CRLF breadcrumbs must resolve identically to the Python hooks
(they used to silently no-op or write to phantom `slug\r/` dirs). Context
claims must be truthful: a failed session-note write must not inject a
'created' line.
"""

import json
import os
import stat
import subprocess
import tempfile
import unittest
from datetime import date
from pathlib import Path

HOOKS = Path(__file__).resolve().parent.parent / "hooks" / "scripts"
PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def _run(
    script: str,
    project: Path,
    home: Path,
    *,
    stdin: str = "",
    plugin_root: bool = False,
    extra_env: dict | None = None,
) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_PROJECT_DIR"] = str(project)
    env["HOME"] = str(home)
    env["TMPDIR"] = str(home)  # keep reminder markers inside the sandbox
    env.pop("OB_VAULT", None)  # ambient override must never leak into tests
    env.pop("ADJUDANT_REMINDER_DISABLE", None)
    if plugin_root:
        env["CLAUDE_PLUGIN_ROOT"] = str(PLUGIN_ROOT)
    else:
        env.pop("CLAUDE_PLUGIN_ROOT", None)  # exercise the pure-bash path
    if extra_env:
        env.update(extra_env)
    return subprocess.run(
        ["bash", str(HOOKS / script)],
        env=env, capture_output=True, text=True,
        input=stdin if stdin else None,
        stdin=None if stdin else subprocess.DEVNULL,
        timeout=15,
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

    def test_crlf_breadcrumb_creates_no_phantom_cr_dir(self):
        # A CRLF breadcrumb (Windows-side edit / sync round-trip) used to leak
        # \r into the slug, creating a phantom `projects/demo\r/` dir while the
        # Python hooks wrote to the real `projects/demo/`.
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._project(
                Path(tmp), "vault_path: {vault}\r\nslug: demo\r\n")
            r = _run("session-start.sh", project, home)
            self.assertEqual(r.returncode, 0)
            self.assertIn("Vault:", r.stdout)
            projects = home / "vault" / "projects"
            self.assertEqual([d.name for d in projects.iterdir()], ["demo"])
            self.assertTrue(
                (projects / "demo" / "sessions" / f"{date.today().isoformat()}.md").is_file())

    def test_failed_write_never_claims_creation(self):
        # Read-only sessions dir: the note can't be written — the context
        # stream must not claim 'Session note created'.
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._project(Path(tmp), "vault_path: {vault}\nslug: demo\n")
            sessions = home / "vault" / "projects" / "demo" / "sessions"
            sessions.mkdir(parents=True)
            sessions.chmod(stat.S_IRUSR | stat.S_IXUSR)  # r-x: no writes
            try:
                r = _run("session-start.sh", project, home)
                self.assertEqual(r.returncode, 0)
                self.assertIn("Vault:", r.stdout)  # context block still injected
                self.assertNotIn("Session note created", r.stdout)
                self.assertNotIn("Session note resumed", r.stdout)
            finally:
                sessions.chmod(stat.S_IRWXU)

    def test_second_start_resumes_not_truncates(self):
        # Same-day second SessionStart must resume (append), never truncate.
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._project(Path(tmp), "vault_path: {vault}\nslug: demo\n")
            r1 = _run("session-start.sh", project, home)
            self.assertIn("Session note created", r1.stdout)
            session_file = (home / "vault" / "projects" / "demo" / "sessions"
                            / f"{date.today().isoformat()}.md")
            session_file.write_text(session_file.read_text() + "- 10:00 · precious entry\n")
            r2 = _run("session-start.sh", project, home)
            self.assertIn("Session note resumed", r2.stdout)
            content = session_file.read_text()
            self.assertIn("precious entry", content)      # first note preserved
            self.assertIn("session resumed", content)

    def test_stale_path_with_vault_name_falls_back_via_resolver(self):
        # Legacy `=` breadcrumb whose absolute path is from the other machine:
        # with the plugin root available, resolve_vault's vault_name step must
        # find the vault under a standard location on THIS machine.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            vault = home / "Documents" / "MyVault"
            (vault / "projects" / "demo").mkdir(parents=True)
            project = Path(tmp) / "code"
            (project / ".claude").mkdir(parents=True)
            (project / ".claude" / "adjudant").write_text(
                "vault_path=/other-machine/vault\nvault_name=MyVault\nslug=demo\n")
            r = _run("session-start.sh", project, home, plugin_root=True)
            self.assertEqual(r.returncode, 0)
            self.assertIn("MyVault", r.stdout)
            self.assertTrue(
                (vault / "projects" / "demo" / "sessions"
                 / f"{date.today().isoformat()}.md").is_file())

    def test_ob_vault_override_in_pure_bash_mode(self):
        # Degraded (no plugin root) mode must still honor OB_VAULT — parity
        # with resolve_vault's step 1.
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._project(Path(tmp), "vault_path: /nope/nowhere\nslug: demo\n")
            override = Path(tmp) / "override-vault"
            (override / "projects" / "demo").mkdir(parents=True)
            r = _run("session-start.sh", project, home,
                     extra_env={"OB_VAULT": str(override)})
            self.assertEqual(r.returncode, 0)
            self.assertIn("override-vault", r.stdout)


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
            session_file = sessions / f"{date.today().isoformat()}.md"
            session_file.write_text("## Log\n")
            project = Path(tmp) / "code"
            (project / ".claude").mkdir(parents=True)
            (project / ".claude" / "adjudant").write_text("vault_path: ~/vault\nslug: demo\n")
            r = _run("sessionend.sh", project, home)
            self.assertEqual(r.returncode, 0)
            self.assertIn("session ended", session_file.read_text())

    def test_midnight_straddle_appends_to_latest_note(self):
        # No note exists for *today* (session started before midnight): the
        # end marker must land in the latest existing daily note, not vanish.
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            sessions = home / "vault" / "projects" / "demo" / "sessions"
            sessions.mkdir(parents=True)
            older = sessions / "2020-01-01.md"
            newer = sessions / "2020-01-02.md"
            decoy = sessions / "abcd-ef-gh.md"  # 4-2-2 shape, not a date
            older.write_text("## Log\n")
            newer.write_text("## Log\n")
            decoy.write_text("## Not a session\n")
            project = Path(tmp) / "code"
            (project / ".claude").mkdir(parents=True)
            (project / ".claude" / "adjudant").write_text("vault_path: ~/vault\nslug: demo\n")
            r = _run("sessionend.sh", project, home)
            self.assertEqual(r.returncode, 0)
            self.assertIn("session ended", newer.read_text())
            self.assertNotIn("session ended", older.read_text())
            self.assertNotIn("session ended", decoy.read_text())  # digit glob


class TestUserPromptReminder(unittest.TestCase):

    def _payload(self, prompt: str, session_id: str = "sess-123") -> str:
        return json.dumps({"session_id": session_id, "prompt": prompt})

    def _unlinked_project(self, tmp: Path) -> tuple[Path, Path]:
        home = tmp / "home"; home.mkdir()
        project = tmp / "code"; project.mkdir()
        return project, home

    def test_fires_on_vaulty_prompt_when_unlinked(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._unlinked_project(Path(tmp))
            r = _run("user-prompt-reminder.sh", project, home,
                     stdin=self._payload("note this decision in the vault"))
            self.assertEqual(r.returncode, 0)
            self.assertIn("Vault not linked", r.stdout)

    def test_silent_on_unrelated_prompt(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._unlinked_project(Path(tmp))
            r = _run("user-prompt-reminder.sh", project, home,
                     stdin=self._payload("fix the css on the landing page"))
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, "")

    def test_silent_when_project_linked(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._unlinked_project(Path(tmp))
            (project / ".claude").mkdir()
            (project / ".claude" / "adjudant").write_text("slug: demo\n")
            r = _run("user-prompt-reminder.sh", project, home,
                     stdin=self._payload("record this in the vault"))
            self.assertEqual(r.returncode, 0)
            self.assertEqual(r.stdout, "")

    def test_fires_once_per_session(self):
        with tempfile.TemporaryDirectory() as tmp:
            project, home = self._unlinked_project(Path(tmp))
            r1 = _run("user-prompt-reminder.sh", project, home,
                      stdin=self._payload("vault please", session_id="s-once"))
            self.assertIn("Vault not linked", r1.stdout)
            r2 = _run("user-prompt-reminder.sh", project, home,
                      stdin=self._payload("vault again", session_id="s-once"))
            self.assertEqual(r2.stdout, "")  # suppressed for the same session
            r3 = _run("user-prompt-reminder.sh", project, home,
                      stdin=self._payload("vault anew", session_id="s-other"))
            self.assertIn("Vault not linked", r3.stdout)  # new session fires


if __name__ == "__main__":
    unittest.main()
