"""Tests for hooks/scripts/precompact.py — the PreCompact/SessionEnd hook.

Regression focus: the hook must fail closed on a stale/cross-machine breadcrumb
instead of materializing a phantom vault directory chain via mkdir(parents=True).
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks" / "scripts"))
import precompact


class TestFailClosedOnStaleVault(unittest.TestCase):

    def _breadcrumb(self, project: Path, vault_path: str, slug: str = "demo") -> None:
        (project / ".claude").mkdir(parents=True)
        (project / ".claude" / "adjudant").write_text(
            f"vault_path: {vault_path}\nvault_name: vault\nslug: {slug}\nmode: project\n"
        )

    def test_stale_vault_path_creates_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "code"
            phantom = Path(tmp) / "gone" / "vault"  # does not exist
            self._breadcrumb(project, str(phantom))
            (project / ".remember").mkdir()
            (project / ".remember" / "remember.md").write_text("NEXT: something\n")

            os.environ["CLAUDE_PROJECT_DIR"] = str(project)
            try:
                rc = precompact.main()
            finally:
                del os.environ["CLAUDE_PROJECT_DIR"]

            self.assertEqual(rc, 0)  # hook never blocks
            self.assertFalse(phantom.exists(),
                             "stale vault path must NOT be materialized by the hook")

    def test_real_vault_still_gets_handoff_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp) / "code"
            vault = Path(tmp) / "vault"
            (vault / "projects" / "demo").mkdir(parents=True)
            self._breadcrumb(project, str(vault))
            (project / ".remember").mkdir()
            (project / ".remember" / "remember.md").write_text("body\n\nNEXT: keep going\n")

            os.environ["CLAUDE_PROJECT_DIR"] = str(project)
            argv_before = sys.argv
            sys.argv = ["precompact.py", "--sync-only"]
            try:
                rc = precompact.main()
            finally:
                sys.argv = argv_before
                del os.environ["CLAUDE_PROJECT_DIR"]

            self.assertEqual(rc, 0)
            handoff = vault / "projects" / "demo" / "_handoff.md"
            self.assertTrue(handoff.is_file(), "handoff mirror must be written for a real vault")
            self.assertIn("NEXT: keep going", handoff.read_text())


if __name__ == "__main__":
    unittest.main()
