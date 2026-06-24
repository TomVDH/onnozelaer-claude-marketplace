#!/usr/bin/env python3
"""Adjudant board — scaffold a self-hosted work-order kanban board for a project.

Generates `board-data.json` (the deck) + a self-contained `board.html`
(drag-to-move, auto-saves to disk via the File System Access API). The deck can
be seeded from the vault project's `tasks/*.md` notes, from an existing
`board-data.json`, or left as an empty 6-stage starter.

The board is a *view*: cards carry short ids and mono `ref` tags that cross-link
your own codes (specs, handoffs, commits). Category colour is data-driven —
names get palette hues by index, or supply explicit `{name: oklch(...)}`.

CLI:
    python3 board.py scaffold --project-dir PATH [--dest DIR] [--from-tasks]
                              [--data board-data.json] [--title STR] [--force]
    python3 board.py serve --dir DIR [--port 8787]

`scaffold` is idempotent: it never clobbers an existing `board-data.json`
unless `--force`; `board.html` is always refreshed from the template.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Optional

from _vault_walk import parse_frontmatter, smart_project_dir

TEMPLATE = Path(__file__).resolve().parent.parent / "skills" / "adjudant" / "templates" / "board.html"
MARK_RE = re.compile(r"/\*BOARD_DATA_START\*/.*?/\*BOARD_DATA_END\*/", re.DOTALL)

DEFAULT_COLUMNS = [
    {"id": "backlog", "name": "Backlog"},
    {"id": "next", "name": "Next"},
    {"id": "doing", "name": "Doing"},
    {"id": "review", "name": "Review"},
    {"id": "done", "name": "Done"},
    {"id": "icebox", "name": "Icebox"},
]
# task status (lower-cased) -> board column
STATUS_TO_COLUMN = {
    "backlog": "backlog", "todo": "backlog", "planned": "backlog", "proposed": "backlog",
    "next": "next", "ready": "next", "queued": "next",
    "doing": "doing", "in-progress": "doing", "in_progress": "doing", "active": "doing", "wip": "doing",
    "review": "review", "blocked": "review", "in-review": "review",
    "done": "done", "complete": "done", "completed": "done", "implemented": "done", "shipped": "done", "accepted": "done",
    "icebox": "icebox", "deferred": "icebox", "parked": "icebox", "shelved": "icebox", "someday": "icebox",
}


def _first_heading(body: str) -> Optional[str]:
    for line in body.split("\n"):
        s = line.strip()
        if s.startswith("# "):
            return s[2:].strip()
    return None


def _as_list(val: Any) -> list[str]:
    if val is None:
        return []
    items = val if isinstance(val, list) else [val]
    out = []
    for it in items:
        s = str(it).strip()
        # strip wikilink form [[target|alias]] / [[target]] -> alias or target
        m = re.match(r"^\[\[([^\]]+)\]\]$", s)
        if m:
            inner = m.group(1)
            s = inner.split("|", 1)[1] if "|" in inner else inner
        if s:
            out.append(s)
    return out


def cards_from_tasks(project_dir: Path) -> list[dict[str, Any]]:
    """Build cards from `{project}/tasks/*.md` frontmatter + first heading."""
    tasks = project_dir / "tasks"
    if not tasks.is_dir():
        return []
    cards: list[dict[str, Any]] = []
    for f in sorted(tasks.iterdir()):
        if not f.is_file() or f.suffix != ".md" or f.name == "_index.md":
            continue
        fm, body = parse_frontmatter(f.read_text(errors="replace"))
        fields = fm.fields
        status = str(fields.get("status", "") or "").strip().lower()
        category = fields.get("category")
        if not category:
            tags = _as_list(fields.get("tags"))
            category = next((t for t in tags if t not in ("task", "tasks")), None)
        cards.append({
            "id": str(fields.get("code") or fields.get("id") or f.stem),
            "title": fields.get("title") or _first_heading(body) or f.stem,
            "column": STATUS_TO_COLUMN.get(status, "backlog"),
            "category": category or "task",
            "related": _as_list(fields.get("related")),
            "notes": str(fields.get("note") or ""),
        })
    return cards


def build_deck(project_dir: Path, *, from_tasks: bool, title: str) -> dict[str, Any]:
    cards = cards_from_tasks(project_dir) if from_tasks else []
    cats: list[str] = []
    for c in cards:
        if c["category"] and c["category"] not in cats:
            cats.append(c["category"])
    if not cats:
        cats = ["build", "docs", "infra", "chore"]
    return {"title": title, "updated": "", "columns": DEFAULT_COLUMNS, "categories": cats, "cards": cards}


def emit_html(deck: dict[str, Any], dest_html: Path) -> None:
    if not TEMPLATE.is_file():
        raise FileNotFoundError(f"board template missing: {TEMPLATE}")
    tpl = TEMPLATE.read_text()
    payload = "/*BOARD_DATA_START*/" + json.dumps(deck, indent=2) + "/*BOARD_DATA_END*/"
    if not MARK_RE.search(tpl):
        raise ValueError("template has no BOARD_DATA markers")
    out = MARK_RE.sub(lambda _m: payload, tpl, count=1)
    dest_html.write_text(out)


def cmd_scaffold(args: argparse.Namespace) -> int:
    project_dir, _hint = smart_project_dir(args.project_dir)
    if not project_dir.is_dir():
        print(f"error: project-dir not found: {project_dir} (run /adjudant connect first)", file=sys.stderr)
        return 1
    dest = Path(args.dest).expanduser() if args.dest else (project_dir / "board")
    dest.mkdir(parents=True, exist_ok=True)
    data_path = dest / "board-data.json"

    if args.data:
        deck = json.loads(Path(args.data).expanduser().read_text())
        deck.setdefault("columns", DEFAULT_COLUMNS)
        deck.setdefault("categories", ["build", "docs", "infra", "chore"])
        deck.setdefault("cards", [])
        if args.title:
            deck["title"] = args.title
        data_path.write_text(json.dumps(deck, indent=2) + "\n")
    elif data_path.is_file() and not args.force:
        deck = json.loads(data_path.read_text())  # keep the user's card state
    else:
        title = args.title or project_dir.name.replace("-", " ").title()
        deck = build_deck(project_dir, from_tasks=args.from_tasks, title=title)
        data_path.write_text(json.dumps(deck, indent=2) + "\n")

    emit_html(deck, dest / "board.html")
    print(f"[board] {dest}/board.html  ({len(deck.get('cards', []))} cards, {len(deck.get('columns', []))} stages)", file=sys.stderr)
    print(f"[board] serve: python3 {Path(__file__).name} serve --dir \"{dest}\"  → http://localhost:8787/board.html", file=sys.stderr)
    print(str(dest / "board.html"))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    import functools
    import http.server
    import socketserver
    directory = str(Path(args.dir).expanduser())
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    with socketserver.TCPServer(("127.0.0.1", args.port), handler) as httpd:
        print(f"[board] serving {directory} at http://localhost:{args.port}/board.html (Ctrl-C to stop)", file=sys.stderr)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[board] stopped", file=sys.stderr)
    return 0


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="board.py", description="Adjudant board — scaffold/serve a work-order kanban board.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sc = sub.add_parser("scaffold", help="write board-data.json + a self-contained board.html")
    sc.add_argument("--project-dir", default=".", help="project root (breadcrumb-resolved; default cwd)")
    sc.add_argument("--dest", help="output dir (default: {project}/board)")
    sc.add_argument("--from-tasks", action="store_true", help="seed cards from {project}/tasks/*.md")
    sc.add_argument("--data", help="use this board-data.json as the deck (verbatim)")
    sc.add_argument("--title", help="board title")
    sc.add_argument("--force", action="store_true", help="overwrite an existing board-data.json")
    sc.set_defaults(func=cmd_scaffold)

    sv = sub.add_parser("serve", help="serve a board dir over localhost (so disk-save works)")
    sv.add_argument("--dir", required=True, help="board dir to serve")
    sv.add_argument("--port", type=int, default=8787)
    sv.set_defaults(func=cmd_serve)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(cli_main())
