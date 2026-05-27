# Adjudant

Vault editor/writer and project initializer for Claude Code (and Gemini CLI). Successor to `obsidian-bridge`. One skill, one command, seven verbs.

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
| Verbs | `connect`, `sync`, `check`, `ramasse`, `dream`, `draw` |
| Skill | one (`adjudant`) — verbs dispatch internally via reference files |
| Hooks | five (SessionStart, UserPromptSubmit, PostToolUse, PreCompact, SessionEnd) |
| Templates | 18 (AGENTS.md, CLAUDE.md, project briefs × 4, session, decision, note, doc, handoff, source, iteration, release, dream-report, home, indexes × 2) |
| Drift defense | `python3 scripts/validate.py` — six validators, runs via pre-commit hook |

## Verbs

| Verb | Purpose |
|---|---|
| `/adjudant connect` | Rigid 5-step project init — breadcrumb, AGENTS.md + CLAUDE.md, vault scaffold, session note, .gitignore. Idempotent. |
| `/adjudant sync` | Push brief + handoff to vault. |
| `/adjudant check` | Read-only project + vault summary. |
| `/adjudant ramasse` | Rebuild `_index.md` files, normalize tags, fix wikilink form. |
| `/adjudant dream` | Diagnostic crawl — drift report, broken wikilinks, doc/decision mismatches. Reports only, no auto-fix. |
| `/adjudant draw <canvas\|base\|diagram> <name>` | Create visual artefacts. |

## Architecture

- **Source of truth**: `skills/adjudant/` — the canonical skill directory.
- **Harness copies**: `source/skills/adjudant/`, `.claude/skills/adjudant/`, and `.gemini/skills/adjudant/` are symlinks to the canonical. Edit the canonical, all harnesses see it instantly. No build step.
- **Validators**: `scripts/validate.py` enforces schema coherence on pre-commit.

## Vault standards

`source/skills/adjudant/reference/vault-standards.md` is the authoritative spec for tag taxonomy, frontmatter, folder structure, file-naming, and wikilink form. All vault writes conform.

## Hooks

All five hooks are vault-aware. Universal drift-defense (git safety, voice checks, etc.) lives in `hookify`, not here.

## Pairing

Pairs with `gemineye` for Gemini-assisted review hand-off (see the Gemineye plugin).

## License

MIT
