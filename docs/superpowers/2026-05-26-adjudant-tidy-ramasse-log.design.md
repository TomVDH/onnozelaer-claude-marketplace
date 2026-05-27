---
date: 2026-05-26
status: design-locked
supersedes: 2026-05-26-adjudant-verb-gaps.brief.md (for ramasse only)
audience: next adjudant session
priority: tidy > ramasse > log
---

# Adjudant surface redesign — tidy + ramasse + log

Three decisions taken in the 2026-05-26 evening (`tomlinson` machine) session that reshape the adjudant verb surface.

## Context

The morning session on the work machine produced the `verb-implementation-gaps` brief which prioritised building `ramasse.py` as a mechanical sweep — TDD, idempotent, port.py-pattern. The evening session **reversed the semantics of ramasse** and split the mechanical work into a new verb.

## The three changes

### 1. New verb: `/adjudant tidy` (was the planned `ramasse.py`)

**Purpose:** routine mechanical sweep. Idempotent. Daily/weekly cadence. Python-backed, TDD'd, follows `port.py` pattern.

**Features** (locked, ported verbatim from the original ramasse spec):

1. Rebuild `_index.md` in every project subfolder holding ≥2 sibling files of the same type. Skip `sessions/`, `images/`, `assets/`, `previews/`, `iterations/`.
2. Bump `updated:` frontmatter on touched files where applicable (doc, project brief, note).
3. Normalise tags per the locked 2026-05-25 schema in `reference/vault-standards.md` §2 (drop Bucket D, migrate Bucket B).
4. Fix wikilink form: rewrite `[text](path)` to `[[wikilink|text]]` IFF `path` resolves to a vault `.md` file.

**Scope:** project (default) or `--vault` for vault-wide.

**Files to ship:**
- `adjudant/scripts/tidy.py` (~600–800 lines, stdlib-only)
- `adjudant/scripts/test_tidy.py` (TDD partner)
- `adjudant/skills/adjudant/reference/tidy.md` (runbook)
- New entry in `command-metadata.json`, `commands/adjudant.md`, `SKILL.md` verb router

**Implementation:** copy `port.py` structure, swap content. The existing fixtures (`_port-test-hubspot/`, `/tmp/dupe-snapshot-pre-ramasse/`) are still valid for tidy testing.

### 2. Redefined verb: `/adjudant ramasse`

**New purpose:** deep structural refactor of a vault project. Used **sparingly** — quarterly or after major project-shape changes (consolidation, splitting, retitling). Leverages superpowers skills.

**Phase shape** (proposed, not yet locked):

| Phase | Skill leveraged | Output |
|---|---|---|
| 1. Analyse | (dream-like deep scan) | full drift catalog + project-shape assessment |
| 2. Brainstorm | `superpowers:brainstorming` | explore restructure options with user (folder reorgs, file consolidations, schema shifts) |
| 3. Plan | `superpowers:writing-plans` | content arrangement plan with step-by-step structural changes |
| 4. Review | (human checkpoint) | user reviews + approves plan; can edit |
| 5. Execute | `superpowers:executing-plans` | applies the plan with checkpoints; preview → apply pattern like `/adjudant port` |

**Distinction from `/adjudant tidy`:**
- tidy = mechanical, idempotent, runs often, no user dialogue
- ramasse = restructural, planning-driven, runs rarely, user-in-the-loop

**Distinction from `/adjudant dream`:**
- dream = read-only diagnostic crawl, generates a report file, no plan
- ramasse = uses dream-like analysis but goes further to propose + execute restructure

**Implementation:** runbook-only (no Python). The whole verb is Claude-runtime, leveraging the superpowers skill chain.

**Files to ship:**
- Rewrite `adjudant/skills/adjudant/reference/ramasse.md` to the new spec
- Update `command-metadata.json` description
- Update `SKILL.md` verb router

### 3. New verb: `/adjudant log` (lowest priority)

**Purpose:** snapshot the user's full Claude Code setup → vault. Cross-machine sync aid; setup-reproducibility doc.

**Output location:** `{vault}/IDE/{machine-or-slug}.md`. The `/IDE/` folder lives at vault root, not under any project. Auto-created on first invocation.

**Captures (proposed scope — to refine):**
- Installed plugins (from marketplaces + local) with versions
- Hooks (project-level + global hookify state)
- Skills (user-invocable + auto-loaded, by source)
- MCP servers (claude.ai-hosted + plugin-bundled + custom)
- Custom slash commands
- Memory files (`~/.claude/projects/.../memory/*.md` — filenames only, content optional with flag)
- `settings.json` summary (model, theme, permission allowlist counts — no secrets)
- Claude Code version

**Implementation:** Python-backed (`adjudant/scripts/log.py`) is overkill — better as a shell + jq script + Claude runtime narrative. Decide at implementation time.

**Files to ship:**
- `adjudant/skills/adjudant/reference/log.md` (runbook)
- `adjudant/scripts/log.sh` (shell harvest) or `log.py` if needed
- New `templates/ide-snapshot.md` template
- vault-standards.md update: add `/IDE/` folder + `ide-snapshot` file type to Bucket A

## Resulting surface

| | Before (v0.2.5) | After (v0.4.x target) |
|---|---|---|
| Verbs | 7 | 9 |
| Python-backed | port | port, tidy |
| Claude-runtime | connect, sync, check, ramasse, dream, draw | connect, sync, check, ramasse, dream, draw, log |
| Idempotent | port | port, tidy, log |

## Dream reframe — semantic compaction (2026-05-26 late evening)

User raised a fundamental reframe of what `dream` should be. Captured here for v0.4+ work.

### Current dream (v0.3.0) — structural drift catalog

What `dream.py` does today:
- Walks project, reports frontmatter / tag / type / naming / wikilink-form / broken-wikilink / folder / index / doc-decision drift
- Read-only, JSON output, Claude renders narrative
- Scope: schema-level (the *form* of files, not the *content*)

This is useful but **not what dream should primarily be.** It's closer to a `lint` / `audit` pass.

### Future dream (v0.4+) — semantic compaction

User's vision: **dream is to a vault project what PreCompact is to a Claude conversation.**

- Read the actual **content** of decisions, notes, sessions (not just frontmatter)
- Identify:
  - **Outdated info**: decision A made 2026-05-08 contradicts decision B made 2026-05-15 → A might be stale
  - **Irregularities**: notes referencing things that no longer exist; sessions mentioning archived projects
  - **Redundancy**: multiple notes saying the same thing
  - **Orphan threads**: open questions from old sessions never resolved
  - **Stale references**: decisions citing outdated tech/files/people
- **Clean up semantically** — meaning dream becomes write-capable (mark decisions as superseded, consolidate duplicates, archive stale sessions, update references)
- Output is a **distilled, current view** of the project, not "X drift items"

This is LLM-judgment heavy. The Python helper does the heavy reading + emits structured comparators ("decision A line 42 conflicts with decision B line 18 about subject X"); Claude does the semantic judging + writes the cleanup plan.

### What this means for ramasse

Open question. Two plausible reads:
- **Dream eats ramasse**: three verbs total (check / tidy / dream) with dream as the deep semantic+structural cleanup. Ramasse goes away or means something else.
- **Distinct layers**: dream operates at the content-level (semantic) within one project; ramasse operates at the architectural-level (folder reshapes, schema evolution) across projects.

Defer the choice until designing v0.4. The current `reference/ramasse.md` (deep planning verb spec) stays as a placeholder.

### What v0.3.0 ships meanwhile

The structural detection in `dream.py` is **the foundation layer** the semantic version will sit on:
- `_vault_walk.py` walks + parses
- `dream.py` structural detectors run
- v0.4+ adds: content-level semantic detectors → write-capable compaction phase

Don't tear down v0.3.0 to build v0.4. Layer it.

### Naming question (deferred)

If v0.4 dream becomes semantic-write, the current `dream.py` structural pass could be:
- (a) Renamed to `audit.py` and given its own verb `/adjudant audit`
- (b) Folded into tidy's preview (which already reports what it would change)
- (c) Kept as the first phase of dream (structural before semantic)

Lean (c) for minimal surface churn. The runbook (`reference/dream.md`) describes a 2-pass model: structural pass first, semantic pass second. v0.3.0 ships pass 1.

---

## Phasing / version bumps

- **v0.3.0 — Python-helper layer** ships. Bundle:
  - `scripts/_vault_walk.py` — shared primitives (file walk, frontmatter parse, tag extract, wikilink extract, schema-conformance checks)
  - `scripts/tidy.py` + `test_tidy.py` — 4-feature mechanical sweep (was the ramasse.py plan)
  - `scripts/dream.py` + `test_dream.py` — drift-catalog harvester; emits JSON for Claude to render
  - `scripts/check.py` + `test_check.py` — quick status; emits compact JSON
  - Updates: `command-metadata.json`, `commands/adjudant.md`, `SKILL.md`, `reference/tidy.md` (new), `reference/dream.md` (rewrite to consume `dream.py` output), `reference/check.md` (rewrite to consume `check.py` output)
  - Updates: `validate.py` invariants for the new helpers
- **v0.3.1 — `/adjudant ramasse`** rewritten as the deep planning verb. Runbook only. Consumes `dream.py` output for phase 1. References superpowers skill chain (brainstorming → writing-plans → executing-plans).
- **v0.4.0 — `/adjudant log`** ships. New `/IDE/` folder convention. Vault-standards extension. `log.sh` or `log.py` per implementation-time decision.
- **v0.5.0+ — session chunking** revisited if/when warranted.

v0.3.0 is the foundational bundle — three helpers share `_vault_walk.py`. Building one at a time means the shared module evolves; building all three in one session keeps the shared API coherent. Recommend single session for the full v0.3.0 bundle.

## Carry-forward from gap brief

The gap brief's other observations remain valid:
- `connect.py` and `sync.py` are still gaps (lower priority than tidy)
- `check`, `dream`, `draw` correctly runbook-only — confirmed unchanged

## Open questions (defer to implementation session)

- Ramasse phase 5 ("execute") — does it use `/adjudant tidy` internally for the mechanical bits of the plan, or apply its own changes directly?
- Log verb — per-machine snapshot OR per-project snapshot? Filename convention: `{hostname}.md`, `{user}-{hostname}.md`, or `{date}-{hostname}.md`?
- Does `/IDE/` need its own `_index.md` listing snapshots? (Per §5 of vault-standards, ≥2 siblings → yes.)
- Should `log` also capture state of *this* vault (e.g., project count, last sync) — i.e., does it write a self-referential summary?

## Test fixture

Same fixture as gap brief — duplicate at `_port-test-hubspot/` in Cabinet vault. Pre-port snapshot at `/tmp/dupe-snapshot-pre-ramasse/` (work machine only). Tidy can validate against the same duplicate after a `cp -R` re-snapshot.

---

## Cross-cutting concern: context budget per verb

Prompted by the 2026-05-26 evening dream-run on `hubspot-nightly` (104 files, manageable) and the realisation that `tf-renewal` (577 files) or a vault-wide sweep would blow Claude's context.

### Doctrine: every verb has a Python harvester upstream of Claude

Adjudant's per-verb cost should be a small, dense, structured input Claude renders — **not bulk file reads**. The pattern: shell/Python scan → JSON or compact markdown blob → Claude reads only that.

| Verb | Helper script | Helper job | Claude job |
|---|---|---|---|
| `port` | `port.py` ✓ | detect, copy files, classify mechanically | AI-classifier for Z flavor (small subset) |
| `tidy` | `tidy.py` (v0.3.0) | full mechanical sweep | kick off, render summary |
| `dream` | `dream.py` (NEW) | scan all files, extract drift candidates, emit JSON | read JSON, render narrative report, save |
| `ramasse` | `dream.py` reused + `ramasse-plan.py` (NEW) | drift catalog + restructure-candidate grouping | brainstorm → plan → execute (superpowers) |
| `check` | `check.py` (NEW) | quick stat scan, brief metadata, drift counts | render summary |
| `log` | `log.sh` (or `log.py`) | harvest `~/.claude/`, plugin lists, hooks, settings | render snapshot |
| `connect` | (none — no scanning) | — | pure runbook |
| `sync` | maybe — pre-compute brief + handoff diff | Claude writes briefs + handoff |
| `draw` | (none — pure generation) | — | content gen |

### Hard rule

**No verb is allowed to do bulk file reads from Claude.** If the verb touches > ~10 files, it has a Python helper that pre-digests. The helper's output target: ≤ 5K tokens.

### Migration of dream

This evening's dream-run was Claude-driven (Bash + ad-hoc Python). Convert to a real `dream.py` in the same release as `tidy.py` (v0.3.0). Both helpers share the same vault-walk primitives — design them in one file or a shared `_vault_walk.py`.

---

## Cross-cutting concern: session-log chunking — DEFERRED

**2026-05-26 decision:** defer session-chunking implementation until the Python-helper layer ships. Rationale: chunking is speculative until we see how long sessions actually run under the new helper architecture. The three shapes below are preserved for future selection.

### Current state

Session spec: one file per project per day (`sessions/{YYYY-MM-DD}.md`, append on resume). Real-world max in `hubspot-nightly`: **241 lines** (2026-05-14). No formal cap. Append-only.

The user has raised an accuracy concern: long sessions are harder for Claude to read precisely. We want smarter chunking.

### Three candidate shapes (pick one)

**A. Hard line cap with rollover**
```
sessions/2026-05-26.md       — original, up to N lines (e.g. 200)
sessions/2026-05-26-2.md     — continuation after rollover
sessions/2026-05-26-3.md     — ...
```
`_index.md` links all chunks. Simple. The Python helper writes new chunk when threshold hit. Tradeoff: chronological reads need to traverse multiple files.

**B. PreCompact-aligned chunks**
```
sessions/2026-05-26.md       — primary session, append-only until PreCompact
sessions/2026-05-26-compact-1.md  — written by PreCompact hook, freezes context window
sessions/2026-05-26-compact-2.md  — second compact
```
Each chunk = one Claude context-window of work. The PreCompact hook is already wired in adjudant; this just specialises its write. Natural semantic boundary: "what fit in one window."

**C. Hierarchical summary + detail**
```
sessions/2026-05-26.md           — running summary (capped, edited each turn)
sessions/2026-05-26-detail/      — folder of raw log chunks
  001-{HHMM}.md
  002-{HHMM}.md
  ...
```
Most context-efficient for Claude reading-back (summary is small). Costs: most complex to maintain; not idiomatic Obsidian; folder-per-session inflates structure.

### Recommendation: **B** (PreCompact-aligned)

PreCompact is an objectively meaningful boundary (a context window literally ended). Aligning chunks with compactions means each chunk represents what Claude could see at once when it was written. Claude reading back can pick the chunk most relevant to a question without traversal. The PreCompact hook already exists — just extend it.

A and C are runner-up if PreCompact-alignment proves too coarse (sessions that never compact stay one file) or too fine (rapid compactions over-fragment).

### Implementation

`hooks/scripts/precompact.py` gains chunk-write behavior. Vault-standards.md §4 names the chunk pattern. `tidy.py` indexes chunks alongside primary session in folder `_index.md` rebuilds. `dream.py` flags drift like "primary session > N lines with no compact-chunk" as a possible chunking-failure.
