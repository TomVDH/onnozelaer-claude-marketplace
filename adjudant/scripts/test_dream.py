"""Tests for adjudant/scripts/dream.py."""

import datetime as dt
import json
import tempfile
import unittest
from pathlib import Path

from dream import (
    detect_contradiction_candidates,
    detect_orphan_questions,
    detect_orphan_threads,
    detect_redundancy_clusters,
    detect_stale_refs,
    detect_staleness,
    detect_supersession_signals,
    run_dream,
)
from _vault_walk import build_vault_index, walk_project

TODAY = dt.date(2026, 6, 1)


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_minimal_project(root: Path, slug: str = "test", project_type: str = "coding") -> None:
    _write_file(root / "brief.md", (
        "---\n"
        "type: project\n"
        f"project_type: {project_type}\n"
        f"slug: {slug}\n"
        "tags:\n  - project\n"
        "---\n\n# Test Project\n"
    ))
    _write_file(root / "_handoff.md", "---\ntype: handoff\nupdated: 2026-05-26\n---\n\nbody")
    (root / "sessions").mkdir()
    (root / "images").mkdir()


# ============================================================
# Staleness
# ============================================================


class TestDetectStaleness(unittest.TestCase):

    def test_old_note_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "old.md", "---\ntype: note\nupdated: 2024-01-01\n---\n\nold body line")
            files = list(walk_project(root))
            out = detect_staleness(files, TODAY)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["file"], "old.md")
            self.assertGreater(out[0]["age_days"], 180)
            self.assertIn("old body line", out[0]["excerpt_head"])

    def test_recent_note_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "fresh.md", "---\ntype: note\nupdated: 2026-05-20\n---\n\nfresh")
            files = list(walk_project(root))
            self.assertEqual(detect_staleness(files, TODAY), [])

    def test_filename_date_used_when_no_frontmatter_date(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "sessions" / "2024-02-02.md", "---\ntype: session\n---\n\nlog")
            files = list(walk_project(root))
            out = detect_staleness(files, TODAY)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["type"], "session")

    def test_undateable_file_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "n.md", "---\ntype: note\n---\n\nno date here")
            files = list(walk_project(root))
            self.assertEqual(detect_staleness(files, TODAY), [])


# ============================================================
# Supersession
# ============================================================


class TestDetectSupersession(unittest.TestCase):

    def test_same_topic_decisions_paired(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "decisions" / "2026-01-01-auth-strategy.md",
                        "---\ntype: decision\ndate: 2026-01-01\n---\n\nUse sessions for auth.")
            _write_file(root / "decisions" / "2026-05-01-auth-strategy.md",
                        "---\ntype: decision\ndate: 2026-05-01\n---\n\nUse JWT for auth.")
            files = list(walk_project(root))
            out = detect_supersession_signals(files, TODAY)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["older"]["file"], "decisions/2026-01-01-auth-strategy.md")
            self.assertEqual(out[0]["newer"]["file"], "decisions/2026-05-01-auth-strategy.md")
            self.assertFalse(out[0]["older_has_superseded_marker"])

    def test_unrelated_decisions_not_paired(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "decisions" / "2026-01-01-database-choice.md",
                        "---\ntype: decision\ndate: 2026-01-01\n---\n\nPostgres.")
            _write_file(root / "decisions" / "2026-05-01-styling-approach.md",
                        "---\ntype: decision\ndate: 2026-05-01\n---\n\nTailwind.")
            files = list(walk_project(root))
            self.assertEqual(detect_supersession_signals(files, TODAY), [])

    def test_existing_superseded_marker_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "decisions" / "2026-01-01-cache-layer.md",
                        "---\ntype: decision\ndate: 2026-01-01\nsuperseded: true\n---\n\nRedis cache layer.")
            _write_file(root / "decisions" / "2026-05-01-cache-layer.md",
                        "---\ntype: decision\ndate: 2026-05-01\n---\n\nIn-memory cache layer.")
            files = list(walk_project(root))
            out = detect_supersession_signals(files, TODAY)
            self.assertEqual(len(out), 1)
            self.assertTrue(out[0]["older_has_superseded_marker"])


# ============================================================
# Contradiction
# ============================================================


class TestDetectContradiction(unittest.TestCase):

    def test_change_verb_with_overlap_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "decisions" / "2026-01-01-build-tooling.md",
                        "---\ntype: decision\ndate: 2026-01-01\n---\n\nWe use webpack for build tooling.")
            _write_file(root / "decisions" / "2026-05-01-build-tooling.md",
                        "---\ntype: decision\ndate: 2026-05-01\n---\n\nWe no longer use webpack; switched to vite.")
            files = list(walk_project(root))
            out = detect_contradiction_candidates(files, TODAY)
            self.assertEqual(len(out), 1)
            self.assertTrue(out[0]["a"]["line"] or out[0]["b"]["line"])

    def test_overlap_without_change_verb_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "a-build-tooling.md", "---\ntype: note\n---\n\nNotes about build tooling setup.")
            _write_file(root / "b-build-tooling.md", "---\ntype: note\n---\n\nMore on build tooling config.")
            files = list(walk_project(root))
            self.assertEqual(detect_contradiction_candidates(files, TODAY), [])


# ============================================================
# Redundancy
# ============================================================


class TestDetectRedundancy(unittest.TestCase):

    def test_near_duplicate_notes_clustered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shared = "deployment pipeline runs migrations then restarts workers gracefully always"
            _write_file(root / "notes" / "deploy-a.md", f"---\ntype: note\n---\n\n{shared} alpha")
            _write_file(root / "notes" / "deploy-b.md", f"---\ntype: note\n---\n\n{shared} beta")
            files = list(walk_project(root))
            out = detect_redundancy_clusters(files, TODAY)
            self.assertEqual(len(out), 1)
            self.assertEqual(len(out[0]["files"]), 2)

    def test_distinct_notes_not_clustered(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "notes" / "alpha.md", "---\ntype: note\n---\n\nquantum entanglement physics lecture")
            _write_file(root / "notes" / "beta.md", "---\ntype: note\n---\n\ngardening tomatoes compost watering")
            files = list(walk_project(root))
            self.assertEqual(detect_redundancy_clusters(files, TODAY), [])


# ============================================================
# Stale refs
# ============================================================


class TestDetectStaleRefs(unittest.TestCase):

    def test_archive_ref_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "n.md", "---\ntype: note\n---\n\nSee [[_archive/old-plan]] for history.")
            files = list(walk_project(root))
            out = detect_stale_refs(files, TODAY, vault_index=None)
            self.assertEqual(len(out), 1)
            self.assertIn("archived", out[0]["reason"])

    def test_old_dated_ref_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "n.md", "---\ntype: note\n---\n\nBack in [[2024-01-01]] we decided X.")
            files = list(walk_project(root))
            out = detect_stale_refs(files, TODAY, vault_index=None)
            self.assertEqual(len(out), 1)
            self.assertIn("dated target", out[0]["reason"])

    def test_fresh_ref_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "n.md", "---\ntype: note\n---\n\nSee [[notes/current-plan]].")
            files = list(walk_project(root))
            self.assertEqual(detect_stale_refs(files, TODAY, vault_index=None), [])

    def test_unresolved_skipped_when_index_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "n.md", "---\ntype: note\n---\n\nSee [[_archive/ghost]].")
            files = list(walk_project(root))
            idx = build_vault_index(root)  # ghost doesn't exist → unresolved
            self.assertEqual(detect_stale_refs(files, TODAY, vault_index=idx), [])


# ============================================================
# Orphan questions
# ============================================================


class TestDetectOrphanQuestions(unittest.TestCase):

    def test_old_todo_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "sessions" / "2024-01-01.md",
                        "---\ntype: session\n---\n\n- TODO: decide on the cache eviction policy")
            files = list(walk_project(root))
            out = detect_orphan_questions(files, TODAY)
            self.assertEqual(len(out), 1)
            self.assertIn("cache eviction", out[0]["text"])

    def test_recent_todo_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "sessions" / "2026-05-28.md",
                        "---\ntype: session\n---\n\n- TODO: still fresh")
            files = list(walk_project(root))
            self.assertEqual(detect_orphan_questions(files, TODAY), [])

    def test_code_fence_todo_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "old.md",
                        "---\ntype: note\nupdated: 2024-01-01\n---\n\n```\n# TODO: in code\n```\nclean prose")
            files = list(walk_project(root))
            self.assertEqual(detect_orphan_questions(files, TODAY), [])


# ============================================================
# Orphan threads
# ============================================================


class TestDetectOrphanThreads(unittest.TestCase):

    def test_unlinked_old_note_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "notes" / "lonely.md", "---\ntype: note\nupdated: 2024-01-01\n---\n\nnobody links here")
            files = list(walk_project(root))
            out = detect_orphan_threads(files, TODAY)
            self.assertEqual(len(out), 1)
            self.assertEqual(out[0]["file"], "notes/lonely.md")

    def test_linked_note_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "notes" / "popular.md", "---\ntype: note\nupdated: 2024-01-01\n---\n\nlinked")
            _write_file(root / "hub.md", "---\ntype: doc\n---\n\nSee [[popular]].")
            files = list(walk_project(root))
            self.assertEqual(detect_orphan_threads(files, TODAY), [])

    def test_recent_unlinked_note_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write_file(root / "notes" / "newish.md", "---\ntype: note\nupdated: 2026-05-20\n---\n\nfresh orphan")
            files = list(walk_project(root))
            self.assertEqual(detect_orphan_threads(files, TODAY), [])


# ============================================================
# End-to-end run_dream
# ============================================================


class TestRunDream(unittest.TestCase):

    def test_clean_project_no_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            (root / "decisions").mkdir()
            _write_file(root / "decisions" / "2026-05-20-fresh.md",
                        "---\ntype: decision\ndate: 2026-05-20\n---\n\nrecent decision")
            report = run_dream(root, root, today=TODAY)
            self.assertEqual(report["meta"]["project_slug"], "test")
            self.assertEqual(report["summary"]["candidates"], 0)

    def test_dirty_project_candidates_caught(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            _write_file(root / "stale.md", "---\ntype: note\nupdated: 2023-01-01\n---\n\nold thinking")
            _write_file(root / "sessions" / "2024-01-01.md",
                        "---\ntype: session\n---\n\n- TODO: resolve the open thread")
            report = run_dream(root, root, today=TODAY)
            self.assertGreater(report["summary"]["candidates"], 0)
            self.assertGreater(report["summary"]["staleness"], 0)
            self.assertGreater(report["summary"]["orphan_questions"], 0)

    def test_emits_serializable_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            _write_file(root / "stale.md", "---\ntype: note\nupdated: 2023-01-01\n---\n\nold")
            report = run_dream(root, root, today=TODAY)
            payload = json.dumps(report, default=str)
            roundtrip = json.loads(payload)
            self.assertEqual(roundtrip["meta"]["project_slug"], "test")

    def test_today_override_changes_age(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_minimal_project(root)
            _write_file(root / "n.md", "---\ntype: note\nupdated: 2025-12-01\n---\n\nbody")
            # Far-future today → stale; near today → fresh
            self.assertGreater(run_dream(root, root, today=dt.date(2026, 12, 1))["summary"]["staleness"], 0)
            self.assertEqual(run_dream(root, root, today=dt.date(2025, 12, 15))["summary"]["staleness"], 0)


if __name__ == "__main__":
    unittest.main()
