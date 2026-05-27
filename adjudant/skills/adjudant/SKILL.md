---
name: adjudant
description: Use when operating an Obsidian vault — connect a project, sync state, check status, tidy mechanical drift (tidy), deep structural restructure (ramasse), or create canvases/diagrams (draw). Handles vault layout, frontmatter, tags, wikilinks, templates, and project AGENTS.md/CLAUDE.md files. Also when writing decisions, sessions, notes, or docs into a vault, or when the user types `/adjudant {verb}`.
version: 0.3.1
user-invocable: true
argument-hint: "[connect|port|sync|check|tidy|ramasse|draw] [args]"
license: MIT
---

# Adjudant

Vault editor/writer and project initializer. One skill, one command, seven verbs. Pairs with hookify for universal drift-defense hooks, and with Gemineye for Gemini-assisted review hand-off.

## Verb router

| Verb | Loads | Purpose |
|---|---|---|
| `connect` | `reference/connect.md` | Rigid project init — breadcrumb, AGENTS.md+CLAUDE.md, vault scaffold, session note, .gitignore |
| `port` | `reference/port.md` | Migrate any legacy project (raw / obsidian-bridge / hand-authored) to adjudant compliance via two-phase preview → apply |
| `sync` | `reference/sync.md` | Push brief + handoff to vault |
| `check` | `reference/check.md` | Read-only project + vault summary (consumes `check.py` JSON) |
| `tidy` | `reference/tidy.md` | Surface mechanical sweep — indexes, tags, wikilink form, `updated:`. Routine cadence. Two-phase preview→apply (via `tidy.py`) |
| `ramasse` | `reference/ramasse.md` | Deep structural clean — folder shape, schema, file types, naming, doc/decision mismatches. Sparing cadence. Analysis via `ramasse_scan.py`, planning + execute via superpowers |
| `draw` | `reference/draw.md` | Create canvas / base / diagram |

When a verb is invoked, load **only** the matching reference file. Do not bring all reference files into context.

## The locked three-tier model (v0.3.1)

```
tidy    = surface mechanical    (routine, daily/weekly, never breaks)
ramasse = deep structural clean (sparing, quarterly, deliberate)
dream   = content/knowledge/memory refresh (semantic; NOT YET BUILT — v0.4+)
```

`dream` is reserved for the future content-refresh verb that reads actual prose and identifies outdated/stale/redundant ideas. The structural-drift detector previously named `dream.py` in v0.3.0 has been renamed `ramasse_scan.py` and now feeds ramasse's analysis phase.

## Python helper layer

Verbs touching many files use a Python helper that pre-digests structured output Claude renders, keeping per-verb context cost bounded.

| Verb | Helper | Output |
|---|---|---|
| `port` | `port.py` | preview/apply with backup |
| `tidy` | `tidy.py` + `_vault_walk.py` | preview/apply with backup |
| `ramasse` | `ramasse_scan.py` + `_vault_walk.py` | JSON drift catalog (analysis phase) |
| `check` | `check.py` + `_vault_walk.py` | JSON status snapshot |

`_vault_walk.py` is the shared primitives module. Read-only CLI smoke-test: `python3 _vault_walk.py --project-dir PATH [--vault-dir PATH]`.

## Vault standards — single source of truth

`reference/vault-standards.md` is the authoritative spec for tag taxonomy, frontmatter requirements per file type, folder structure, file-naming rules, and wikilink form. All vault writes must conform. The build's `validate.py` enforces.

## Content authoring

For specialized content types, load the matching reference on demand:

- `reference/content-canvas.md` — `.canvas` files
- `reference/content-bases.md` — `.base` files
- `reference/content-mermaid.md` — mermaid diagrams
- `reference/content-markdown.md` — Obsidian-flavoured markdown (callouts, embeds, wikilinks)
- `reference/content-clipper.md` — Web Clipper templates
- `reference/content-cli.md` — Obsidian CLI

## Templates

`templates/` contains the canonical scaffolds for every file type Adjudant ships. Provisioning is done by `/adjudant connect`. Schema is enforced — every write must match the template frontmatter shape per `reference/vault-standards.md`.

## Hooks

This plugin registers 5 hooks (vault-aware only):

| Event | Script | Purpose |
|---|---|---|
| SessionStart | `hooks/scripts/session-start.sh` | Discover vault, detect AGENTS.md+CLAUDE.md, init/resume session note |
| UserPromptSubmit | `hooks/scripts/user-prompt-reminder.sh` | Smart-fire vault reminder when project isn't linked and prompt has vault-y keywords |
| PostToolUse (Write) | `hooks/scripts/posttooluse-vault-log.py` | Append vault file creation entries to today's session log |
| PreCompact | `hooks/scripts/precompact.py` | Append `paused (compaction)` marker + sync handoff to vault |
| SessionEnd | `hooks/scripts/sessionend.sh` | Append `session ended` marker + sync handoff to vault |

Universal drift-defense hooks (git safety, voice checks, etc.) live in hookify, not here.
