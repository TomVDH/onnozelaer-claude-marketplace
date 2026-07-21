# Adjudant Ambient Board Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This run executes via the session Workflow orchestrator in four waves (A parallel, B parallel, C sequential, D release); lane boundaries below are drawn so no two Wave-A or Wave-B lanes touch the same file.

**Goal:** The board, diagrams, and session narrative become ambient: schema-locked task notes feed a self-refreshing board, hooks capture real content, and every rendered surface follows the shape rules.

**Architecture:** All board writes go through board.py functions (one writer per artifact). Hooks are thin shell/python wrappers that call scripts/ helpers, fail open on themselves, fail closed on a bad vault, and gate on real signal. Event-dependent features carry a verified branch and a fallback branch; the probe verdict (Task 0) selects one.

**Tech Stack:** stdlib-only Python 3, bash hooks, unittest, repo validate.py validators.

## Global Constraints

- Version target: 0.15.0, bumped only in Wave D via `python3 scripts/bump_plugin_version.py adjudant 0.15.0`.
- No model calls in any hook. No new state files outside the vault except the TMPDIR ledger.
- Voice: no banned lexicon (see reference/voice.md), no em dashes in any file this plan touches.
- Every hook script: `set -euo pipefail` + `main "$@" || exit 0` (bash) or top-level `except: sys.exit(0)` (python); never claim an effect before the write succeeds.
- Suite must stay green after every task: `python3 -m unittest discover -s adjudant/scripts -p "test_*.py"` (591 baseline) and `python3 adjudant/scripts/validate.py` (24 baseline).
- Wave A lanes and Wave B lanes each own their files exclusively; validate.py, hooks.json, SKILL.md, README.md are Wave C property only.

---

### Task 0: Event probes (gate for Tasks 6-9 branches)

**Files:** none (scratchpad only; verdict recorded in the Wave D vault note).

- [ ] Collect the claude-code-guide agent report on PostCompact, TaskCreated, TaskCompleted, FileChanged availability and payloads for the installed version.
- [ ] Where cheap, live-probe: temporary echo-hook in `.claude/settings.local.json` hooks section, trigger the event (TaskCreate tool for TaskCreated; an Edit for FileChanged), read the sentinel, remove the temp hook. PostCompact accepts a docs-only verdict.
- [ ] Verdict per event: AVAILABLE (wire it) or NOT AVAILABLE (use the task's fallback branch). UNCERTAIN counts as NOT AVAILABLE (rule 5: never wire an unproven trigger).

### Task 1: Lane L1, task schema + board coherence (Wave A)

**Files:**
- Modify: `adjudant/skills/adjudant/reference/vault-standards.md` (§2A tag list, §3 file-type table, §4 frontmatter specs, §5 auto-created list)
- Create: `adjudant/skills/adjudant/templates/task.md`
- Modify: `adjudant/scripts/_vault_walk.py` (AUTO_CREATED_FOLDERS at ~687; file-type/tag schema constants)
- Modify: `adjudant/scripts/connect.py` (receipt line), `adjudant/skills/adjudant/reference/connect.md`
- Test: extend `adjudant/scripts/test__vault_walk.py`, `adjudant/scripts/test_ramasse_scan.py`, `adjudant/scripts/test_connect.py`

**Interfaces:**
- Produces: `templates/task.md` with frontmatter `type: task`, `project: "[[projects/{slug}/brief|{slug}]]"`, `status: todo`, `category: ""`, `code: ""`, `related: []`, `note: ""` and body `## Task` / `## Notes`. Canonical statuses: `todo | doing | review | blocked | done | icebox`. `#task` tag. `'board'` present in `AUTO_CREATED_FOLDERS`.
- Consumes: existing schema constants in `_vault_walk.py`; existing §3/§4 table format in vault-standards.md.

- [ ] Failing test: `test_ramasse_scan.py::test_board_folder_not_drift` builds a temp project containing `board/`, asserts `detect_folder_drift` returns no item for it. Run; expect FAIL.
- [ ] Add `'board'` to `AUTO_CREATED_FOLDERS` (`_vault_walk.py:687`); add `task` to the file-type/tag schema constants beside the existing eleven, matching how `decision` is declared. Run test; expect PASS.
- [ ] Failing test: `test__vault_walk.py::test_task_type_in_schema` asserts `task` in the file-type constant and `#task` in the tag set. Implement until PASS (covered by the constant edit; keep the test).
- [ ] Write `templates/task.md` per Produces above, mirroring `templates/decision.md` layout.
- [ ] vault-standards.md: add the `task` row to §3 (template `task.md`, body sections `## Task` / `## Notes`), the §4 frontmatter block with the six canonical statuses plus this sentence: aliases accepted on input and normalized by the board (deferred, parked, shelved, someday, wip, and the rest of board.py's STATUS_TO_COLUMN table); add `board` to §5's auto-created list; add `#task` to §2A.
- [ ] Failing test: `test_connect.py::test_receipt_names_board` asserts the connect receipt for a coding-type project contains the string `/adjudant board`. Implement: one receipt line in `connect.py` for coding/plugin types ("tasks/ seeds the kanban: /adjudant board, born automatically on the first task note"). Mirror the wording into `reference/connect.md`. PASS.
- [ ] Run full suite; expect 591+3 OK. Do not commit (Wave commit).

### Task 2: Lane L2, board birth + public reseed (Wave A)

**Files:**
- Modify: `adjudant/scripts/board.py`
- Test: extend `adjudant/scripts/test_board.py`

**Interfaces:**
- Produces: `ensure_board(project_dir: Path, vault_dir: Path | None = None) -> str` returning one of `"created" | "reseeded" | "no-tasks" | "no-change"`. Behavior: no `tasks/*.md` beyond `_index.md` and `type: tasks` roadmaps, return `no-tasks` and write nothing; tasks exist and `board/board-data.json` absent, scaffold via the existing `scaffold_one` path and return `created`; board exists, run the existing `--from-tasks` merge (`merge_deck`) and return `reseeded` when the deck changed, else `no-change`. Never touches dragged columns (locked merge semantics).
- Consumes: `cards_from_tasks` (~104), `merge_deck` (~189), `scaffold_one` (~284), default dest `{project}/board/` (~419).

- [ ] Failing tests (four): `test_ensure_board_no_tasks_writes_nothing`, `test_ensure_board_creates_on_first_task`, `test_ensure_board_reseed_preserves_dragged_columns` (create board, drag a card by editing deck JSON column, add a task note, ensure column survives), `test_ensure_board_idempotent_no_change`. Run; expect 4 FAIL (`ensure_board` not defined).
- [ ] Implement `ensure_board` as a thin composition of the existing functions; add a `--ensure` CLI flag mapping to it so hooks can call `python3 board.py --ensure --project-dir X`. No new write paths.
- [ ] Run the four tests, then the whole test_board.py; expect PASS with the 37 existing green.

### Task 3: Lane L3, PostCompact content capture (Wave A)

**Files:**
- Create: `adjudant/hooks/scripts/postcompact.py`
- Test: create `adjudant/scripts/test_postcompact.py`

**Interfaces:**
- Produces: script reading stdin JSON, extracting the compaction summary field per the Task 0 probe (documented fallback keys tried in order: `summary`, `compact_summary`, `message`), appending `- HH:MM · compacted: {first 160 chars, single line}` to today's session log using the same resolve/midnight-fallback discipline as `posttooluse-vault-log.py` (~126-150).
- Consumes: `_vault_walk.resolve_vault`; session-note path conventions.

- [ ] Failing tests: empty/missing summary writes nothing (`test_empty_summary_no_write`); non-empty appends exactly one line (`test_appends_gist_line`); stale breadcrumb writes nothing (`test_stale_breadcrumb_fail_closed`); summary with newlines collapses to one line (`test_gist_single_line`). Structure after `test_precompact.py` (invoke `main` with stdin patched).
- [ ] Implement per the posttooluse-vault-log.py skeleton: single clock read, try/except around every I/O, `except Exception: sys.exit(0)` last. PASS all four.
- [ ] Branch note: if Task 0 says PostCompact NOT AVAILABLE, the script still ships tested but is not wired in Wave C, and the Wave D vault note records why.

### Task 4: Lane L4, commit-gated session logging (Wave A)

**Files:**
- Create: `adjudant/hooks/scripts/posttooluse-commit-log.py`
- Test: create `adjudant/scripts/test_commit_log.py`

**Interfaces:**
- Produces: PostToolUse(Bash) script, SELF-GATED (no dependency on the `if` filter): reads stdin JSON, exits 0 unless `tool_input.command` matches `^git commit` (after stripping leading `cd ... && `), and `tool_response` indicates success. Then: (a) append `- HH:MM · commit: {subject}` to today's session log; (b) when subject matches `^release\(([a-z0-9-]+)\): v(\d+\.\d+\.\d+)`, write `{vault}/projects/{slug}/releases/v{version}.md` from `templates/release.md` frontmatter with title `# v{version} ({plugin})` and body = commit message body, only if that file does not exist; (c) upsert one `- [[v{version}|v{version} ({plugin})]]` line into `releases/_index.md`.
- Consumes: `_vault_walk.resolve_vault`; `templates/release.md` shape (see releases/v0.3.1.md precedent); subject parsed from the `git commit -m` argument in `tool_input.command` (first `-m` string).

- [ ] Failing tests: non-commit Bash exits silently (`test_non_commit_ignored`); commit appends log line (`test_commit_logged`); release subject scaffolds release note + index row (`test_release_scaffold`); existing release file never overwritten (`test_release_no_clobber`); failed commit (non-zero exit in payload) writes nothing (`test_failed_commit_ignored`).
- [ ] Implement with the same fail-open/fail-closed skeleton as Task 3. PASS all five.

### Task 5: Lane L5, session-start board line + suitcase pointer (Wave A)

**Files:**
- Modify: `adjudant/hooks/scripts/session-start.sh` (extend the `## Adjudant` block, ~75-92)
- Test: extend `adjudant/scripts/test_hook_shell.py`

**Interfaces:**
- Produces: when `{vault}/projects/{slug}/board/board-data.json` exists, one context line `- Board: {todo}/{doing}/{review}/{blocked}/{done}/{icebox}{stale_flag}` where `stale_flag` is ` · stale` when any `tasks/*.md` mtime is newer than the deck file mtime; computed by one `python3 - <<PY` block (single JSON read). When `command -v suitcase-brief` succeeds AND hook payload `source` is `startup`: one line `- Suitcase detected: run suitcase-brief for orientation (vault is canonical; writes via adjudant)`.
- Consumes: existing block structure; payload `source` already parsed (~18-38).

- [ ] Failing tests in test_hook_shell.py's harness: board line present when deck exists (`test_sessionstart_board_line`), absent when not (`test_sessionstart_no_board_no_line`), stale flag when task newer (`test_sessionstart_board_stale_flag`), suitcase line only on startup source with a fake `suitcase-brief` on PATH (`test_sessionstart_suitcase_pointer_startup_only`).
- [ ] Implement; both additions inside the existing guarded block, each independently wrapped so failure of one never kills the block. PASS.

### Task 6: Lane L6, check/sitrep board section (Wave B)

**Files:**
- Modify: `adjudant/scripts/check.py`, `adjudant/scripts/sitrep.py`
- Modify: `adjudant/skills/adjudant/reference/check.md`, `adjudant/skills/adjudant/reference/sitrep.md`
- Test: extend `adjudant/scripts/test_check.py`, `adjudant/scripts/test_sitrep.py`

**Interfaces:**
- Consumes: Task 2's deck layout (read-only JSON parse; do NOT import board.py write paths).
- Produces: `check` JSON gains `"board": {"present": bool, "columns": {name: count}, "updated": str | null, "stale": bool}`; sitrep briefing gains one line when present: `Board: {n_open} open ({doing} in motion){", stale" if stale}` and, per the shape rules, sitrep's final line remains the single next action.
- [ ] Failing tests: check board absent (`present: false`, no crash), check board present with counts, stale computed from mtimes; sitrep renders the one line. Implement read-only in check.py (one function `_board_status`), sitrep consumes it. Update both render specs with the new line, keeping first-line-actionable and one-next-step shape. PASS; keep board reads out of the cost-estimate path.

### Task 7: Lane L7, ledger + session-end bridge + reseed (Wave B)

**Files:**
- Create: `adjudant/hooks/scripts/task-ledger.py` (only if Task 0 verdict AVAILABLE for TaskCreated/TaskCompleted)
- Create: `adjudant/scripts/board_bridge.py`
- Modify: `adjudant/hooks/scripts/sessionend.sh` (after the `--sync-only` call, ~77-80)
- Test: create `adjudant/scripts/test_board_bridge.py`; extend `test_hook_shell.py`

**Interfaces:**
- Produces: `task-ledger.py` appends `{"id","subject","status","ts"}` JSONL to `$TMPDIR/adjudant-task-ledger-{session_id}.jsonl` (create ok, never read in-session). `board_bridge.py` CLI: `--bridge {ledger_path}` converts ledger entries whose latest status is not completed into `tasks/{kebab-subject}.md` per templates/task.md, deduped against existing task-note slugs, then calls `board.ensure_board`; `--ensure-only` just calls `ensure_board`. sessionend.sh calls `board_bridge.py --bridge "$ledger"` when the ledger file exists, else `--ensure-only` when a board exists.
- Consumes: Task 2 `ensure_board`; Task 1 `templates/task.md`.
- [ ] Failing tests: survivor bridged, completed skipped, slug dedup (existing note not duplicated), bridge triggers board creation, ledger absent means ensure-only path, malformed ledger line skipped without crash.
- [ ] Implement; ledger hook ships only under an AVAILABLE verdict, bridge logic ships regardless (harvester in sub-project B will reuse it). PASS.

### Task 8: Lane L8, tasks-change board refresh (Wave B)

**Files:**
- Branch AVAILABLE (FileChanged): wiring only, done in Wave C; no new script (calls `board_bridge.py --ensure-only`, async).
- Branch FALLBACK: modify `adjudant/hooks/scripts/posttooluse-vault-log.py` + `test_precompact.py`-style tests in a new `adjudant/scripts/test_posttooluse_tasks.py`.

**Interfaces:**
- FALLBACK produces: matcher widened to `Write|Edit` (Wave C wiring); inside the script, the existing session-log job stays Write-only (explicit `tool_name == "Write"` guard, current behavior byte-identical), and a new branch fires on either tool when `rel.parts[0] == "tasks"`: invoke `board_bridge.py --ensure-only` via subprocess with a 3s timeout, never blocking exit 0.
- [ ] Failing tests: Write under tasks/ triggers ensure (subprocess mocked), Edit under tasks/ triggers ensure, Edit elsewhere does not, session-log job still ignores Edit. Implement per verdict branch. PASS.

### Task 9: Wave C, wiring + validators + shape + docs parity (sequential, single owner)

**Files:**
- Modify: `adjudant/hooks/hooks.json`, `adjudant/scripts/validate.py`, `adjudant/skills/adjudant/reference/voice.md`, `adjudant/skills/adjudant/SKILL.md`, `adjudant/README.md`, `adjudant/skills/adjudant/reference/board.md`, `adjudant/skills/adjudant/reference/draw.md`
- Test: extend `adjudant/scripts/test_validate.py`

Steps, in order, suite run between each:
- [ ] hooks.json: wire postcompact.py (PostCompact, only if AVAILABLE), posttooluse-commit-log.py (PostToolUse matcher Bash, timeout 5), task-ledger.py (TaskCreated + TaskCompleted, only if AVAILABLE), FileChanged (only if AVAILABLE, matcher glob on tasks/*.md) or instead widen the existing PostToolUse Write matcher to `Write|Edit` (fallback). Async flags where the probe confirmed support.
- [ ] validate.py: register `task` in FILE_TYPES_REQUIRING_TEMPLATE (~52-73); new validators following the numbered pattern: `board-template-markers` (templates/board.html exists, both BOARD_DATA markers present, seeded JSON parses), `task-status-vocabulary` (board.py STATUS_TO_COLUMN keys are a subset of the §4 alias table parsed from vault-standards.md), `hooks-wiring` (every command in hooks.json resolves to an existing executable file under hooks/scripts/). TDD each in test_validate.py.
- [ ] voice.md: add `## Shape` section with the ten i-have-adhd rules condensed to one line each plus the soft-dependency sentence; add `## Shape phrases` bullet section (parsed like Banned lexicon by the validator 24 parser, extend `_parse_voice_lexicon` to include it): `Great question`, `Hope this helps`, `Let me know if`, `Uh oh`, `Happy to clarify`, `Feel free to ask`. Extend validator 24 to match these across templates/ and reference render specs. Fix any violations it finds.
- [ ] Render audits: check.md, sitrep.md, board.md, tidy.md, ramasse.md render specs each verified: first line actionable, one next step last; adjust wording where they fail.
- [ ] board.md: document ensure/birth semantics and the passive refresh surfaces. draw.md: add the two embed points (session-note board snapshot, tiers fence for briefs). SKILL.md hook table: new rows exactly matching shipped behavior (only wired hooks appear). README: hook table parity + board ambient paragraph.
- [ ] Full suite + validate.py; everything green.

### Task 10: Wave D, release + vault records

- [ ] `python3 -m unittest discover -s adjudant/scripts -p "test_*.py"` green; `python3 adjudant/scripts/validate.py` green (24 + new).
- [ ] `python3 scripts/bump_plugin_version.py adjudant 0.15.0`.
- [ ] Commit sequence: wave commits already made (A: `feat(adjudant): task schema, board birth, postcompact + commit-log hooks`; B: `feat(adjudant): board passives - check/sitrep section, session bridge, tasks refresh`; C: `feat(adjudant): hook wiring, validators, shape enforcement, docs parity`); final `release(adjudant): v0.15.0 - ambient board: task schema, passive surfacing, hook wave, shape`. Push.
- [ ] Vault: write `releases/v0.15.0.md` (or verify the commit-log hook wrote it; complete it if stub) and a `notes/2026-07-21-ambient-board-parked-questions.md` doc for anything unresolved (probe verdicts, deferred branches, questions for Tom). Update releases/_index.md.
