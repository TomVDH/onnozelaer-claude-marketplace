"""Tests for adjudant/scripts/board.py."""

import json
import tempfile
import unittest
from pathlib import Path

from board import (
    DECK_VERSION,
    STATUS_TO_COLUMN,
    _as_list,
    _first_heading,
    build_deck,
    cards_from_tasks,
    emit_html,
    enumerate_projects,
    merge_deck,
    scaffold_one,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


def _make_project(root: Path, slug: str, *, brief: bool = True) -> Path:
    """A minimal vault project dir under {root}/projects/{slug}."""
    p = root / "projects" / slug
    p.mkdir(parents=True, exist_ok=True)
    if brief:
        _write(p / "brief.md", f"---\ntype: project\nproject_type: coding\n---\n# {slug}\n")
    return p


class TestHelpers(unittest.TestCase):

    def test_as_list_forms(self):
        self.assertEqual(_as_list(None), [])
        self.assertEqual(_as_list("SPEC-1"), ["SPEC-1"])
        self.assertEqual(_as_list(["a", "b"]), ["a", "b"])

    def test_as_list_strips_wikilinks(self):
        self.assertEqual(_as_list("[[2026-06-09-canon|Form canon]]"), ["Form canon"])
        self.assertEqual(_as_list("[[SPEC-012]]"), ["SPEC-012"])

    def test_first_heading(self):
        self.assertEqual(_first_heading("intro\n# Title here\nmore"), "Title here")
        self.assertIsNone(_first_heading("no heading at all"))

    def test_status_mapping(self):
        self.assertEqual(STATUS_TO_COLUMN["in-progress"], "doing")
        self.assertEqual(STATUS_TO_COLUMN["shipped"], "done")
        self.assertEqual(STATUS_TO_COLUMN["deferred"], "icebox")


class TestCardsFromTasks(unittest.TestCase):

    def test_maps_frontmatter_to_card(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(
                root / "tasks" / "cf-03.md",
                "---\ncode: CF-03\nstatus: doing\ncategory: provisioner\n"
                "related:\n  - \"[[SPEC-012]]\"\nnote: a note\n---\n\n# De-hardcode engine\n",
            )
            _write(root / "tasks" / "_index.md", "# idx")  # skipped
            cards = cards_from_tasks(root)
            self.assertEqual(len(cards), 1)
            c = cards[0]
            self.assertEqual(c["id"], "CF-03")
            self.assertEqual(c["column"], "doing")
            self.assertEqual(c["category"], "provisioner")
            self.assertEqual(c["related"], ["SPEC-012"])
            self.assertEqual(c["title"], "De-hardcode engine")
            self.assertEqual(c["notes"], "a note")

    def test_category_falls_back_to_tag(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "tasks" / "x.md", "---\nstatus: todo\ntags:\n  - task\n  - infra\n---\n# X\n")
            card = cards_from_tasks(root)[0]
            self.assertEqual(card["category"], "infra")
            self.assertEqual(card["column"], "backlog")  # unknown/todo -> backlog

    def test_no_tasks_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(cards_from_tasks(Path(tmp)), [])

    def test_skips_type_tasks_roadmap_file(self):
        # a `type: tasks` roadmap/index file must NOT become a card (the
        # real-vault oz-floer shape) — only per-card task notes do.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "tasks" / "tasks.md", "---\ntype: tasks\nproject: oz\n---\n# Roadmap\n- [ ] a\n")
            _write(root / "tasks" / "real.md", "---\ncode: R-1\nstatus: doing\n---\n# Real card\n")
            cards = cards_from_tasks(root)
            self.assertEqual([c["id"] for c in cards], ["R-1"])


class TestDeckFields(unittest.TestCase):

    def test_build_deck_emits_standard_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = build_deck(Path(tmp) / "my-proj", from_tasks=False, title="My Proj")
            self.assertEqual(deck["version"], DECK_VERSION)
            self.assertEqual(deck["boardId"], "my-proj")  # defaults to dir name
            self.assertEqual(deck["subtitle"], "Work-order board")
            self.assertTrue(deck["updated"])  # stamped with a date
            self.assertEqual(deck["title"], "My Proj")

    def test_build_deck_board_id_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = build_deck(Path(tmp) / "x", from_tasks=False, title="T", board_id="slug-9")
            self.assertEqual(deck["boardId"], "slug-9")


class TestEnumerateProjects(unittest.TestCase):

    def test_filesystem_truth_skips_underscore_and_briefless(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_project(root, "beta")
            _make_project(root, "alpha")
            (root / "projects" / "_portfolio").mkdir(parents=True)       # underscore → skip
            (root / "projects" / ".obsidian").mkdir(parents=True)        # dot → skip
            (root / "projects" / "scratch").mkdir(parents=True)          # no brief → skip
            _write(root / "projects" / "_index.md", "# idx")
            got = [slug for slug, _ in enumerate_projects(root)]
            self.assertEqual(got, ["alpha", "beta"])  # sorted, real only

    def test_tolerant_of_malformed_index(self):
        # discovery is filesystem-based; a messy _index.md never affects it.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_project(root, "a")
            _write(
                root / "projects" / "_index.md",
                "| Project |\n|---|\n| [[projects/ghost/brief|ghost]] |\n"
                "| [[b/brief\\|b]] |\n| — |\n",
            )
            self.assertEqual([s for s, _ in enumerate_projects(root)], ["a"])

    def test_no_projects_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(enumerate_projects(Path(tmp)), [])


class TestMergeDeck(unittest.TestCase):

    def _deck(self, cards, **kw):
        d = {"version": 1, "boardId": "p", "title": "P", "subtitle": "s",
             "updated": "2026-01-01", "columns": [], "categories": [], "cards": cards}
        d.update(kw)
        return d

    def test_preserves_dragged_column(self):
        existing = self._deck([{"id": "X-1", "title": "old", "column": "done", "category": "build", "notes": ""}])
        fresh = self._deck([{"id": "X-1", "title": "new", "column": "backlog", "category": "build", "notes": ""}])
        out = merge_deck(existing, fresh)
        card = out["cards"][0]
        self.assertEqual(card["column"], "done")   # drag state preserved
        self.assertEqual(card["title"], "new")     # task-owned field re-seeded

    def test_adds_new_task_card(self):
        existing = self._deck([{"id": "X-1", "column": "doing", "category": "build", "notes": ""}])
        fresh = self._deck([
            {"id": "X-1", "column": "backlog", "category": "build", "notes": ""},
            {"id": "X-2", "column": "next", "category": "docs", "notes": ""},
        ])
        out = merge_deck(existing, fresh)
        by_id = {c["id"]: c for c in out["cards"]}
        self.assertEqual(by_id["X-1"]["column"], "doing")   # preserved
        self.assertEqual(by_id["X-2"]["column"], "next")    # new, task-derived

    def test_orphan_goes_to_icebox_not_deleted(self):
        existing = self._deck([{"id": "X-9", "column": "done", "category": "build", "notes": "keep"}])
        fresh = self._deck([{"id": "X-1", "column": "backlog", "category": "build", "notes": ""}])
        out = merge_deck(existing, fresh)
        by_id = {c["id"]: c for c in out["cards"]}
        self.assertIn("X-9", by_id)
        self.assertEqual(by_id["X-9"]["column"], "icebox")
        self.assertEqual(by_id["X-9"]["notes"], "keep")

    def test_preserves_board_title_and_local_notes(self):
        existing = self._deck([{"id": "X-1", "column": "doing", "category": "b", "notes": "my annotation"}],
                              title="Custom Title")
        fresh = self._deck([{"id": "X-1", "column": "backlog", "category": "b", "notes": ""}],
                           title="Auto Title")
        out = merge_deck(existing, fresh)
        self.assertEqual(out["title"], "Custom Title")           # deck title preserved
        self.assertEqual(out["cards"][0]["notes"], "my annotation")  # local note preserved


class TestScaffoldOne(unittest.TestCase):

    def _seed_tasks(self, proj, specs):
        for fname, fm in specs.items():
            _write(proj / "tasks" / fname, fm)

    def test_merge_refresh_without_clobber_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"
            self._seed_tasks(proj, {
                "t1.md": "---\ncode: T-1\nstatus: backlog\ncategory: build\n---\n# One\n",
                "t2.md": "---\ncode: T-2\nstatus: next\ncategory: docs\n---\n# Two\n",
            })
            dest = proj / "board"
            rc = scaffold_one(proj, dest, from_tasks=True, data=None, force=False, title=None, board_id="proj")
            self.assertEqual(rc, 0)
            data_path = dest / "board-data.json"
            deck = json.loads(data_path.read_text())
            self.assertEqual({c["id"]: c["column"] for c in deck["cards"]},
                             {"T-1": "backlog", "T-2": "next"})

            # user drags T-1 to doing
            deck["cards"][0]["column"] = "doing"
            data_path.write_text(json.dumps(deck))

            # tasks change: T-2 removed, T-3 added, T-1 retitled
            (proj / "tasks" / "t2.md").unlink()
            self._seed_tasks(proj, {
                "t1.md": "---\ncode: T-1\nstatus: backlog\ncategory: build\n---\n# One renamed\n",
                "t3.md": "---\ncode: T-3\nstatus: review\ncategory: build\n---\n# Three\n",
            })
            rc = scaffold_one(proj, dest, from_tasks=True, data=None, force=False, title=None, board_id="proj")
            self.assertEqual(rc, 0)
            deck = json.loads(data_path.read_text())
            by_id = {c["id"]: c for c in deck["cards"]}
            self.assertEqual(by_id["T-1"]["column"], "doing")          # drag preserved
            self.assertEqual(by_id["T-1"]["title"], "One renamed")     # task-owned re-seed
            self.assertEqual(by_id["T-2"]["column"], "icebox")         # orphan parked
            self.assertEqual(by_id["T-3"]["column"], "review")         # new card
            self.assertTrue((dest / "board.html").is_file())

    def test_force_rebuild_discards_drag_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"
            self._seed_tasks(proj, {"t1.md": "---\ncode: T-1\nstatus: backlog\n---\n# One\n"})
            dest = proj / "board"
            scaffold_one(proj, dest, from_tasks=True, data=None, force=False, title=None, board_id="proj")
            data_path = dest / "board-data.json"
            deck = json.loads(data_path.read_text())
            deck["cards"][0]["column"] = "done"
            data_path.write_text(json.dumps(deck))
            scaffold_one(proj, dest, from_tasks=True, data=None, force=True, title=None, board_id="proj")
            deck = json.loads(data_path.read_text())
            self.assertEqual(deck["cards"][0]["column"], "backlog")    # reset to status

    def test_empty_tasks_yields_starter_deck(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"
            (proj).mkdir(parents=True)
            dest = proj / "board"
            rc = scaffold_one(proj, dest, from_tasks=True, data=None, force=False, title=None, board_id="proj")
            self.assertEqual(rc, 0)
            deck = json.loads((dest / "board-data.json").read_text())
            self.assertEqual(deck["cards"], [])
            self.assertIn("build", deck["categories"])

    def test_without_from_tasks_keeps_existing_deck(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "proj"
            dest = proj / "board"
            dest.mkdir(parents=True)
            (dest / "board-data.json").write_text(json.dumps(
                {"title": "Keep", "cards": [{"id": "K-1", "column": "doing"}], "columns": [], "categories": []}))
            scaffold_one(proj, dest, from_tasks=False, data=None, force=False, title=None, board_id="proj")
            deck = json.loads((dest / "board-data.json").read_text())
            self.assertEqual(deck["title"], "Keep")
            self.assertEqual(deck["cards"][0]["column"], "doing")
            self.assertEqual(deck["boardId"], "proj")   # backfilled


class TestBuildDeck(unittest.TestCase):

    def test_empty_deck_has_default_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            deck = build_deck(Path(tmp), from_tasks=False, title="T")
            self.assertEqual(deck["title"], "T")
            self.assertEqual(deck["cards"], [])
            self.assertEqual(len(deck["columns"]), 6)
            self.assertIn("build", deck["categories"])

    def test_categories_derived_from_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "tasks" / "a.md", "---\nstatus: done\ncategory: form\n---\n# A\n")
            _write(root / "tasks" / "b.md", "---\nstatus: next\ncategory: spec\n---\n# B\n")
            deck = build_deck(root, from_tasks=True, title="T")
            self.assertEqual(set(deck["categories"]), {"form", "spec"})
            self.assertEqual(len(deck["cards"]), 2)


class TestEmitHtml(unittest.TestCase):

    def test_injects_deck_between_markers(self):
        deck = {"title": "Z", "columns": [], "categories": ["x"], "cards": [{"id": "Q-1"}]}
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "board.html"
            emit_html(deck, out)
            html = out.read_text()
            self.assertIn("BOARD_DATA_START", html)
            self.assertIn("Q-1", html)
            # the injected JSON is parseable back out
            start = html.index("/*BOARD_DATA_START*/") + len("/*BOARD_DATA_START*/")
            end = html.index("/*BOARD_DATA_END*/")
            self.assertEqual(json.loads(html[start:end])["title"], "Z")


if __name__ == "__main__":
    unittest.main()
