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


from port import map_ob_sections


class TestMapObSections(unittest.TestCase):
    def test_working_tree_maps_to_where_things_live_row(self):
        ob_sections = {"working tree": "/path/to/repo"}
        result = map_ob_sections(ob_sections)
        self.assertIn("/path/to/repo", result["where_things_live_extra_rows"])

    def test_stack_maps_to_conventions(self):
        ob_sections = {"stack": "Node 22, pnpm, Vite"}
        result = map_ob_sections(ob_sections)
        self.assertIn("Node 22, pnpm, Vite", result["conventions"])

    def test_vault_rules_dropped(self):
        ob_sections = {"vault rules": "Use [[Title|Alias]] form"}
        result = map_ob_sections(ob_sections)
        self.assertEqual(result["conventions"], "")
        self.assertEqual(result["where_things_live_extra_rows"], "")
        self.assertIn("vault rules", result["decisions"])
        self.assertIn("DROPPED", result["decisions"])

    def test_claude_instructions_moved_to_claude_md(self):
        ob_sections = {"claude instructions": "Always use /pnpm not /npm"}
        result = map_ob_sections(ob_sections)
        self.assertIn("Always use /pnpm not /npm", result["claude_md_body"])

    def test_what_this_is_preserved(self):
        ob_sections = {"what this is": "A tool that does X."}
        result = map_ob_sections(ob_sections)
        self.assertIn("A tool that does X.", result["what_this_is"])

    def test_unmatched_heading_goes_to_legacy_section(self):
        ob_sections = {"random heading": "Custom note"}
        result = map_ob_sections(ob_sections)
        self.assertIn("Custom note", result["from_legacy"])
        self.assertIn("random heading", result["from_legacy"])

    def test_aliases_work(self):
        ob_sections = {"purpose": "A tool."}
        result = map_ob_sections(ob_sections)
        self.assertIn("A tool.", result["what_this_is"])


from port import render_agents_md


class TestRenderAgentsMd(unittest.TestCase):
    def test_basic_render_has_all_template_sections(self):
        result = render_agents_md(
            project_name="My Project",
            slug="my-project",
            project_type="coding",
            what_this_is="A tool that does X.",
            conventions="Tabs not spaces.",
            where_things_live_extra_rows="",
            from_legacy="",
        )
        self.assertIn("# My Project", result)
        self.assertIn("`my-project` · type: `coding`", result)
        self.assertIn("[[projects/my-project/brief|my-project]]", result)
        self.assertIn("A tool that does X.", result)
        self.assertIn("Tabs not spaces.", result)
        self.assertIn("## What this is", result)
        self.assertIn("## Where things live", result)
        self.assertIn("## Conventions", result)
        self.assertIn("## Vault is canonical", result)

    def test_from_legacy_section_appended_at_end(self):
        result = render_agents_md(
            project_name="P", slug="p", project_type="coding",
            what_this_is="", conventions="",
            where_things_live_extra_rows="",
            from_legacy="### custom\n\nSome content\n",
        )
        self.assertIn("## From legacy AGENTS.md", result)
        self.assertIn("Some content", result)
        self.assertGreater(
            result.index("## From legacy AGENTS.md"),
            result.index("## Vault is canonical"),
        )

    def test_extra_rows_added_to_where_things_live_table(self):
        result = render_agents_md(
            project_name="P", slug="p", project_type="coding",
            what_this_is="", conventions="",
            where_things_live_extra_rows="| Custom path | `/foo/bar` |",
            from_legacy="",
        )
        self.assertIn("| Custom path | `/foo/bar` |", result)
        self.assertIn("| Working tree | (this folder) |", result)


from port import render_breadcrumb


class TestRenderBreadcrumb(unittest.TestCase):
    def test_basic_breadcrumb_format(self):
        result = render_breadcrumb(
            vault_path=Path("/v"),
            vault_name="VaultName",
            slug="my-proj",
            mode="project",
        )
        self.assertIn("vault_path: /v", result)
        self.assertIn("vault_name: VaultName", result)
        self.assertIn("slug: my-proj", result)
        self.assertIn("mode: project", result)


from port import render_claude_md


class TestRenderClaudeMd(unittest.TestCase):
    def test_minimal_render_just_template(self):
        result = render_claude_md(claude_specific_body="")
        self.assertTrue(result.startswith("@AGENTS.md"))
        self.assertIn("Claude-specific overrides", result)

    def test_with_body_inserts_after_template(self):
        result = render_claude_md(claude_specific_body="## Bash allowlist\n\n- npm, pnpm\n")
        self.assertTrue(result.startswith("@AGENTS.md"))
        self.assertIn("## Bash allowlist", result)
        self.assertIn("- npm, pnpm", result)


if __name__ == "__main__":
    unittest.main()
