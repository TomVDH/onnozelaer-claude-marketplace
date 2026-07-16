# Adjudant

Vault editor/writer and project initializer for Claude Code (and Gemini CLI). Successor to `obsidian-bridge`. One skill, one command, eleven verbs, Python helpers under each.

## Install

```
# in Claude Code
/plugin marketplace add TomVDH/onnozelaer-claude-marketplace
/plugin install adjudant
```

## Surface

| | |
|---|---|
| Command | `/adjudant {verb}` |
| Verbs | `connect`, `port`, `sync`, `check`, `sitrep`, `tidy`, `ramasse`, `dream`, `draw`, `board`, `shelf` |
| Skill | one (`adjudant`) — verbs dispatch internally via reference files |
| Hooks | five (SessionStart, UserPromptSubmit, PostToolUse, PreCompact, SessionEnd) |
| Templates | 18 file-type scaffolds + `board.html` (self-hosted kanban) |
| Python helpers | `_vault_walk.py` · `_handoff_freshness.py` · `_session_stamp.py` (primitives), `connect.py`, `port.py`, `sync.py`, `tidy.py`, `ramasse_scan.py`, `dream.py`, `board.py`, `graph.py`, `check.py`, `sitrep.py`, `shelf.py`; repo target: `repo_walk.py`, `repo_scan.py`, `repo_tidy.py` |
| Drift defense | `python3 scripts/validate.py` — 22 validators, runs via pre-commit |
| Tests | 479 unit tests; `python3 -m unittest discover -p 'test_*.py'` |

## The three-tier cleanup model (locked 2026-05-26)

```
tidy    = surface mechanical    (routine; tags, indexes, wikilink form, updated:)
ramasse = deep structural clean (sparing; folders, schema, file types, naming, renames)
dream   = content / knowledge / memory refresh  (semantic; staleness, contradictions, redundancy)
```

Risk tolerance is the dividing line: tidy never breaks anything; ramasse can break things deliberately under human supervision via the superpowers chain; dream is LLM-judgment-heavy semantic cleanup — `dream.py` emits a read-only comparator catalog, Claude judges, and a superpowers chain applies the refresh with backups for destructive content ops.

## Verbs

| Verb | Purpose | Helper |
|---|---|---|
| `/adjudant connect` | Onboard a code project to a vault. Rigid 5-step idempotent init. | `connect.py` |
| `/adjudant port` | Migrate a legacy project (raw / obsidian-bridge / hand-authored) to adjudant compliance. Two-phase preview → apply. | `port.py` |
| `/adjudant sync` | Push project state to the vault: refresh brief, mirror handoff, refresh project-row counts. | `sync.py` |
| `/adjudant check [vault\|repo\|all]` | Read-only summary — project + vault snapshot, schema compliance; `repo`/`all` also audit repo structure (versions, symlinks, registration, stale plans). | `check.py`, `repo_scan.py` |
| `/adjudant sitrep` | ELI5 orientation briefing — where we were, what's done, where the vault is, where to start. Read-only. | `sitrep.py` |
| `/adjudant tidy [vault\|repo\|all]` | Surface mechanical sweep — rebuild indexes, normalise tags, fix wikilink form. Two-phase preview → apply; `repo`/`all` also repair adopted-plugin harness symlinks. | `tidy.py`, `repo_tidy.py` |
| `/adjudant ramasse` | Deep structural clean — analysis phase via `ramasse_scan.py`, planning + execute via the superpowers chain. | `ramasse_scan.py` |
| `/adjudant dream` | Content/knowledge/memory refresh — semantic. Analysis via `dream.py` (read-only comparator catalog), judge + plan + execute via the superpowers chain, backups for destructive content ops. | `dream.py` |
| `/adjudant draw <canvas\|base\|diagram> <name\|type>` | Create visual artefacts — canvases, bases, mermaid diagrams (hand-authored or generated from vault data). | `graph.py` |
| `/adjudant board [scaffold\|serve\|status] [--project <slug>\|--all]` | Scaffold a self-hosted work-order kanban — drag-to-move, disk-persisted, seeded from `tasks/`. One project, a named one, or the whole vault. Re-seeds without clobbering dragged cards or custom columns; `status` prints terminal column counts. | `board.py` |
| `/adjudant shelf [<slug> <state>] [--reason "..."]` | Project lifecycle: status table across zones (list) and confirmed transitions (preview/apply): brief + status log + zone move + wikilink rewrite + index row. | `shelf.py` |

All helpers follow the breadcrumb: pass `--project-dir` (connect/port also accept it as an alias of their original `--project-root`) pointed at your **code project root** (where `.claude/adjudant` lives) and the helper auto-resolves to the vault project. Direct vault-project paths still work for backward compatibility.

## Architecture

- **Canonical skill location**: `skills/adjudant/` — single source of truth.
- **Harness copies**: `source/skills/adjudant/`, `.claude/skills/adjudant/`, `.gemini/skills/adjudant/` are symlinks. Edit the canonical, all harnesses see it. No build step.
- **Helper layer doctrine**: every verb touching >10 files gets a Python helper that pre-digests structured output Claude renders. Keeps per-verb context cost bounded regardless of project size.
- **Cross-machine portability**: the breadcrumb stores both `vault_path` (absolute, current machine) and `vault_name` (canonical). If the absolute path doesn't resolve on another machine, `vault_name` triggers a search of standard Obsidian locations under the current user's `$HOME`.
- **Validators**: `scripts/validate.py` enforces schema + version coherence on pre-commit.

## Vault standards

`skills/adjudant/reference/vault-standards.md` is the authoritative spec for tag taxonomy, frontmatter, folder structure, file-naming, and wikilink form. All vault writes conform.

## Hooks

All five hooks are vault-aware:

| Event | Script | Purpose |
|---|---|---|
| SessionStart | `hooks/scripts/session-start.sh` | Discover vault, detect AGENTS.md+CLAUDE.md, init/resume session note |
| UserPromptSubmit | `hooks/scripts/user-prompt-reminder.sh` | Smart vault reminder when project isn't linked and prompt has vault-y keywords |
| PostToolUse (Write) | `hooks/scripts/posttooluse-vault-log.py` | Append vault file creation entries to today's session log |
| PreCompact | `hooks/scripts/precompact.py` | Append `paused (compaction)` marker + sync handoff |
| SessionEnd | `hooks/scripts/sessionend.sh` | Append `session ended` marker + sync handoff |

Universal drift-defense (git safety, voice checks, etc.) lives in `hookify` — not here.

## Pairing

Pairs with `gemineye` for Gemini-assisted review hand-off (see the Gemineye plugin).

## License

MIT
