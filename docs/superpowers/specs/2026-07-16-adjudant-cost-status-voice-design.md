---
date: 2026-07-16
status: design, ready for implementation planning
scope: adjudant plugin, four workstreams — token-cost awareness, project status lifecycle with status-driven vault zones, standardized connect contract, enforceable voice layer
plugin: adjudant
version-target: 0.14.0
related: 2026-07-07-adjudant-repo-target-design.md (shipped as 0.13.0)
---

# Adjudant 0.14.0: cost gate, shelf lifecycle, connect contract, voice layer

Adjudant becomes the de-facto assistant. Four workstreams ship as one release:

1. **Token-cost awareness.** Every heavy operation estimates what it will pull into Claude's context before it runs, and gates on a threshold.
2. **Project status lifecycle.** A controlled six-state vocabulary, a new `shelf` verb (verb #11), and status-driven physical placement in the vault.
3. **Connect contract.** `connect` standardizes its intake: infer everything possible, confirm once on a single contract card, apply, print a receipt.
4. **Voice layer.** Strictly enforceable language and tone rules, canonical in `reference/voice.md`, validated in-repo, mirrored into hookify as a side task.

Decisions below were made interactively on 2026-07-16 and are settled: estimate + confirm gate (not hard hook, not informational-only); auto-suggest with human confirmation (not fully automatic, not fully manual); six status states; a new verb rather than folding into sync/check/board; adjudant-canonical voice with hookify assist; one integrated release with a shared cost module.

## Goals

- No heavy verb ever surprises on cost. The estimate appears before the spend, and above threshold nothing runs without confirmation.
- Every project brief carries an enforced status; the vault's top level shows only living work.
- `connect` asks for exactly five things, once, and discloses everything it sets up per agent harness.
- No Valley-speak, no glazing, no em dashes in adjudant output or vault writes. Pushback is a duty, not an option.

## Non-goals

- No post-hoc "actual tokens used" measurement. Claude cannot read its own meter; the estimate is the product.
- No hard PreToolUse hook blocking helper invocations. The gate is the SKILL router rule plus user confirmation.
- No automatic writes of status transitions. Machines suggest along the active/stale axis only; every deliberate state (`fridge`, `done`, `dead`, `seed`) is set by the user.
- No conversation-wide voice enforcement from this repo. The hookify `tom-voice` extension lives in iCloud and is tracked as a side task, not part of this release's diff.

---

## Workstream 1: token-cost awareness

### `_cost.py` (new shared primitives module, sibling of `_vault_walk.py`)

Three responsibilities:

1. **Estimator.** `est_tokens = bytes // 4` over the *read surface*: what Claude will ingest, not what Python scans. The read surface per verb is (a) the helper's own JSON output, (b) files the verb's reference flow instructs Claude to read afterwards (dream candidate prose, ramasse catalog targets), and (c) the verb's reference file loaded by the router. Estimation walks use `stat()` sizes only; no file is opened.
2. **Threshold logic.** Default warn threshold: **30,000 estimated read tokens**. Overridable per project in the `.claude/adjudant` breadcrumb via `cost_warn_tokens: <int>`.
3. **Weight table.** Static per-verb class: `light | medium | heavy`. Recorded in `command-metadata.json` as a `weight` field on each verb. Serves as documentation and as the fallback signal for verbs with no dynamic estimate (`connect`, `port`, `sync`, `draw`, `board`).

Verb weights:

| Verb | Weight | Dynamic estimate |
|---|---|---|
| connect | light | no |
| port | medium | no |
| sync | light | no |
| check | medium (heavy with `all`) | yes |
| sitrep | medium | yes |
| tidy | medium | yes |
| ramasse | heavy | yes |
| dream | heavy | yes |
| draw | light | no |
| board | light | no |
| shelf | light | no |

### Helper changes

Each dynamic-estimate helper (`check.py`, `sitrep.py`, `tidy.py`, `ramasse_scan.py`, `dream.py`, `repo_scan.py`) gains:

- a `cost` block in its JSON output:

  ```json
  "cost": {
    "est_read_tokens": 85200,
    "files": 210,
    "bytes": 340800,
    "threshold": 30000,
    "warn": true
  }
  ```

- an `--estimate-only` flag: performs the cheap stat-only walk, prints **only** the cost block, exits. Target runtime: well under one second on a large vault.

### The gate (locked SKILL.md rule)

For heavy verbs (`dream`, `ramasse`, `check all`), the router:

1. Runs the helper with `--estimate-only` first.
2. If `warn` is false: runs the verb normally and includes the estimate as one line in the rendered output ("cost: ~12k tokens, 96 files").
3. If `warn` is true: stops, shows the numbers ("dream would pull ~85k tokens into context: 210 files, 1.1 MB prose"), and offers exactly three options: **proceed**, **scope down** (offered only where the verb has a real scoping flag), or **abort**.

Medium verbs with a dynamic estimate (`check`, `sitrep`, `tidy`) skip the pre-flight: they compute the cost block during their normal run and the rendered output includes it as one line. Light verbs carry only the static weight badge; `sync` and `connect` gain zero friction.

---

## Workstream 2: status lifecycle, `shelf`, and vault zones

### Vocabulary (locked, in `_vault_walk.py` constants)

`active | stale | fridge | done | dead | seed`

- `active`: being worked.
- `stale`: declared active but quiet past threshold (the only machine-suggested state).
- `fridge`: deliberately paused; intent to return.
- `done`: shipped and complete; a success, not an abandonment.
- `dead`: abandoned.
- `seed`: captured idea, not yet started.

Brief templates gain the enum comment (same style as `decision.md`'s status line). A new validator rejects any other value on a brief.

### Status-driven placement

```
projects/            active, stale, seed    (the living top level)
projects/_fridge/    fridge                 (deliberately paused)
projects/_archive/   done, dead             (finished or abandoned)
```

A zone-placement validator enforces status/folder agreement.

### `shelf` verb (verb #11), backed by `shelf.py`

- `shelf` (no args): read-only table across all three zones: slug, declared status, suggested status, days quiet, last touch.
- `shelf <slug> <state> [--reason "…"]`: two-phase like tidy (preview, then apply with backup). Apply does five things atomically:
  1. validates the target state against the vocabulary,
  2. rewrites brief frontmatter `status:` (and `updated:`),
  3. appends a dated line to a `## Status log` section in the brief body (section created on first transition): `- 2026-07-16: active → fridge (reason)`,
  4. moves the project folder to the correct zone when the zone changes, rewriting inbound wikilinks vault-wide (`projects/x/…` → `projects/_archive/x/…`),
  5. refreshes the `projects/_index.md` row via the existing `upsert_projects_index_row`.

### Suggestion engine (one implementation, in `_vault_walk.py`)

Shared by `shelf.py`, `check.py`, `sitrep.py` so all three read identical signals:

- declared `active` and no session note within `stale_after_days` (default **30**, breadcrumb-overridable) → suggest `stale`
- declared `stale` and new activity since the last session-note gap → suggest `active`
- `fridge` older than 180 days → nudge line ("in the fridge 200 days, still intentional?"), never a suggested transition
- `seed`, `done`, `dead`: never suggested away

`check` and `sitrep` render mismatches ("brief says active, looks stale: 47 days quiet → `/adjudant shelf`") and never write. `projects/_index.md` always shows declared status only; suggestions live in rendered output.

### Resolver hardening

`_vault_walk.py`'s project resolver and `enumerate_projects` learn the `_fridge` and `_archive` zones so `board --all`, `sync`, `check`, and `port` keep working on fridged and archived projects. The `project:` piped-wikilink format in vault-standards gains the zone-aware path forms.

---

## Workstream 3: the connect contract

`connect` becomes a strict three-phase verb. Idempotent as today.

### Phase 1: infer (`connect.py --contract`)

Gathers without asking: slug (dirname), `project_type` (repo signals: `plugin.json` → plugin, mostly-markdown → knowledge, code → coding, else tinkerage), vault (existing breadcrumb, else the single registered vault), initial status (`seed` if the repo is nearly empty, else `active`), git remote, detected harnesses (`.claude/`, `.gemini/`, `AGENTS.md` presence). Emits the contract as JSON.

### Phase 2: confirm (one card)

Claude renders the contract once, two halves:

**Required from the user (five fields):** vault, slug, project_type, initial status, one-line purpose. The purpose line becomes the brief's opening line and the anchor `sitrep` orients from. Inferred values are pre-filled; the user approves or corrects once.

**Disclosure, per agent:**

| Artifact | Who reads it |
|---|---|
| `AGENTS.md` (canonical context) | Codex, Gemini/agy, any agent |
| `CLAUDE.md` (`@AGENTS.md` import + Claude-only overrides) | Claude Code |
| `GEMINI.md` (thin pointer to AGENTS.md) | agy / Antigravity |
| `.claude/adjudant` breadcrumb | adjudant helpers |
| Vault scaffold (`projects/<slug>/`, brief, session note) | the user, in Obsidian |
| `.gitignore` entries | git |

`GEMINI.md` is a new scaffold artifact in this release: a thin pointer so agy reads the same canonical context.

### Phase 3: apply + receipt

Apply as today, then print the same contract back as a receipt with per-artifact marks: `created / already-present / updated`. Re-running `connect` on a healthy project shows all-green and writes nothing.

New breadcrumb keys land here with defaults visible at init: `cost_warn_tokens: 30000`, `stale_after_days: 30`.

---

## Workstream 4: voice layer

### `reference/voice.md` (canonical, new)

Four parts:

1. **Banned lexicon.** Valley/LinkedIn vocabulary: forward-thinking, load-bearing, leverage (as verb), deep dive, double-click (figurative), game-changer, cutting-edge, seamless, journey (figurative), empower, unlock (figurative), elevate (figurative), circle back, synergy, "at the end of the day", and kin. Glazing phrases: "You're absolutely right", "Great question", "Excellent point", "Perfect!". Plain-list format so the user extends it without touching code.
2. **Pushback contract.** The user can be wrong, impatient, or insistent. The assistant's duty: say so clearly and concisely, evidence first, one short paragraph, no hedging, no ceremony. State disagreement once; if overruled, proceed without sulking.
3. **Explanation modes.** Recognized as request tokens on any verb:
   - `ELI5`: stepped plan, cause and effect, top level only.
   - `ELI12`: granular steps with the architectural and strategic layer; top-to-mid plus a bit of low.
   - `ELICTO`: trench detail and big picture together; no hand-holding.
   Defaults: `sitrep` renders ELI5 (already its register), `check` renders ELI12, `dream` and `ramasse` judging render ELICTO.
4. **Typography.** No em dashes in rendered output or vault writes; use colon, comma, or parentheses. Flourishes irregular and rare: an occasional fleuron (❦), sparse emoji, room for easter eggs. Never per-message.

### Enforcement, two rings

**In-repo (this release):**
- SKILL.md router loads `voice.md` alongside every verb's reference file (the one exception to load-only-the-matching-reference; voice.md stays small).
- New validator scans `templates/`, `SKILL.md`, and `reference/*.md` for banned lexicon and glazing phrases (helper `.py` files are out of the scanned surface; their output text obeys voice.md and is covered by tests instead). Em-dash ban enforced strictly on `templates/` (vault-bound content).
- One-time sweep in this release cleans existing violations in the scanned surface.

**Cross-machine (side task, out of this repo's diff):**
- Extend the hookify `tom-voice` rule in iCloud with the regexable subset (em dash, glazing phrases, lexicon) so it bites in every project.

---

## Cross-cutting

- `command-metadata.json`: `shelf` entry; `weight` field on all 11 verbs.
- `SKILL.md`: router row for `shelf`, the locked cost-gate rule, the voice.md loading rule, version 0.14.0.
- Vault-standards: status vocabulary section, zone map, status-log body section on briefs, zone-aware wikilink forms.
- Version bump via `python3 scripts/bump_plugin_version.py adjudant 0.14.0` (plugin.json, command-metadata.json, SKILL.md frontmatter, marketplace.json atomically).
- README and `docs/` updates.

## Error handling

- `shelf` move phase: if any inbound wikilink rewrite fails, the apply aborts and restores from the backup taken at phase start; no half-moved project.
- `shelf` on an unknown slug or invalid state: usage error listing the vocabulary, exit nonzero, no writes.
- `--estimate-only` on a helper whose vault/breadcrumb is unresolvable: same resolution error the helper emits today; the router treats it as warn=true (fail toward caution, ask the user).
- Missing breadcrumb keys: defaults apply (30000 / 30); no migration needed for existing projects.
- Zone folders absent in an existing vault: created on first `shelf` apply that needs them; `check` does not flag their absence.

## Testing

TDD throughout, matching the existing suite (449 tests at 0.13.0):

- `test_cost.py`: estimator math, threshold resolution (default vs breadcrumb override), read-surface enumeration per verb, weight-table integrity against command-metadata.json.
- `test_shelf.py`: vocabulary validation, frontmatter rewrite, status-log append (first transition creates section; later ones append), zone move + wikilink rewrite, index-row refresh, preview/apply parity, backup-restore on failure.
- Per-helper `--estimate-only` tests: output is exactly the cost block, stat-only (no content reads), sub-second on a fixture vault.
- Suggestion-engine tests: each rule above, plus never-suggest guarantees for seed/fridge/done/dead.
- Connect contract tests: inference per project_type signal, contract JSON shape, receipt marks (created / already-present / updated), idempotent re-run all-green, GEMINI.md scaffold.
- Voice validator tests: lexicon hit, glazing hit, em dash in templates/ fails, em dash in scripts/ passes (out of scanned surface).
- Resolver tests: enumerate/resolve across `_fridge` and `_archive`.

## Out of scope, deferred

- `ramasse repo` (still deferred from 0.13.0).
- Post-hoc token accounting.
- Hookify tom-voice extension (side task in iCloud, tracked separately).
- Any automated status transition writes.
