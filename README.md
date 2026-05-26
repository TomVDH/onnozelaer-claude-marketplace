# Onnozelaer Claude Marketplace

Personal collection of Claude Code plugins by Onnozelaer.

## Plugins

| Plugin | Version | Description |
|--------|---------|-------------|
| [cabinet-of-imd](./cabinet-of-imd) | 3.0.0 | The Cabinet of IMD Agents — a flavour layer for Claude Code. Eight college classmates with distinct personalities, voices, and disciplines serve as specialised web-development agents. Flavour-only (characters, voices, pairings, working disciplines); persistence is delegated to `adjudant` when active. |
| [iteration-shelf](./iteration-shelf) | 0.1.0 | Terminal-aesthetic review boards for in-browser design iteration — curated shelves and monster indexes with on-demand iframe loading, sidebar outliner, and browser-safety guards. Explicit invocation only. |
| [cli-wrapper-helper](./cli-wrapper-helper) | 1.0.0 | Build polished CLI tools — interactive bash TUIs (menus, spinners, animations) and clean Python helper scripts (sqlite readers, data reporters). Two skills: `bash-tui` and `python-helper`. |
| [gemineye](./gemineye) | 0.2.0 | Invoke Gemini as a review and coding partner from inside Claude Code. Vault-aware, context-disciplined, contained outputs — Gemini reviews land under `gemineye/` subfolders, never scattered across the codebase. |

### Iteration Shelf — Skill & Suggested Command

| Skill | Trigger | What it does |
|-------|---------|-------------|
| `iteration-shelf` | `/iteration-shelf` (explicit only) | Generates two review boards — a curated shelf and a monster index — from a JSON manifest. Terminal aesthetic, zero dependencies, on-demand iframe loading, warn-gate at 20+ loaded, sticky outliner sidebar with scrollspy. Pairs with the Cabinet plugin when active (Bostrol owns shelf ops). |

**Layering**: the shelf chrome has its own hard-coded terminal aesthetic. The iterations it indexes are unconstrained — use any aesthetic freely on those.

### CLI Wrapper Helper — Skills & Commands

| Skill | Trigger | What it does |
|-------|---------|-------------|
| `bash-tui` | bash script, shell tool, TUI, CLI menu, progress bar, spinner, splash screen, terminal polish | Pattern library for crafted bash CLIs. Mandatory checklist (strict mode, cleanup, semantic palette), copy-paste components (menus, tables, spinners, splash, transitions), multi-file architecture guide. |
| `python-helper` | python helper, read local data, query sqlite, python CLI, sqlite reader, csv reader, data reporter | Stdlib-only Python read-and-report scripts. `die()`, `section()`, `cell()` helpers, argparse, sqlite3, JSON/CSV patterns. Clean emoji-led output, `--json` mode for piping. |

| Command | What it scaffolds |
|---------|------------------|
| `/bash-new` | Full bash TUI script — palette, cleanup trap, splash, menu or linear flow |
| `/bash-component` | Single component — menu, spinner, loading bar, table, splash, or transition |
| `/py-new` | Python helper script — argparse, die/section/cell helpers, data source of choice |
| `/py-sqlite` | Python sqlite reader — named columns, truncated table, emoji readout |
| `/py-csv` | Python CSV reader — DictReader, filtering, optional aggregation |

### Gemineye — Skill

| Skill | Trigger | What it does |
|-------|---------|-------------|
| `gemineye` | `/gemineye`, "ask Gemini", "second opinion", "Gemini review", "Gemini's take" | Calls the `gemini` CLI with a deliberately bundled context (Claude-prepared, project Markdown, vault context when `adjudant` is active). Default mode is in-line; persistence routes Gemini outputs to `gemineye/` subfolders only — never into source. Override clauses unlock scaffolding, full-repo reviews, or direct file writes when Tom explicitly asks. |

**Layering**: Gemineye is a partner, not a successor — Claude remains the architect. Pairs with `adjudant` to auto-load project context and route outputs into the project's vault folder; pairs with `cabinet-of-imd` so Bostrol indexes Gemini reviews as documentation artefacts.

## Structure

```
├── .claude-plugin/
│   └── marketplace.json    # Marketplace manifest — lists all plugins with versions
├── cabinet-of-imd/         # Plugin: Cabinet of IMD Agents (v3.0.0)
│   ├── .claude-plugin/     # Plugin metadata (plugin.json)
│   ├── skills/             # 1 invocable skill (crew-roster)
│   ├── commands/           # 1 slash command (/cabinet)
│   ├── hooks/              # SessionStart, PreCompact, UserPromptSubmit, Stop, SessionEnd, Notification
│   ├── references/         # Character definitions, protocols, conventions, vault integration
│   ├── examples/           # Templates and samples
│   ├── CHANGELOG.md
│   └── README.md
├── iteration-shelf/        # Plugin: Iteration Shelf (v0.1.0, 1 skill)
│   ├── .claude-plugin/     # Plugin metadata (plugin.json)
│   ├── skills/iteration-shelf/SKILL.md
│   ├── references/         # Design tokens, schemas, interaction spec
│   ├── templates/          # curated-shelf.html, monster-index.html
│   ├── examples/           # Sample iteration-shelf.json
│   ├── CHANGELOG.md
│   └── README.md
├── cli-wrapper-helper/     # Plugin: CLI Wrapper Helper (v1.0.0, 2 skills, 5 commands)
│   ├── .claude-plugin/     # Plugin metadata (plugin.json)
│   ├── skills/bash-tui/    # Bash TUI skill — interactive terminal tools
│   ├── skills/python-helper/ # Python helper skill — read-and-report scripts
│   ├── commands/           # /bash-new, /bash-component, /py-new, /py-sqlite, /py-csv
│   ├── references/         # components.md, palette.md, architecture.md, python-helpers.md
│   └── evals/              # Skill evaluation cases
├── gemineye/              # Plugin: Gemineye (v0.2.0, 1 skill)
│   ├── .claude-plugin/     # Plugin metadata (plugin.json)
│   ├── skills/gemineye/SKILL.md
│   ├── references/         # invocation-patterns.md (prompt scaffolds, CLI usage)
│   ├── CHANGELOG.md
│   └── README.md
└── README.md               # This file
```

## Adding a new plugin

1. Create a directory at the repo root with the plugin slug (e.g. `my-new-plugin/`).
2. Add a `.claude-plugin/plugin.json` inside it with name, version, description, and author.
3. Add skills under `my-new-plugin/skills/<skill-name>/SKILL.md`.
4. Register the plugin in `.claude-plugin/marketplace.json` under the `plugins` array.
