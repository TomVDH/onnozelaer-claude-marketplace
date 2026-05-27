"""Tests for adjudant/scripts/dream.py."""

import json
import tempfile
import unittest
from pathlib import Path

from dream import (
    detect_broken_wikilinks,
    detect_doc_decision_flags,
    detect_folder_drift,
    detect_frontmatter_drift,
    detect_index_gaps,
    detect_naming_violations,
    detect_tag_drift,
    detect_type_drift,
    detect_wikilink_form_violations,
    run_dream,
)
from _vault_walk import build_vault_index, walk_project


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_minimal_project(root: Path, slug: str = "test", project_type: str = "coding", extra_folders=None) -> None:
    """Standard adjudant project skeleton for tests."""
    ef = extra_folders or []
    ef_block = "extra_folders:\n" + "".join(f"  - {x}\n" for x in ef) if ef else ""
    _write_file(root / "brief.md", (
        "---\n"
        "type: project\n"
        f"project_type: {project_type}\n"
        f"slug: {slug}\n"
        f"{ef_block}"
        "tags:\n  - project\n"
        "---\n\n# Test Project\n"
    ))
    _write_file(root / "_handoff.md", "---\ntype: handoff\nupdated: 2026-05-26\n---\n\nbody")
    (root / "sessions").mkdir()
    (root / "images").mkdir()


# ============================================================
# Folder drift
# ============================================================


class TestDetectFolderDrift(unittest.TestCase):

    def test_no_drift_when_only_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            (root / "decisions").mkdir()
            (root / "notes").mkdir()
            drift = detect_folder_drift(root, "coding", [])
            self.assertEqual(drift, [])

    def test_unexpected_folder_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            (root / "weird-folder").mkdir()
            drift = detect_folder_drift(root, "coding", [])
            self.assertEqual(drift, ["weird-folder"])

    def test_extra_folders_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root, extra_folders=["memory", "gemini"])
            (root / "memory").mkdir()
            (root / "gemini").mkdir()
            drift = detect_folder_drift(root, "coding", ["memory", "gemini"])
            self.assertEqual(drift, [])

    def test_auto_created_folders_allowed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            (root / "dreams").mkdir()
            (root / "canvases").mkdir()
            drift = detect_folder_drift(root, "coding", [])
            self.assertEqual(drift, [])

    def test_dotted_folders_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            (root / ".obsidian").mkdir()
            (root / ".trash").mkdir()
            drift = detect_folder_drift(root, "coding", [])
            self.assertEqual(drift, [])


# ============================================================
# Index gaps
# ============================================================


class TestDetectIndexGaps(unittest.TestCase):

    def test_two_siblings_no_index_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "memory" / "a.md", "---\ntype: note\n---\n\na")
            _write_file(root / "memory" / "b.md", "---\ntype: note\n---\n\nb")
            files = list(walk_project(root))
            gaps = detect_index_gaps(root, files)
            self.assertEqual(gaps, ["memory"])

    def test_index_present_no_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "memory" / "a.md", "---\ntype: note\n---\n\na")
            _write_file(root / "memory" / "b.md", "---\ntype: note\n---\n\nb")
            _write_file(root / "memory" / "_index.md", "---\ntype: index\n---\n# Memory")
            files = list(walk_project(root))
            self.assertEqual(detect_index_gaps(root, files), [])

    def test_exempt_folders_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "sessions" / "2026-05-26.md", "---\ntype: session\n---\n")
            _write_file(root / "sessions" / "2026-05-27.md", "---\ntype: session\n---\n")
            files = list(walk_project(root))
            self.assertEqual(detect_index_gaps(root, files), [])

    def test_single_file_no_gap(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "notes" / "lone.md", "---\ntype: note\n---\n")
            files = list(walk_project(root))
            self.assertEqual(detect_index_gaps(root, files), [])


# ============================================================
# Frontmatter drift
# ============================================================


class TestDetectFrontmatterDrift(unittest.TestCase):

    def test_null_value_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "x.md", "---\ntype: note\ncodename: null\n---\n\nbody")
            files = list(walk_project(root))
            drift = detect_frontmatter_drift(files)
            self.assertEqual(len(drift), 1)
            self.assertIn("codename", drift[0]["issue"])

    def test_missing_frontmatter_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "MEMORY.md", "Just body, no frontmatter")
            files = list(walk_project(root))
            drift = detect_frontmatter_drift(files)
            self.assertEqual(len(drift), 1)
            self.assertIn("missing frontmatter", drift[0]["issue"])


# ============================================================
# Tag drift
# ============================================================


class TestDetectTagDrift(unittest.TestCase):

    def test_ob_prefix_counted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "a.md", "---\ntype: doc\ntags:\n  - ob/doc\n  - ob/api-ref\n---\n")
            _write_file(root / "b.md", "---\ntype: doc\ntags:\n  - ob/doc\n---\n")
            files = list(walk_project(root))
            drift = detect_tag_drift(files, project_slug="test")
            self.assertEqual(drift["bucket_d_total_occurrences"], 3)
            self.assertIn("ob/doc", dict(drift["bucket_d_top"]))

    def test_bucket_b_migrations_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "a.md", "---\ntype: decision\ntags:\n  - cabinet/decision\n---\n")
            files = list(walk_project(root))
            drift = detect_tag_drift(files, project_slug="test")
            self.assertIn("cabinet/decision", drift["bucket_b_migrations_needed"])

    def test_project_slug_tag_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "a.md", "---\ntype: note\ntags:\n  - hubspot-nightly\n---\n")
            files = list(walk_project(root))
            drift = detect_tag_drift(files, project_slug="hubspot-nightly")
            self.assertIn("hubspot-nightly", drift["bucket_d_by_category"].get("project_slug", []))


# ============================================================
# Type drift
# ============================================================


class TestDetectTypeDrift(unittest.TestCase):

    def test_canonical_types_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "a.md", "---\ntype: note\n---\n")
            _write_file(root / "b.md", "---\ntype: decision\n---\n")
            files = list(walk_project(root))
            self.assertEqual(detect_type_drift(files)["non_canonical_count"], 0)

    def test_non_canonical_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "a.md", "---\ntype: api-ref\n---\n")
            _write_file(root / "b.md", "---\ntype: dream\n---\n")  # should be dream-report
            _write_file(root / "c.md", "---\ntype: api-ref\n---\n")
            files = list(walk_project(root))
            drift = detect_type_drift(files)
            self.assertEqual(drift["non_canonical_count"], 3)
            self.assertEqual(drift["values"]["api-ref"]["count"], 2)


# ============================================================
# Naming violations
# ============================================================


class TestDetectNamingViolations(unittest.TestCase):

    def test_lowercase_doc_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "lowercase-name.md", "---\ntype: doc\n---\n")
            files = list(walk_project(root))
            v = detect_naming_violations(files)
            self.assertTrue(any("UPPERCASE" in x["issue"] for x in v))

    def test_uppercase_doc_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "STANDARDS.md", "---\ntype: doc\n---\n")
            files = list(walk_project(root))
            self.assertEqual(detect_naming_violations(files), [])

    def test_decision_without_date_prefix_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "decisions" / "no-date.md", "---\ntype: decision\n---\n")
            files = list(walk_project(root))
            v = detect_naming_violations(files)
            self.assertTrue(any("YYYY-MM-DD-" in x["issue"] for x in v))

    def test_session_with_trailing_kebab_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "sessions" / "2026-05-26-extra.md", "---\ntype: session\n---\n")
            files = list(walk_project(root))
            v = detect_naming_violations(files)
            self.assertTrue(any("session" in x["issue"].lower() for x in v))


# ============================================================
# Wikilink form + broken
# ============================================================


class TestDetectWikilinkFormViolations(unittest.TestCase):

    def test_markdown_link_to_vault_md_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "target.md", "---\ntype: note\n---\n# T")
            _write_file(root / "src.md", "---\ntype: note\n---\n\nSee [target](target.md).")
            files = list(walk_project(root))
            idx = build_vault_index(root)
            v = detect_wikilink_form_violations(files, idx)
            self.assertEqual(len(v), 1)
            self.assertEqual(v[0]["path"], "target.md")

    def test_external_md_link_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "src.md", "---\ntype: note\n---\n\nSee [doc](nonexistent.md).")
            files = list(walk_project(root))
            idx = build_vault_index(root)
            self.assertEqual(detect_wikilink_form_violations(files, idx), [])


class TestDetectBrokenWikilinks(unittest.TestCase):

    def test_counts_broken(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "target.md", "---\ntype: note\n---\n")
            _write_file(root / "src.md",
                "---\ntype: note\n---\n\n"
                "Real: [[target]]\n"
                "Broken: [[no-such-target]]\n"
            )
            files = list(walk_project(root))
            idx = build_vault_index(root)
            result = detect_broken_wikilinks(files, idx)
            self.assertEqual(result["total_wikilinks"], 2)
            self.assertEqual(result["broken_count"], 1)


# ============================================================
# Doc-decision flags
# ============================================================


class TestDetectDocDecisionFlags(unittest.TestCase):

    def test_decision_at_root_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "2026-05-26-misplaced.md", "---\ntype: decision\n---\n")
            files = list(walk_project(root))
            flags = detect_doc_decision_flags(files)
            self.assertEqual(len(flags), 1)


# ============================================================
# End-to-end run_dream
# ============================================================


class TestRunDream(unittest.TestCase):

    def test_clean_project_no_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            (root / "decisions").mkdir()
            _write_file(root / "decisions" / "2026-05-26-test.md", "---\ntype: decision\n---\n")
            _write_file(root / "decisions" / "2026-05-25-test.md", "---\ntype: decision\n---\n")
            _write_file(root / "decisions" / "_index.md", "---\ntype: index\n---\n# Decisions")
            report = run_dream(root, root)
            self.assertEqual(report["meta"]["project_slug"], "test")
            self.assertEqual(report["meta"]["project_type"], "coding")
            self.assertEqual(report["summary"]["drift_items"], 0)

    def test_dirty_project_drift_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            # Add a Bucket D tag
            _write_file(root / "a.md", "---\ntype: note\ntags:\n  - ob/note\n---\n")
            # Add a non-canonical type
            _write_file(root / "b.md", "---\ntype: api-ref\n---\n")
            report = run_dream(root, root)
            self.assertGreater(report["summary"]["drift_items"], 0)
            self.assertGreater(report["tag_drift"]["bucket_d_total_occurrences"], 0)
            self.assertGreater(report["type_drift"]["non_canonical_count"], 0)

    def test_emits_serializable_json(self):
        """The full report must round-trip through json.dumps without errors."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            _write_file(root / "a.md", "---\ntype: note\ntags:\n  - ob/note\n---\n")
            report = run_dream(root, root)
            payload = json.dumps(report, default=str)
            roundtrip = json.loads(payload)
            self.assertEqual(roundtrip["meta"]["project_slug"], "test")


if __name__ == "__main__":
    unittest.main()
