# /adjudant board

Scaffold a self-hosted **work-order kanban board** for the linked project. The
board is a single, dependency-free `board.html` (drag a card between stages; it
auto-saves to disk via the File System Access API on Chromium, with a
localStorage mirror) driven by a sibling `board-data.json`.

It is a *view*: cards carry short ids and mono `ref ·` tags that cross-link your
own codes (specs, handoffs, commits). Category colour is data-driven — names get
OKLCH palette hues by index, or supply explicit `{ "name": "oklch(...)" }`.

## The 3 features (locked spec)

1. **Scaffold** — `board.py scaffold` writes `board-data.json` (the deck) + a
   self-contained `board.html` (template with the deck injected between its
   `BOARD_DATA` markers). Default dest is `{vault}/projects/{slug}/board/`; pass
   `--dest` to target a code repo (e.g. `<repo>/_docs/board`).
2. **Seed from tasks** — `--from-tasks` builds cards from `{project}/tasks/*.md`:
   `code`/`id`/filename → card id, first `# heading`/`title:` → title,
   `status:` → column, `category:`/first non-`task` tag → category,
   `related:` → mono refs, `note:` → note.
3. **Serve** — `board.py serve --dir DIR` runs a localhost static server so the
   disk-save (File System Access API) works (it needs a secure context, not
   `file://`).

## Run

```bash
# scaffold from the project's tasks/ into the vault project
python3 "$(dirname "$0")/../../../scripts/board.py" scaffold --project-dir "$PROJECT_ROOT" --from-tasks

# or target a code repo and reuse an existing deck verbatim
python3 .../scripts/board.py scaffold --project-dir "$PROJECT_ROOT" \
  --dest "$REPO/_docs/board" --data "$REPO/_docs/board/board-data.json" --title "My Board"

# serve it (background), then open http://localhost:8787/board.html
python3 .../scripts/board.py serve --dir "$DEST" --port 8787
```

Then present the board: start `serve` in the background, open the URL, and tell
the user they can drag cards + hit **connect file** to enable disk auto-save.

## Data model (`board-data.json`)

```json
{
  "title": "My Board", "subtitle": "Work-order board", "updated": "2026-06-24",
  "columns": [{ "id": "backlog", "name": "Backlog" }, ...],
  "categories": ["build", "docs", "infra"],
  "cards": [{ "id": "X-01", "title": "...", "column": "backlog",
              "category": "build", "related": ["SPEC-001"], "notes": "" }]
}
```

`done` and `icebox` columns get `BUILT` / `PARKED` rubber-stamp overprints. A
re-scaffold (new `updated:` or card count) supersedes stale browser state.

## Idempotency

- `board-data.json` is **kept** if it already exists (your card moves survive a
  re-scaffold) unless `--force` or `--data` is passed.
- `board.html` is always refreshed from the template — edits to the template /
  styling land on the next `board` run.

## Fail conditions

- No breadcrumb at cwd → exit non-zero with "run `/adjudant connect` first".
- Template missing / `BOARD_DATA` markers absent → exit non-zero (don't emit a
  half-written board).

## What board does NOT do

- No live sync to GitHub issues / Jira / a database — the JSON is the source of truth.
- No multi-user/server backend — single-file, local, disk-or-browser persistence.
- No auto-status-writeback to `tasks/` notes (seeding is one-way: `tasks/` → board).
