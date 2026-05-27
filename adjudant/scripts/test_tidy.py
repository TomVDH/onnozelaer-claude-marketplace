"""Tests for adjudant/scripts/tidy.py."""

import json
import tempfile
import unittest
from pathlib import Path

from tidy import (
    PREVIEW_DIR_NAME,
    BACKUP_DIR_NAME,
    apply_preview,
    build_preview,
    detect_phase,
    fix_wikilink_form,
    generate_index_content,
    normalize_tags,
    upsert_index_content,
    write_preview_to_disk,
    _migrate_ob_to_bucket_a,
    _rewrite_tags_block,
    _bump_updated_field,
)
from _vault_walk import build_vault_index


def _w(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


# ============================================================
# Detection
# ============================================================


class TestDetectPhase(unittest.TestCase):

    def test_fresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(detect_phase(Path(tmp)), "fresh")

    def test_preview(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / PREVIEW_DIR_NAME).mkdir()
            self.assertEqual(detect_phase(Path(tmp)), "preview")

    def test_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / BACKUP_DIR_NAME / "20260526T120000Z").mkdir(parents=True)
            (Path(tmp) / BACKUP_DIR_NAME / "20260526T120000Z" / "x.legacy").write_text("old")
            self.assertEqual(detect_phase(Path(tmp)), "applied")


# ============================================================
# Tag normalisation
# ============================================================


class TestNormalizeTags(unittest.TestCase):

    def test_ob_bucket_a_migrates(self):
        # ob/{bucket-A-type} → {bucket-A-type} preserves §2A file-type tag
        new, dropped = normalize_tags(["ob/doc"], project_slug="x")
        self.assertEqual(new, ["doc"])
        self.assertEqual(dropped, ["ob/doc → doc"])

    def test_ob_non_bucket_a_drops(self):
        # ob/api-ref is not Bucket A → drop
        new, dropped = normalize_tags(["ob/api-ref"], project_slug="x")
        self.assertEqual(new, [])
        self.assertEqual(dropped, ["ob/api-ref"])

    def test_ob_dedup_with_existing_bare(self):
        new, _ = normalize_tags(["project", "ob/project"], project_slug="x")
        # ob/project migrates to project, dedup keeps just 'project'
        self.assertEqual(new, ["project"])

    def test_migrates_bucket_b(self):
        new, dropped = normalize_tags(["cabinet/decision"], project_slug="x")
        self.assertEqual(new, ["decision"])
        self.assertEqual(dropped, ["cabinet/decision → decision"])

    def test_drops_project_slug_self_tag(self):
        new, _ = normalize_tags(["hubspot-nightly", "decision"], project_slug="hubspot-nightly")
        self.assertEqual(new, ["decision"])

    def test_dedup(self):
        new, _ = normalize_tags(["a", "a", "b"], project_slug=None)
        self.assertEqual(new, ["a", "b"])

    def test_preserves_unknown(self):
        new, _ = normalize_tags(["content/blog", "auth"], project_slug=None)
        # content/blog is canonical (§2C); 'auth' is uncategorised but not Bucket D
        self.assertIn("content/blog", new)
        self.assertIn("auth", new)


# ============================================================
# Wikilink form fix
# ============================================================


class TestFixWikilinkForm(unittest.TestCase):

    def test_rewrites_resolvable(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _w(vault / "target.md", "x")
            idx = build_vault_index(vault)
            body = "See [target](target.md)."
            new, count = fix_wikilink_form(body, idx)
            self.assertEqual(count, 1)
            self.assertIn("[[target]]", new)

    def test_preserves_alias(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _w(vault / "target.md", "x")
            idx = build_vault_index(vault)
            body = "See [the target](target.md)."
            new, _ = fix_wikilink_form(body, idx)
            self.assertIn("[[target|the target]]", new)

    def test_unresolvable_left_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            idx = build_vault_index(Path(tmp))  # empty vault
            body = "See [target](target.md)."
            new, count = fix_wikilink_form(body, idx)
            self.assertEqual(count, 0)
            self.assertEqual(new, body)

    def test_skips_code_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _w(vault / "target.md", "x")
            idx = build_vault_index(vault)
            body = "Real [target](target.md)\n```\n[fake](target.md)\n```"
            new, count = fix_wikilink_form(body, idx)
            self.assertEqual(count, 1)
            # fenced block content unchanged
            self.assertIn("[fake](target.md)", new)


# ============================================================
# Tags block surgical rewrite
# ============================================================


class TestRewriteTagsBlock(unittest.TestCase):

    def test_replace_existing(self):
        text = "---\ntype: note\ntags:\n  - ob/note\n  - keep\n---\n\nbody"
        new = _rewrite_tags_block(text, ["keep"])
        self.assertIn("tags:\n  - keep", new)
        self.assertNotIn("ob/note", new)
        self.assertIn("body", new)

    def test_empty_tags_removes_block(self):
        text = "---\ntype: note\ntags:\n  - ob/note\n---\n\nbody"
        new = _rewrite_tags_block(text, [])
        self.assertNotIn("tags:", new)

    def test_no_existing_block_adds_when_tags(self):
        text = "---\ntype: note\n---\n\nbody"
        new = _rewrite_tags_block(text, ["new"])
        self.assertIn("tags:\n  - new", new)


class TestBumpUpdatedField(unittest.TestCase):

    def test_bumps_existing(self):
        text = "---\ntype: note\nupdated: 2026-05-01\n---\n\nbody"
        new = _bump_updated_field(text, "2026-05-26")
        self.assertIn("updated: 2026-05-26", new)
        self.assertNotIn("updated: 2026-05-01", new)

    def test_does_not_add(self):
        text = "---\ntype: note\n---\n\nbody"
        new = _bump_updated_field(text, "2026-05-26")
        self.assertNotIn("updated:", new)


# ============================================================
# Index generation
# ============================================================


class TestMigrateObToBucketA(unittest.TestCase):

    def test_bucket_a_migrates(self):
        self.assertEqual(_migrate_ob_to_bucket_a("ob/decision"), "decision")
        self.assertEqual(_migrate_ob_to_bucket_a("ob/doc"), "doc")
        self.assertEqual(_migrate_ob_to_bucket_a("ob/dream-report"), "dream-report")

    def test_non_bucket_a_returns_none(self):
        self.assertIsNone(_migrate_ob_to_bucket_a("ob/api-ref"))
        self.assertIsNone(_migrate_ob_to_bucket_a("ob/gemini"))

    def test_non_ob_prefix_returns_none(self):
        self.assertIsNone(_migrate_ob_to_bucket_a("decision"))
        self.assertIsNone(_migrate_ob_to_bucket_a("cabinet/decision"))


class TestUpsertIndexContent(unittest.TestCase):

    def test_upsert_bullet_list_preserves_intro(self):
        existing = (
            "---\n"
            "type: index\n"
            "tags:\n  - ob/index\n  - architecture\n"
            "updated: 2026-05-01\n"
            "---\n\n"
            "# Decisions\n\n"
            "Intro paragraph that the human wrote. Preserve me.\n\n"
            "## Entries\n\n"
            "- [[old-entry|old]]\n\n"
            "## Notes\n\n"
            "Trailing section. Preserve me too.\n"
        )
        entries = [Path("a.md"), Path("b.md")]
        new, mode = upsert_index_content(existing, "decisions", entries, "x")
        self.assertEqual(mode, "upserted")
        # Intro preserved
        self.assertIn("Intro paragraph that the human wrote", new)
        # Trailing section preserved
        self.assertIn("Trailing section. Preserve me too.", new)
        # New entries
        self.assertIn("[[a|a]]", new)
        self.assertIn("[[b|b]]", new)
        # Old entry gone
        self.assertNotIn("old-entry", new)
        # Tags normalized
        self.assertNotIn("ob/index", new)
        self.assertIn("- index", new)

    def test_upsert_table_format_leaves_body_alone(self):
        existing = (
            "---\n"
            "type: index\n"
            "tags:\n  - ob/index\n"
            "updated: 2026-05-01\n"
            "---\n\n"
            "# Nightly\n\n"
            "## Entries\n\n"
            "| Doc | Purpose |\n"
            "|---|---|\n"
            "| [[architecture]] | system overview |\n"
        )
        new, mode = upsert_index_content(existing, "nightly", [Path("a.md"), Path("b.md")], "x")
        self.assertEqual(mode, "frontmatter_only")
        # Table preserved verbatim
        self.assertIn("| Doc | Purpose |", new)
        self.assertIn("[[architecture]]", new)
        # But tags normalized
        self.assertNotIn("ob/index", new)

    def test_upsert_no_entries_heading_leaves_body_alone(self):
        existing = (
            "---\n"
            "type: index\n"
            "tags:\n  - index\n"
            "updated: 2026-05-01\n"
            "---\n\n"
            "# Some Index\n\n"
            "Free-form content with no entries heading.\n"
        )
        new, mode = upsert_index_content(existing, "x", [Path("a.md"), Path("b.md")], "x")
        self.assertEqual(mode, "frontmatter_only")
        self.assertIn("Free-form content with no entries heading.", new)


class TestGenerateIndexContent(unittest.TestCase):

    def test_chronological_for_dated(self):
        out = generate_index_content("decisions", [
            Path("2026-05-26-a.md"),
            Path("2026-05-27-b.md"),
            Path("2026-05-25-c.md"),
        ], project_slug="x")
        # 2026-05-27 should come first
        lines = out.split("\n")
        entry_lines = [l for l in lines if l.startswith("- [[")]
        self.assertEqual(entry_lines[0], "- [[2026-05-27-b|2026-05-27 b]]")
        self.assertEqual(entry_lines[1], "- [[2026-05-26-a|2026-05-26 a]]")
        self.assertEqual(entry_lines[2], "- [[2026-05-25-c|2026-05-25 c]]")

    def test_alphabetical_for_plain(self):
        out = generate_index_content("notes", [
            Path("zebra.md"),
            Path("alpha.md"),
            Path("mango.md"),
        ], project_slug="x")
        entry_lines = [l for l in out.split("\n") if l.startswith("- [[")]
        self.assertEqual(entry_lines[0], "- [[alpha|alpha]]")
        self.assertEqual(entry_lines[2], "- [[zebra|zebra]]")

    def test_has_frontmatter_and_heading(self):
        out = generate_index_content("decisions", [Path("2026-05-26-a.md")], project_slug="x")
        self.assertTrue(out.startswith("---\n"))
        self.assertIn("type: index", out)
        self.assertIn("# Decisions", out)


# ============================================================
# build_preview end-to-end
# ============================================================


class TestBuildPreview(unittest.TestCase):

    def test_dirty_project_produces_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _w(root / "brief.md",
                "---\ntype: project\nslug: t\nproject_type: coding\nupdated: 2026-05-01\n"
                "tags:\n  - project\n  - ob/project\n---\n\n# T\n")
            # Two decisions, no index
            _w(root / "decisions" / "2026-05-26-a.md", "---\ntype: decision\n---\n")
            _w(root / "decisions" / "2026-05-25-b.md", "---\ntype: decision\n---\n")
            # File with a markdown-style link to a vault file
            _w(root / "target.md", "---\ntype: note\n---\n")
            _w(root / "src.md",
                "---\ntype: note\ntags:\n  - ob/note\n---\n\nSee [target](target.md).")
            vault_index = build_vault_index(root)
            cs = build_preview(root, vault_index, project_slug="t")
            # Should rebuild decisions/_index.md
            self.assertIn("decisions/_index.md", cs["index_proposals"])
            # Should propose changes to src.md (tags + wikilink)
            self.assertIn("src.md", cs["file_proposals"])
            # Should propose changes to brief.md (tags)
            self.assertIn("brief.md", cs["file_proposals"])

    def test_clean_project_no_changes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _w(root / "brief.md",
                "---\ntype: project\nslug: t\nproject_type: coding\n"
                "tags:\n  - project\n---\n\n# T\n")
            _w(root / "_handoff.md", "---\ntype: handoff\n---\nbody")
            cs = build_preview(root, set(), project_slug="t")
            self.assertEqual(cs["summary"]["total_changes"], 0)


# ============================================================
# write_preview + apply_preview round-trip
# ============================================================


class TestPreviewApplyRoundTrip(unittest.TestCase):

    def test_full_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _w(root / "brief.md",
                "---\ntype: project\nslug: t\nproject_type: coding\n"
                "tags:\n  - project\n  - ob/project\n---\n\n# T\n")
            _w(root / "_handoff.md", "---\ntype: handoff\n---\nbody")

            # Phase 1: preview
            self.assertEqual(detect_phase(root), "fresh")
            vault_idx = build_vault_index(root)
            cs = build_preview(root, vault_idx, project_slug="t")
            self.assertGreater(cs["summary"]["total_changes"], 0)
            write_preview_to_disk(root, cs)
            self.assertEqual(detect_phase(root), "preview")
            preview = root / PREVIEW_DIR_NAME
            self.assertTrue((preview / "summary.md").is_file())
            self.assertTrue((preview / "changes.json").is_file())
            self.assertTrue((preview / "files" / "brief.md").is_file())

            # Verify the proposed brief no longer has ob/project
            proposed_brief = (preview / "files" / "brief.md").read_text()
            self.assertNotIn("ob/project", proposed_brief)

            # Phase 2: apply
            backup = apply_preview(root)
            self.assertTrue(backup.is_dir())
            backup_brief = backup / "brief.md.legacy"
            self.assertTrue(backup_brief.is_file())
            # Original brief had ob/project — backup retains it
            self.assertIn("ob/project", backup_brief.read_text())
            # Live brief no longer has it
            live_brief = (root / "brief.md").read_text()
            self.assertNotIn("ob/project", live_brief)
            # Preview gone
            self.assertFalse((root / PREVIEW_DIR_NAME).exists())
            self.assertEqual(detect_phase(root), "applied")

    def test_idempotence(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _w(root / "brief.md",
                "---\ntype: project\nslug: t\nproject_type: coding\n"
                "tags:\n  - project\n---\n\n# T\n")
            _w(root / "_handoff.md", "---\ntype: handoff\n---\nbody")
            # First pass — clean already
            cs = build_preview(root, set(), project_slug="t")
            self.assertEqual(cs["summary"]["total_changes"], 0)


if __name__ == "__main__":
    unittest.main()
