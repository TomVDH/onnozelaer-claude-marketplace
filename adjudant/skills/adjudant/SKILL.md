---
name: adjudant
description: Use when operating an Obsidian vault — connect a project, sync state, check status, tidy mechanical drift (tidy), deep restructure (ramasse), run diagnostics (dream), or create canvases/diagrams (draw). Handles vault layout, frontmatter, tags, wikilinks, templates, and project AGENTS.md/CLAUDE.md files. Also when writing decisions, sessions, notes, or docs into a vault, or when the user types `/adjudant {verb}`.
version: 0.3.0
user-invocable: true
argument-hint: "[connect|port|sync|check|tidy|ramasse|dream|draw] [args]"
license: MIT
---

# Adjudant

Vault editor/writer and project initializer. One skill, one command, eight verbs. Pairs with hookify for universal drift-defense hooks, and with Gemineye for Gemini-assisted review hand-off.

## Verb router

| Verb | Loads | Purpose |
|---|---|---|
| `connect` | `reference/connect.md` | Rigid project init — breadcrumb, AGENTS.md+CLAUDE.md, vault scaffold, session note, .gitignore |
| `port` | `reference/port.md` | Migrate any legacy project (raw / obsidian-bridge / hand-authored) to adjudant compliance via two-phase preview → apply |
| `sync` | `reference/sync.md` | Push brief + handoff to vault |
| `check` | `reference/check.md` | Read-only project + vault summary (consumes `check.py` JSON) |
| `tidy` | `reference/tidy.md` | Mechanical sweep — rebuild indexes, normalise tags, fix wikilink form. Two-phase preview→apply (via `tidy.py`) |
| `ramasse` | `reference/ramasse.md` | Deep structural refactor — used sparingly, superpowers-driven planning |
| `dream` | `reference/dream.md` | Diagnostic crawl — drift report (consumes `dream.py` JSON), no auto-fix |
| `draw` | `reference/draw.md` | Create canvas / base / diagram |

When a verb is invoked, load **only** the matching reference file. Do not bring all reference files into context.

## Python helper layer (v0.3.0)

The four heaviest verbs are backed by Python helpers in `scripts/` that pre-digest project files into compact structured output Claude renders. This keeps per-verb context cost bounded regardless of project size.

| Verb | Helper | Output |
|---|---|---|
| `port` | `port.py` | preview/apply with backup |
| `tidy` | `tidy.py` + `_vault_walk.py` | preview/apply with backup |
| `dream` | `dream.py` + `_vault_walk.py` | JSON drift catalog |
| `check` | `check.py` + `_vault_walk.py` | JSON status snapshot |

`_vault_walk.py` is the shared primitives module (frontmatter parsing, wikilink extraction, schema constants). Has a CLI smoke-test mode for debugging: `python3 _vault_walk.py --project-dir PATH [--vault-dir PATH]`.

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
