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


if __name__ == "__main__":
    unittest.main()
