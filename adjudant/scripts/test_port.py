"""Tests for adjudant/scripts/port.py."""

import tempfile
import unittest
from pathlib import Path

from port import detect_flavor


class TestDetectFlavor(unittest.TestCase):
    def test_raw_repo_returns_x(self):
        """An empty project dir (no breadcrumb, no AGENTS.md) is flavor X."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(detect_flavor(Path(tmp)), "X")

    def test_preview_dir_present_returns_preview(self):
        """If .adjudant-port-preview/ exists, flavor is 'preview' (phase 2)."""
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".adjudant-port-preview").mkdir()
            self.assertEqual(detect_flavor(Path(tmp)), "preview")

    def test_applied_state_returns_applied(self):
        """Backup dir + compliant project (breadcrumb + AGENTS.md starting with project header) → 'applied'."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".adjudant-port-backup").mkdir()
            (root / ".claude").mkdir()
            (root / ".claude" / "adjudant").write_text("vault_path: /tmp/v\nvault_name: v\nslug: x\nmode: project\n")
            (root / "AGENTS.md").write_text("# Test Project\n\n`x` · type: `coding` · vault: [[projects/x/brief|x]]\n")
            (root / "CLAUDE.md").write_text("@AGENTS.md\n\n# Claude-specific overrides\n")
            self.assertEqual(detect_flavor(root), "applied")

    def test_obsidian_bridge_breadcrumb_returns_y(self):
        """If .claude/obsidian-bridge breadcrumb exists, flavor is Y."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "obsidian-bridge").write_text("vault: /tmp/v\nslug: legacy-proj\n")
            self.assertEqual(detect_flavor(root), "Y")

    def test_hand_authored_agents_md_returns_z(self):
        """AGENTS.md with non-template content (no .claude/obsidian-bridge) is Z."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(
                "# My Custom Project\n\n## Stack\n- Node 22, pnpm\n\n## Conventions\n- Tabs not spaces\n"
            )
            self.assertEqual(detect_flavor(root), "Z")

    def test_template_shaped_agents_md_returns_x(self):
        """An AGENTS.md whose content matches the template (placeholders intact) is NOT Z; falls through to X."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Mirror first line of templates/AGENTS.md
            (root / "AGENTS.md").write_text(
                "# {Project Name}\n\n`{slug}` · type: `{coding|knowledge|plugin|tinkerage}` · vault: [[projects/{slug}/brief|{slug}]]\n\n> One-line purpose of this project.\n"
            )
            self.assertEqual(detect_flavor(root), "X")


import os
from port import resolve_vault_path


class TestResolveVaultPath(unittest.TestCase):
    def test_ob_vault_env_var_wins(self):
        """OB_VAULT env var is preferred over any other resolution path."""
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["OB_VAULT"] = tmp
            try:
                self.assertEqual(resolve_vault_path(Path("/nonexistent")), Path(tmp))
            finally:
                del os.environ["OB_VAULT"]

    def test_existing_adjudant_breadcrumb_returns_its_vault(self):
        """If .claude/adjudant breadcrumb exists, its vault_path field is used."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as vault:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "adjudant").write_text(
                f"vault_path: {vault}\nvault_name: v\nslug: x\nmode: project\n"
            )
            self.assertEqual(resolve_vault_path(root), Path(vault))

    def test_ob_breadcrumb_returns_its_vault(self):
        """For Y case: read vault from .claude/obsidian-bridge breadcrumb."""
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as vault:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "obsidian-bridge").write_text(
                f"vault: {vault}\nslug: legacy-proj\n"
            )
            self.assertEqual(resolve_vault_path(root), Path(vault))

    def test_walk_up_finds_home_md_with_vault_home_frontmatter(self):
        """If parent dir contains Home.md with `type: vault-home` frontmatter, that dir is the vault."""
        with tempfile.TemporaryDirectory() as parent:
            vault_root = Path(parent)
            (vault_root / "Home.md").write_text("---\ntype: vault-home\n---\n\n# Vault\n")
            child = vault_root / "projects" / "myproject"
            child.mkdir(parents=True)
            self.assertEqual(resolve_vault_path(child), vault_root)

    def test_none_returned_when_unresolvable(self):
        """No env var, no breadcrumbs, no Home.md anywhere up → returns None."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(resolve_vault_path(Path(tmp)))


from port import parse_markdown_sections


class TestParseMarkdownSections(unittest.TestCase):
    def test_simple_two_section_file(self):
        text = "# Title\n\nIntro\n\n## Working tree\n\nThis folder\n\n## Stack\n\nNode 22\n"
        sections = parse_markdown_sections(text)
        self.assertEqual(set(sections.keys()), {"working tree", "stack"})
        self.assertIn("This folder", sections["working tree"])
        self.assertIn("Node 22", sections["stack"])

    def test_headings_are_case_insensitive(self):
        text = "## WORKING TREE\n\nfoo\n## stack\n\nbar\n"
        sections = parse_markdown_sections(text)
        self.assertEqual(set(sections.keys()), {"working tree", "stack"})

    def test_h3_headings_also_captured(self):
        text = "## Top\n\n### Subheading\n\ncontent\n"
        sections = parse_markdown_sections(text)
        self.assertIn("top", sections)
        self.assertIn("subheading", sections)

    def test_empty_text_returns_empty_dict(self):
        self.assertEqual(parse_markdown_sections(""), {})


if __name__ == "__main__":
    unittest.main()
