---
name: adjudant
description: Use when the user wants to operate an Obsidian vault — connect a project, sync state, check status, tidy the vault, run diagnostics, or create visual artefacts. Handles vault layout, frontmatter schema, tag taxonomy, wikilink form, folder conventions, and template provisioning. Also use when working with project-level AGENTS.md/CLAUDE.md context files, when writing decisions/sessions/notes/docs into a vault, or whenever the user types `/adjudant {verb}`.
version: 0.1.0
user-invocable: true
argument-hint: "[connect|sync|check|ramasse|dream|draw] [args]"
license: MIT
---

# Adjudant

Vault editor/writer and project initializer. One skill, one command, six verbs. Pairs with hookify for universal drift-defense hooks.

## Verb router

| Verb | Loads | Purpose |
|---|---|---|
| `connect` | `reference/connect.md` | Rigid project init — breadcrumb, AGENTS.md+CLAUDE.md, vault scaffold, session note, .gitignore |
| `sync` | `reference/sync.md` | Push brief + handoff to vault |
| `check` | `reference/check.md` | Read-only project + vault summary |
| `ramasse` | `reference/ramasse.md` | Rebuild indexes + normalize tags + fix wikilink form |
| `dream` | `reference/dream.md` | Diagnostic crawl — drift report, no auto-fix |
| `draw` | `reference/draw.md` | Create canvas / base / diagram |

When a verb is invoked, load **only** the matching reference file. Do not bring all reference files into context.

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
| PostToolUse (Write\|Edit\|MultiEdit) | `hooks/scripts/posttooluse-vault-log.py` | Append vault file creation entries to today's session log |
| PreCompact | `hooks/scripts/precompact.py` | Append `paused (compaction)` marker + run `/adjudant sync` |
| SessionEnd | `hooks/scripts/sessionend.sh` | Append `session ended` marker + run `/adjudant sync` |

Universal drift-defense hooks (git safety, voice checks, etc.) live in hookify, not here.
