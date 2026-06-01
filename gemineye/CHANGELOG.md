# Gemineye — Changelog

All notable changes to the `gemineye` plugin are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
This project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.0] — 2026-06-01

Migrate the review backend from the deprecated `gemini` CLI to Google's
Antigravity CLI (`agy`), and clear accumulated cross-plugin drift.

### Added
- **Antigravity CLI (`agy`) as the primary backend.** Invocation is
  `agy --sandbox --add-dir "$ROOT" -p` — write-sandboxed, read-trusted to the
  project root. Backend-detection block prefers `agy`, falls back to `gemini`.
- **Folder-trust guidance** — read-trust scoped to the project root via
  `--add-dir`; one-time interactive `agy` handshake documented for the case
  where a headless `-p` call would block on a trust prompt.
- Failure-mode rows for the `agy -p` non-TTY stdout bug (#27466) and the
  untrusted-folder hang.

### Changed
- **Tier model collapses under `agy`.** `agy` exposes no per-invocation model
  flag, so the plugin pins **no model IDs**; `megareview` now differs by prompt
  scope, not a model string. (Legacy `gemini` fallback still honours
  `-m gemini-2.5-pro` for the pro tier.)
- Containment reframed: `--sandbox` + `--add-dir` (read-trust) replaces the old
  "folder is not trusted" stance; forbidden flag is now
  `--dangerously-skip-permissions` (agy) / `--yolo` (gemini).

### Deprecated
- **`gemini` CLI fallback is temporary.** Google sunsets `gemini` for AI
  Pro/Ultra and free users on **2026-06-18**. The fallback exists only for the
  transition; a follow-up release will remove the `gemini` path entirely.

### Removed
- **Dead `cabinet-of-imd` / Bostrol coupling.** cabinet v3.0.0 sunset all
  functionality (character-only), so "Bostrol indexes Gemineye outputs" no
  longer holds — dropped from SKILL.md and README.
- The non-existent `--file` flag throughout `invocation-patterns.md` (it was
  flagged broken in 0.3.2). Multi-file context is `--add-dir` + inline bundle.

### Fixed
- Stale claim that adjudant auto-harvests at PreCompact — false since adjudant
  v0.7.0 made the hook mechanical-only. `/gemineye harvest` is the harvest
  surface; reframed as historical note.
- README subcommand list was missing `harvest`; added.
- `marketplace.json` version drift (registry was 0.3.1 vs plugin 0.3.2) — now
  synced at 0.5.0.

## [0.3.2] — 2026-05-27

### Fixed
- **Model IDs are no longer hard-coded.** Previously the plugin pinned
  `gemini-3.5-flash` / `gemini-3.5-pro`, which the Gemini CLI rejects
  with `ModelNotFoundError (404)` — those revs don't exist.
  - Fast tier (review, wip, sanity, name, compare, harvest) now omits
    `-m` entirely; the CLI picks its current default model. No more
    drift when Google rotates fast models.
  - Pro tier (megareview) uses `-m gemini-2.5-pro`. Update this single
    string in `SKILL.md` when a new Pro rev ships.
- README, SKILL.md, invocation-patterns.md, and the persisted-file
  frontmatter template all rephrased in tier terms (`fast` / `pro`)
  instead of version-pinned model IDs.

### Known
- The `--file` flag in `references/invocation-patterns.md` does not
  exist in the current `gemini` CLI (rejected as `Unknown argument`).
  Multi-file context must be inlined into the prompt for now. Fix
  deferred to a follow-up.

## [0.3.1] — 2026-05-27

### Changed
- Concise skill description in SKILL.md frontmatter (commit 080aa8c).

## [0.3.0]

### Changed
- **Renamed** plugin slug `gemin-eye` → `gemineye` (command is now
  `/gemineye`; persisted-output folders are now `gemineye/`). Breaking —
  re-install from the marketplace to pick up the new command.
- Vault pairing references updated from the retired `obsidian-bridge`
  to its successor `adjudant` in the live skill docs.

## [0.2.0] — 2026-05-01

Action-oriented restructure. Sandboxed by default. Rigid prompt template.

### Added
- `/gemineye` command with seven action-shaped subcommands:
  `review`, `megareview`, `wip`, `sanity`, `name`, `compare`, `save`.
- **Mandatory prompt template** — every Gemini call wraps the prompt
  in `ROLE / DO / DON'T / SCOPE — IN / SCOPE — OUT / OUTPUT / CONTEXT`.
  No exceptions. Filled-in per subcommand in `invocation-patterns.md`.
- **Sandbox by default** — every call passes `--sandbox`. Folder is
  not trusted. Gemini reviews only — never writes files. No `--yolo`.
- **Edit format** — proposed changes return as elaborate code blocks
  (`PROPOSED EDIT — file:line` + BEFORE/AFTER blocks + WHY). Claude
  reviews and applies.
- **Model split** — default `gemini-3.5-flash`; `megareview` switches
  to `gemini-3.5-pro` for the deeper pass.
- `megareview` subcommand — broad sweep across module / feature /
  plugin. Cross-file patterns, inconsistencies, architectural concerns.
- `wip` subcommand — review uncommitted changes + current branch diff.
  "Before you commit" framing.
- `compare` subcommand — head-to-head ranking of 2+ options with
  explicit criteria, comparison table, winner + runner-up condition.
- `save` subcommand — explicit persist trigger; in-line stays in-line
  until `save` runs.
- Override clause: `"drop the sandbox"` for the rare case Tom needs
  Gemini outside the sandbox (logged in frontmatter).

### Changed
- SKILL.md sharpened end-to-end. Tighter prose, imperative voice,
  table-led where prose was redundant. Operating-modes section
  collapsed — modes now correspond to subcommands.
- `references/invocation-patterns.md` rewritten — every prompt
  scaffold conforms to the rigid template. Loose prose prompts removed.
- `name` subcommand broadened — now works on a single thing or a
  related set with internal coherence.
- `compare` subcommand broadened — supports 2+ options, not just two.
- README rewritten around subcommands and sandbox/review-only defaults.
- Updated vault-bridge references — vault integration now lives in
  `obsidian-bridge` (post v2.3.0 cabinet refactor), not `cabinet-of-imd`.

### Removed
- Implicit "operating modes" abstraction (in-line / CLI / persisted) —
  replaced by explicit subcommands and `save`.
- Loose prose prompt scaffolds in `invocation-patterns.md` — every
  scaffold now uses the rigid template.

## [0.1.0] — 2026-04-28

Initial release.

### Added
- `gemineye` skill — invoke Gemini as a review and coding partner from
  inside Claude Code, with strict context-sourcing and output-routing
  rules.
- Three operating modes: in-line review (default), CLI review with file
  context, persisted review.
- Context-sourcing protocol prioritising Claude-prepared bundles, project
  Markdown, and Obsidian vault context (when `vault-bridge` is active).
- Output protocol routing all persisted Gemini reviews to `gemineye/`
  subfolders (vault project folder or `docs/gemineye/`), never into
  source paths.
- Override clauses for relaxing default containment when explicitly
  authorised.
- Pairing rules for `vault-bridge` and `cabinet-of-imd` (Bostrol-mediated
  indexing of Gemini reviews as documentation artefacts).
- `references/invocation-patterns.md` — reusable prompt scaffolds (code
  review, doc review, architecture sanity check, naming bikeshed, prompt
  review), CLI usage patterns, context-bundle assembly guidance, and
  anti-patterns.
- Pre-flight check for the `gemini` CLI on `PATH`.
- `README.md` with install + behaviour-at-a-glance summary.

### Dependencies
- `gemini` CLI — Google's official Gemini CLI must be on `PATH`.
- Optional: `vault-bridge` skill (from `cabinet-of-imd`) for vault
  integration.
- Optional: `cabinet-of-imd` plugin for Bostrol-mediated indexing.
