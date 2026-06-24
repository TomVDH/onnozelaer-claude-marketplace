"""Tests for adjudant/scripts/board.py."""

import json
import tempfile
import unittest
from pathlib import Path

from board import (
    STATUS_TO_COLUMN,
    _as_list,
    _first_heading,
    build_deck,
    cards_from_tasks,
    emit_html,
)


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


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
