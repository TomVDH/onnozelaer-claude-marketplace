"""Tests for adjudant/scripts/_vault_walk.py."""

import tempfile
import unittest
from pathlib import Path

from _vault_walk import (
    Frontmatter,
    Wikilink,
    ProjectContext,
    parse_frontmatter,
    extract_wikilinks,
    extract_inline_tags,
    extract_markdown_md_links,
    walk_project,
    build_vault_index,
    resolve_wikilink,
    parse_breadcrumb,
    resolve_vault,
    resolve_project_from_cwd,
    smart_project_dir,
    VaultUnresolvableError,
    is_bucket_d_tag,
    is_bucket_b_migration,
    BUCKET_A_TYPES,
    BUCKET_B_MIGRATIONS,
)


# ============================================================
# parse_frontmatter
# ============================================================


class TestParseFrontmatter(unittest.TestCase):

    def test_simple_frontmatter(self):
        text = "---\ntype: note\ntitle: Hello\n---\n\nBody here."
        fm, body = parse_frontmatter(text)
        self.assertTrue(fm.has_block)
        self.assertEqual(fm.fields["type"], "note")
        self.assertEqual(fm.fields["title"], "Hello")
        self.assertEqual(body, "\nBody here.")
        self.assertIsNone(fm.parse_error)

    def test_no_frontmatter(self):
        text = "Just body, no frontmatter."
        fm, body = parse_frontmatter(text)
        self.assertFalse(fm.has_block)
        self.assertEqual(fm.fields, {})
        self.assertEqual(body, text)

    def test_missing_closing_delimiter(self):
        text = "---\ntype: note\nno closing delim follows"
        fm, body = parse_frontmatter(text)
        self.assertFalse(fm.has_block)
        self.assertIsNotNone(fm.parse_error)

    def test_quoted_value(self):
        text = '---\ntitle: "Hello: with colon"\nproject: \'simple-quoted\'\n---\n'
        fm, _ = parse_frontmatter(text)
        self.assertEqual(fm.fields["title"], "Hello: with colon")
        self.assertEqual(fm.fields["project"], "simple-quoted")

    def test_null_value_preserved_as_string(self):
        # Per vault-standards §1: `null` is drift (should omit the key).
        # The parser preserves the literal so drift detection can flag it.
        text = "---\ncodename: null\nstatus: active\n---\n"
        fm, _ = parse_frontmatter(text)
        self.assertEqual(fm.fields["codename"], "null")
        self.assertEqual(fm.fields["status"], "active")

    def test_list_value(self):
        text = "---\ntags:\n  - note\n  - decision\n  - ob/doc\n---\n"
        fm, _ = parse_frontmatter(text)
        self.assertEqual(fm.fields["tags"], ["note", "decision", "ob/doc"])

    def test_empty_value_becomes_None(self):
        text = "---\ncodename:\nstatus: active\n---\n"
        fm, _ = parse_frontmatter(text)
        self.assertIsNone(fm.fields["codename"])

    def test_comment_skipped(self):
        text = "---\n# this is a comment\ntype: note\n---\n"
        fm, _ = parse_frontmatter(text)
        self.assertEqual(fm.fields, {"type": "note"})

    def test_piped_wikilink_value_kept_raw(self):
        text = '---\nproject: "[[projects/hubspot-nightly/brief|hubspot-nightly]]"\n---\n'
        fm, _ = parse_frontmatter(text)
        self.assertEqual(fm.fields["project"], "[[projects/hubspot-nightly/brief|hubspot-nightly]]")


# ============================================================
# extract_wikilinks
# ============================================================


class TestExtractWikilinks(unittest.TestCase):

    def test_simple(self):
        body = "Refer to [[my-note]] for details."
        links = extract_wikilinks(body)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].target, "my-note")
        self.assertIsNone(links[0].alias)

    def test_with_alias(self):
        body = "See [[my-note|the note]]."
        links = extract_wikilinks(body)
        self.assertEqual(links[0].target, "my-note")
        self.assertEqual(links[0].alias, "the note")

    def test_escaped_pipe_in_table(self):
        # `[[README\|README]]` is an Obsidian-table escape: target=README, alias=README
        body = "| [[README\\|README]] | description |"
        links = extract_wikilinks(body)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].target, "README")
        self.assertEqual(links[0].alias, "README")

    def test_heading_anchor(self):
        body = "Jump to [[note#Section Two]]."
        links = extract_wikilinks(body)
        self.assertEqual(links[0].target, "note")
        self.assertEqual(links[0].heading, "Section Two")

    def test_inside_fenced_code_block_skipped(self):
        body = (
            "Real [[link-one]]\n"
            "```python\n"
            "x = [[fake-link]]\n"
            "```\n"
            "Real [[link-two]]"
        )
        links = extract_wikilinks(body)
        targets = [l.target for l in links]
        self.assertEqual(targets, ["link-one", "link-two"])

    def test_inside_indented_code_block_skipped(self):
        body = "Real [[a]]\n    x = [[fake]]\n[[b]]"
        links = extract_wikilinks(body)
        targets = [l.target for l in links]
        self.assertEqual(targets, ["a", "b"])

    def test_multiple_on_line(self):
        body = "Compare [[one]] and [[two|the second]]."
        links = extract_wikilinks(body)
        self.assertEqual(len(links), 2)
        self.assertEqual(links[0].target, "one")
        self.assertEqual(links[1].target, "two")
        self.assertEqual(links[1].alias, "the second")

    def test_line_numbers(self):
        body = "first\n[[a]]\nthird\n[[b]]\n"
        links = extract_wikilinks(body)
        self.assertEqual(links[0].line, 2)
        self.assertEqual(links[1].line, 4)


# ============================================================
# extract_inline_tags
# ============================================================


class TestExtractInlineTags(unittest.TestCase):

    def test_simple_tag(self):
        body = "Some text with #cool-tag in it."
        self.assertEqual(extract_inline_tags(body), ["cool-tag"])

    def test_namespaced_tag(self):
        body = "Use #content/seafood-companies for that."
        self.assertEqual(extract_inline_tags(body), ["content/seafood-companies"])

    def test_url_not_a_tag(self):
        body = "Visit https://example.com/page#anchor for more."
        self.assertEqual(extract_inline_tags(body), [])

    def test_inside_code_block_skipped(self):
        body = "Tag #real here.\n```\n#fake\n```\n#also-real"
        tags = extract_inline_tags(body)
        self.assertEqual(set(tags), {"real", "also-real"})

    def test_heading_anchor_not_a_tag(self):
        # `#Section` mid-prose IS sometimes a tag-looking heading anchor.
        # We treat it as a tag — there's no reliable disambiguation; vault
        # convention is heading anchors only appear inside wikilinks.
        body = "See section #Section above."
        self.assertEqual(extract_inline_tags(body), ["Section"])


# ============================================================
# extract_markdown_md_links
# ============================================================


class TestExtractMarkdownMdLinks(unittest.TestCase):

    def test_finds_md_link(self):
        body = "See [the note](path/to/note.md) for context."
        out = extract_markdown_md_links(body)
        self.assertEqual(len(out), 1)
        text, path, line = out[0]
        self.assertEqual(text, "the note")
        self.assertEqual(path, "path/to/note.md")

    def test_ignores_non_md_links(self):
        body = "See [docs](https://example.com) and [image](pic.png)."
        out = extract_markdown_md_links(body)
        self.assertEqual(out, [])

    def test_skips_code_blocks(self):
        body = "Real [a](a.md)\n```\n[fake](fake.md)\n```\n[b](b.md)"
        out = extract_markdown_md_links(body)
        paths = [p for _, p, _ in out]
        self.assertEqual(paths, ["a.md", "b.md"])


# ============================================================
# walk_project
# ============================================================


class TestWalkProject(unittest.TestCase):

    def _make_project(self, tmp: Path) -> None:
        (tmp / "brief.md").write_text(
            "---\ntype: project\nslug: test\n---\n\n# Test\n\nBody."
        )
        (tmp / "decisions").mkdir()
        (tmp / "decisions" / "2026-05-26-decide.md").write_text(
            "---\ntype: decision\n---\n\n## Decision\n\nDo X."
        )
        (tmp / "sessions").mkdir()
        (tmp / "sessions" / "2026-05-26.md").write_text(
            "---\ntype: session\n---\n\n## Log\n\n- 10:00 start"
        )
        # _legacy should be skipped by default
        (tmp / "_legacy").mkdir()
        (tmp / "_legacy" / "old.md").write_text(
            "---\ntype: doc\n---\n\nLegacy."
        )
        # .git should be skipped
        (tmp / ".git").mkdir()
        (tmp / ".git" / "ignored.md").write_text("# ignored")

    def test_skips_legacy_and_git_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            files = list(walk_project(root))
            rels = sorted(str(f.rel_path) for f in files)
            self.assertEqual(rels, [
                "brief.md",
                "decisions/2026-05-26-decide.md",
                "sessions/2026-05-26.md",
            ])

    def test_include_legacy_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            files = list(walk_project(root, include_legacy=True))
            rels = sorted(str(f.rel_path) for f in files)
            self.assertIn("_legacy/old.md", rels)
            self.assertNotIn(".git/ignored.md", rels)

    def test_frontmatter_parsed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._make_project(root)
            files = list(walk_project(root))
            briefs = [f for f in files if f.rel_path.name == "brief.md"]
            self.assertEqual(len(briefs), 1)
            self.assertEqual(briefs[0].frontmatter.fields["type"], "project")
            self.assertEqual(briefs[0].file_type, "project")

    def test_tags_collected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "note.md").write_text(
                "---\ntype: note\ntags:\n  - alpha\n  - beta\n---\n\n"
                "Body with #inline-tag."
            )
            files = list(walk_project(root))
            self.assertEqual(set(files[0].tags), {"alpha", "beta", "inline-tag"})


# ============================================================
# build_vault_index + resolve_wikilink
# ============================================================


class TestVaultIndex(unittest.TestCase):

    def test_resolves_relative_and_bare(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "projects").mkdir()
            (vault / "projects" / "x").mkdir()
            (vault / "projects" / "x" / "brief.md").write_text("# brief")
            idx = build_vault_index(vault)
            # Relative path with extension
            self.assertTrue(resolve_wikilink("projects/x/brief.md", idx))
            # Without extension
            self.assertTrue(resolve_wikilink("projects/x/brief", idx))
            # Bare basename
            self.assertTrue(resolve_wikilink("brief", idx))
            # Non-existent
            self.assertFalse(resolve_wikilink("does/not/exist", idx))

    def test_canvas_indexed(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            (vault / "art.canvas").write_text("{}")
            idx = build_vault_index(vault)
            self.assertTrue(resolve_wikilink("art.canvas", idx))
            self.assertTrue(resolve_wikilink("art", idx))


# ============================================================
# breadcrumb + vault resolution
# ============================================================


class TestBreadcrumb(unittest.TestCase):

    def test_parse_breadcrumb(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "adjudant").write_text(
                "vault_path: /v\nvault_name: v\nslug: x\nmode: project\n"
            )
            bc = parse_breadcrumb(root)
            self.assertEqual(bc["slug"], "x")
            self.assertEqual(bc["vault_path"], "/v")

    def test_resolve_vault_via_breadcrumb(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as vault:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "adjudant").write_text(
                f"vault_path: {vault}\nvault_name: v\nslug: x\nmode: project\n"
            )
            resolved = resolve_vault(root)
            self.assertEqual(resolved, Path(vault))

    def test_resolve_vault_via_walk_up_to_home_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp) / "vault"
            vault.mkdir()
            (vault / "Home.md").write_text("---\ntype: vault-home\n---\n# Home\n")
            (vault / "projects").mkdir()
            (vault / "projects" / "x").mkdir()
            self.assertEqual(resolve_vault(vault / "projects" / "x"), vault.resolve())

    def test_resolve_vault_env_override(self):
        with tempfile.TemporaryDirectory() as tmp, tempfile.TemporaryDirectory() as vault:
            self.assertEqual(resolve_vault(Path(tmp), env_vault=vault), Path(vault))


# ============================================================
# Schema constants + Bucket D classification
# ============================================================


class TestBucketDClassification(unittest.TestCase):

    def test_ob_prefix_is_bucket_d(self):
        self.assertTrue(is_bucket_d_tag("ob/doc"))
        self.assertTrue(is_bucket_d_tag("ob/session"))
        self.assertTrue(is_bucket_d_tag("ob/project"))

    def test_cabinet_prefix_drops_unless_bucket_b(self):
        # Other cabinet/* — drop
        self.assertTrue(is_bucket_d_tag("cabinet/random"))
        self.assertTrue(is_bucket_d_tag("cabinet/old"))
        # Bucket B migration sources — NOT Bucket D (they survive via migration)
        self.assertFalse(is_bucket_d_tag("cabinet/decision"))
        self.assertFalse(is_bucket_d_tag("cabinet/recon"))

    def test_vague_topicals_dropped(self):
        for t in ["architecture", "frontend", "moc", "scheduler"]:
            self.assertTrue(is_bucket_d_tag(t), f"{t} should be Bucket D")

    def test_crew_names_dropped(self):
        for t in ["bostrol", "kevijntje", "jonasty"]:
            self.assertTrue(is_bucket_d_tag(t))

    def test_project_type_tag_dropped(self):
        self.assertTrue(is_bucket_d_tag("type/coding"))
        self.assertTrue(is_bucket_d_tag("type/plugin"))

    def test_project_slug_self_tag_dropped(self):
        self.assertTrue(is_bucket_d_tag("hubspot-nightly", project_slug="hubspot-nightly"))
        # slug-variant: "slug/sub"
        self.assertTrue(is_bucket_d_tag("hubspot-nightly/sub", project_slug="hubspot-nightly"))
        # slug-variant: "slug-suffix"
        self.assertTrue(is_bucket_d_tag("hubspot-nightly-thing", project_slug="hubspot-nightly"))
        # unrelated tag with no slug context
        self.assertFalse(is_bucket_d_tag("project"))  # Bucket A

    def test_bucket_a_passes_through(self):
        for t in ["decision", "session", "note", "project"]:
            self.assertFalse(is_bucket_d_tag(t))

    def test_bucket_b_migration_lookup(self):
        self.assertEqual(is_bucket_b_migration("cabinet/decision"), "decision")
        self.assertEqual(is_bucket_b_migration("cabinet/recon"), "recon-item")
        self.assertIsNone(is_bucket_b_migration("cabinet/random"))
        self.assertIsNone(is_bucket_b_migration("project"))


# ============================================================
# Inline-code wikilink skip (regression: false positive in release notes)
# ============================================================


class TestInlineCodeSkip(unittest.TestCase):

    def test_wikilink_inside_backticks_skipped(self):
        body = "Rewrite `[[stem|text]]` to the canonical form."
        links = extract_wikilinks(body)
        self.assertEqual(links, [])

    def test_wikilink_outside_backticks_kept(self):
        body = "Real [[link]] here."
        links = extract_wikilinks(body)
        self.assertEqual(len(links), 1)
        self.assertEqual(links[0].target, "link")

    def test_mixed_inline_code_and_real_link(self):
        body = "Use `[[code-example]]` but see [[real-link]]."
        links = extract_wikilinks(body)
        self.assertEqual([l.target for l in links], ["real-link"])

    def test_tag_inside_backticks_skipped(self):
        body = "Use `#sample-tag` as literal; real tag is #real-tag."
        tags = extract_inline_tags(body)
        self.assertEqual(tags, ["real-tag"])

    def test_md_link_inside_backticks_skipped(self):
        body = "Don't link `[a](b.md)` from inside code; do link [c](c.md) outside."
        out = extract_markdown_md_links(body)
        paths = [p for _, p, _ in out]
        self.assertEqual(paths, ["c.md"])


# ============================================================
# Breadcrumb auto-follow (smart_project_dir + resolve_project_from_cwd)
# ============================================================


class TestSmartProjectDir(unittest.TestCase):

    def test_passes_through_when_no_breadcrumb(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No .claude/adjudant — should treat arg as the vault project itself
            scan_dir, vault_hint = smart_project_dir(tmp)
            self.assertEqual(scan_dir, Path(tmp).resolve())
            self.assertIsNone(vault_hint)

    def test_follows_breadcrumb_to_vault_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = Path(tmp) / "code"; code.mkdir()
            vault = Path(tmp) / "vault"; vault.mkdir()
            (vault / "projects").mkdir()
            (vault / "projects" / "p").mkdir()
            (code / ".claude").mkdir()
            (code / ".claude" / "adjudant").write_text(
                f"vault_path: {vault}\nvault_name: vault\nslug: p\nmode: project\n"
            )
            scan_dir, vault_hint = smart_project_dir(str(code))
            self.assertEqual(scan_dir.resolve(), (vault / "projects" / "p").resolve())
            self.assertEqual(vault_hint.resolve(), vault.resolve())

    def test_raises_when_breadcrumb_present_but_vault_unresolvable(self):
        # Regression: this used to fall through and return the CODE REPO as the
        # scan dir, letting write-path verbs (tidy apply) rewrite the repository.
        with tempfile.TemporaryDirectory() as tmp:
            code = Path(tmp) / "code"; code.mkdir()
            (code / ".claude").mkdir()
            (code / ".claude" / "adjudant").write_text(
                f"vault_path: {tmp}/does-not-exist\nvault_name: no-such-vault\nslug: p\nmode: project\n"
            )
            with self.assertRaises(VaultUnresolvableError):
                smart_project_dir(str(code))


class TestResolveProjectFromCwd(unittest.TestCase):

    def test_returns_context_when_breadcrumb_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = Path(tmp) / "code"; code.mkdir()
            vault = Path(tmp) / "vault"; vault.mkdir()
            (vault / "projects" / "p").mkdir(parents=True)
            (code / ".claude").mkdir()
            (code / ".claude" / "adjudant").write_text(
                f"vault_path: {vault}\nvault_name: vault\nslug: p\nmode: project\n"
            )
            ctx = resolve_project_from_cwd(code)
            self.assertIsNotNone(ctx)
            self.assertEqual(ctx.slug, "p")
            self.assertTrue(ctx.is_connected)

    def test_returns_none_without_breadcrumb(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(resolve_project_from_cwd(Path(tmp)))


# ============================================================
# Vault-name cross-machine resolution
# ============================================================


class TestVaultNameResolution(unittest.TestCase):

    def test_vault_name_resolves_when_abs_path_fails(self):
        """If breadcrumb's vault_path is missing/wrong but vault_name matches a
        standard-location vault, resolve_vault should still find it."""
        with tempfile.TemporaryDirectory() as tmp:
            from unittest.mock import patch

            home = Path(tmp)
            (home / "Documents").mkdir()
            vault = home / "Documents" / "MyVault"
            vault.mkdir()

            code = home / "code"; code.mkdir()
            (code / ".claude").mkdir()
            # Absolute path is bogus, vault_name should rescue
            (code / ".claude" / "adjudant").write_text(
                "vault_path: /nope/missing\nvault_name: MyVault\nslug: p\nmode: project\n"
            )

            with patch("pathlib.Path.home", return_value=home):
                resolved = resolve_vault(code)
            self.assertEqual(resolved.resolve(), vault.resolve())


if __name__ == "__main__":
    unittest.main()
