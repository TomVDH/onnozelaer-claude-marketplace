# Obsidian Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Create the `obsidian-bridge` standalone plugin that owns canonical Obsidian-vault layout, schema, type-shaped project templates, `/vault-bridge` command, `/dream` two-pass cleanup, CLI-first transport, and light remember integration — extracted from cabinet-of-imd but fully functional without it.

**Architecture:** Plugin with commands/, skills/, hooks/, references/, examples/ directories. Two commands (`/vault-bridge`, `/dream`), two skill files backing them, three hooks (SessionStart mandatory, SessionEnd opt-in, UserPromptSubmit conditional), four reference docs, and 13 vault templates. Vault primitives abstract CLI vs filesystem transport. Breadcrumb file (`.obsidian-bridge`) links working directories to vault projects.

**Tech Stack:** Claude Code plugin system (markdown commands/skills, JSON hooks, bash scripts). Obsidian CLI 1.12+ (primary transport). Bash/zsh shell scripts for hooks. YAML frontmatter. Wikilinks.

**Spec:** `docs/superpowers/2026-04-30-obsidian-bridge.design.md` — all section references (§N) point there.

---

## File Structure

### New files (obsidian-bridge plugin)

```
obsidian-bridge/
├── .claude-plugin/
│   └── plugin.json                          # Plugin manifest
├── README.md                                # Plugin overview for marketplace
├── CHANGELOG.md                             # Release log
├── LICENSE                                  # MIT
├── commands/
│   ├── vault-bridge.md                      # /vault-bridge command wrapper
│   └── dream.md                             # /dream command wrapper
├── skills/
│   ├── vault-bridge/
│   │   └── SKILL.md                         # Full vault-bridge skill (~600 lines)
│   └── dream/
│       └── SKILL.md                         # /dream Pass 1 + Pass 2 (~350 lines)
├── hooks/
│   ├── hooks.json                           # Hook configuration
│   └── scripts/
│       ├── session-start-vault.sh           # SessionStart: vault discovery + context injection
│       └── session-end-handoff.sh           # SessionEnd: remember handoff nudge (opt-in)
├── references/
│   ├── vault-standards.md                   # Canonical frontmatter schemas, naming, tags
│   ├── vault-integration.md                 # vault.* primitives, CLI/filesystem ops
│   ├── obsidian-setup.md                    # Obsidian plugin recommendations
│   └── remember-integration.md              # remember ↔ vault handoff protocol
└── examples/
    └── vault-templates/
        ├── brief-coding.md                  # type-shaped brief: coding projects
        ├── brief-knowledge.md               # type-shaped brief: knowledge projects
        ├── brief-plugin.md                  # type-shaped brief: plugin projects
        ├── brief-tinkerage.md               # type-shaped brief: tinkerage projects
        ├── decision.md                      # Decision record template
        ├── session.md                       # Session summary template
        ├── note.md                          # General note template
        ├── source.md                        # Source reference template (knowledge type)
        ├── doc.md                           # Root-of-project singleton doc template
        ├── handoff.md                       # Handoff from remember plugin template
        ├── home.md                          # Home.md vault root template
        ├── projects-index.md                # projects/_index.md template
        └── collection-index.md              # Generic collection _index.md template
```

### Modified files (cabinet-of-imd + marketplace)

```
.claude-plugin/marketplace.json              # Add obsidian-bridge entry
cabinet-of-imd/.claude-plugin/plugin.json    # Bump to 2.3.0 + stale note
cabinet-of-imd/README.md                     # Add extraction banner
cabinet-of-imd/CHANGELOG.md                  # Add v2.3.0 entry
cabinet-of-imd/commands/cabinet.md           # Update step 1.5 vault check
cabinet-of-imd/hooks/scripts/boot-flair.sh   # Read .obsidian-bridge breadcrumb
cabinet-of-imd/references/vault-integration.md  # Add stale banner
cabinet-of-imd/references/vault-standards.md    # Add stale banner
cabinet-of-imd/references/obsidian-setup.md     # Add stale banner
```

### Deleted files (cabinet-of-imd)

```
cabinet-of-imd/skills/vault-bridge/SKILL.md  # Moved to obsidian-bridge
cabinet-of-imd/commands/dream.md             # Moved to obsidian-bridge
```

---

### Task 1: Plugin scaffold — directories and manifests

**Files:**
- Create: `obsidian-bridge/.claude-plugin/plugin.json`
- Modify: `.claude-plugin/marketplace.json`

- [ ] **Step 1: Create the full directory tree**

```bash
cd onnozelaer-claude-plugins
mkdir -p obsidian-bridge/.claude-plugin
mkdir -p obsidian-bridge/commands
mkdir -p obsidian-bridge/skills/vault-bridge
mkdir -p obsidian-bridge/skills/dream
mkdir -p obsidian-bridge/hooks/scripts
mkdir -p obsidian-bridge/references
mkdir -p obsidian-bridge/examples/vault-templates
```

- [ ] **Step 2: Verify directory structure**

```bash
find obsidian-bridge -type d | sort
```

Expected output:
```
obsidian-bridge
obsidian-bridge/.claude-plugin
obsidian-bridge/commands
obsidian-bridge/examples
obsidian-bridge/examples/vault-templates
obsidian-bridge/hooks
obsidian-bridge/hooks/scripts
obsidian-bridge/references
obsidian-bridge/skills
obsidian-bridge/skills/dream
obsidian-bridge/skills/vault-bridge
```

- [ ] **Step 3: Write plugin.json**

Write to `obsidian-bridge/.claude-plugin/plugin.json`:

```json
{
  "name": "obsidian-bridge",
  "version": "0.1.0",
  "description": "Canonical Obsidian-vault layout, schema, primitives, and cleanup workflow for Claude Code. Standalone and cabinet-aware.",
  "author": { "name": "Onnozelaer" },
  "homepage": "https://github.com/TomVDH/onnozelaer-claude-marketplace/tree/main/obsidian-bridge",
  "repository": "https://github.com/TomVDH/onnozelaer-claude-marketplace",
  "license": "MIT",
  "keywords": ["obsidian", "vault", "knowledge-management", "markdown", "frontmatter", "wikilinks"]
}
```

- [ ] **Step 4: Update marketplace.json**

Add the obsidian-bridge entry to the `plugins` array in `.claude-plugin/marketplace.json`:

```json
{
  "name": "obsidian-bridge",
  "version": "0.1.0",
  "source": "./obsidian-bridge",
  "description": "Standalone Obsidian-vault primitive layer: canonical schema, type-shaped project layouts, /vault-bridge command, /dream cleanup, CLI-first writes with filesystem fallback. Pairs cleanly with the cabinet-of-imd plugin but functions on its own."
}
```

- [ ] **Step 5: Verify JSON validity**

```bash
python3 -m json.tool obsidian-bridge/.claude-plugin/plugin.json > /dev/null && echo "plugin.json OK"
python3 -m json.tool .claude-plugin/marketplace.json > /dev/null && echo "marketplace.json OK"
```

Expected: both print OK.

- [ ] **Step 6: Commit**

```bash
git add obsidian-bridge/.claude-plugin/plugin.json .claude-plugin/marketplace.json
git commit -m "feat(obsidian-bridge): scaffold plugin directories and manifests"
```

---

### Task 2: README, CHANGELOG, LICENSE

**Files:**
- Create: `obsidian-bridge/README.md`
- Create: `obsidian-bridge/CHANGELOG.md`
- Create: `obsidian-bridge/LICENSE`

- [ ] **Step 1: Write README.md**

Write to `obsidian-bridge/README.md`:

```markdown
# Obsidian Bridge

Canonical Obsidian-vault layout, schema, primitives, and cleanup workflow for Claude Code.

Standalone plugin — works without any other plugins. Pairs cleanly with `cabinet-of-imd` when both are installed.

## What it does

- **Type-shaped projects** — `coding`, `knowledge`, `plugin`, `tinkerage` — each with appropriate brief blocks and subfolder defaults.
- **Vault primitives** — CLI-first Obsidian operations with filesystem fallback. Read, write, search, move, rename — abstracted behind `vault.*` calls.
- **SessionStart hook** — discovers vault, injects context, steers toward vault connection when not linked.
- **`/vault-bridge`** — create, connect, scaffold, sync, archive, reindex, housekeeping, iterations, migration.
- **`/dream`** — two-pass cleanup. Pass 1: structural sanitation (auto-fixable). Pass 2: content analysis (report-only).
- **Remember integration** — mirror `.remember/remember.md` to vault as `_handoff.md`.

## Commands

| Command | Description |
|---|---|
| `/vault-bridge` | Vault operations — create, connect, scaffold, sync, status, housekeeping, migrate |
| `/dream` | Two-pass vault analysis — structural fixes + content review |

## Install

Add to your Claude Code plugins or install from the Onnozelaer marketplace.

## Vault schema version

This plugin uses vault schema **v3**. Projects created with cabinet-of-imd v2 vaults can be migrated via `/vault-bridge migrate`.

## License

MIT
```

- [ ] **Step 2: Write CHANGELOG.md**

Write to `obsidian-bridge/CHANGELOG.md`:

```markdown
# Changelog

## 0.1.0 — 2026-04-30

Initial release. Extracted from `cabinet-of-imd` v2.2.0.

- Plugin scaffold with commands, skills, hooks, references, templates.
- Vault schema v3: type-shaped projects (`coding`, `knowledge`, `plugin`, `tinkerage`).
- `/vault-bridge` command: create, connect, link, create-project, add-collection, sync, status, archive, unarchive, reindex, housekeeping, migrate, set-type, templates, iterations, handoff.
- `/dream` command: Pass 1 (structural sanitation) + Pass 2 (content analysis).
- SessionStart hook with vault discovery and context injection.
- SessionEnd hook with optional remember handoff nudge.
- 13 vault templates.
- v2 → v3 migration command.
- Remember plugin integration (handoff sync).
```

- [ ] **Step 3: Write LICENSE**

Write to `obsidian-bridge/LICENSE`:

```
MIT License

Copyright (c) 2026 Onnozelaer

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

- [ ] **Step 4: Commit**

```bash
git add obsidian-bridge/README.md obsidian-bridge/CHANGELOG.md obsidian-bridge/LICENSE
git commit -m "docs(obsidian-bridge): add README, CHANGELOG, LICENSE"
```

---

### Task 3: Brief templates (4 files)

**Files:**
- Create: `obsidian-bridge/examples/vault-templates/brief-coding.md`
- Create: `obsidian-bridge/examples/vault-templates/brief-knowledge.md`
- Create: `obsidian-bridge/examples/vault-templates/brief-plugin.md`
- Create: `obsidian-bridge/examples/vault-templates/brief-tinkerage.md`

- [ ] **Step 1: Write brief-coding.md**

Write to `obsidian-bridge/examples/vault-templates/brief-coding.md`:

```markdown
---
type: project
project_type: coding
slug:
aliases:
  -                        # set to project slug — enables [[slug]] wikilink resolution
status: active
created:
updated:
tags:
  - ob/project
  - type/coding
repo:                      # optional — git remote URL or local path
stack: []                  # optional — e.g. [Next.js, Tailwind, Node, Postgres]
---

# {Project Name}

## INTRO

## TECHNICAL STACK

## CONSTRAINTS

## WORK NOTES

## MILESTONES

## USER DECISIONS
```

- [ ] **Step 2: Write brief-knowledge.md**

Write to `obsidian-bridge/examples/vault-templates/brief-knowledge.md`:

```markdown
---
type: project
project_type: knowledge
slug:
aliases:
  -                        # set to project slug
status: active
created:
updated:
tags:
  - ob/project
  - type/knowledge
---

# {Project Name}

## INTRO

## SOURCES

## OPEN QUESTIONS

## WORK NOTES

## USER DECISIONS
```

- [ ] **Step 3: Write brief-plugin.md**

Write to `obsidian-bridge/examples/vault-templates/brief-plugin.md`:

```markdown
---
type: project
project_type: plugin
slug:
aliases:
  -                        # set to project slug
status: active
created:
updated:
tags:
  - ob/project
  - type/plugin
repo:                      # optional — git remote URL or local path
stack: []                  # optional — e.g. [TypeScript, Node]
marketplace:               # optional — marketplace name (e.g. onnozelaer)
---

# {Project Name}

## INTRO

## TECHNICAL STACK

## CONSTRAINTS

## WORK NOTES

## MILESTONES

## USER DECISIONS

## RELEASE NOTES
```

- [ ] **Step 4: Write brief-tinkerage.md**

Write to `obsidian-bridge/examples/vault-templates/brief-tinkerage.md`:

```markdown
---
type: project
project_type: tinkerage
slug:
aliases:
  -                        # set to project slug
status: active
created:
updated:
tags:
  - ob/project
  - type/tinkerage
---

# {Project Name}

## INTRO

## WORK NOTES
```

- [ ] **Step 5: Verify all four templates have correct frontmatter**

```bash
for f in obsidian-bridge/examples/vault-templates/brief-*.md; do
  echo "=== $(basename $f) ==="
  head -5 "$f"
  echo
done
```

Expected: each shows `---`, `type: project`, and the correct `project_type` value.

- [ ] **Step 6: Commit**

```bash
git add obsidian-bridge/examples/vault-templates/brief-*.md
git commit -m "feat(obsidian-bridge): add type-shaped brief templates"
```

---

### Task 4: Content-type templates (6 files)

**Files:**
- Create: `obsidian-bridge/examples/vault-templates/decision.md`
- Create: `obsidian-bridge/examples/vault-templates/session.md`
- Create: `obsidian-bridge/examples/vault-templates/note.md`
- Create: `obsidian-bridge/examples/vault-templates/source.md`
- Create: `obsidian-bridge/examples/vault-templates/doc.md`
- Create: `obsidian-bridge/examples/vault-templates/handoff.md`

- [ ] **Step 1: Write decision.md**

Write to `obsidian-bridge/examples/vault-templates/decision.md`:

```markdown
---
type: decision
project: "[[projects/{slug}/brief|{slug}]]"
status: active
date:
tags:
  - ob/decision
---

## Decision

## Context

## Consequence

---
*Recorded at session.*
```

- [ ] **Step 2: Write session.md**

Write to `obsidian-bridge/examples/vault-templates/session.md`:

```markdown
---
type: session
project: "[[projects/{slug}/brief|{slug}]]"
date:
specialists: []
tags:
  - ob/session
---

## Summary

## Decisions Made

## Open Items
```

- [ ] **Step 3: Write note.md**

Write to `obsidian-bridge/examples/vault-templates/note.md`:

```markdown
---
type: note
project: "[[projects/{slug}/brief|{slug}]]"
created:
updated:
tags:
  - ob/note
---

# {Title}
```

- [ ] **Step 4: Write source.md**

Write to `obsidian-bridge/examples/vault-templates/source.md`:

```markdown
---
type: source
project: "[[projects/{slug}/brief|{slug}]]"
title:
author:
url:
medium:                    # book | paper | article | course | talk | other
year:
tags:
  - ob/source
---

# {Title}

## Key Points

## Notes

## Relevance
```

- [ ] **Step 5: Write doc.md**

Write to `obsidian-bridge/examples/vault-templates/doc.md`:

```markdown
---
type: doc
project: "[[projects/{slug}/brief|{slug}]]"
title:
updated:
tags:
  - ob/doc
---

# {Title}
```

- [ ] **Step 6: Write handoff.md**

Write to `obsidian-bridge/examples/vault-templates/handoff.md`:

```markdown
---
type: handoff
project: "[[projects/{slug}/brief|{slug}]]"
updated:
source: remember
tags:
  - ob/handoff
---

# Handoff — {project}

*Mirrored from `.remember/remember.md` on {date}.*

---
```

- [ ] **Step 7: Verify all six templates**

```bash
for f in decision session note source doc handoff; do
  echo "=== $f ==="
  grep "^type:" "obsidian-bridge/examples/vault-templates/$f.md"
done
```

Expected: each shows the correct `type:` value.

- [ ] **Step 8: Commit**

```bash
git add obsidian-bridge/examples/vault-templates/{decision,session,note,source,doc,handoff}.md
git commit -m "feat(obsidian-bridge): add content-type templates"
```

---

### Task 5: Structural templates (3 files)

**Files:**
- Create: `obsidian-bridge/examples/vault-templates/home.md`
- Create: `obsidian-bridge/examples/vault-templates/projects-index.md`
- Create: `obsidian-bridge/examples/vault-templates/collection-index.md`

- [ ] **Step 1: Write home.md**

Write to `obsidian-bridge/examples/vault-templates/home.md`:

```markdown
---
type: vault-home
updated:
---

# Vault

Persistent knowledge base. Project briefs, decisions, session history — all interlinked and queryable.

## Active Projects

*No projects yet. Run `/vault-bridge create-project <slug> <type>` to scaffold your first project.*

## Recent Decisions

*Decisions will appear here as projects progress.*

## Recent Sessions

*Session summaries will be logged here at wrap-up.*

## Archived Projects

*No archived projects.*

## Quick Links

- [[projects/_index|All Projects]]
```

- [ ] **Step 2: Write projects-index.md**

Write to `obsidian-bridge/examples/vault-templates/projects-index.md`:

```markdown
---
type: index
tags:
  - ob/index
---

# All Projects

| Project | Type | Status | Decisions | Sessions | Last Session |
|---|---|---|---|---|---|

*Run `/vault-bridge create-project <slug> <type>` to add a project.*
```

- [ ] **Step 3: Write collection-index.md**

Write to `obsidian-bridge/examples/vault-templates/collection-index.md`:

```markdown
---
type: index
project: "[[projects/{slug}/brief|{slug}]]"
tags:
  - ob/index
---

# {Collection Name}

{One-line description of what this collection holds.}

## Entries
```

- [ ] **Step 4: Verify all three templates**

```bash
ls -la obsidian-bridge/examples/vault-templates/
wc -l obsidian-bridge/examples/vault-templates/*.md | tail -1
```

Expected: 13 total template files, combined line count ~200.

- [ ] **Step 5: Commit**

```bash
git add obsidian-bridge/examples/vault-templates/{home,projects-index,collection-index}.md
git commit -m "feat(obsidian-bridge): add structural templates (home, indices)"
```

---

### Task 6: Reference — vault-standards.md

**Files:**
- Create: `obsidian-bridge/references/vault-standards.md`

This is the canonical schema reference, derived from spec §4, §5, §6, §7. The model reads this on-demand when writing to the vault.

- [ ] **Step 1: Write vault-standards.md**

Write to `obsidian-bridge/references/vault-standards.md`:

```markdown
# Vault Standards

Canonical frontmatter schemas, naming conventions, tag taxonomy, wikilink forms, and structural rules for the Obsidian vault. Single source of truth — all vault writes must conform. Templates in `examples/vault-templates/` mirror these definitions.

## General Rules

### Frontmatter

Every vault file has YAML frontmatter. No exceptions.

- Use standard YAML — no Obsidian-specific syntax inside frontmatter values except `project` fields (piped wikilinks).
- Dates: ISO format `YYYY-MM-DD` for date-only, full ISO 8601 for timestamps.
- Strings with special characters (colons, brackets) must be quoted.
- Empty optional fields: **omit the key entirely** rather than `null` or empty string.
- Arrays use YAML list syntax, not inline `[]` (exception: empty arrays use `[]`).

### Project References

The `project` field in frontmatter uses a **piped wikilink to the brief**:

```yaml
project: "[[projects/hubspot-dev/brief|hubspot-dev]]"
```

Clickable in Obsidian, resolves to the brief, displays the slug as alias. Always this format — not bare slugs, not unpiped wikilinks.

### Specialist Names (cabinet integration)

When cabinet-of-imd is installed and populates the `specialist:` field, names are always **lowercase**: `bostrol`, `thieuke`, `sakke`, `jonasty`, `pitr`, `henske`, `kevijntje`, `poekie`. Bridge preserves these values but does not require the field.

---

## Tag Taxonomy

Two flat categories, deliberately lean. No deep nesting.

### Structural tags — `#ob/{filetype}`

One per file, always present:

`#ob/project`, `#ob/decision`, `#ob/session`, `#ob/note`, `#ob/source`, `#ob/doc`, `#ob/handoff`, `#ob/release`, `#ob/iteration`, `#ob/dream-report`, `#ob/index`

### Type tags — `#type/{project_type}`

Briefs only: `#type/coding`, `#type/knowledge`, `#type/plugin`, `#type/tinkerage`

### Topical tags

Bare, lowercase, hyphenated. Optional, sparingly. Must be **queryable** — the user would actually filter on them. Bridge does not auto-add topical tags. `/dream` flags:

- Single-use tags
- Near-duplicate tags (`#postgres` vs `#postgresql`)
- Vague tags (`#wip`, `#misc`, `#general`, `#thoughts`)
- Tags drifting out of `ob/` namespace conventions

### Cabinet coexistence

Cabinet's `#cabinet/*` tags are preserved alongside `#ob/*` equivalents during migration (multi-tag). Bridge does not strip them.

---

## Naming Rules

| Item | Pattern |
|---|---|
| Project slug | lowercase, hyphenated, no spaces, no dots (`dff2026-web`) |
| Brief | always `brief.md` |
| Decision | `YYYY-MM-DD-{kebab-title}.md` |
| Session | `YYYY-MM-DD.md` (one per project per day; same-day re-runs append) |
| Note | `{kebab-title}.md` (no date prefix unless time-relevant) |
| Source | `{kebab-title}.md` |
| Reference | `{kebab-title}.md` |
| Release (plugin) | `vX.Y.Z.md` |
| Iteration (file form) | `YYYY-MM-DD-iter-{id}-{kebab-slug}.md` |
| Iteration (folder form) | `YYYY-MM-DD-iter-{id}-{kebab-slug}/` containing `_iteration.md` |
| Dream report | `YYYY-MM-DD.md` |
| Doc (singleton) | `{NAME}.md` (often UPPERCASE: `MANIFESTO.md`, `STANDARDS.md`) |
| Handoff | `_handoff.md` (single file per project, overwriteable) |
| Index | `_index.md` |

---

## Wikilink Rules

All vault-internal links use `[[note-name]]` form. Markdown-style `[text](path)` is **forbidden** inside the vault — `/dream` flags violations.

| Context | Form |
|---|---|
| Frontmatter `project:` field | `"[[projects/{slug}/brief\|{slug}]]"` (piped, always) |
| Body → brief | `[[projects/{slug}/brief\|{display}]]` |
| Body → decision | `[[projects/{slug}/decisions/{file}\|{short title}]]` |
| Body → session | `[[projects/{slug}/sessions/{date}\|{date}]]` |
| Body → source | `[[projects/{slug}/sources/{file}\|{author, year}]]` |
| Image embed | `![[image.png]]` with caption line below |

Briefs always carry `aliases: [{slug}]` so bare `[[my-project]]` resolves cleanly.

---

## File Type Schemas

### Brief — `projects/{slug}/brief.md`

```yaml
---
type: project                          # required
project_type: coding                   # required — coding | knowledge | plugin | tinkerage
slug: my-project                       # required — kebab-case
aliases:                               # required — at minimum contains the slug
  - my-project
status: active                         # required — active | paused | archived | complete
created: 2026-04-30                    # required
updated: 2026-04-30                    # required — date of last substantive update
tags:                                  # required
  - ob/project
  - type/coding                        # matches project_type
repo: git@github.com:owner/repo.git   # optional (coding/plugin only)
stack: [Next.js, Tailwind]             # optional (coding/plugin only)
marketplace: onnozelaer                # optional (plugin only)
---
```

Body: type-shaped block set (see §5 in spec). Block headers are UPPERCASE.

### Decision — `projects/{slug}/decisions/YYYY-MM-DD-{title}.md`

```yaml
---
type: decision                                              # required
project: "[[projects/{slug}/brief|{slug}]]"                 # required
status: active                                              # required — active | superseded | reversed | implemented
date: 2026-04-30                                            # required
tags:                                                       # required
  - ob/decision
specialist: bostrol                                         # optional (cabinet)
supersedes: "[[projects/{slug}/decisions/{prev}]]"          # optional
---
```

Body: `## Decision`, `## Context`, `## Consequence`. Ends with backlink to brief.

### Session — `projects/{slug}/sessions/YYYY-MM-DD.md`

```yaml
---
type: session                                               # required
project: "[[projects/{slug}/brief|{slug}]]"                 # required
date: 2026-04-30                                            # required
tags:                                                       # required
  - ob/session
specialists: [bostrol]                                      # optional (cabinet)
branch: main                                                # optional
commits: [abc1234]                                          # optional
gates_completed: 0                                          # optional (cabinet)
---
```

### Note — `projects/{slug}/notes/{title}.md`

```yaml
---
type: note
project: "[[projects/{slug}/brief|{slug}]]"
created: 2026-04-30
updated: 2026-04-30
tags:
  - ob/note
---
```

### Source — `projects/{slug}/sources/{title}.md`

```yaml
---
type: source
project: "[[projects/{slug}/brief|{slug}]]"
title: "Title of source"
author: "Author name"
url: https://example.com
medium: article                        # book | paper | article | course | talk | other
year: 2026
tags:
  - ob/source
---
```

### Doc — `projects/{slug}/{NAME}.md`

```yaml
---
type: doc
project: "[[projects/{slug}/brief|{slug}]]"
title: "Document title"
updated: 2026-04-30
tags:
  - ob/doc
---
```

### Handoff — `projects/{slug}/_handoff.md`

```yaml
---
type: handoff
project: "[[projects/{slug}/brief|{slug}]]"
updated: 2026-04-30
source: remember                       # remember | manual
tags:
  - ob/handoff
---
```

### Iteration — `projects/{slug}/iterations/YYYY-MM-DD-iter-{id}-{slug}.md`

```yaml
---
type: iteration
project: "[[projects/{slug}/brief|{slug}]]"
identifier: D                          # letter, number, or short word
status: drafting                       # drafting | on-shelf | picked | parked | rejected | superseded
date: 2026-04-30
tags:
  - ob/iteration
track: navy-dominant                   # optional — grouping/direction
register: "Navy-dominant · modern B2B SaaS"  # optional — short tagline
supersedes: "[[...]]"                  # optional
builds_on: "[[...]]"                   # optional
artefacts: [shelf.html, concept.png]   # optional (folder form only)
---
```

### Release — `projects/{slug}/releases/vX.Y.Z.md`

```yaml
---
type: release
project: "[[projects/{slug}/brief|{slug}]]"
version: X.Y.Z
date: 2026-04-30
tags:
  - ob/release
---
```

### Dream Report — `projects/{slug}/dreams/YYYY-MM-DD.md`

```yaml
---
type: dream-report
project: "[[projects/{slug}/brief|{slug}]]"
date: 2026-04-30
tags:
  - ob/dream-report
---
```

### Index — `_index.md` (project-scoped or vault-root)

```yaml
---
type: index
project: "[[projects/{slug}/brief|{slug}]]"    # only for project-scoped
tags:
  - ob/index
---
```

### Home — `Home.md`

```yaml
---
type: vault-home
updated: 2026-04-30
---
```

Multi-plugin vault (cabinet installed):

```yaml
type:
  - vault-home
  - cabinet-home
```

---

## The `_index.md` Rule

Every folder under a project (or at vault root) that holds ≥2 sibling `.md` files of the same conceptual type gets an `_index.md`.

**Exceptions:** `sessions/` (chronological ordering is the index), `images/`, `assets/`, `previews/` (non-text or build artefacts).

**Auto-creation triggers:**
- `/vault-bridge create-project` scaffolds defaults per type.
- `/vault-bridge add-collection <name>` scaffolds arbitrary collection.
- `/vault-bridge reindex` rebuilds all.
- `/dream` flags missing `_index.md` and offers to create.
- Migration auto-creates missing ones.

**Index content shape:** `# {Collection Name}`, one-line description, `## Entries` with wikilinks. Chronological sort where dates are in filenames; alphabetical otherwise.

---

## Per-Type Project Subfolder Defaults

| Type | Subfolders with `_index.md` | Subfolders without `_index.md` |
|---|---|---|
| **coding** | `decisions/`, `notes/`, `tasks/`, `references/` | `sessions/`, `images/` |
| **plugin** | coding + `releases/` | `sessions/`, `images/` |
| **knowledge** | `notes/`, `sources/`, `references/` | `sessions/` |
| **tinkerage** | (none by default) | `sessions/` (optional) |
```

- [ ] **Step 2: Verify the file is well-formed**

```bash
head -3 obsidian-bridge/references/vault-standards.md
wc -l obsidian-bridge/references/vault-standards.md
```

Expected: starts with `# Vault Standards`, ~250+ lines.

- [ ] **Step 3: Commit**

```bash
git add obsidian-bridge/references/vault-standards.md
git commit -m "feat(obsidian-bridge): add vault-standards reference"
```

---

### Task 7: Reference — vault-integration.md

**Files:**
- Create: `obsidian-bridge/references/vault-integration.md`

Defines the `vault.*` abstraction layer, CLI detection, operations, and graceful degradation. Derived from spec §10 + §11.

- [ ] **Step 1: Write vault-integration.md**

Write to `obsidian-bridge/references/vault-integration.md`:

```markdown
# Vault Integration

The `vault.*` abstraction layer for Obsidian vault operations. Single interface that resolves CLI vs filesystem at call time. This is the implementation reference — read on-demand when performing vault operations.

## Transport Modes

### CLI mode (preferred)

Uses Obsidian CLI 1.12+. Advantages:

- Wikilinks in frontmatter recognised natively by Obsidian's parser.
- `property:set` writes frontmatter without re-parsing the file.
- `move` and `rename` trigger Obsidian's automatic internal-link updater.
- `search` uses Obsidian's index — vault-aware, faster.
- `backlinks` and `tags` return live graph data.
- No manual YAML parsing, no fragile regex.

### Filesystem mode (fallback)

Direct file access via Read/Write/Glob/Grep tools. Used when CLI is unavailable (Cowork, Obsidian not installed, CLI broken).

### Detection

```bash
command -v obsidian >/dev/null 2>&1 && obsidian version 2>/dev/null
```

Result stored in breadcrumb file as `mode=cli` or `mode=filesystem`. Re-detection on next SessionStart only.

### Graceful degradation

If CLI was selected but a CLI op fails mid-session (e.g., Obsidian closed), attempt filesystem fallback transparently for that op, log once, continue.

---

## Vault Discovery

Run by SessionStart hook. Order:

1. Read breadcrumb `$CLAUDE_PROJECT_DIR/.obsidian-bridge` if it exists.
2. Fall back to `$CLAUDE_PROJECT_DIR/.cabinet-anchor-hint` (backward-compatible).
3. Try `$OB_DEFAULT_VAULT` env var.
4. Try CLI: `obsidian vault="<known name>" files total` for known vault names.
5. Walk parent dirs of `$CLAUDE_PROJECT_DIR` for `Home.md` with `type: vault-home` or `type: cabinet-home`.
6. None found → emit "not linked" context.

---

## Breadcrumb File — `.obsidian-bridge`

Plain `KEY=VALUE` text file in the working directory. Written by `/vault-bridge connect` or `/vault-bridge link`. Add to `.gitignore`.

```
vault_path=/Users/tom/Library/Mobile Documents/iCloud~md~obsidian/Documents/Claude Cabinet
vault_name=Claude Cabinet
project_slug=oz-floer
linked_at=2026-04-30
mode=cli
```

Optional field for iteration-shelf coordination:

```
iterations_path=projects/oz-floer/iterations
```

---

## Vault Primitives — `vault.*` Operations

### Resolution

```pseudocode
FUNCTION vault.<op>(args):
    IF cli_available() AND op is supported by CLI:
        RUN obsidian CLI command
    ELSE:
        RUN filesystem equivalent
```

### CLI + filesystem (both supported)

| Operation | CLI command | Filesystem equivalent |
|---|---|---|
| `vault.read(path)` | `obsidian vault="V" read "path"` | Read tool on `{vault_path}/{path}` |
| `vault.write(path, content)` | `obsidian vault="V" write "path" --content "..."` | Write tool to `{vault_path}/{path}` (mkdir -p parent) |
| `vault.append(path, content)` | `obsidian vault="V" append "path" --content "..."` | Read + append + Write |
| `vault.search(query, folder?)` | `obsidian vault="V" search "query" --folder "f"` | Grep tool in `{vault_path}/{folder}` |
| `vault.search_context(query, folder?)` | `obsidian vault="V" search "query" --context --folder "f"` | Grep with context lines |
| `vault.exists(path)` | `obsidian vault="V" read "path" --dry-run` | Check file exists via Read |
| `vault.list(dir)` | `obsidian vault="V" list "dir"` | Glob `{vault_path}/{dir}/*.md` |

### CLI-exclusive (filesystem degrades to best-effort)

| Operation | CLI command | Filesystem fallback |
|---|---|---|
| `vault.property_read(path, name)` | `obsidian vault="V" property:read "path" "name"` | Parse YAML frontmatter from file |
| `vault.property_set(path, name, value)` | `obsidian vault="V" property:set "path" "name" "value"` | Rewrite YAML frontmatter in file |
| `vault.backlinks(path)` | `obsidian vault="V" backlinks "path"` | Grep for `[[{filename}]]` across vault |
| `vault.tags(path?)` | `obsidian vault="V" tags "path"` | Parse frontmatter tags + grep body |
| `vault.move(from, to)` | `obsidian vault="V" move "from" "to"` | Filesystem move + manual link rewrite (lossy) |
| `vault.rename(from, new_name)` | `obsidian vault="V" rename "from" "new_name"` | Filesystem rename + manual link rewrite (lossy) |

Note: CLI `move` and `rename` automatically update all internal links pointing to the moved/renamed file. Filesystem fallback cannot do this reliably — it's marked "lossy" and `/dream` should be run afterward to detect broken links.

---

## `update_home()` Procedure

Rebuilds `Home.md` from disk state. Never appends — always rewrites dynamic sections.

```pseudocode
Scan projects/ for active projects (slug, status, project_type, latest session from brief.md + sessions/)
Scan all projects/*/decisions/ for recent decisions (last 5 across vault)
Scan all projects/*/sessions/ for recent sessions (last 5 across vault)
Scan archive/ for archived project names

WRITE Home.md:
  Active Projects (per project: link, type, status, last session date)
  Recent Decisions (last 5: link, project, date)
  Recent Sessions (last 5: link, project, date)
  Archived Projects (if any)
  Quick Links (all projects index, crew/ if it exists)
```

When `crew/` exists (cabinet installed), Quick Links includes pointers to crew files. Bridge does not rewrite the crew section — just links to it.
```

- [ ] **Step 2: Verify**

```bash
grep -c "^##" obsidian-bridge/references/vault-integration.md
```

Expected: 8+ second-level headings.

- [ ] **Step 3: Commit**

```bash
git add obsidian-bridge/references/vault-integration.md
git commit -m "feat(obsidian-bridge): add vault-integration reference (primitives layer)"
```

---

### Task 8: References — obsidian-setup.md + remember-integration.md

**Files:**
- Create: `obsidian-bridge/references/obsidian-setup.md`
- Create: `obsidian-bridge/references/remember-integration.md`

- [ ] **Step 1: Write obsidian-setup.md**

Write to `obsidian-bridge/references/obsidian-setup.md`:

```markdown
# Obsidian Setup

Recommended Obsidian configuration for optimal vault experience with obsidian-bridge.

## Required

### Obsidian CLI

Install the Obsidian CLI (v1.12+) for full vault primitive support.

```bash
# Verify installation
obsidian version
```

If CLI is unavailable, bridge falls back to filesystem mode. All core operations work, but `move`/`rename` lose automatic link rewriting, and `backlinks`/`tags` degrade to grep-based approximations.

## Recommended Plugins

### Dataview

Enables dynamic queries across vault frontmatter. Useful for:
- Listing all decisions by status
- Filtering projects by type
- Iteration tracking dashboards

### Templater

For manual vault work outside of Claude sessions. Bridge's templates in `examples/vault-templates/` can be copied to the vault's `templates/` folder for use with Templater.

### Tag Wrangler

Helps manage the `#ob/*` structural tags and topical tags. Useful for renaming or merging tags across the vault.

## Vault Settings

### Files & Links

- **Default location for new notes:** `In the folder specified below` → root
- **New link format:** `Shortest path when possible`
- **Use [[Wikilinks]]:** ON (mandatory — bridge uses wikilinks exclusively)

### Appearance

No requirements. Bridge's frontmatter and content render correctly with any theme.

## Folder Structure

Bridge manages:
- `projects/` — active project folders
- `archive/` — archived projects
- `templates/` — vault templates (optional, for Templater)
- `Home.md` — auto-rebuilt vault home

Bridge leaves alone:
- `.obsidian/` — Obsidian's internal config
- `crew/` — cabinet-of-imd owned (if installed)
- Any root-level files not matching known types
```

- [ ] **Step 2: Write remember-integration.md**

Write to `obsidian-bridge/references/remember-integration.md`:

```markdown
# Remember Plugin Integration

Light, opt-in integration between obsidian-bridge and the `remember` Claude Code plugin. Bridge does not absorb remember's compression pipeline — it only mirrors the output.

## Direction

| Direction | Mechanism | Behavior |
|---|---|---|
| remember → vault | `/vault-bridge handoff sync` | Read `$CLAUDE_PROJECT_DIR/.remember/remember.md`, mirror to `{vault}/projects/{slug}/_handoff.md` with `type: handoff` frontmatter. Single file per project, overwritten each sync. |
| remember → vault (auto) | SessionEnd hook (opt-in) | If `remember.md` mtime > `_handoff.md` mtime + active project breadcrumb, emit one-line nudge. |
| vault → remember | n/a | Bridge never writes to `.remember/`. |

## Handoff File

Lives at `projects/{slug}/_handoff.md`. Underscore prefix pins it at top of folder listing.

```yaml
---
type: handoff
project: "[[projects/{slug}/brief|{slug}]]"
updated: 2026-04-30
source: remember
tags:
  - ob/handoff
---
```

Body: verbatim copy of `remember.md` content, preceded by a header noting source and timestamp.

## Status Surface

`/vault-bridge status` shows: `Remember plugin: detected — last handoff sync: 2026-04-29` when `.remember/` exists in the working directory.

## Enabling Auto-Nudge

Set env var `OB_SESSION_END_NUDGE=1` or configure in Claude Code settings. The SessionEnd hook checks remember.md mtime vs _handoff.md mtime and emits a one-line reminder if the handoff is stale.
```

- [ ] **Step 3: Verify both files**

```bash
head -1 obsidian-bridge/references/obsidian-setup.md
head -1 obsidian-bridge/references/remember-integration.md
ls obsidian-bridge/references/
```

Expected: 4 files in references/ (vault-standards.md, vault-integration.md, obsidian-setup.md, remember-integration.md).

- [ ] **Step 4: Commit**

```bash
git add obsidian-bridge/references/obsidian-setup.md obsidian-bridge/references/remember-integration.md
git commit -m "feat(obsidian-bridge): add obsidian-setup and remember-integration references"
```

---

### Task 9: Hook — SessionStart script

**Files:**
- Create: `obsidian-bridge/hooks/scripts/session-start-vault.sh`

The most important hook. Discovers vault, detects CLI, reads brief frontmatter, emits context. Must never block the session. Spec §9.1.

- [ ] **Step 1: Write session-start-vault.sh**

Write to `obsidian-bridge/hooks/scripts/session-start-vault.sh`:

```bash
#!/usr/bin/env bash
# session-start-vault.sh — SessionStart hook for obsidian-bridge
# Discovers vault, detects CLI, injects context. Never blocks startup.
set -euo pipefail

main() {
  local project_dir="${CLAUDE_PROJECT_DIR:-}"
  [ -z "$project_dir" ] && return 0

  local vault_path="" vault_name="" project_slug="" mode="" linked_at=""

  # --- 1. Read breadcrumb (.obsidian-bridge) ---
  local breadcrumb="$project_dir/.obsidian-bridge"
  if [ -f "$breadcrumb" ]; then
    vault_path=$(grep -E '^vault_path=' "$breadcrumb" 2>/dev/null | head -n1 | cut -d= -f2- || true)
    vault_name=$(grep -E '^vault_name=' "$breadcrumb" 2>/dev/null | head -n1 | cut -d= -f2- || true)
    project_slug=$(grep -E '^project_slug=' "$breadcrumb" 2>/dev/null | head -n1 | cut -d= -f2- || true)
    mode=$(grep -E '^mode=' "$breadcrumb" 2>/dev/null | head -n1 | cut -d= -f2- || true)
  fi

  # --- 2. Fallback: cabinet anchor hint ---
  if [ -z "$vault_path" ]; then
    local hint_file="$project_dir/.cabinet-anchor-hint"
    if [ -f "$hint_file" ]; then
      vault_path=$(grep -E '^vault=' "$hint_file" 2>/dev/null | head -n1 | cut -d= -f2- || true)
      project_slug=$(grep -E '^slug=' "$hint_file" 2>/dev/null | head -n1 | cut -d= -f2- || true)
    fi
  fi

  # --- 3. Fallback: OB_DEFAULT_VAULT env var ---
  if [ -z "$vault_path" ] && [ -n "${OB_DEFAULT_VAULT:-}" ]; then
    vault_path="$OB_DEFAULT_VAULT"
    vault_name=$(basename "$vault_path")
  fi

  # --- 4. Fallback: walk parent dirs for Home.md ---
  if [ -z "$vault_path" ]; then
    local check_dir="$project_dir"
    local depth=0
    while [ "$depth" -lt 5 ] && [ "$check_dir" != "/" ]; do
      if [ -f "$check_dir/Home.md" ]; then
        if grep -qE '^type:\s*(vault-home|cabinet-home)' "$check_dir/Home.md" 2>/dev/null; then
          vault_path="$check_dir"
          vault_name=$(basename "$check_dir")
          break
        fi
      fi
      check_dir=$(dirname "$check_dir")
      depth=$((depth + 1))
    done
  fi

  # --- 5. Detect CLI ---
  local cli_available="no"
  local cli_version=""
  if command -v obsidian >/dev/null 2>&1; then
    cli_version=$(obsidian version 2>/dev/null || true)
    if [ -n "$cli_version" ]; then
      cli_available="yes"
      mode="${mode:-cli}"
    fi
  fi
  mode="${mode:-filesystem}"

  # --- 6. Read project type from brief if slug is known ---
  local project_type="" project_status=""
  if [ -n "$vault_path" ] && [ -n "$project_slug" ]; then
    local brief="$vault_path/projects/$project_slug/brief.md"
    if [ -f "$brief" ]; then
      project_type=$(grep -E '^project_type:\s*' "$brief" 2>/dev/null | head -n1 | sed 's/^project_type:\s*//' || true)
      project_status=$(grep -E '^status:\s*' "$brief" 2>/dev/null | head -n1 | sed 's/^status:\s*//' || true)
    fi
  fi

  # --- 7. Emit context ---
  if [ -n "$vault_path" ] && [ -d "$vault_path" ]; then
    # Vault linked — emit rich context
    local ctx="## Obsidian Bridge\n\n"
    ctx+="- Vault: \`${vault_name:-$(basename "$vault_path")}\` at \`$vault_path\` (CLI: $cli_available)\n"

    if [ -n "$project_slug" ]; then
      local type_info=""
      [ -n "$project_type" ] && type_info=" (type: $project_type)"
      local status_info=""
      [ -n "$project_status" ] && status_info=" — status: $project_status"
      ctx+="- Project: \`$project_slug\`$type_info$status_info\n"
      ctx+="\nDecisions: \`projects/$project_slug/decisions/YYYY-MM-DD-{slug}.md\`\n"
      ctx+="Sessions: \`projects/$project_slug/sessions/YYYY-MM-DD.md\`\n"
    else
      ctx+="- Project: not linked (run \`/vault-bridge link <slug>\` to set)\n"
    fi

    ctx+="Root docs require \`type: doc\` frontmatter.\n"
    ctx+="Standards: \`obsidian-bridge/references/vault-standards.md\` (read on demand)."

    printf '%b' "$ctx"
  else
    # Vault not linked — emit steering context
    printf '## Obsidian Bridge — Not Linked\n\n'
    printf 'No vault linked to this session. Before vault-dependent work, ask the user\n'
    printf 'to run `/vault-bridge connect <path>` or `/vault-bridge create`. Do not\n'
    printf 'fabricate vault paths or invent a layout.'
  fi

  return 0
}

main "$@" 2>/dev/null || true
exit 0
```

- [ ] **Step 2: Make the script executable**

```bash
chmod +x obsidian-bridge/hooks/scripts/session-start-vault.sh
```

- [ ] **Step 3: Syntax check**

```bash
bash -n obsidian-bridge/hooks/scripts/session-start-vault.sh && echo "syntax OK"
```

Expected: `syntax OK`

- [ ] **Step 4: Dry run without breadcrumb (should emit "Not Linked")**

```bash
CLAUDE_PROJECT_DIR=/tmp/test-no-vault bash obsidian-bridge/hooks/scripts/session-start-vault.sh
```

Expected output contains: `Obsidian Bridge — Not Linked`

- [ ] **Step 5: Commit**

```bash
git add obsidian-bridge/hooks/scripts/session-start-vault.sh
git commit -m "feat(obsidian-bridge): add SessionStart vault discovery hook"
```

---

### Task 10: Hook — SessionEnd script + hooks.json

**Files:**
- Create: `obsidian-bridge/hooks/scripts/session-end-handoff.sh`
- Create: `obsidian-bridge/hooks/hooks.json`

- [ ] **Step 1: Write session-end-handoff.sh**

Write to `obsidian-bridge/hooks/scripts/session-end-handoff.sh`:

```bash
#!/usr/bin/env bash
# session-end-handoff.sh — SessionEnd hook for obsidian-bridge
# Opt-in nudge: reminds user to sync remember handoff if stale.
# Enable via OB_SESSION_END_NUDGE=1 env var.
set -euo pipefail

main() {
  # Only run if opted in
  [ "${OB_SESSION_END_NUDGE:-0}" = "1" ] || return 0

  local project_dir="${CLAUDE_PROJECT_DIR:-}"
  [ -z "$project_dir" ] && return 0

  local breadcrumb="$project_dir/.obsidian-bridge"
  [ -f "$breadcrumb" ] || return 0

  local vault_path="" project_slug=""
  vault_path=$(grep -E '^vault_path=' "$breadcrumb" 2>/dev/null | head -n1 | cut -d= -f2- || true)
  project_slug=$(grep -E '^project_slug=' "$breadcrumb" 2>/dev/null | head -n1 | cut -d= -f2- || true)

  [ -z "$vault_path" ] && return 0
  [ -z "$project_slug" ] && return 0

  local remember_file="$project_dir/.remember/remember.md"
  local handoff_file="$vault_path/projects/$project_slug/_handoff.md"

  # Only nudge if remember.md exists
  [ -f "$remember_file" ] || return 0

  # Compare mtimes
  if [ -f "$handoff_file" ]; then
    local remember_mtime handoff_mtime
    # macOS stat
    remember_mtime=$(stat -f %m "$remember_file" 2>/dev/null || stat -c %Y "$remember_file" 2>/dev/null || echo 0)
    handoff_mtime=$(stat -f %m "$handoff_file" 2>/dev/null || stat -c %Y "$handoff_file" 2>/dev/null || echo 0)
    if [ "$remember_mtime" -gt "$handoff_mtime" ]; then
      printf 'remember.md updated since last handoff — run /vault-bridge handoff sync to mirror.'
    fi
  else
    printf 'remember.md exists but no vault handoff yet — run /vault-bridge handoff sync to mirror.'
  fi

  return 0
}

main "$@" 2>/dev/null || true
exit 0
```

- [ ] **Step 2: Make executable**

```bash
chmod +x obsidian-bridge/hooks/scripts/session-end-handoff.sh
```

- [ ] **Step 3: Write hooks.json**

Write to `obsidian-bridge/hooks/hooks.json`:

```json
{
  "hooks": {
    "SessionStart": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/session-start-vault.sh",
        "timeout": 10
      }]
    }],
    "SessionEnd": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "bash ${CLAUDE_PLUGIN_ROOT}/hooks/scripts/session-end-handoff.sh",
        "timeout": 5
      }]
    }],
    "UserPromptSubmit": [{
      "matcher": "*",
      "hooks": [{
        "type": "command",
        "command": "[ -f \"$CLAUDE_PROJECT_DIR/.obsidian-bridge\" ] || printf 'No vault linked. Run /vault-bridge connect or /vault-bridge create before vault-dependent work.'",
        "timeout": 3
      }]
    }]
  }
}
```

- [ ] **Step 4: Verify JSON and scripts**

```bash
python3 -m json.tool obsidian-bridge/hooks/hooks.json > /dev/null && echo "hooks.json OK"
bash -n obsidian-bridge/hooks/scripts/session-end-handoff.sh && echo "session-end OK"
```

Expected: both OK.

- [ ] **Step 5: Commit**

```bash
git add obsidian-bridge/hooks/scripts/session-end-handoff.sh obsidian-bridge/hooks/hooks.json
git commit -m "feat(obsidian-bridge): add SessionEnd hook and hooks.json config"
```

---

### Task 11: Command wrapper — vault-bridge.md

**Files:**
- Create: `obsidian-bridge/commands/vault-bridge.md`

Thin wrapper that dispatches to the vault-bridge skill. Lists all subcommands for discoverability.

- [ ] **Step 1: Write vault-bridge.md**

Write to `obsidian-bridge/commands/vault-bridge.md`:

```markdown
---
description: Vault operations — create, connect, scaffold, sync, status, housekeeping, migrate, iterations, handoff.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

Obsidian vault management. Dispatches to the `vault-bridge` skill.

## Subcommands

```
/vault-bridge create [path]                     Scaffold new v3 vault
/vault-bridge connect <path>                    Connect to existing vault
/vault-bridge link <slug>                       Switch project in current directory
/vault-bridge create-project <slug> <type>      Scaffold type-shaped project
/vault-bridge add-collection <name>             Add sub-collection folder + _index.md
/vault-bridge sync                              Write/update current project's brief
/vault-bridge status                            Vault summary + per-project counts
/vault-bridge archive <slug>                    Move project → archive/
/vault-bridge unarchive <slug>                  Restore archive/ → projects/
/vault-bridge reindex                           Rebuild all _index.md files
/vault-bridge housekeeping                      Full consistency check
/vault-bridge migrate                           v2 → v3 walkthrough
/vault-bridge handoff sync                      Mirror .remember/remember.md → _handoff.md
/vault-bridge handoff status                    Show last sync time
/vault-bridge set-type <slug> <type>            Change project type
/vault-bridge templates [list|print <name>]     List/print templates

Iterations:
/vault-bridge add-iteration <id> <slug> [--track <name>] [--with-folder]
/vault-bridge add-iteration-artefact <iter-id> <file>
/vault-bridge iterations [<slug>] [--tree]
/vault-bridge iteration-set-status <iter-id> <status>
```

Parse the user's subcommand and arguments, then invoke the `vault-bridge` skill with the appropriate action.
```

- [ ] **Step 2: Verify**

```bash
head -3 obsidian-bridge/commands/vault-bridge.md
```

Expected: YAML frontmatter with `description:`.

- [ ] **Step 3: Commit**

```bash
git add obsidian-bridge/commands/vault-bridge.md
git commit -m "feat(obsidian-bridge): add /vault-bridge command wrapper"
```

---

### Task 12: Skill — vault-bridge SKILL.md (foundation)

**Files:**
- Create: `obsidian-bridge/skills/vault-bridge/SKILL.md`

This is the largest file. Built incrementally across Tasks 12–16. This task writes the foundation: frontmatter, intro, vault structure reference, primitives section, and the first three commands (`create`, `connect`, `link`).

- [ ] **Step 1: Write SKILL.md foundation**

Write to `obsidian-bridge/skills/vault-bridge/SKILL.md`:

```markdown
---
name: vault-bridge
description: Connect, create, scaffold, or manage the Obsidian vault. Use for setting up vaults, scaffolding projects, syncing briefs, running housekeeping, managing iterations, migrating from v2, and handoff operations.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
version: 0.1.0
---

Bridge between Claude Code sessions and a persistent Obsidian vault. This skill handles explicit vault operations — creating, connecting, scaffolding, syncing, archiving, housekeeping, iterations, migration, and handoff. Vault interactions outside of explicit `/vault-bridge` commands should be silent and automatic.

## Vault Structure (v3)

Full structure, frontmatter schemas, naming rules, wikilink conventions, and tag taxonomy are in `references/vault-standards.md`. Key paths:

- `projects/{slug}/brief.md` — project brief (type-shaped by `project_type`)
- `projects/{slug}/decisions/` — decision records
- `projects/{slug}/sessions/` — session summaries
- `projects/{slug}/notes/` — general notes
- `projects/{slug}/iterations/` — design/code iterations (opt-in)
- `archive/{slug}/` — archived projects (same shape)
- `Home.md` — auto-rebuilt vault home

Subfolder defaults vary by project type (`coding`, `knowledge`, `plugin`, `tinkerage`) — see `vault-standards.md § Per-Type Project Subfolder Defaults`.

## Vault Primitives

All vault operations go through the `vault.*` abstraction defined in `references/vault-integration.md`. CLI-first policy: prefer Obsidian CLI for every operation it supports. Filesystem fallback when CLI unavailable.

```pseudocode
FUNCTION vault_op(op, args):
    IF cli_available():
        RUN via obsidian CLI
    ELSE:
        RUN via filesystem (Read/Write/Glob/Grep)
```

Read `references/vault-integration.md` for the full operation table and fallback rules.

---

## Commands

### create — Scaffold a new v3 vault

```pseudocode
IF user provides path: vault_path = resolve(path)
ELSE: REQUEST path from user

IF non-empty dir AND not an Obsidian vault:
    offer subfolder mode (_cabinet/) or new location
ELSE:
    base = vault_path

mkdir -p projects, archive, templates
COPY templates from plugin examples/vault-templates/ to {base}/templates/
CREATE Home.md from home.md template (set updated: TODAY)
CREATE projects/_index.md from projects-index.md template

// Detect transport
IF cli_available():
    mode = "cli"
    vault_name = basename(vault_path)
ELSE:
    mode = "filesystem"
    vault_name = basename(vault_path)

// Write breadcrumb
WRITE $CLAUDE_PROJECT_DIR/.obsidian-bridge:
    vault_path={base}
    vault_name={vault_name}
    project_slug=
    linked_at={TODAY}
    mode={mode}

// Add to .gitignore if not present
IF .gitignore exists AND NOT contains ".obsidian-bridge":
    APPEND ".obsidian-bridge" to .gitignore

REPORT: "Vault created at {base}. Transport: {mode}. Run /vault-bridge create-project <slug> <type> to scaffold your first project."
```

### connect — Point at an existing vault

```pseudocode
path = resolve(user-provided path)

// 1. Detect vault
IF path contains Home.md with type: vault-home OR type: cabinet-home:
    base = path
ELIF path/projects/ exists:
    base = path
ELSE:
    ERROR "No vault found at this path. Expected Home.md with type: vault-home or a projects/ folder."

// 2. Detect schema version
has_project_type = false
FOR each project dir in base/projects/:
    IF brief.md exists AND contains "project_type:":
        has_project_type = true
        BREAK

IF has_project_type:
    version = "v3"
ELIF any project has brief.md + decisions/ + sessions/:
    version = "v2"
ELSE:
    version = "unknown"

// 3. Detect transport
IF cli_available():
    mode = "cli"
    vault_name = detect_vault_name() OR basename(path)
ELSE:
    mode = "filesystem"
    vault_name = basename(path)

// 4. Inventory
FOR each project dir in base/projects/:
    count decisions, sessions
    read brief status and project_type
    REPORT: slug, type, status, decisions, sessions

// 5. Write breadcrumb (no project_slug yet — user links separately)
WRITE $CLAUDE_PROJECT_DIR/.obsidian-bridge:
    vault_path={base}
    vault_name={vault_name}
    project_slug=
    linked_at={TODAY}
    mode={mode}

// 6. Add to .gitignore if needed
IF .gitignore exists AND NOT contains ".obsidian-bridge":
    APPEND ".obsidian-bridge" to .gitignore

// 7. Cabinet detection
IF base/crew/ exists:
    REPORT: "Cabinet detected — crew/ folder present, untouched by bridge."

IF version == "v2":
    SUGGEST: "Run /vault-bridge migrate to convert to v3 schema."

REPORT: "Connected to {vault_name} at {base}. Schema: {version}. Transport: {mode}."
```

### link — Set project slug for current directory

```pseudocode
slug = user-provided slug
breadcrumb = $CLAUDE_PROJECT_DIR/.obsidian-bridge

IF NOT exists breadcrumb:
    ERROR "No vault connected. Run /vault-bridge connect <path> first."

// Read existing breadcrumb
vault_path = read vault_path from breadcrumb

// Validate slug exists
IF NOT exists {vault_path}/projects/{slug}/brief.md:
    // List available projects
    available = list dirs in {vault_path}/projects/
    ERROR "Project '{slug}' not found. Available: {available}"

// Update breadcrumb with new slug
UPDATE breadcrumb: project_slug={slug}, linked_at={TODAY}

// Read project info
project_type = read project_type from brief.md
status = read status from brief.md

REPORT: "Linked to project '{slug}' (type: {project_type}, status: {status})."
```
```

- [ ] **Step 2: Verify frontmatter and first command**

```bash
head -7 obsidian-bridge/skills/vault-bridge/SKILL.md
grep -c "^### " obsidian-bridge/skills/vault-bridge/SKILL.md
```

Expected: YAML frontmatter with `name: vault-bridge`, 3 command headings (create, connect, link).

- [ ] **Step 3: Commit**

```bash
git add obsidian-bridge/skills/vault-bridge/SKILL.md
git commit -m "feat(obsidian-bridge): vault-bridge skill foundation (create, connect, link)"
```

---

### Task 13: Skill — vault-bridge: project commands

**Files:**
- Modify: `obsidian-bridge/skills/vault-bridge/SKILL.md`

Adds `create-project`, `add-collection`, `sync`, `status`, `templates` commands.

- [ ] **Step 1: Append project commands to SKILL.md**

Append after the `link` command section (after the last ` ``` ` of the link pseudocode block):

```markdown

### create-project — Scaffold a type-shaped project

Requires both `<slug>` and `<type>`. Asks if either is omitted. Validates slug against naming rules (lowercase, hyphenated, no spaces, no dots).

```pseudocode
slug = validate_slug(user-provided slug)
project_type = validate_type(user-provided type)  // coding | knowledge | plugin | tinkerage

// Read breadcrumb for vault path
vault_path = read vault_path from $CLAUDE_PROJECT_DIR/.obsidian-bridge
IF NOT vault_path: ERROR "No vault connected."

project_dir = {vault_path}/projects/{slug}
IF exists project_dir: ERROR "Project '{slug}' already exists."

// 1. Create project directory
mkdir {project_dir}

// 2. Create brief from type-shaped template
template = read examples/vault-templates/brief-{project_type}.md
brief = template with:
    slug: {slug}
    aliases: [{slug}]
    created: {TODAY}
    updated: {TODAY}
    # Title set to slug (user can rename)
vault.write("projects/{slug}/brief.md", brief)

// 3. Scaffold type-specific subfolders
MATCH project_type:
    "coding":
        FOR folder IN [decisions, notes, tasks, references, sessions, images]:
            mkdir {project_dir}/{folder}
        FOR folder IN [decisions, notes, tasks, references]:
            vault.write("projects/{slug}/{folder}/_index.md", collection_index(slug, folder))

    "plugin":
        FOR folder IN [decisions, notes, tasks, references, releases, sessions, images]:
            mkdir {project_dir}/{folder}
        FOR folder IN [decisions, notes, tasks, references, releases]:
            vault.write("projects/{slug}/{folder}/_index.md", collection_index(slug, folder))

    "knowledge":
        FOR folder IN [notes, sources, references, sessions]:
            mkdir {project_dir}/{folder}
        FOR folder IN [notes, sources, references]:
            vault.write("projects/{slug}/{folder}/_index.md", collection_index(slug, folder))

    "tinkerage":
        mkdir {project_dir}/sessions   // optional, created for convenience

// 4. Update projects/_index.md
REBUILD projects/_index.md from all project briefs

// 5. Update Home.md
RUN update_home()

// 6. Update breadcrumb with slug
UPDATE $CLAUDE_PROJECT_DIR/.obsidian-bridge: project_slug={slug}

// 7. If codebase root detected, scaffold codebase dirs
IF git root OR $CLAUDE_PROJECT_DIR is a code project:
    mkdir -p assets, concepts, previews in codebase root (if not exists)

REPORT: "Project '{slug}' scaffolded as {project_type}. Folders: [list]. Brief at projects/{slug}/brief.md."


// Helper: generate collection _index.md
FUNCTION collection_index(slug, folder_name):
    RETURN template from examples/vault-templates/collection-index.md with:
        project: "[[projects/{slug}/brief|{slug}]]"
        title: capitalize(folder_name)
```

### add-collection — Add sub-collection folder + `_index.md`

```pseudocode
name = validate_slug(user-provided name)  // kebab-case

// Read breadcrumb
vault_path = read vault_path from breadcrumb
project_slug = read project_slug from breadcrumb
IF NOT project_slug: ERROR "No project linked. Run /vault-bridge link <slug> first."

collection_dir = {vault_path}/projects/{project_slug}/{name}
IF exists collection_dir: ERROR "Collection '{name}' already exists."

mkdir {collection_dir}
vault.write("projects/{project_slug}/{name}/_index.md", collection_index(project_slug, name))

REPORT: "Collection '{name}' added to project '{project_slug}' with _index.md."
```

### sync — Write/update current project's brief

```pseudocode
// Read breadcrumb
vault_path = read vault_path from breadcrumb
project_slug = read project_slug from breadcrumb
IF NOT project_slug: ERROR "No project linked."

brief_path = "projects/{project_slug}/brief.md"

// Build brief content from current session context
// Gather: overview, tech stack, constraints, work notes, milestones, user decisions
// from conversation context and any existing brief content

IF vault.exists(brief_path):
    existing = vault.read(brief_path)
    ASK: "Brief exists. Merge (preserve existing, update changed sections) or overwrite?"
    IF merge:
        // Preserve existing sections, update scope + work notes from session
        merged = merge_briefs(existing, session_context)
        vault.write(brief_path, merged)
    ELSE:
        vault.write(brief_path, new_brief)
ELSE:
    // Read project_type from breadcrumb context or ask
    vault.write(brief_path, new_brief)

// Update brief frontmatter
vault.property_set(brief_path, "updated", TODAY)

// Rebuild indices
REBUILD projects/_index.md
RUN update_home()

REPORT: "Brief synced for '{project_slug}'."
```

### status — Vault summary + per-project counts

```pseudocode
// Read breadcrumb
vault_path = read vault_path from breadcrumb
vault_name = read vault_name from breadcrumb
mode = read mode from breadcrumb

REPORT header: "Vault: {vault_name} at {vault_path}"
REPORT: "Transport: {mode}"
IF mode == "cli":
    cli_ver = run "obsidian version"
    REPORT: "CLI version: {cli_ver}"

// Schema version detection
has_v3 = any brief has project_type field
has_v2 = any brief lacks project_type field
IF has_v3 AND has_v2: version_note = "v3 (mixed — some v2 projects remain)"
ELIF has_v3: version_note = "v3"
ELSE: version_note = "v2"
REPORT: "Schema: {version_note}"

// Per-project inventory
FOR each project dir in {vault_path}/projects/:
    slug = dirname
    brief = read brief.md frontmatter
    status = brief.status
    project_type = brief.project_type OR "unknown"
    decisions = count files in decisions/
    sessions = count files in sessions/
    last_session = most recent session filename date
    REPORT row: "  {slug} — {project_type} — {status} — {decisions}d {sessions}s — last: {last_session}"

// Archive
FOR each dir in {vault_path}/archive/:
    REPORT: "  [archived] {dirname}"

// Cabinet detection
IF {vault_path}/crew/ exists:
    REPORT: "Cabinet: detected — crew/ folder present, untouched by bridge."

// Remember detection
IF $CLAUDE_PROJECT_DIR/.remember/ exists:
    IF _handoff.md exists for current project:
        handoff_date = read updated from _handoff.md frontmatter
        REPORT: "Remember: detected — last handoff sync: {handoff_date}"
    ELSE:
        REPORT: "Remember: detected — no handoff yet."

// Drift teaser (quick check)
issues = quick_scan_for_drift()  // briefs missing project_type, collections without _index, etc.
IF issues > 0:
    REPORT: "Drift: {issues} issues detected. Run /dream for details."
```

### templates — List or print available templates

```pseudocode
IF subcommand == "list" OR no subcommand:
    FOR each .md file in examples/vault-templates/:
        name = filename without .md
        type = read type from frontmatter
        REPORT: "  {name} — type: {type}"

IF subcommand == "print" AND template_name provided:
    path = examples/vault-templates/{template_name}.md
    IF NOT exists path:
        path = examples/vault-templates/{template_name}  // try with extension
    IF NOT exists path:
        ERROR "Template '{template_name}' not found."
    content = read path
    REPORT: content
```
```

- [ ] **Step 2: Verify command count**

```bash
grep -c "^### " obsidian-bridge/skills/vault-bridge/SKILL.md
```

Expected: 8 (create, connect, link, create-project, add-collection, sync, status, templates).

- [ ] **Step 3: Commit**

```bash
git add obsidian-bridge/skills/vault-bridge/SKILL.md
git commit -m "feat(obsidian-bridge): vault-bridge skill — project commands (create-project, sync, status)"
```

---

### Task 14: Skill — vault-bridge: lifecycle + housekeeping commands

**Files:**
- Modify: `obsidian-bridge/skills/vault-bridge/SKILL.md`

Adds `archive`, `unarchive`, `reindex`, `set-type`, `housekeeping`.

- [ ] **Step 1: Append lifecycle commands to SKILL.md**

Append after the `templates` command section:

```markdown

### archive — Move project to archive/

```pseudocode
slug = user-provided slug OR read project_slug from breadcrumb
vault_path = read vault_path from breadcrumb

IF NOT exists {vault_path}/projects/{slug}/:
    ERROR "Project '{slug}' not found in projects/."

// Update brief status
vault.property_set("projects/{slug}/brief.md", "status", "archived")
vault.property_set("projects/{slug}/brief.md", "updated", TODAY)

// Move the folder
vault.move("projects/{slug}", "archive/{slug}")

// Rebuild indices
REBUILD projects/_index.md
RUN update_home()

// If current breadcrumb points to this slug, clear it
IF breadcrumb project_slug == slug:
    UPDATE breadcrumb: project_slug=

REPORT: "Project '{slug}' archived."
```

### unarchive — Restore project from archive/

```pseudocode
slug = user-provided slug
vault_path = read vault_path from breadcrumb

IF NOT exists {vault_path}/archive/{slug}/:
    ERROR "Project '{slug}' not found in archive/."

// Update brief status
vault.property_set("archive/{slug}/brief.md", "status", "active")
vault.property_set("archive/{slug}/brief.md", "updated", TODAY)

// Move back
vault.move("archive/{slug}", "projects/{slug}")

// Rebuild indices
REBUILD projects/_index.md
RUN update_home()

REPORT: "Project '{slug}' restored to active."
```

### reindex — Rebuild all `_index.md` files from disk

```pseudocode
vault_path = read vault_path from breadcrumb

// 1. Rebuild projects/_index.md
projects = list dirs in {vault_path}/projects/
FOR each project:
    read brief frontmatter (slug, status, project_type, created, updated)
    count decisions, sessions
    find latest session date
WRITE projects/_index.md with table rows

// 2. Rebuild per-project collection indices
FOR each project dir:
    FOR each subfolder that is a collection (has ≥2 .md siblings, not sessions/images/assets/):
        IF _index.md missing:
            CREATE from collection-index template
        REBUILD _index.md entries from folder contents
            sort chronologically if filenames have dates, else alphabetically

// 3. Rebuild iterations/_index.md (if exists)
FOR each project with iterations/:
    group iterations by track (from frontmatter)
    sort by date within track
    WRITE iterations/_index.md with track grouping and status badges

// 4. Rebuild Home.md
RUN update_home()

// 5. Report
REPORT: "Reindexed {N} projects, rebuilt {M} _index.md files."
```

### set-type — Change project type post-hoc

```pseudocode
slug = user-provided slug
new_type = validate_type(user-provided type)
vault_path = read vault_path from breadcrumb

brief_path = "projects/{slug}/brief.md"
IF NOT vault.exists(brief_path): ERROR "Project '{slug}' not found."

old_type = vault.property_read(brief_path, "project_type")

// Update frontmatter
vault.property_set(brief_path, "project_type", new_type)
vault.property_set(brief_path, "updated", TODAY)

// Update tags: remove old type tag, add new
// Read tags, replace type/{old_type} with type/{new_type}
tags = vault.property_read(brief_path, "tags")
tags = replace "type/{old_type}" with "type/{new_type}" in tags
vault.property_set(brief_path, "tags", tags)

// Scaffold new type-specific folders if missing
MATCH new_type:
    // Same logic as create-project folder scaffolding
    // Only create folders that don't already exist
    // Create _index.md for new collection folders

REPORT: "Project '{slug}' type changed from {old_type} to {new_type}. New folders scaffolded if needed."
```

### housekeeping — Full consistency check

Runs all structural checks from the housekeeping checklist. Auto-fixes safe items, reports manual items.

```pseudocode
vault_path = read vault_path from breadcrumb
project_slug = read project_slug from breadcrumb

// Scope: current project if linked, otherwise vault-wide
IF project_slug:
    scope = [project_slug]
ELSE:
    scope = list all project slugs

auto_fixes = []
manual_items = []

FOR each slug in scope:
    project_dir = {vault_path}/projects/{slug}

    // 1. Empty project folder
    IF project_dir has no .md files and no subfolders:
        manual_items.add("Empty project folder: {slug} — archive or delete?")

    // 2. Missing brief.md
    IF NOT exists brief.md:
        auto_fixes.add("Missing brief.md for {slug} — scaffold from template")
        ACTION: scaffold brief from type template (ask type if unknown)

    // 3. Slug shape violation
    IF slug contains dots, spaces, or uppercase:
        manual_items.add("Slug '{slug}' violates naming rules — rename with /vault-bridge?")

    // 4. Collection folders missing _index.md
    FOR each subfolder with ≥2 .md siblings (excluding sessions/, images/, assets/):
        IF NOT exists _index.md:
            auto_fixes.add("Missing _index.md in {slug}/{folder}")
            ACTION: create from collection-index template

    // 5. _index.md out of sync
    FOR each _index.md:
        expected_entries = list .md siblings
        actual_entries = parse _index.md links
        IF mismatch:
            auto_fixes.add("_index.md out of sync in {slug}/{folder}")
            ACTION: rebuild from disk

    // 6. Files missing frontmatter
    FOR each .md file (excluding .obsidian/, templates/):
        IF no YAML frontmatter:
            auto_fixes.add("Missing frontmatter: {file}")
            ACTION: add minimal valid frontmatter based on location

    // 7. Malformed/incomplete frontmatter
    FOR each .md file with frontmatter:
        IF missing required fields for its type:
            auto_fixes.add("Incomplete frontmatter: {file} — missing {fields}")
            ACTION: add missing required fields with defaults

    // 8. Broken wikilinks
    FOR each wikilink [[target]] in all files:
        IF target not resolvable:
            manual_items.add("Broken wikilink [[{target}]] in {file}")

    // 9. Markdown-style links
    FOR each [text](path) in vault files:
        auto_fixes.add("Markdown link in {file} — convert to wikilink")
        ACTION: replace with [[equivalent]]

    // 10. Tag clutter
    all_tags = collect all tags across scope
    FOR tag with usage_count == 1:
        manual_items.add("Single-use tag #{tag} in {file}")
    FOR near-duplicates (e.g. #postgres vs #postgresql):
        manual_items.add("Near-duplicate tags: #{a} vs #{b}")

    // 11. Stale updated date
    IF status == "active" AND updated > 90 days ago:
        manual_items.add("Stale project '{slug}' — last updated {updated}")

    // 12. Decision filename pattern
    FOR each file in decisions/:
        IF NOT matches YYYY-MM-DD-{kebab}.md:
            auto_fixes.add("Decision filename violation: {file}")
            ACTION: rename to correct pattern

    // 13. Session filename pattern
    FOR each file in sessions/:
        IF NOT matches YYYY-MM-DD.md:
            auto_fixes.add("Session filename violation: {file}")
            ACTION: rename or merge same-day

    // 14. Root docs missing type: doc
    FOR each .md in project root (not brief.md, not _handoff.md, not _index.md):
        IF NOT has type: doc in frontmatter:
            auto_fixes.add("Root doc missing type: doc — {file}")
            ACTION: add type: doc frontmatter

    // 15. Brief body missing required blocks for type
    project_type = read from brief frontmatter
    required_blocks = get_required_blocks(project_type)
    existing_blocks = parse ## headers from brief body
    FOR each missing block:
        auto_fixes.add("Brief missing block: ## {block} for type {project_type}")
        ACTION: add empty block with placeholder

// Report
REPORT:
    "## Auto-fixable ({count})"
    list auto_fixes
    "[Fix all] [Pick] [Skip]"
    ""
    "## Needs decision ({count})"
    list manual_items

// If user chooses "Fix all": run all auto_fixes sequentially
// If "Pick": present each, user approves/skips
// If "Skip": done
```
```

- [ ] **Step 2: Verify command count**

```bash
grep -c "^### " obsidian-bridge/skills/vault-bridge/SKILL.md
```

Expected: 13 (create, connect, link, create-project, add-collection, sync, status, templates, archive, unarchive, reindex, set-type, housekeeping).

- [ ] **Step 3: Commit**

```bash
git add obsidian-bridge/skills/vault-bridge/SKILL.md
git commit -m "feat(obsidian-bridge): vault-bridge skill — lifecycle + housekeeping"
```

---

### Task 15: Skill — vault-bridge: iteration commands

**Files:**
- Modify: `obsidian-bridge/skills/vault-bridge/SKILL.md`

Adds `add-iteration`, `add-iteration-artefact`, `iterations`, `iteration-set-status`. Spec §8.

- [ ] **Step 1: Append iteration commands to SKILL.md**

Append after the `housekeeping` command section:

```markdown

---

## Iteration Commands

Iterations are a first-class collection type. Canonical folder: `projects/{slug}/iterations/`. Opt-in for all project types — not auto-created on `create-project`. See `references/vault-standards.md` for the iteration schema.

### add-iteration — Create iteration in current project

```pseudocode
identifier = user-provided id (letter, number, or short word)
iter_slug = validate_slug(user-provided slug)
track = optional --track flag
with_folder = optional --with-folder flag

vault_path = read vault_path from breadcrumb
project_slug = read project_slug from breadcrumb
IF NOT project_slug: ERROR "No project linked."

iter_dir = {vault_path}/projects/{project_slug}/iterations

// Create iterations/ folder if first iteration
IF NOT exists iter_dir:
    mkdir iter_dir
    vault.write("projects/{project_slug}/iterations/_index.md",
        iterations_index(project_slug))

// Build filename
date = TODAY
filename = "{date}-iter-{identifier}-{iter_slug}"

IF with_folder:
    // Folder form
    mkdir {iter_dir}/{filename}
    vault.write("projects/{project_slug}/iterations/{filename}/_iteration.md",
        iteration_template(project_slug, identifier, date, track))
ELSE:
    // File form
    vault.write("projects/{project_slug}/iterations/{filename}.md",
        iteration_template(project_slug, identifier, date, track))

// Add ## ITERATIONS block to brief if not present
brief_content = vault.read("projects/{project_slug}/brief.md")
IF NOT contains "## ITERATIONS":
    APPEND to brief before last section or at end:
        "\n## ITERATIONS\n\nSee [[projects/{project_slug}/iterations/_index|iterations]].\n"

// Rebuild iterations/_index.md
REBUILD iterations/_index.md from disk (grouped by track, sorted by date)

REPORT: "Iteration {identifier} created: {filename}"


FUNCTION iteration_template(slug, identifier, date, track):
    frontmatter = {
        type: iteration,
        project: "[[projects/{slug}/brief|{slug}]]",
        identifier: identifier,
        status: drafting,
        date: date,
        tags: [ob/iteration]
    }
    IF track:
        frontmatter.track = track
    RETURN: frontmatter + "\n# Iteration {identifier}\n"


FUNCTION iterations_index(slug):
    RETURN collection_index template with:
        project: "[[projects/{slug}/brief|{slug}]]"
        title: "Iterations — {slug}"
        description: "Design and code iterations grouped by track."
```

### add-iteration-artefact — Promote .md to folder; add artefact

```pseudocode
iter_id = user-provided iteration identifier (matches identifier field)
file = user-provided file path (absolute or relative to CWD)

vault_path = read vault_path from breadcrumb
project_slug = read project_slug from breadcrumb
iter_dir = {vault_path}/projects/{project_slug}/iterations

// Find the iteration by identifier
found = null
FOR each entry in iter_dir:
    IF entry name contains "-iter-{iter_id}-":
        found = entry
        BREAK
IF NOT found: ERROR "Iteration '{iter_id}' not found."

// If file form (.md), promote to folder form
IF found is a .md file:
    folder_name = found without .md extension
    mkdir {iter_dir}/{folder_name}
    // Rename the .md to _iteration.md inside the new folder
    vault.move("projects/{project_slug}/iterations/{found}",
               "projects/{project_slug}/iterations/{folder_name}/_iteration.md")
    found = folder_name  // now a folder

// Copy artefact into iteration folder
artefact_name = basename(file)
cp {file} to {iter_dir}/{found}/{artefact_name}

// Update frontmatter artefacts list
iter_file = "projects/{project_slug}/iterations/{found}/_iteration.md"
existing_artefacts = vault.property_read(iter_file, "artefacts") OR []
existing_artefacts.add(artefact_name)
vault.property_set(iter_file, "artefacts", existing_artefacts)

// Rebuild _index.md
REBUILD iterations/_index.md

REPORT: "Artefact '{artefact_name}' added to iteration {iter_id}. Promoted to folder form."
```

### iterations — List iterations grouped by track

```pseudocode
slug = user-provided slug OR read project_slug from breadcrumb
tree_flag = optional --tree flag
vault_path = read vault_path from breadcrumb

iter_dir = {vault_path}/projects/{slug}/iterations
IF NOT exists iter_dir: REPORT "No iterations for project '{slug}'." RETURN

// Collect all iterations
iterations = []
FOR each entry in iter_dir (excluding _index.md):
    IF entry is .md file:
        fm = read frontmatter
    ELIF entry is folder with _iteration.md:
        fm = read _iteration.md frontmatter
    ELSE: SKIP

    iterations.add({
        identifier: fm.identifier,
        status: fm.status,
        date: fm.date,
        track: fm.track OR "Loose",
        register: fm.register,
        supersedes: fm.supersedes,
        builds_on: fm.builds_on,
        filename: entry name
    })

// Group by track
tracks = group iterations by track
sort tracks by most recent iteration date (descending)

FOR each track:
    REPORT: "## Track: {track_name}"
    FOR each iteration in track (sorted by date):
        status_badge = iteration.status
        REPORT: "  [{iteration.identifier}] {iteration.filename} — {status_badge}"
        IF iteration.register:
            REPORT: "      {iteration.register}"

IF tree_flag:
    // Show lineage tree
    REPORT: "\n## Lineage"
    FOR each iteration with supersedes or builds_on:
        REPORT: "  {identifier} → supersedes {target}" or "  {identifier} ← builds on {ancestor}"
```

### iteration-set-status — Change iteration status

```pseudocode
iter_id = user-provided identifier
new_status = validate(user-provided status)
    // drafting | on-shelf | picked | parked | rejected | superseded

vault_path = read vault_path from breadcrumb
project_slug = read project_slug from breadcrumb
iter_dir = {vault_path}/projects/{project_slug}/iterations

// Find iteration
iter_file = find iteration file by identifier (same logic as add-iteration-artefact)
IF NOT found: ERROR "Iteration '{iter_id}' not found."

// Set status
vault.property_set(iter_file, "status", new_status)

// If "picked": offer to mark same-track siblings as "superseded"
IF new_status == "picked":
    track = vault.property_read(iter_file, "track")
    IF track:
        siblings = find other iterations with same track AND status NOT IN [rejected, superseded]
        IF siblings.length > 0:
            ASK: "Mark {siblings.length} sibling(s) on track '{track}' as superseded?"
            IF yes:
                FOR each sibling:
                    vault.property_set(sibling.file, "status", "superseded")

// Rebuild _index.md
REBUILD iterations/_index.md

REPORT: "Iteration {iter_id} status set to {new_status}."
```
```

- [ ] **Step 2: Verify iteration commands added**

```bash
grep "^### " obsidian-bridge/skills/vault-bridge/SKILL.md | tail -4
```

Expected: last 4 headings are `add-iteration`, `add-iteration-artefact`, `iterations`, `iteration-set-status`.

- [ ] **Step 3: Commit**

```bash
git add obsidian-bridge/skills/vault-bridge/SKILL.md
git commit -m "feat(obsidian-bridge): vault-bridge skill — iteration commands"
```

---

### Task 16: Skill — vault-bridge: handoff + migrate

**Files:**
- Modify: `obsidian-bridge/skills/vault-bridge/SKILL.md`

Adds `handoff sync`, `handoff status`, `migrate`. Spec §15 and §16.

- [ ] **Step 1: Append handoff and migrate commands to SKILL.md**

Append after the iteration commands section:

```markdown

---

## Handoff Commands

Light integration with the `remember` plugin. See `references/remember-integration.md`.

### handoff sync — Mirror remember.md → `_handoff.md`

```pseudocode
vault_path = read vault_path from breadcrumb
project_slug = read project_slug from breadcrumb
IF NOT project_slug: ERROR "No project linked."

remember_file = $CLAUDE_PROJECT_DIR/.remember/remember.md
IF NOT exists remember_file:
    ERROR "No .remember/remember.md found in project directory."

// Read remember content
content = read remember_file

// Build handoff file
handoff = """
---
type: handoff
project: "[[projects/{project_slug}/brief|{project_slug}]]"
updated: {TODAY}
source: remember
tags:
  - ob/handoff
---

# Handoff — {project_slug}

*Mirrored from `.remember/remember.md` on {TODAY}.*

---

{content}
"""

vault.write("projects/{project_slug}/_handoff.md", handoff)

REPORT: "Handoff synced for '{project_slug}'. Mirrored {line_count} lines from remember.md."
```

### handoff status — Show last sync time

```pseudocode
vault_path = read vault_path from breadcrumb
project_slug = read project_slug from breadcrumb

remember_file = $CLAUDE_PROJECT_DIR/.remember/remember.md
handoff_file = {vault_path}/projects/{project_slug}/_handoff.md

remember_exists = exists remember_file
handoff_exists = vault.exists("projects/{project_slug}/_handoff.md")

IF NOT remember_exists:
    REPORT: "No .remember/remember.md found."
    RETURN

IF handoff_exists:
    handoff_date = vault.property_read("projects/{project_slug}/_handoff.md", "updated")
    // Compare mtimes
    remember_mtime = file mtime of remember_file
    handoff_mtime = file mtime of handoff_file (resolved to filesystem path)
    IF remember_mtime > handoff_mtime:
        REPORT: "Handoff: stale. Last sync: {handoff_date}. remember.md updated since."
    ELSE:
        REPORT: "Handoff: current. Last sync: {handoff_date}."
ELSE:
    REPORT: "Handoff: never synced. Run /vault-bridge handoff sync."
```

---

## Migration

### migrate — v2 → v3 walkthrough

One-shot opt-in command. Idempotent — re-running on a v3 vault effectively becomes `housekeeping`. See spec §16 for full detail.

```pseudocode
vault_path = read vault_path from breadcrumb

// 1. Confirm scope
projects = list dirs in {vault_path}/projects/
archived = list dirs in {vault_path}/archive/
total_files = count all .md files in vault
REPORT: "Migration scope: {projects.length} projects, {archived.length} archived, {total_files} files."
REPORT: "This will: add project_type to briefs, reformat brief bodies to v3 blocks, add _index.md to collections, normalise tags."
ASK: "Proceed? (A backup will be created first.)"
IF NOT proceed: RETURN

// 2. Backup
backup_dir = {vault_path}/.backup-v2-{TODAY}
cp -r {vault_path}/projects {backup_dir}/projects
cp -r {vault_path}/archive {backup_dir}/archive 2>/dev/null || true
cp {vault_path}/Home.md {backup_dir}/Home.md
REPORT: "Backup created at {backup_dir}. Delete after verifying migration."

// 3. Migrate each project
FOR each project in projects + archived:
    slug = dirname
    brief_path = resolve brief.md path (projects/ or archive/)

    // a. Detect project_type if not set
    existing_type = vault.property_read(brief_path, "project_type")
    IF NOT existing_type:
        // Heuristic defaults
        IF exists decisions/ under project: suggested = "coding"
        ELIF exists sources/ under project: suggested = "knowledge"
        ELIF exists releases/ under project: suggested = "plugin"
        ELSE: suggested = "tinkerage"

        ASK: "Project '{slug}' — assign type? Suggested: {suggested}. Options: coding, knowledge, plugin, tinkerage."
        project_type = user response OR suggested
        vault.property_set(brief_path, "project_type", project_type)
    ELSE:
        project_type = existing_type

    // b. Add aliases if missing
    aliases = vault.property_read(brief_path, "aliases")
    IF NOT aliases OR aliases is empty:
        vault.property_set(brief_path, "aliases", [slug])

    // c. Normalise tags: keep cabinet/*, add ob/*, add type/*
    tags = vault.property_read(brief_path, "tags")
    IF NOT contains "ob/project": tags.add("ob/project")
    IF NOT contains "type/{project_type}": tags.add("type/{project_type}")
    vault.property_set(brief_path, "tags", tags)

    // d. Ensure slug field
    IF NOT vault.property_read(brief_path, "slug"):
        vault.property_set(brief_path, "slug", slug)

    // e. Brief body reformat
    body = read brief body (after frontmatter)
    reformatted = reformat_brief_body(body, project_type)
    IF reformatted != body:
        write reformatted body back

    // f. Slug repair
    IF slug contains dots, spaces, or uppercase:
        suggested_slug = slugify(slug)
        ASK: "Rename '{slug}' → '{suggested_slug}'?"
        IF yes:
            vault.move("projects/{slug}", "projects/{suggested_slug}")
            slug = suggested_slug


// 4. Backfill _index.md
FOR each project:
    FOR each collection folder (≥2 .md siblings, not sessions/images/assets/):
        IF NOT exists _index.md:
            CREATE from collection-index template
        REBUILD _index.md from folder contents

// 5. Emergent iteration folders
FOR each project:
    FOR folder_name IN [design-iterations, surfaces, aesthetics]:
        IF exists {project_dir}/{folder_name}/:
            ASK: "Canonicalise '{folder_name}/' → 'iterations/' for project '{slug}'?"
            IF yes:
                vault.move("projects/{slug}/{folder_name}", "projects/{slug}/iterations")
                // Update frontmatter in moved files
                FOR each .md in iterations/:
                    IF type == "design-iteration":
                        vault.property_set(file, "type", "iteration")
                    tags = read tags
                    IF "cabinet/design-iteration" in tags:
                        tags.add("ob/iteration")
                    vault.property_set(file, "tags", tags)
                    // Preserve register, identifier, status, etc.
                CREATE iterations/_index.md (rebuild from disk)
            ELSE:
                // Leave as user-defined collection
                IF NOT exists _index.md:
                    CREATE _index.md for it

// 6. Root-level singleton docs
FOR each project:
    FOR each .md in project root (not brief.md, not _handoff.md, not _index.md):
        IF NOT has type: doc frontmatter:
            ADD type: doc frontmatter (preserve body)

// 7. Update Home.md frontmatter
home = read Home.md
IF type == "cabinet-home":
    IF {vault_path}/crew/ exists:
        SET type to [vault-home, cabinet-home]
    ELSE:
        SET type to vault-home
RUN update_home()

// 8. Run housekeeping
RUN housekeeping (auto-fix all safe items)

// 9. Report
changes = count all changes made
REPORT: "Migration complete. Changed {changes} files. Backup at {backup_dir}."
REPORT: "Review the changes, then delete {backup_dir} when satisfied."


FUNCTION reformat_brief_body(body, project_type):
    // v2 → v3 section mapping for coding type:
    //   ## Overview      → ## INTRO
    //   ## Tech Stack    → ## TECHNICAL STACK
    //   ## Scope         → split: ## CONSTRAINTS + ## USER DECISIONS
    //   ## Conventions   → append to ## TECHNICAL STACK or ## CONSTRAINTS
    //   ## Team Notes    → ## WORK NOTES
    //   anything else    → ## WORK NOTES
    //
    // Similar mappings for other types (knowledge, plugin, tinkerage)
    // All content preserved verbatim under best-fit headers.
    // Empty required blocks added with "TBD" placeholder.

    required_blocks = get_blocks_for_type(project_type)
    mapped_body = map_sections(body, project_type)

    FOR each required block NOT present in mapped_body:
        APPEND "## {BLOCK}\n\nTBD\n"

    RETURN mapped_body
```
```

- [ ] **Step 2: Verify full command count**

```bash
grep -c "^### " obsidian-bridge/skills/vault-bridge/SKILL.md
```

Expected: 17 command headings total.

- [ ] **Step 3: Verify total file length**

```bash
wc -l obsidian-bridge/skills/vault-bridge/SKILL.md
```

Expected: ~600+ lines.

- [ ] **Step 4: Commit**

```bash
git add obsidian-bridge/skills/vault-bridge/SKILL.md
git commit -m "feat(obsidian-bridge): vault-bridge skill — handoff + migrate commands"
```

---

### Task 17: Command + Skill — /dream

**Files:**
- Create: `obsidian-bridge/commands/dream.md`
- Create: `obsidian-bridge/skills/dream/SKILL.md`

Bridge-owned `/dream` with two passes: structural sanitation (new) and content analysis (ported from cabinet). Spec §13.

- [ ] **Step 1: Write dream command wrapper**

Write to `obsidian-bridge/commands/dream.md`:

```markdown
---
description: Two-pass vault analysis — structural sanitation (auto-fixable) + content review (report-only). Run on current project or vault-wide.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

Deep analytical crawl of vault data. Pass 1 finds and fixes structural drift. Pass 2 surfaces content-level issues for human review.

## Usage

```
/dream                     Analyse current project (default)
/dream --vault-wide        Analyse all projects
/dream --save              Write report to projects/{slug}/dreams/YYYY-MM-DD.md
```

Dispatches to the `dream` skill.
```

- [ ] **Step 2: Write dream SKILL.md**

Write to `obsidian-bridge/skills/dream/SKILL.md`:

```markdown
---
name: dream
description: Two-pass vault analysis. Pass 1 finds structural drift and offers auto-fixes. Pass 2 surfaces content-level issues for review.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
version: 0.1.0
---

`/dream` performs a deep analysis of vault data, surfacing issues that accumulate silently across sessions. This is not a status report — it's a diagnostic.

## Scope

Default: current project only (read `project_slug` from breadcrumb). `--vault-wide` scans all projects. `--save` persists the report to `projects/{slug}/dreams/YYYY-MM-DD.md`.

## Token Budget

`/dream` is the hungriest command. Mitigations:
- Read frontmatter first; full body only when needed for content checks.
- Summarise findings as the scan proceeds; don't accumulate then dump.
- Target: complete project dream in <5 minutes wall time.

---

## Pass 1 — Structural Sanitation

Scans for auto-fixable drift and manual-decision items.

```pseudocode
vault_path = read vault_path from breadcrumb
project_slug = read project_slug from breadcrumb
vault_wide = "--vault-wide" in args

IF vault_wide:
    slugs = list all project dirs in projects/ and archive/
ELSE:
    IF NOT project_slug: ERROR "No project linked. Use --vault-wide or link a project first."
    slugs = [project_slug]

auto_fixes = []
needs_decision = []

FOR each slug in slugs:
    project_dir = resolve(slug)  // projects/{slug} or archive/{slug}

    // --- Core structural checks ---

    // 1. Empty project folder
    md_count = count .md files in project_dir (recursive)
    IF md_count == 0:
        needs_decision.add("Empty project folder: {slug} — archive or delete?")
        CONTINUE

    // 2. Missing brief.md
    IF NOT exists brief.md:
        needs_decision.add("Project '{slug}' has no brief.md — scaffold from template?")

    // 3. Slug shape violation
    IF slug contains dots OR spaces OR uppercase:
        needs_decision.add("Slug '{slug}' violates naming rules — rename via CLI?")

    // 4. Collection folders missing _index.md
    FOR each subfolder:
        IF has ≥2 .md siblings AND name NOT IN [sessions, images, assets, previews, .obsidian]:
            IF NOT exists _index.md:
                auto_fixes.add({
                    desc: "Missing _index.md in {slug}/{folder}",
                    action: "create from collection-index template"
                })

    // 5. _index.md out of sync
    FOR each _index.md:
        disk_entries = list .md siblings (excluding _index.md)
        index_links = extract [[...]] from _index.md
        IF disk_entries != index_links:
            auto_fixes.add({
                desc: "_index.md out of sync in {slug}/{folder}",
                action: "rebuild from disk"
            })

    // 6. Files missing frontmatter
    FOR each .md file (excluding .obsidian/, templates/):
        IF no YAML frontmatter (no leading ---):
            auto_fixes.add({
                desc: "No frontmatter: {file}",
                action: "add minimal frontmatter based on location"
            })

    // 7. Malformed/incomplete frontmatter
    FOR each .md with frontmatter:
        required = get_required_fields(file.type)
        missing = required - present_fields
        IF missing:
            auto_fixes.add({
                desc: "Incomplete frontmatter: {file} — missing {missing}",
                action: "add missing fields with defaults"
            })

    // 8. Broken wikilinks
    FOR each [[target]] in all files:
        IF NOT resolvable in vault:
            needs_decision.add("Broken wikilink [[{target}]] in {file}")

    // 9. Markdown-style links
    FOR each [text](path) in vault files:
        auto_fixes.add({
            desc: "Markdown link in {file}: [{text}]({path})",
            action: "replace with [[{equivalent}]]"
        })

    // 10. Tag hygiene
    all_tags = collect all tags in scope
    FOR tag with usage == 1:
        needs_decision.add("Single-use tag #{tag} in {file}")
    FOR (a, b) where a and b are near-duplicates:
        needs_decision.add("Near-duplicate tags: #{a} vs #{b}")
    FOR tag in [wip, misc, general, thoughts]:
        IF used:
            needs_decision.add("Vague tag #{tag} — consolidate or remove?")
    FOR tag NOT matching ob/* and starting with ob/:
        needs_decision.add("Tag #{tag} drifts from ob/ namespace convention")

    // 11. Stale updated date
    IF brief.status == "active" AND brief.updated > 90 days ago:
        needs_decision.add("Stale project '{slug}' — active but not updated in {days}d")

    // 12. Decision filename pattern
    FOR each file in decisions/:
        IF NOT matches /^\d{4}-\d{2}-\d{2}-.+\.md$/:
            auto_fixes.add({
                desc: "Decision filename violation: {file}",
                action: "rename to YYYY-MM-DD-{slug}.md"
            })

    // 13. Session filename pattern
    FOR each file in sessions/:
        IF NOT matches /^\d{4}-\d{2}-\d{2}\.md$/:
            auto_fixes.add({
                desc: "Session filename violation: {file}",
                action: "rename to YYYY-MM-DD.md"
            })

    // 14. Root docs missing type: doc
    FOR each .md in project root:
        IF name NOT IN [brief.md, _handoff.md, _index.md] AND NOT starts with _:
            IF NOT has type: doc:
                auto_fixes.add({
                    desc: "Root doc missing type: doc — {file}",
                    action: "add type: doc frontmatter"
                })

    // 15. Brief body missing required blocks
    IF brief.md exists:
        project_type = read project_type from brief
        required_blocks = get_required_blocks(project_type)
        existing_blocks = parse ## headers from brief body
        FOR block IN required_blocks NOT IN existing_blocks:
            auto_fixes.add({
                desc: "Brief missing block: ## {block}",
                action: "add empty block"
            })

    // --- Iteration-specific checks ---

    // 16. Emergent iteration folders
    FOR folder_name IN [design-iterations, surfaces, aesthetics]:
        IF exists {project_dir}/{folder_name}/:
            needs_decision.add("Emergent iteration folder '{folder_name}' — canonicalise to iterations/?")

    // 17. Iteration filename pattern
    IF exists iterations/:
        FOR each entry in iterations/:
            IF is .md AND NOT matches /^\d{4}-\d{2}-\d{2}-iter-.+\.md$/ AND name != _index.md:
                auto_fixes.add({
                    desc: "Iteration filename violation: {entry}",
                    action: "rename to YYYY-MM-DD-iter-{id}-{slug}.md"
                })

    // 18. Stale drafting iterations (>30d)
    FOR each iteration with status == "drafting":
        IF date > 30 days ago:
            needs_decision.add("Iteration {identifier} drafting for {days}d — park, finish, or reject?")

    // 19. Track with picked but siblings not superseded
    tracks = group iterations by track
    FOR each track:
        picked = iterations with status == "picked"
        others = iterations with status NOT IN [picked, rejected, superseded, parked]
        IF picked.length > 0 AND others.length > 0:
            auto_fixes.add({
                desc: "Track '{track}' has picked iteration but {others.length} sibling(s) not superseded",
                action: "set siblings to superseded"
            })

    // 20. Broken supersedes/builds_on
    FOR each iteration with supersedes or builds_on:
        IF target not resolvable:
            needs_decision.add("Broken lineage link in iteration {identifier}: {link}")

    // 21. iterations/_index.md out of sync
    IF exists iterations/_index.md:
        disk_iters = list iteration files
        index_iters = parse _index.md links
        IF mismatch:
            auto_fixes.add({
                desc: "iterations/_index.md out of sync",
                action: "rebuild from disk"
            })
```

---

## Pass 2 — Content Analysis

Report-only findings. Never auto-actioned.

```pseudocode
content_findings = {
    contradictions: [],
    stale_info: [],
    dangling_scopes: [],
    unacted_decisions: [],
    documentation_gaps: []
}

FOR each slug in slugs:

    // 1. Contradicting information
    // Scan brief, decisions, sessions for conflicting statements:
    // - Decisions that contradict each other (e.g., "chose REST" vs "using GraphQL")
    // - Brief stating one stack but decisions referencing another
    // - Scope "out" items appearing in later sessions as completed
    decisions = read all decision files (frontmatter + body)
    brief = read brief body
    sessions = read recent session summaries
    FOR each pair of potentially contradicting claims:
        content_findings.contradictions.add({
            what: description of contradiction,
            where: [wikilink to file A, wikilink to file B],
            likely_current: best guess at which is current
        })

    // 2. Stale information
    // - Decisions marked "active" but >30d with no recent references
    // - Brief sections unchanged since creation
    // - Session notes referencing components that may no longer exist
    FOR each decision with status "active" AND date > 30 days ago:
        refs = vault.search("[[{decision_filename}]]", "projects/{slug}")
        IF refs.count == 0:
            content_findings.stale_info.add({
                what: "Unreferenced active decision: {title}",
                age: "{days}d",
                suggestion: "update, archive, or mark implemented"
            })

    // 3. Dangling scopes
    // - Scope "in" items never appearing in session summaries
    // - Parking lot items never revisited
    // - References to "next session" or "follow-up" with no subsequent entry
    IF brief contains scope sections:
        scope_items = parse scope in/out items from brief
        session_content = concatenate all session summaries
        FOR each scope_in item:
            IF item NOT mentioned in any session:
                content_findings.dangling_scopes.add({
                    what: item,
                    added: "unknown",
                    suggestion: "do, park, or drop"
                })

    // 4. Unacted decisions
    // Decisions with consequences that show no evidence of implementation
    FOR each decision with status "active":
        consequences = parse consequence section
        IF consequences AND NOT found evidence in sessions/brief:
            content_findings.unacted_decisions.add({
                decision: wikilink to decision,
                consequence: summary,
                gap: "no evidence of implementation"
            })

    // 5. Documentation gaps
    // - Sessions with no decisions (notable work happened but wasn't captured?)
    // - Brief missing core sections for its type
    // - Empty stub files
    FOR each session:
        session_date = filename date
        decisions_on_date = decisions with date == session_date
        IF decisions_on_date.count == 0:
            content_findings.documentation_gaps.add({
                what: "Session {date} has no decisions",
                severity: "minor"
            })
    FOR each .md file with body shorter than 3 lines (excluding frontmatter):
        content_findings.documentation_gaps.add({
            what: "Stub file: {file}",
            severity: "minor"
        })
```

---

## Output

```pseudocode
// Build report
report = """
# Dream Report — {project_name}
*{TODAY}*

## Structural — Auto-fixable ({auto_fixes.count} items)
"""
FOR each fix in auto_fixes:
    report += "1. {fix.desc}\n"

report += "[Fix all] [Pick] [Skip]\n\n"

report += "## Structural — Needs decision ({needs_decision.count} items)\n"
FOR each item in needs_decision:
    report += "- {item}\n"

report += "\n## Content — Findings\n"

IF content_findings.contradictions:
    report += "### Contradictions ({count})\n"
    FOR each: report += "- {what}\n  Files: {where}\n"

IF content_findings.stale_info:
    report += "### Stale Info ({count})\n"
    FOR each: report += "- {what} ({age})\n"

IF content_findings.dangling_scopes:
    report += "### Dangling Scopes ({count})\n"
    FOR each: report += "- {what}\n"

IF content_findings.unacted_decisions:
    report += "### Unacted Decisions ({count})\n"
    FOR each: report += "- {decision}: {consequence}\n"

IF content_findings.documentation_gaps:
    report += "### Documentation Gaps ({count})\n"
    FOR each: report += "- {what} ({severity})\n"

// Display
PRINT report

// Handle auto-fix choices
IF user chooses "Fix all":
    FOR each fix in auto_fixes:
        EXECUTE fix.action
        REPORT: "✓ {fix.desc}"
ELIF user chooses "Pick":
    FOR each fix in auto_fixes:
        ASK: "Fix: {fix.desc}? [y/n]"
        IF yes: EXECUTE fix.action

// Save if --save flag
IF "--save" in args:
    dreams_dir = "projects/{slug}/dreams"
    IF NOT exists dreams_dir:
        mkdir dreams_dir
        CREATE dreams/_index.md from collection-index template
    vault.write("projects/{slug}/dreams/{TODAY}.md", dream_report_with_frontmatter(report))
    REPORT: "Report saved to projects/{slug}/dreams/{TODAY}.md"
```

---

## Personality Layer

When cabinet-of-imd is installed and active, the chronicler voice (Bostrol/Kevijntje/Jonasty) wraps the report. Bridge detects cabinet via the `crew/` folder and adjusts formatting if the current session is a `/cabinet` session. Without cabinet, `/dream` is dry — no personality, no flair, just the report.

---

## When to Suggest

Bridge does not auto-suggest `/dream`. The command is always explicit. If cabinet is installed, cabinet's suggestion logic applies (Kevijntje suggests at 5+ sessions, 14+ days idle, or 3+ scope drifts).
```

- [ ] **Step 3: Verify both files**

```bash
head -3 obsidian-bridge/commands/dream.md
head -3 obsidian-bridge/skills/dream/SKILL.md
wc -l obsidian-bridge/skills/dream/SKILL.md
```

Expected: command has `description:` frontmatter, skill has `name: dream` frontmatter, skill is 300+ lines.

- [ ] **Step 4: Commit**

```bash
git add obsidian-bridge/commands/dream.md obsidian-bridge/skills/dream/SKILL.md
git commit -m "feat(obsidian-bridge): /dream command and skill (Pass 1 + Pass 2)"
```

---

### Task 18: Cabinet stale-flag edits

**Files:**
- Delete: `cabinet-of-imd/skills/vault-bridge/SKILL.md`
- Delete: `cabinet-of-imd/commands/dream.md`
- Modify: `cabinet-of-imd/.claude-plugin/plugin.json`
- Modify: `cabinet-of-imd/references/vault-integration.md`
- Modify: `cabinet-of-imd/references/vault-standards.md`
- Modify: `cabinet-of-imd/references/obsidian-setup.md`
- Create: `cabinet-of-imd/examples/vault-templates/STALE.md`
- Modify: `cabinet-of-imd/CHANGELOG.md` (or create if not exists)
- Modify: `cabinet-of-imd/commands/cabinet.md`
- Modify: `cabinet-of-imd/hooks/scripts/boot-flair.sh`

- [ ] **Step 1: Delete cabinet vault-bridge skill and dream command**

```bash
rm cabinet-of-imd/skills/vault-bridge/SKILL.md
rmdir cabinet-of-imd/skills/vault-bridge/
rm cabinet-of-imd/commands/dream.md
```

- [ ] **Step 2: Bump cabinet plugin.json to v2.3.0**

Edit `cabinet-of-imd/.claude-plugin/plugin.json`:

Change `"version": "2.2.0"` to `"version": "2.3.0"`.

Change `"description"` to:
```
"The Cabinet of IMD Agents — a crew of 8 college classmates serving as specialised web development agents. Vault-first operation: chatter, memories, decisions, and session anchors persist in an Obsidian vault. Gated handoffs, organic personality, lazy character loading, Cowork + terminal support. (Vault structure & /dream now owned by obsidian-bridge plugin — cabinet refactor pending.)"
```

- [ ] **Step 3: Add stale banners to cabinet references**

Prepend to `cabinet-of-imd/references/vault-integration.md` (after frontmatter if any, or at line 1):

```markdown
> **STALE.** Superseded by `obsidian-bridge/references/vault-integration.md`. Cabinet refactor pending.

```

Prepend to `cabinet-of-imd/references/vault-standards.md` (after line 1 `# Vault Standards`):

```markdown
> **STALE.** Superseded by `obsidian-bridge/references/vault-standards.md`. Cabinet refactor pending.

```

Prepend to `cabinet-of-imd/references/obsidian-setup.md` (after title):

```markdown
> **STALE.** Superseded by `obsidian-bridge/references/obsidian-setup.md`. Cabinet refactor pending.

```

- [ ] **Step 4: Create STALE.md in cabinet templates folder**

Write to `cabinet-of-imd/examples/vault-templates/STALE.md`:

```markdown
> **STALE.** These templates are superseded by `obsidian-bridge/examples/vault-templates/`. Cabinet refactor pending.
```

- [ ] **Step 5: Update marketplace.json cabinet version**

Edit `.claude-plugin/marketplace.json` — update cabinet-of-imd version from `"2.2.0"` to `"2.3.0"` and update its description to match the plugin.json change.

- [ ] **Step 6: Add/update cabinet CHANGELOG.md**

If `cabinet-of-imd/CHANGELOG.md` exists, prepend new entry. If not, create with:

```markdown
# Changelog

## 2.3.0 — 2026-04-30

Vault structure & /dream extracted to obsidian-bridge plugin. Cabinet's /vault-bridge skill and /dream command removed. Cabinet's vault refactor pending; existing v2 vault behavior preserved as deprecated path.
```

- [ ] **Step 7: Update cabinet.md step 1.5 vault check**

In `cabinet-of-imd/commands/cabinet.md`, find the "1.5. Vault Check" section. Replace the vault discovery logic with:

```markdown
### 1.5. Vault Check (REQUIRED)

A connected vault is mandatory.

**If `obsidian-bridge` plugin is installed:** Defer to bridge's vault discovery (bridge's SessionStart hook has already run and injected vault context). Read `.obsidian-bridge` breadcrumb for vault path and project slug. Skip cabinet's own discovery chain.

**If `obsidian-bridge` is NOT installed (deprecated path):** Run the discovery chain from `vault-integration.md § "Vault Discovery"`:
```

Keep the rest of the section (the error messages and fallback behavior) unchanged.

- [ ] **Step 8: Update boot-flair.sh to read .obsidian-bridge breadcrumb**

In `cabinet-of-imd/hooks/scripts/boot-flair.sh`, after the existing `.cabinet-anchor-hint` block (line 14-23), add a prior check for `.obsidian-bridge`:

Before:
```bash
  local hint_file="$project_dir/.cabinet-anchor-hint"
```

After:
```bash
  # Prefer bridge breadcrumb, fall back to cabinet hint
  local bridge_file="$project_dir/.obsidian-bridge"
  if [ -f "$bridge_file" ]; then
    vault=$(grep -E '^vault_path=' "$bridge_file" 2>/dev/null | head -n1 | cut -d= -f2- || true)
    slug=$(grep -E '^project_slug=' "$bridge_file" 2>/dev/null | head -n1 | cut -d= -f2- || true)
  fi

  # Fall back to cabinet anchor hint
  local hint_file="$project_dir/.cabinet-anchor-hint"
```

And wrap the existing hint_file block with a condition:

```bash
  if [ -z "$vault" ] && [ -f "$hint_file" ]; then
```

- [ ] **Step 9: Verify deletions and edits**

```bash
# Verify deletions
ls cabinet-of-imd/skills/vault-bridge/ 2>/dev/null && echo "FAIL: vault-bridge skill still exists" || echo "OK: vault-bridge skill deleted"
ls cabinet-of-imd/commands/dream.md 2>/dev/null && echo "FAIL: dream command still exists" || echo "OK: dream command deleted"

# Verify version bump
grep '"version"' cabinet-of-imd/.claude-plugin/plugin.json
```

Expected: version shows `"2.3.0"`, both deletions confirmed.

- [ ] **Step 10: Commit**

```bash
git add -A cabinet-of-imd/ .claude-plugin/marketplace.json
git commit -m "refactor(cabinet-of-imd): v2.3.0 — extract vault-bridge and dream to obsidian-bridge"
```

---

### Task 19: Integration verification

Manual verification steps — no code changes, just checks.

- [ ] **Step 1: Verify complete obsidian-bridge file tree**

```bash
find obsidian-bridge -type f | sort
```

Expected output (19 files):
```
obsidian-bridge/.claude-plugin/plugin.json
obsidian-bridge/CHANGELOG.md
obsidian-bridge/LICENSE
obsidian-bridge/README.md
obsidian-bridge/commands/dream.md
obsidian-bridge/commands/vault-bridge.md
obsidian-bridge/examples/vault-templates/brief-coding.md
obsidian-bridge/examples/vault-templates/brief-knowledge.md
obsidian-bridge/examples/vault-templates/brief-plugin.md
obsidian-bridge/examples/vault-templates/brief-tinkerage.md
obsidian-bridge/examples/vault-templates/collection-index.md
obsidian-bridge/examples/vault-templates/decision.md
obsidian-bridge/examples/vault-templates/doc.md
obsidian-bridge/examples/vault-templates/handoff.md
obsidian-bridge/examples/vault-templates/home.md
obsidian-bridge/examples/vault-templates/note.md
obsidian-bridge/examples/vault-templates/projects-index.md
obsidian-bridge/examples/vault-templates/session.md
obsidian-bridge/examples/vault-templates/source.md
obsidian-bridge/hooks/hooks.json
obsidian-bridge/hooks/scripts/session-end-handoff.sh
obsidian-bridge/hooks/scripts/session-start-vault.sh
obsidian-bridge/references/obsidian-setup.md
obsidian-bridge/references/remember-integration.md
obsidian-bridge/references/vault-integration.md
obsidian-bridge/references/vault-standards.md
obsidian-bridge/skills/dream/SKILL.md
obsidian-bridge/skills/vault-bridge/SKILL.md
```

- [ ] **Step 2: Verify all JSON files parse**

```bash
python3 -m json.tool obsidian-bridge/.claude-plugin/plugin.json > /dev/null && echo "plugin.json OK"
python3 -m json.tool obsidian-bridge/hooks/hooks.json > /dev/null && echo "hooks.json OK"
python3 -m json.tool .claude-plugin/marketplace.json > /dev/null && echo "marketplace.json OK"
python3 -m json.tool cabinet-of-imd/.claude-plugin/plugin.json > /dev/null && echo "cabinet plugin.json OK"
```

- [ ] **Step 3: Verify all shell scripts pass syntax check**

```bash
bash -n obsidian-bridge/hooks/scripts/session-start-vault.sh && echo "session-start OK"
bash -n obsidian-bridge/hooks/scripts/session-end-handoff.sh && echo "session-end OK"
bash -n cabinet-of-imd/hooks/scripts/boot-flair.sh && echo "boot-flair OK"
```

- [ ] **Step 4: Verify no bridge file references cabinet-of-imd by name**

```bash
grep -rl "cabinet-of-imd" obsidian-bridge/ || echo "OK: no references to cabinet-of-imd"
```

Expected: `OK: no references to cabinet-of-imd` (one-way dependency invariant).

- [ ] **Step 5: Verify all template frontmatter has type field**

```bash
for f in obsidian-bridge/examples/vault-templates/*.md; do
  type=$(grep "^type:" "$f" | head -1)
  echo "$(basename $f): $type"
done
```

Expected: each template has a `type:` line.

- [ ] **Step 6: Verify cabinet deletions are clean**

```bash
ls cabinet-of-imd/commands/
ls cabinet-of-imd/skills/
```

Expected: `commands/` has `cabinet.md`, `create-classmate.md`, `invoke.md` (no `dream.md`). `skills/` has whatever other skills remain (no `vault-bridge/`).

- [ ] **Step 7: Run SessionStart hook dry test**

```bash
CLAUDE_PROJECT_DIR=/tmp/test-no-vault bash obsidian-bridge/hooks/scripts/session-start-vault.sh 2>/dev/null
```

Expected output contains: `Obsidian Bridge — Not Linked`

- [ ] **Step 8: Verify spec coverage — cross-reference**

Check that all 21 spec sections have corresponding implementation:

| Spec § | Implementation |
|---|---|
| §1 Overview | README.md + plugin.json |
| §2 Plugin scaffolding | Task 1 (dirs + manifests) |
| §3 Vault structure | vault-standards.md § Per-Type Defaults |
| §4 Frontmatter schemas | vault-standards.md § File Type Schemas |
| §5 Brief templates | 4 brief-*.md templates |
| §6 Naming/wikilinks/tags | vault-standards.md §§ Naming, Wikilinks, Tags |
| §7 _index.md rule | vault-standards.md § _index.md Rule |
| §8 Iterations | vault-bridge SKILL.md iteration commands |
| §9 Hooks | hooks.json + 2 scripts |
| §10 Vault primitives | vault-integration.md |
| §11 Breadcrumb | vault-integration.md § Breadcrumb |
| §12 /vault-bridge commands | vault-bridge SKILL.md (17 commands) |
| §13 /dream | dream SKILL.md (Pass 1 + Pass 2) |
| §14 Cabinet contract | Task 18 (stale flag edits) |
| §15 Remember integration | remember-integration.md + handoff commands |
| §16 Migration | vault-bridge SKILL.md migrate command |
| §17 Housekeeping | vault-bridge SKILL.md housekeeping command |
| §18 Open questions | Addressed inline (see notes below) |
| §19 Out of scope | n/a |
| §20 Testing | This task (verification steps) |
| §21 Implementation phasing | This plan |

**Open question resolutions (§18):**
- Tag normalisation: dual-tag policy — keep both `#cabinet/*` and `#ob/*` during migration, no sunset timeline.
- Session anchor: `.anchor.json` is cabinet-private, bridge never touches it. Confirmed.
- Cabinet's `crew/scrapbook/questions.md`: entirely cabinet-owned, untouched by bridge. Confirmed.
- CLI command syntax: implementor should run `obsidian --help` to verify command set before coding vault primitives.

---

*End of plan.*
