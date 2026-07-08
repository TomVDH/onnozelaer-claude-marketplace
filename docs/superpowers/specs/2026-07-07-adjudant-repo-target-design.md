---
date: 2026-07-07
status: design — ready for implementation
scope: adjudant plugin — extend check/tidy with a [vault|repo|all] target so adjudant audits and safely repairs the code repo, not just the vault
plugin: adjudant
version-target: 0.13.0
supersedes: 2026-06-07-adjudant-repo-target-design.md
related: 2026-06-07-adjudant-repo-target.md (superseded plan)
---

# Repo as a second cleanup target (v2): check/tidy the repo, not just the vault

## Why this supersedes the June 7 design

The original design (`2026-06-07-adjudant-repo-target-design.md`, version-target
0.6.0) centred on **version drift** — `marketplace.json` disagreeing with a
plugin's `plugin.json` — with the gemineye `0.3.1≠0.3.2` mismatch as its
headline dogfood, and a `tidy repo` **version-sync fixer** as the payoff.

Two things changed between then and now (0.12.0):

1. **Version drift is already gated.** `scripts/check_marketplace_versions.py`
   runs as a pre-commit hook enforcing marketplace ↔ plugin.json parity for
   *every* plugin. Drift can no longer land in a commit, and the gemineye
   mismatch is resolved (registry in sync). A `tidy repo` version-sync fixer
   would be redundant with a gate that is strictly stronger (it *blocks*, not
   *repairs*).
2. **The structural drift the original design also named is still real and
   unaddressed:** only `adjudant/` has the Impeccable symlink harness; the
   other skill-bearing plugins do not; stale plan files accumulate in
   `docs/superpowers/`.

So the scope narrows to what still has value: a **read-only structural audit**
(`check repo`) and a **safe mechanical repair arm** (`tidy repo`, symlink
repair only). `ramasse repo` and the version-sync fixer are deferred.

## Goals

1. **One target argument, two existing verbs.** `check` and `tidy` each take
   `[vault|repo|all]`. No new verb vocabulary; the locked three-tier model
   stays intact.
2. **Exact back-compat.** Default target is `vault`. `/adjudant check` and
   `/adjudant tidy` with no argument behave identically to today.
3. **Layered detectors.** A general repo-hygiene core (context files, plan age)
   runs on any connected repo; a marketplace-aware layer auto-activates only
   when `.claude-plugin/marketplace.json` is present.
4. **Same safety contract.** `tidy repo` is two-phase `preview → apply`,
   idempotent, `.legacy`-backed, never breaks.
5. **Mirror existing modules.** New helpers parallel `_vault_walk.py`,
   `ramasse_scan.py`, `tidy.py` one-for-one in structure, CLI shape, and JSON
   I/O contract.
6. **Reuse, don't duplicate.** The version-coherence signal in `check repo`
   reuses `check_marketplace_versions.py`'s logic rather than re-implementing
   it. `check repo` *displays* version parity read-only; it never "fixes" it
   (the pre-commit gate owns that).

## Non-goals

- **No `ramasse repo` yet.** Migrating a plugin *into* the symlink pattern, or
  scaffolding per-plugin context files, is deliberate structural work with no
  current trigger. Deferred to a later release once `check repo` surfaces
  demand. When built, its mechanical sub-steps will call `repo_tidy.py`.
- **No `dream repo`.** The semantic tier stays vault-only.
- **No version-sync fixer.** Superseded by the `check_marketplace_versions.py`
  pre-commit gate.
- **No target on `connect`/`port`/`sync`/`sitrep`/`draw`/`board`.** Those are
  project↔vault flows or generators, not cleanup tiers.
- **No auto-adoption in `tidy`.** `tidy repo` only *repairs* a broken symlink
  where the harness is already adopted; it never *creates* a harness for a
  plugin that lacks one.
- **No overlap with hookify.** Hookify owns regex drift-defense. This is
  structural drift only.

## Surface

| Invocation | Tier | Behaviour |
|---|---|---|
| `/adjudant check [vault\|repo\|all]` | read-only | Audit. Reports repo drift alongside (or instead of) the vault snapshot. Never writes. |
| `/adjudant tidy [vault\|repo\|all]` | surface mechanical | Safe repo fixes (symlink repair). Two-phase `preview → apply`. Idempotent. |

Default target = `vault`. `argumentHint` for `check` and `tidy` becomes
`[vault|repo|all]` (was `(no args)`). `ramasse` is untouched (stays `(no args)`).

**Path resolution.** Repo ops use `--project-dir` as the repo root directly.
Only vault ops follow the breadcrumb into the vault. No new resolution logic —
the repo *is* the project dir. `all` runs the vault pass (breadcrumb-resolved)
and the repo pass (project-dir) and renders both.

## Detectors (`repo_scan.py`)

**General core** (any connected repo):
- **context-files** — repo-root `AGENTS.md` + `CLAUDE.md` present, and
  `CLAUDE.md` opens with `@AGENTS.md` (a real, checkable convention). Per-plugin
  context-file absence is reported *informational*, NOT counted in
  `drift_items` — the root files cover this repo's scale.
- **plan-age** — `docs/superpowers/**` plan/spec files with no completion
  marker, older than a threshold (default 30 days), by mtime. Reported with age.

**Marketplace layer** (auto-activates when `.claude-plugin/marketplace.json`
found — `repo_walk.is_marketplace_repo()`):
- **version-coherence** — marketplace entry version vs each `plugin.json`
  (reuses `check_marketplace_versions` logic). Read-only display. Any mismatch
  counts as drift, but in practice the pre-commit gate keeps it at zero.
- **symlink-integrity** — for each plugin that HAS a `skills/` dir, the
  `source/`, `.claude/`, `.gemini/` skill symlinks exist and resolve to the
  canonical `skills/<name>` dir. A plugin with no `skills/` needs no harness and
  is skipped (not drift). Mirrors the `harness-parity` validator's contract.
- **registration-coherence** — every plugin dir at repo root is registered in
  `marketplace.json`, and every registered `source` path exists.

`drift_items` is cardinality-based — distinct items summed, never
frequency-weighted — identical to `ramasse_scan.py`. Informational signals
(per-plugin context files) are carried in the JSON but excluded from the score.

## `tidy repo` — the one safe fixer

**Symlink repair.** A plugin is *harness-adopted* iff its canonical
`skills/<name>/` exists AND at least one of `source/`, `.claude/`, `.gemini/`
already carries the `skills/<name>` symlink. For an adopted plugin with a
missing or dangling harness symlink among the three, recreate it as a relative
symlink to the canonical dir. A plugin with a `skills/` dir but *zero* harness
symlinks is treated as not-adopted — `tidy repo` leaves it alone (auto-adoption
is `ramasse`-tier, deferred), so `tidy` can never silently harness a plugin.

Two-phase, mirroring `tidy.py`:
- `preview` writes `.adjudant-repo-tidy-preview/` (`summary.md`, `changes.json`,
  and a `files/` record of intended symlink targets).
- `apply` backs the live state up to `.adjudant-repo-tidy-backup/{ts}/*.legacy`
  (a dangling symlink's current target, recorded for reversibility), performs
  the symlink recreation, deletes the preview.

**Honest scope note.** On the current clean repo `tidy repo` has nothing to fix
(versions gated, adjudant's harness intact). It is the *repair arm* of
`check repo`'s *detect*: `harness-parity` fails the build when adjudant's
symlinks break; `tidy repo` is the tool that repairs them. It is also the
mechanical entry point the deferred `ramasse repo` will call.

## New modules & files

| New file | Mirrors | Role |
|---|---|---|
| `adjudant/scripts/repo_walk.py` | `_vault_walk.py` | Primitives: `walk_plugins(root)`, `parse_plugin_json`, `parse_marketplace_json`, `plugin_symlink_status`, `context_files_status`, `plan_file_ages`, `is_marketplace_repo`. Read-only. |
| `adjudant/scripts/repo_scan.py` | `ramasse_scan.py` | `detect_*()` per drift class + `run_scan()` → JSON with `drift_items`. Feeds `check repo`. Read-only. |
| `adjudant/scripts/repo_tidy.py` | `tidy.py` | `detect`/`preview`/`apply` for symlink repair. |
| `adjudant/scripts/test_repo_walk.py` | `test__vault_walk.py` | Unit tests. |
| `adjudant/scripts/test_repo_scan.py` | `test_ramasse_scan.py` | Unit tests. |
| `adjudant/scripts/test_repo_tidy.py` | `test_tidy.py` | Unit tests (preview → apply, idempotency, symlink repair). |
| `adjudant/skills/adjudant/reference/repo-standards.md` | `reference/vault-standards.md` | Single source of truth for repo conventions (version coherence, Impeccable pattern, context-file requirement, plan-age policy, registration rule). |

**Edits:**
- `reference/check.md`, `reference/tidy.md` — add the `[target]` dimension and a
  repo section each.
- `scripts/command-metadata.json` — `argumentHint` → `[vault|repo|all]` for
  `check` and `tidy`; bump `version` to 0.13.0. Verb descriptions stay ≤220
  chars (the `verb-description-length` validator).
- `skills/adjudant/SKILL.md` — router notes the dual target on check/tidy;
  content-authoring/reference list gains `repo-standards.md`; `argument-hint`
  frontmatter; bump `version`.
- `scripts/validate.py` — five new validators (below).
- `.gitignore` — add `.adjudant-repo-tidy-preview/` and
  `.adjudant-repo-tidy-backup/`.

## I/O contract

Helpers emit structured JSON on **stdout** (Claude renders), diagnostics on
**stderr**. CLI shape mirrors the originals:
`python3 repo_scan.py --project-dir PATH [--json]`;
`python3 repo_tidy.py {detect|preview|apply} --project-dir PATH`. Stdlib only.

## Validators added to validate.py (17 → 22)

- **`repo-standards-coverage`** — `reference/repo-standards.md` exists and names
  each detector category (mirrors `template-coverage`).
- **`repo-helper-parity`** — `repo_walk.py`, `repo_scan.py`, `repo_tidy.py` each
  exist with a matching `test_*.py` (mirrors the harness/helper doctrine).
- **`repo-tidy-preview-coherence`** — if `.adjudant-repo-tidy-preview/` exists,
  it has `summary.md` + `changes.json` + `files/` (mirrors #11).
- **`repo-tidy-backup-integrity`** — `.adjudant-repo-tidy-backup/` subdirs with
  files contain at least one `.legacy` (mirrors #12).
- **`gitignore-includes-repo-tidy-dirs`** — the two repo-tidy dirs are active
  `.gitignore` entries when either exists (mirrors #13).

The new `repo-standards.md` is also covered by `reference-doc-links` (validator
16) — no dead relative links permitted.

Existing **`version-consistency`** (validator 10) enforces the 0.13.0 bump
across `plugin.json` / `command-metadata.json` / `SKILL.md` / `marketplace.json`.

## Versioning

Bump **0.12.0 → 0.13.0** (minor — additive feature) via
`python3 scripts/bump_plugin_version.py adjudant 0.13.0`. Commit style:
`release(adjudant): v0.13.0 — repo as a second audit/repair target (check/tidy [vault|repo|all])`.

## Verification (end-to-end)

1. **Scan runs clean on this repo:**
   `python3 adjudant/scripts/repo_scan.py --project-dir . --json` → version
   coherence in sync, adjudant harness intact, registration coherent;
   `drift_items` reflects only genuinely-open structural items (e.g. stale
   plans), with per-plugin context files listed informational.
2. **Symlink repair is detected and repaired under a fixture:** a test breaks
   a harness symlink in a temp plugin tree; `repo_tidy.py preview` records the
   fix, `apply` recreates it with a `.legacy` backup, second `preview` is empty
   (idempotent).
3. **Back-compat:** `/adjudant check` and `/adjudant tidy` with no target behave
   exactly as 0.12.0 (vault).
4. **Verbs end-to-end:** `check repo` / `check all` / `tidy repo` load the right
   reference and dispatch the right helper.
5. **Tests green:**
   `python3 -m unittest discover -s adjudant/scripts -p 'test_repo_*.py'`.
6. **Validators green:** `python3 adjudant/scripts/validate.py` exits 0 with the
   five new checks (22 total).
7. **Housekeeping:** the superseded June plan + spec are tracked/archived so
   `plan-age` doesn't flag its own predecessors as live drift.
