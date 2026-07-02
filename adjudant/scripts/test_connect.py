"""Tests for adjudant/scripts/connect.py."""

import tempfile
import unittest
from pathlib import Path

from connect import (
    VALID_PROJECT_TYPES,
    append_gitignore,
    count_non_index_files,
    derive_project_name,
    derive_project_type,
    detect_state,
    newest_session_date,
    provision_context_files,
    resolve_vault_for_connect,
    run_connect,
    scaffold_vault_project,
    slug_to_title,
    upsert_projects_index_row,
    validate_slug,
    write_breadcrumb,
    write_session_note,
)


def _w(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _make_vault(tmp: Path) -> Path:
    vault = Path(tmp) / "test-vault"
    vault.mkdir()
    (vault / "Home.md").write_text("---\ntype: vault-home\n---\n# Home\n")
    (vault / "projects").mkdir()
    return vault


# ============================================================
# Slug helpers
# ============================================================


class TestSlugHelpers(unittest.TestCase):

    def test_valid_slugs(self):
        for slug in ["my-project", "abc123", "one"]:
            self.assertIsNone(validate_slug(slug))

    def test_invalid_slugs(self):
        for slug in ["UpperCase", "with space", "-leading", "", "with.dot"]:
            self.assertIsNotNone(validate_slug(slug))

    def test_title_case(self):
        self.assertEqual(slug_to_title("my-cool-project"), "My Cool Project")
        self.assertEqual(slug_to_title("abc"), "Abc")


# ============================================================
# Vault resolution
# ============================================================


class TestResolveVault(unittest.TestCase):

    def test_explicit_path_wins(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"; proj.mkdir()
            vault = Path(tmp) / "vault"; vault.mkdir()
            (vault / "Home.md").write_text("---\ntype: vault-home\n---\n")
            resolved = resolve_vault_for_connect(proj, str(vault), None)
            self.assertEqual(resolved, vault)

    def test_walk_up_for_home_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            (vault / "projects" / "x").mkdir()
            resolved = resolve_vault_for_connect(vault / "projects" / "x", None, None)
            self.assertEqual(resolved.resolve(), vault.resolve())

    def test_ob_vault_env_honored(self):
        """reference/connect.md lists OB_VAULT in the resolution order — the
        function ignored it entirely (regression)."""
        import os
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"; proj.mkdir()
            vault = Path(tmp) / "envvault"; vault.mkdir()
            os.environ["OB_VAULT"] = str(vault)
            try:
                resolved = resolve_vault_for_connect(proj, None, None)
            finally:
                del os.environ["OB_VAULT"]
            self.assertEqual(resolved, vault)

    def test_explicit_path_beats_ob_vault_env(self):
        import os
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"; proj.mkdir()
            env_vault = Path(tmp) / "envvault"; env_vault.mkdir()
            arg_vault = Path(tmp) / "argvault"; arg_vault.mkdir()
            os.environ["OB_VAULT"] = str(env_vault)
            try:
                resolved = resolve_vault_for_connect(proj, str(arg_vault), None)
            finally:
                del os.environ["OB_VAULT"]
            self.assertEqual(resolved, arg_vault)


# ============================================================
# Step 1: breadcrumb
# ============================================================


class TestWriteBreadcrumb(unittest.TestCase):

    def test_writes_correct_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            bc = write_breadcrumb(proj, Path("/v"), "Vault", "my-slug")
            content = bc.read_text()
            self.assertIn("vault_path: /v", content)
            self.assertIn("vault_name: Vault", content)
            self.assertIn("slug: my-slug", content)
            self.assertIn("mode: project", content)


# ============================================================
# Step 2: context files
# ============================================================


class TestProvisionContextFiles(unittest.TestCase):

    def test_creates_if_missing(self):
        # Note: this test uses the real templates dir under adjudant/skills/.../templates
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            result = provision_context_files(proj)
            # If templates exist, both files should be created
            self.assertIn(result["AGENTS.md"], ("created", "template missing"))
            self.assertIn(result["CLAUDE.md"], ("created", "template missing"))

    def test_preserves_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            (proj / "AGENTS.md").write_text("user content")
            (proj / "CLAUDE.md").write_text("user content")
            result = provision_context_files(proj)
            self.assertEqual(result["AGENTS.md"], "preserved")
            self.assertEqual(result["CLAUDE.md"], "preserved")
            self.assertEqual((proj / "AGENTS.md").read_text(), "user content")


# ============================================================
# Step 3: vault scaffold
# ============================================================


class TestScaffoldVaultProject(unittest.TestCase):

    def test_coding_project_creates_default_folders(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            result = scaffold_vault_project(vault, "my-slug", "coding", "My Slug", "2026-05-27")
            proj_dir = vault / "projects" / "my-slug"
            self.assertTrue((proj_dir / "brief.md").is_file())
            for sub in ["decisions", "notes", "tasks", "references", "sessions", "images"]:
                self.assertTrue((proj_dir / sub).is_dir(), f"{sub} missing")
            # Index-required folders have _index.md, exempt ones don't
            self.assertTrue((proj_dir / "decisions" / "_index.md").is_file())
            self.assertFalse((proj_dir / "sessions" / "_index.md").is_file())
            self.assertFalse((proj_dir / "images" / "_index.md").is_file())

    def test_plugin_project_includes_releases(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            scaffold_vault_project(vault, "p", "plugin", "P", "2026-05-27")
            self.assertTrue((vault / "projects" / "p" / "releases").is_dir())
            self.assertTrue((vault / "projects" / "p" / "releases" / "_index.md").is_file())

    def test_brief_has_slug_and_date_substituted(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            scaffold_vault_project(vault, "abc", "coding", "Abc Project", "2026-05-27")
            brief = (vault / "projects" / "abc" / "brief.md").read_text()
            self.assertIn("slug: abc", brief)
            self.assertIn("2026-05-27", brief)
            self.assertIn("# Abc Project", brief)
            # No placeholder leftovers
            self.assertNotIn("{kebab-slug}", brief)
            self.assertNotIn("{YYYY-MM-DD}", brief)

    def test_idempotent_preserves_brief(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            scaffold_vault_project(vault, "abc", "coding", "Abc", "2026-05-27")
            brief_path = vault / "projects" / "abc" / "brief.md"
            brief_path.write_text("USER EDITED")
            scaffold_vault_project(vault, "abc", "coding", "Abc 2", "2026-05-28")
            self.assertEqual(brief_path.read_text(), "USER EDITED")


# ============================================================
# Step 4: session note
# ============================================================


class TestWriteSessionNote(unittest.TestCase):

    def test_creates(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            (vault / "projects" / "x").mkdir()
            r = write_session_note(vault, "x", "2026-05-27", "09:30")
            self.assertEqual(r, "created")
            self.assertTrue((vault / "projects" / "x" / "sessions" / "2026-05-27.md").is_file())

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            write_session_note(vault, "x", "2026-05-27", "09:30")
            r = write_session_note(vault, "x", "2026-05-27", "10:30")
            self.assertEqual(r, "preserved")


# ============================================================
# Step 5: gitignore
# ============================================================


class TestAppendGitignore(unittest.TestCase):

    def test_creates_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = append_gitignore(Path(tmp))
            self.assertEqual(r, "created")
            self.assertIn(".claude/adjudant", (Path(tmp) / ".gitignore").read_text())

    def test_appends_if_missing_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gitignore").write_text("existing\n")
            r = append_gitignore(Path(tmp))
            self.assertEqual(r, "added")
            content = (Path(tmp) / ".gitignore").read_text()
            self.assertIn("existing", content)
            self.assertIn(".claude/adjudant", content)

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".gitignore").write_text(".claude/adjudant\n")
            r = append_gitignore(Path(tmp))
            self.assertEqual(r, "preserved")


# ============================================================
# Step 6: projects/_index.md row upsert
# ============================================================


class TestUpsertProjectsIndexRow(unittest.TestCase):

    def test_creates_index_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            r = upsert_projects_index_row(vault, "x", "coding", "active", 0, 0, "—")
            self.assertEqual(r, "created-index")
            text = (vault / "projects" / "_index.md").read_text()
            self.assertIn("x/brief", text)

    def test_inserts_if_index_exists(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            upsert_projects_index_row(vault, "a", "coding", "active", 0, 0, "—")
            r = upsert_projects_index_row(vault, "b", "plugin", "active", 1, 2, "2026-05-27")
            self.assertEqual(r, "inserted")
            text = (vault / "projects" / "_index.md").read_text()
            self.assertIn("a/brief", text)
            self.assertIn("b/brief", text)

    def test_updates_existing_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = _make_vault(tmp)
            upsert_projects_index_row(vault, "a", "coding", "active", 0, 0, "—")
            r = upsert_projects_index_row(vault, "a", "coding", "active", 5, 10, "2026-05-27")
            self.assertEqual(r, "updated")
            text = (vault / "projects" / "_index.md").read_text()
            # Row contains updated counts + last_session, with wikilink form preserved
            self.assertIn("coding | active | 5 | 10 | 2026-05-27", text)
            # And the old "0 | 0" row is gone
            self.assertNotIn("active | 0 | 0 | —", text)


# ============================================================
# End-to-end run_connect
# ============================================================


class TestRunConnectEndToEnd(unittest.TestCase):

    def test_fresh_connect_produces_all_artefacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "my-project"; proj.mkdir()
            vault = _make_vault(tmp)
            summary = run_connect(
                project_root=proj,
                vault_path=vault,
                vault_name="test-vault",
                slug="my-project",
                project_type="coding",
                project_name="My Project",
                today="2026-05-27",
                now_hhmm="10:00",
            )
            # Breadcrumb
            self.assertTrue((proj / ".claude" / "adjudant").is_file())
            # Vault scaffold
            self.assertTrue((vault / "projects" / "my-project" / "brief.md").is_file())
            self.assertTrue((vault / "projects" / "my-project" / "decisions" / "_index.md").is_file())
            # Session note
            self.assertTrue((vault / "projects" / "my-project" / "sessions" / "2026-05-27.md").is_file())
            # .gitignore
            self.assertIn(".claude/adjudant", (proj / ".gitignore").read_text())
            # Projects index row
            self.assertIn("my-project", (vault / "projects" / "_index.md").read_text())

    def test_reconnect_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "p"; proj.mkdir()
            vault = _make_vault(tmp)
            for _ in range(2):
                run_connect(proj, vault, "v", "p", "coding", "P", "2026-05-27", "10:00")
            self.assertEqual(detect_state(proj, vault, "p"), "connected")


# ============================================================
# Counts + dates
# ============================================================


class TestCounts(unittest.TestCase):

    def test_count_non_index_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "_index.md").write_text("idx")
            (d / "a.md").write_text("a")
            (d / "b.md").write_text("b")
            (d / "c.txt").write_text("c")
            self.assertEqual(count_non_index_files(d), 2)

    def test_newest_session_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for date in ["2026-05-25", "2026-05-27", "2026-05-26"]:
                (d / f"{date}.md").write_text("x")
            self.assertEqual(newest_session_date(d), "2026-05-27")


if __name__ == "__main__":
    unittest.main()
