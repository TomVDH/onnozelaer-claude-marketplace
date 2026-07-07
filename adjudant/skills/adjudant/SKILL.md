---
name: adjudant
description: Operate an Obsidian vault from a code project. `/adjudant {connect|port|sync|check|sitrep|tidy|ramasse|dream|draw|board}` — project init and migration, schema-enforced writes, three-tier cleanup (tidy/ramasse/dream), read-only status (check) and orientation (sitrep), diagrams and canvases (draw), and a self-hosted kanban board. Also fires whenever decisions, sessions, or notes are written into a linked vault.
version: 0.12.0
user-invocable: true
argument-hint: "[connect|port|sync|check|sitrep|tidy|ramasse|dream|draw|board] [args]"
license: MIT
---

# Adjudant

Vault editor/writer and project initializer. One skill, one command, ten verbs. Pairs with hookify for universal drift-defense hooks, and with Gemineye for Gemini-assisted review hand-off.

## Verb router

| Verb | Loads | Purpose |
|---|---|---|
| `connect` | `reference/connect.md` | Rigid project init — breadcrumb, AGENTS.md+CLAUDE.md, vault scaffold, session note, .gitignore |
| `port` | `reference/port.md` | Migrate any legacy project (raw / obsidian-bridge / hand-authored) to adjudant compliance via two-phase preview → apply |
| `sync` | `reference/sync.md` | Push brief + handoff to vault |
| `check` | `reference/check.md` | Read-only project + vault summary (consumes `check.py` JSON) |
| `sitrep` | `reference/sitrep.md` | ELI5 orientation briefing — where we were, what's done, where the vault is, where to start. Read-only (consumes `sitrep.py` JSON). For re-orienting after a break |
| `tidy` | `reference/tidy.md` | Surface mechanical sweep — indexes, tags, wikilink form, `updated:`. Routine cadence. Two-phase preview→apply (via `tidy.py`) |
| `ramasse` | `reference/ramasse.md` | Deep structural clean — folder shape, schema, file types, naming, doc/decision mismatches. Sparing cadence. Analysis via `ramasse_scan.py`, planning + execute via superpowers |
| `dream` | `reference/dream.md` | Content/knowledge/memory refresh — semantic, judgment-heavy. `dream.py` (read-only) emits a 10-category comparator catalog (staleness, supersession, contradictions, redundancy, stale refs, orphans, unacted decisions, gaps, dangling scopes); Claude judges, superpowers executes |
| `draw` | `reference/draw.md` | Create canvas / base / mermaid diagram — hand-authored or generated from vault data via `graph.py` (relations / board / tiers) |
| `board` | `reference/board.md` | Scaffold a self-hosted work-order kanban — drag-to-move, disk-persisted, seeded from `tasks/`. `--project <slug>` for one project, `--all` for the whole vault; `status` prints terminal column counts |

When a verb is invoked, load **only** the matching reference file. Do not bring all reference files into context.

## The locked three-tier model

```
tidy    = surface mechanical    (routine, daily/weekly, never breaks)
ramasse = deep structural clean (sparing, quarterly, deliberate)
dream   = content/knowledge/memory refresh (semantic; judgment-heavy)
```

`dream` (v0.6.0) reads actual prose and surfaces outdated/contradictory/redundant/stale/orphaned content as *candidates* for Claude to judge. `dream.py` is its read-only analyser — net-new, not to be confused with the v0.3.0 file once named `dream.py` that did structural drift and was renamed `ramasse_scan.py` to feed ramasse's analysis phase.

## Python helper layer (v0.4.0)

Every file-touching verb is backed by a Python helper. Helpers follow the `.claude/adjudant` breadcrumb automatically — pass `--project-dir` pointed at the code project root and the helper auto-resolves to the vault project. Cross-machine portable via `vault_name` fallback resolution.

| Verb | Helper | Output |
|---|---|---|
| `connect` | `connect.py` | idempotent project init (5 steps + projects-index row) |
| `port` | `port.py` | preview/apply with backup |
| `sync` | `sync.py` | brief refresh + handoff mirror + projects-index row refresh |
| `tidy` | `tidy.py` + `_vault_walk.py` | preview/apply with backup |
| `ramasse` | `ramasse_scan.py` + `_vault_walk.py` | JSON drift catalog (analysis phase); planning + execute via superpowers |
| `dream` | `dream.py` + `_vault_walk.py` | JSON content/staleness comparator catalog (analysis phase); judge + plan + execute via superpowers |
| `check` | `check.py` + `_vault_walk.py` | JSON status snapshot |
| `sitrep` | `sitrep.py` + `_vault_walk.py` | JSON orientation briefing (recent activity, NEXT, vault location + counts); Claude renders ELI5 |
| `board` | `board.py` + `_vault_walk.py` | scaffold per-project `board-data.json` + a self-contained `board.html`; resolves any project by slug (or `--all`) via `enumerate_projects`. Refresh-without-clobber: re-seeding from `tasks/` merges, preserving dragged columns (idempotent; `--force` rebuilds with a `.bak`). `status` prints per-column counts |
| `draw` | `graph.py` + `_vault_walk.py` | generated mermaid fences from vault data — `relations` (wikilink graph, node-capped), `board` (kanban snapshot), `tiers` (cleanup model). Read-only |

`_vault_walk.py` is the shared primitives module (frontmatter, wikilinks, tags, vault index, vault/project resolvers, schema constants). Read-only CLI smoke-test: `python3 _vault_walk.py --project-dir PATH [--vault-dir PATH]`.

## Vault standards — single source of truth

`reference/vault-standards.md` is the authoritative spec for tag taxonomy, frontmatter requirements per file type, folder structure, file-naming rules, and wikilink form. All vault writes must conform. The build's `validate.py` enforces.

## Content authoring

For specialized content types, load the matching reference on demand:

- `reference/content-canvas.md` — `.canvas` files
- `reference/content-bases.md` — `.base` files
- `reference/content-mermaid.md` — mermaid diagrams (syntax)
- `reference/mermaid-generation-rules.md` — mermaid generation discipline (always applies when producing fences)
- `reference/content-markdown.md` — Obsidian-flavoured markdown (callouts, embeds, wikilinks)
- `reference/content-clipper.md` — Web Clipper templates
- `reference/content-cli.md` — Obsidian CLI

## Templates

`templates/` contains the canonical scaffolds for every file type Adjudant ships. Provisioning is done by `/adjudant connect`. Schema is enforced — every write must match the template frontmatter shape per `reference/vault-standards.md`.

## Hooks

This plugin registers 5 hooks (vault-aware only):

| Event | Script | Purpose |
|---|---|---|
| SessionStart | `hooks/scripts/session-start.sh` | Discover vault, detect AGENTS.md+CLAUDE.md, init/resume session note; stamp the Claude Code conversation UUID into `session_id:` (list, idempotent on resume) |
| UserPromptSubmit | `hooks/scripts/user-prompt-reminder.sh` | Smart-fire vault reminder when project isn't linked and prompt has vault-y keywords (at most once per session) |
| PostToolUse (Write) | `hooks/scripts/posttooluse-vault-log.py` | Append vault file creation entries to today's session log + stamp `source_session: <uuid>` into the new file's frontmatter (skips session notes / `_handoff` / `_index*` / `_iteration`) |
| PreCompact | `hooks/scripts/precompact.py` | Mechanical, no model calls (5s budget): append enriched pause tombstone (`— next: …`) + mirror handoff with a freshness header (traffic light · age · NEXT · stale flag) |
| SessionEnd | `hooks/scripts/sessionend.sh` | Append `session ended` marker + sync handoff to vault |

Universal drift-defense hooks (git safety, voice checks, etc.) live in hookify, not here.
