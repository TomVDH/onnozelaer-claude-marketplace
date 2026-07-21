---
date: 2026-07-21
status: design, ready for implementation planning
scope: adjudant plugin, five workstreams - task file type, board coherence, passive surfacing, hook wave, shape enforcement
plugin: adjudant
version-target: decided at release time (coordinate with the 2026-07-20 deep-review session, which owns the next adjudant version)
related: 2026-07-16-adjudant-cost-status-voice-design.md (shipped as 0.14.0); vault note notes/2026-07-20-adjudant-deep-review-suitcase-integration.md
---

# Adjudant ambient board: task schema, passive surfacing, hook wave, shape

The board, diagrams, and session narrative become ambient: present without being asked for, refreshed without being remembered, and shaped so the reader can act on them. Today the board is pull-only with an empty fuel line (nothing writes `tasks/*.md`), no hook or status verb ever mentions it, and the session log is markers-only because nothing captures real content between explicit verb runs. This release fixes all three.

Every new hook obeys the five rules derived from the 2026-07-20 hook-layer analysis:

1. Fail closed on a bad vault, fail open on the hook itself.
2. Never claim an effect that was not verified (log only after the write succeeds).
3. Gate on real signal; dedupe; rate-limit. Every line must answer "why is this worth a disk write?"
4. One writer per artifact, shared renderer. Board writes go through board.py functions only.
5. Prove the trigger fires with the expected payload before building on it (the crew-notify lesson).

Interactive decisions, settled 2026-07-21: full hook wave in this release (not board-pure, not minimal); harness tasks bridge at session end, survivors only (not live, not explicit-adoption); the board is born on first task (not at connect, not verb-only); i-have-adhd is a soft dependency for the whole plugin.

## Workstream 1: the `task` file type (schema lock)

The format `board.py` reads exists only implicitly in its parser. Lock it:

- New file type in `reference/vault-standards.md` §3/§4: `type: task`, project wikilink, `status:`, `category:`, optional `code:`, `related:`, `note:`. Kebab filename. `#task` joins the tag schema.
- `status:` canonical values: `todo | doing | review | blocked | done | icebox`. The existing 18-alias table from `board.py` `STATUS_TO_COLUMN` (deferred, parked, shelved, someday, wip, ...) is documented as accepted input that normalizes to the six.
- `templates/task.md` scaffold, registered in `FILE_TYPES_REQUIRING_TEMPLATE`.
- tidy and ramasse become task-aware through the normal §2A tag machinery; no special-casing.

This schema is also the write target for the future harvester (sub-project B, separate spec) and the session-end bridge below.

## Workstream 2: board coherence

- `board` joins `AUTO_CREATED_FOLDERS` (`_vault_walk.py`) and vault-standards §5's auto-created list. Kills ramasse's standing false drift on every scaffolded board.
- `connect` stays one rigid path, no flags. Its receipt gains one line naming the board mechanism for coding/plugin project types.
- **Board birth on first task:** when the first real `tasks/*.md` lands (any writer: user, session-end bridge, future harvester), the reseed machinery scaffolds `board-data.json` + `board.html` if absent. Projects that never grow tasks never get board files.
- Card provenance stays as-is: `source: task` cards, merge-without-clobber, icebox-not-delete. No changes to locked merge semantics.

## Workstream 3: passive surfacing

- **SessionStart:** the existing `## Adjudant` context block gains, when a board exists, one board-status line: per-column counts plus a stale flag when the deck `updated` predates the newest task note mtime. One JSON read, budget-safe inside the 10s hook.
- **SessionStart, suitcase pointer:** on `source: startup` only (not resume/compact/clear), and only when `command -v suitcase-brief` resolves, one pointer line: suitcase detected, run `suitcase-brief` for orientation, vault is canonical, writes via adjudant. One line, never the full block (~500 tokens). PATH detection keeps it correct on both machines.
- **check:** new board section in the JSON (present/absent, per-column counts, deck `updated`, tasks-vs-deck freshness delta), reusing `board.py`'s status primitives. Excluded from the cost-estimate path.
- **sitrep:** inherits check's board section; renders one orientation line.
- **SessionEnd:** after the existing handoff sync, re-run the clobber-safe `board.py --from-tasks` merge when a board exists (and birth it per workstream 2 when the first task exists without one). Fail-open, stale-breadcrumb guarded like every other hook.
- Render specs for `reference/check.md`, `sitrep.md`, `board.md` updated in the same change.

## Workstream 4: hook wave

Four additions plus one widening. All mechanical, no model calls, async where the event supports it.

- **PostCompact:** append the compaction summary to today's session log as `- HH:MM · compacted: <gist>`, gated on a non-empty summary payload. Ends the markers-only log disease; PreCompact keeps writing the pause tombstone unchanged.
- **Commit-gated** (`if: Bash(git commit *)`): append the commit subject to the session log. On `release(<plugin>): vX.Y.Z` subjects, additionally scaffold `releases/vX.Y.Z.md` from the commit message (mechanical stub: frontmatter + title + body from the commit body). Fixes the vault release history that stops at v0.3.1 for a repo that ships weekly.
- **TaskCreated / TaskCompleted:** append-only session-local ledger in TMPDIR (task id, subject, status), async, zero vault writes during the session.
- **SessionEnd survivor bridge:** at close, ledger entries still incomplete become schema-conformant `tasks/*.md` notes, deduped by slug against existing task notes. Completed-in-session scratch tasks never touch the vault. This write then triggers board birth/reseed.
- **FileChanged on `{vault}/projects/{slug}/tasks/*.md`:** async board reseed via the merge.
- **Verification-first (rule 5):** before implementation, prove PostCompact, TaskCreated, TaskCompleted, and FileChanged each fire on this Claude Code version with the expected payload fields (scripted probe, recorded in the plan). Fallback if FileChanged is unavailable: widen the existing PostToolUse matcher to `Write|Edit` and branch on `tasks/` paths, which also fixes today's blind spot where editing `status:` in a task note fires nothing. If TaskCreated/TaskCompleted are unavailable, the bridge degrades to a SessionEnd-only scan of the harness task list if readable, else the feature is dropped from the release rather than shipped unverified.

## Workstream 5: shape enforcement (i-have-adhd as soft dependency)

The i-have-adhd plugin (installed 2026-07-21, `i-have-adhd@i-have-adhd`) defines ten output rules: lead with the next action, number multi-step work, end with one concrete next step, suppress tangents, restate state every turn, concrete time estimates, visible wins, matter-of-fact errors, cap lists at five, no preamble/recap/closers.

- `reference/voice.md` gains a **Shape** section adopting the ten rules for every rendered verb output and hook context block. Soft dependency stated explicitly: when the plugin is installed it governs the whole chat; when absent, adjudant enforces the same shape on its own surfaces. Nothing breaks without it; nothing double-fires with it.
- The machine-checkable subset (forbidden openers, closers, and error phrases: "Great question", "Hope this helps", "Let me know if", "Uh oh") joins voice.md as a parsed section, enforced by the existing lexicon-validator machinery over templates/ and reference render specs.
- Render audits as work items: sitrep, check, board status, tidy/ramasse previews, and the SessionStart block each verified against the rules (first line actionable, state restated, one next step at the end). sitrep's "Start here" line and the handoff freshness header already comply.
- Rationale, stated once: the ambient board is itself the ADHD-shaped feature. Externalized task memory (board), restated state (sitrep, freshness header), visible wins (BUILT/PARKED stamps).

## Diagrams: deliberately minimal

No auto-diagram hooks this release. Document the two embed points that already exist implicitly: a `draw board` mermaid snapshot appended to a session note as a point-in-time record, and the `tiers` fence for briefs and docs. Auto-regeneration is deferred until the board passives prove the pattern.

## Enforcement and tests

- New validators in the existing pattern: task-template coverage (via the template registry), board-template-markers (`board.html` exists, `BOARD_DATA` markers parse), status-vocabulary coherence (`STATUS_TO_COLUMN` keys are a subset of the documented alias table), and the deferred hooks-wiring test (every hooks.json entry points at an existing executable script) so dead wiring cannot stay green.
- Every new hook script gets a test module (TDD, repo convention). The ledger, bridge dedup, board-birth, and release-stub paths each get unit coverage.
- README, SKILL.md hook table, and reference docs updated in the same wave; existing parity validators hold them.

## Non-goals

No Jira. No multi-source harvester (sub-project B, own spec). No per-turn Stop hook. No Notification hooks. No model calls in any hook. No board write path outside board.py. No new state files outside the vault except the TMPDIR ledger, which dies with the session.

## Coordination

The 2026-07-20 deep-review session owns adjudant's next version number and may land further themes. Implementation plans from this spec rebase on whatever HEAD that work leaves and take the next free minor version at release time. The task-bridge and FileChanged probes run before any code is written.
