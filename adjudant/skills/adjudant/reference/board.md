# /adjudant board

Scaffold a self-hosted **work-order kanban board** — a *standard project
surface* any adjudant project can have, not a one-off. The board is a single,
dependency-free `board.html` (drag a card between stages; it auto-saves to disk
via the File System Access API on Chromium, with a localStorage mirror) driven
by a sibling `board-data.json`. Each board namespaces its own browser + disk
state by `boardId`, so a portfolio of project boards served from the same
localhost never clobber one another.

It is a *view*: cards carry short ids and mono `ref ·` tags that cross-link your
own codes (specs, handoffs, commits). Category colour is data-driven — names get
OKLCH palette hues by index, or supply explicit `{ "name": "oklch(...)" }`.

## Targeting (which project's board)

| Flag | Board(s) scaffolded |
|---|---|
| *(default)* `--project-dir PATH` | the current breadcrumb-linked project |
| `--project <slug>` | the named project under `{vault}/projects/<slug>` |
| `--all` | one board for **every** project in the vault |

`--project`/`--all` resolve the vault from the cwd breadcrumb (or explicit
`--vault PATH`) and discover projects by **filesystem truth** — every
`{vault}/projects/<slug>/brief.md`, skipping `_`/`.` dirs. The fragile
`projects/_index.md` table is never parsed, so malformed or duplicate rows can't
break discovery. `--all` is error-isolated: one bad project never aborts the batch.

## The features (locked spec)

1. **Scaffold** — `board.py scaffold` writes `board-data.json` (the deck) + a
   self-contained `board.html` (template with the deck injected between its
   `BOARD_DATA` markers). Default dest is `{vault}/projects/{slug}/board/`; pass
   `--dest` to target a code repo (e.g. `<repo>/_docs/board`). `--dest`/`--data`
   are single-project only (not valid with `--all`).
2. **Seed from tasks** — `--from-tasks` builds one card per `{project}/tasks/*.md`
   note: `code`/`id`/filename → card id, first `# heading`/`title:` → title,
   `status:` → column, `category:`/first non-`task` tag → category,
   `related:` → mono refs, `note:` → note. `_index.md` and roadmap/index files
   (`type: tasks`) are skipped — they aren't per-card task notes. Empty `tasks/`
   yields a clean 6-stage starter deck (no error).
3. **Serve** — `board.py serve --dir DIR` runs a localhost static server so the
   disk-save (File System Access API) works (it needs a secure context, not
   `file://`).

## Run

```bash
# the current project, from its tasks/
python3 "$(dirname "$0")/../../../scripts/board.py" scaffold --project-dir "$PROJECT_ROOT" --from-tasks

# a named project by slug (vault resolved from the cwd breadcrumb)
python3 .../scripts/board.py scaffold --project steel-tempest --from-tasks

# every project in the vault, one board each
python3 .../scripts/board.py scaffold --all --from-tasks

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
  "version": 1, "boardId": "my-project",
  "title": "My Board", "subtitle": "Work-order board", "updated": "2026-06-24",
  "columns": [{ "id": "backlog", "name": "Backlog" }, ...],
  "categories": ["build", "docs", "infra"],
  "cards": [{ "id": "X-01", "title": "...", "column": "backlog",
              "category": "build", "related": ["SPEC-001"], "notes": "" }]
}
```

- `boardId` (defaults to the project slug) namespaces the board's browser
  `localStorage` + IndexedDB file-handle, keeping multiple boards independent.
- `done` and `icebox` columns get `BUILT` / `PARKED` rubber-stamp overprints.
- The browser's rev-guard keys on the **set of card ids** (not the date or
  count): a re-scaffold that only moves cards between columns keeps your browser
  state; adding/removing a card refreshes it.

## Idempotency — refresh without clobber

Re-running `board` does not wipe in-progress card state:

- **`--from-tasks` over an existing board → merge.** Per card id: a card present
  in both keeps the **column you dragged it to** (and any board-local `notes`),
  while `title`/`category`/`related` re-seed from the task note. New tasks are
  added in their status-derived column; a card whose task disappeared is moved to
  `icebox` (never deleted).
- **Without `--from-tasks` → the on-disk deck is kept untouched** (only `board.html`
  is refreshed from the template, so styling/engine updates land).
- **`--force` → full rebuild from tasks**, discarding dragged columns.
- **`--data FILE` → that deck verbatim** (missing standard fields are backfilled).

`board.html` is always re-emitted from the canonical template — never hand-fork
instantiations; change `templates/board.html` and re-run.

## Merge provenance (refresh-without-clobber)

Task-seeded cards carry `source: task`. On re-seed, a `source: task` card whose
backing `tasks/*.md` note disappeared is parked in `icebox` (never deleted);
cards **without** task provenance (hand-added in the board UI, or from a
pre-provenance deck) keep their current column untouched.

## Fail conditions

- No breadcrumb at cwd → the target dir is treated as the vault project dir itself
  and the board scaffolds there (deliberate scaffold-anywhere escape hatch; run
  `/adjudant connect` first if you wanted the breadcrumb flow).
- `--project`/`--all` with no resolvable vault → exit non-zero ("pass `--vault PATH`
  or run from a connected project").
- `--project <slug>` not found → exit non-zero, listing the available slugs.
- `--dest`/`--data` combined with `--all` → exit non-zero.
- Template missing / `BOARD_DATA` markers absent → exit non-zero (don't emit a
  half-written board).

## What board does NOT do

- No live sync to GitHub issues / Jira / a database — the JSON is the source of truth.
- No multi-user/server backend — single-file, local, disk-or-browser persistence.
- No auto-status-writeback to `tasks/` notes (seeding is one-way: `tasks/` → board).
