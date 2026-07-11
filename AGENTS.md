# Repository Guidelines

`onnozelaer-claude-marketplace` — personal Claude Code plugin marketplace by Tom Vanderheyden (Onnozelaer). Hosts multiple plugins; each plugin is self-contained in its own directory.

## Project Structure

```
.
├── .claude-plugin/
│   └── marketplace.json     # Marketplace manifest — source of truth for every plugin's version + description
├── adjudant/                # Vault editor/writer + project initializer, /adjudant with ten verbs and a three-tier cleanup model (successor to the retired obsidian-bridge)
├── cabinet-of-imd/          # Crew/persona flavor layer (functionality sunset; character-only)
├── cli-wrapper-helper/      # Operating language for agent-built helper CLIs (bash TUI + python helper)
├── gemineye/                # Sandboxed Gemini second opinion via the agy CLI
├── iteration-shelf/         # Terminal-aesthetic in-browser design review boards
├── docs/                    # cross-plugin documentation
├── .pre-commit-config.yaml  # validators that fail the build on drift
├── README.md
└── AGENTS.md / CLAUDE.md    # this file + Claude overrides
```

## Adding a new plugin

1. Create `<plugin-name>/` at repo root with:
   - `.claude-plugin/plugin.json` — name, version, description, author, keywords
   - `commands/<plugin-name>.md` (if it has slash commands)
   - `skills/<skill-name>/SKILL.md` (if it has skills)
   - `hooks/hooks.json` + `hooks/scripts/` (if it has hooks)
   - `README.md`
2. Add an entry to `.claude-plugin/marketplace.json` with name, version, source path, description.
3. Bump marketplace version if needed.
4. Commit per the conventional-commits style below.

For plugins that follow the **Impeccable pattern** (one skill, one root command with sub-verbs):
- `<plugin>/skills/<plugin>/` is the real canonical directory (content lives here)
- `source/skills/<plugin>/`, `.claude/skills/<plugin>/`, and `.gemini/skills/<plugin>/` are all symlinks into it (`harness-parity` validator enforces they resolve to the canonical dir)
- `scripts/validate.py` enforces drift defense
- `scripts/command-metadata.json` is the single source of truth for verb metadata

`adjudant/` is the reference implementation of this pattern.

### Bumping a plugin version

A plugin's version is kept in lockstep across up to four files (`plugin.json`,
`scripts/command-metadata.json`, `SKILL.md` frontmatter, and the `marketplace.json`
entry). Don't edit them by hand — run `python3 scripts/bump_plugin_version.py <plugin>
<X.Y.Z>` to write all of them atomically (idempotent; enforced by the
`version-consistency` validator + `check_marketplace_versions.py`).

## Build & validate

No compile step. Symlinks propagate the canonical source to harness directories. Validators run via pre-commit (or manually).

```bash
# Install pre-commit hook (one-time per clone)
pre-commit install

# Run validators manually
pre-commit run --all-files

# Run adjudant's specific validators
python3 adjudant/scripts/validate.py
```

## Universal drift defense (via hookify)

Cross-machine, cross-project drift defense rules live in iCloud, NOT in this repo. Hookify reads them from each project's `.claude/` via symlinks.

| | |
|---|---|
| Canonical rules | `~/Library/Mobile Documents/com~apple~CloudDocs/Projects/IDE/claude/hookify/` |
| Install script | `~/Library/Mobile Documents/com~apple~CloudDocs/Projects/IDE/claude/install-hookify-rules.sh` |
| Install into a project | `cd /path/to/project && "$HOME/Library/Mobile Documents/com~apple~CloudDocs/Projects/IDE/claude/install-hookify-rules.sh"` |

Current rules: `git-safety`, `destructive-bash`, `tom-voice`, `secret-scan`, `no-deprecated-tags`, `icloud-eviction-paths`, `path-quote`. Idempotent install; rules sync across machines via iCloud.

Hooks that need logic (not regex) — symlink-integrity, plan-age, version-drift, AGENTS/CLAUDE presence — are not in hookify; they'd need custom shell hooks, currently deferred.

## Cross-machine setup

This repo is mirrored across two machines. The OneDrive folder syncs the working tree; the `.git` store lives **inside** OneDrive (small enough that packfile-deadlock issues haven't surfaced — monitor and move out-of-tree if they do).

| Machine | macOS user |
|---|---|
| Personal | `tomlinson` |
| Work | `tomvanderhegden` |

Always `git pull --ff-only` before starting work; the other machine is often ahead. Branch is `main`; PRs not currently used (direct pushes from both machines).

## Commit conventions

Conventional Commits style. Match existing history:

```
feat(adjudant): add /adjudant connect rigid init
fix(obsidian-bridge): v1.2.1 — stop waking Obsidian on every session
refactor(cabinet-of-imd): v2.3.0 — extract vault-bridge and dream to obsidian-bridge
release(obsidian-bridge): v1.1.0 — relations: schema extension on briefs
chore(marketplace): bump obsidian-bridge to 1.0.0 in marketplace.json registry
docs(obsidian-bridge): migration guide — old vault-bridge surface → new 7 verbs
```

- Scope is the plugin name (or `marketplace` for cross-plugin manifest changes).
- Version bumps use `release(<plugin>): vX.Y.Z — <summary>`.

## Naming

- Plugin slugs: kebab-case, no namespace prefix (`adjudant`, not `onnozelaer-adjudant`).
- Skill names inside a plugin: kebab-case.
- Command names: kebab-case after the `/`.

## What this repo does NOT contain

- No PR / branch workflow — work is pushed directly to `main` from either machine.
- No CI — validation is local (pre-commit). GitHub Action could be added later as belt-and-suspenders.
- No publish step beyond `git push origin main`. Claude Code's marketplace install pulls directly from the git remote.
