# Integration — iteration-shelf

How this skill behaves when other plugins are active, and how it degrades cleanly when they are not.

---

## 1. Standalone skills

Several standalone user-level skills plug into the shelf generator: `full-output-enforcement`, `design-taste-frontend`, `high-end-visual-design`, `redesign-existing-projects`, `minimalist-ui`, `industrial-brutalist-ui`. They are installed separately, not part of any skill pack; any or all of them may be absent.

### 1.1 `full-output-enforcement` — mandatory

When active, every shelf generation follows it. The practical effects:

- **No placeholders in the emitted HTML.** Not `// ...rest of segments`, not `// truncated for brevity`, not `// similarly for the remaining items`. Every segment, every card, every handler attaches in full.
- **No skeleton output.** If the shelf has 130 items, the emitted file has 130 `<div class="card">` blocks. Period.
- **Token-limit handling.** If a single generation would exceed the response budget, use the split protocol:

  ```
  [PAUSED — X of Y segments emitted. Send "continue" to resume from: next segment name]
  ```

  Resume from exactly the next segment boundary. Do not recap what was already emitted.

If `full-output-enforcement` is not installed, enforce these rules anyway: they are the shelf's deliverable contract, not skill-specific.

### 1.2 `design-taste-frontend`

This skill is the designer behind the iterations. The shelf chrome **overrides** its defaults (terminal aesthetic, not premium). But the indexed iterations themselves may have been produced by `design-taste-frontend` and are not constrained.

Practical rule: do not apply this skill's tokens, motion paradigms, or structural recommendations to the shelf chrome. Apply them to new iterations in their own files.

### 1.3 `high-end-visual-design`

**Explicitly suppressed for the shelf chrome.** The shelf is intentionally terminal-flavoured — no Ethereal Glass, no Editorial Luxury, no Soft Structuralism. If the user asks for a "premium-looking shelf", ask once to confirm they understand the shelf is deliberately not that, and offer to apply the aesthetic to their iteration files instead.

### 1.4 `redesign-existing-projects`

If the target folder already has an index file (`_index.html`, `index.html`, `_iterations.html`), invoke this skill's audit-first pattern before generating a new shelf. The flow:

1. Read the existing file.
2. Identify which patterns are reusable (e.g. segment structure, useful banners).
3. Propose a diff: "keep X, replace Y with the canonical shelf chrome."
4. Generate only after user approval.

### 1.5 `minimalist-ui` / `industrial-brutalist-ui`

The industrial-brutalist skill's aesthetic is close in spirit to the shelf (mono, hairlines, utilitarian) but has different tokens. Do not blend — the shelf has its own palette and it is the source of truth for shelf output.

If the user wants an industrial-brutalist _iteration_ (inside the indexed set), that skill applies to the iteration file, not to the shelf chrome.

---

## 2. Adjudant plugin

When adjudant is active and the project is linked to a vault, adjudant is the persistence layer. The shelf skill invents no vault schema of its own: session events use adjudant's session logging, decisions use adjudant's decision schema.

### 2.1 Session log

Writing a shelf is a **session-notable event**. Adjudant keeps one session note per project per day at `projects/{slug}/sessions/{YYYY-MM-DD}.md` with an append-only `## Log` section (its SessionStart hook creates or resumes the note; its PostToolUse hook auto-logs vault-file creations; SessionEnd appends the closing marker).

Shelf files land in the project tree, not in the vault, so adjudant's PostToolUse hook never sees them. Append the event to the session note's `## Log` yourself, in its line format:

```markdown
- {HH:MM} · generated iteration shelves for `{target_folder}`: `_iterations.html` ({curated_count} items), `_monster-index.html` ({total_items} items); manifest `iteration-shelf.json` {new | updated}
```

One line per generation run. Do not log file reads or scans.

### 2.2 Decision records

Adding a **new tag slug** (beyond the nine shipped in `card-anatomy.md`) is a decision, not a cosmetic tweak. Record it with adjudant's decision schema at `projects/{slug}/decisions/{YYYY-MM-DD}-shelf-tag-{slug}.md`:

```markdown
---
type: decision
project: "[[projects/{slug}/brief|{slug}]]"
status: active
date: {YYYY-MM-DD}
tags:
  - decision
---

## Decision

Added tag slug `{slug}` to the shelf tag palette. Colour `{hex}`.

## Context

{reason the user gave, plus the written criterion for when the tag applies}

## Consequence

Both shelves gain the tag CSS:

\`\`\`css
.tag.{slug} { color: {hex}; {optional modifiers}; }
.iter__tag.{slug} { color: {hex}; {optional modifiers}; }
\`\`\`
```

Filename and frontmatter follow adjudant's `vault-standards.md`; the body sections are always `## Decision` / `## Context` / `## Consequence`.

### 2.3 Manifest provenance

The manifest (`iteration-shelf.json`) lives at the **project root**, not inside the vault. It is vault-adjacent, not vault-interior: the vault holds session notes and decisions, the project holds generated artefacts.

If the user asks "where does the manifest live?", the answer is always the project root.

### 2.4 Vault-less mode

If adjudant is not installed, or is installed but the project has no linked vault:

- Skip the session-log append (no note to write to).
- Skip decision records (same).
- Never prompt the user to set up a vault: that is adjudant's remit, not the shelf's.

### 2.5 Cabinet flavour (optional)

The Cabinet of IMD (v3.0.0+) is a character-only flavour layer: no vault writes, no chatter log, no session anchors. If it is active, Bostrol may narrate shelf generation events in chat:

```
[Bostrol]: Emitting _monster-index.html · 12 segments · 132 items.
[Bostrol]: Emitted. Cross-linked to _iterations.html. Done.
```

Narration only, and only the generation events, not every file read. Cabinet writes no files; persistence stays with adjudant.

---

## 3. Standalone mode

No standalone skills, no adjudant, no vault. The skill runs fine:

- No `[Bostrol]:` prefixes in chat.
- No session notes or decision logs written.
- Still emits both artefact types per the manifest.
- Still follows the deliverable rules (no placeholders, complete output).
- Still respects the browser-safety rules in the monster template.

Standalone is the default path. Integrations are enhancements, not prerequisites.

---

## 4. Conflict resolution

If two plugins each have an opinion on an operation the shelf is performing:

| Opinion source | Priority |
|---|---|
| User's direct instruction | 1 (always wins) |
| `iteration-shelf` skill rules (this plugin) | 2 |
| `full-output-enforcement` (standalone) | 3 (never conflicts; reinforces 2) |
| `design-taste-frontend` / aesthetic skills (standalone) | 4 (applies to iterations, not chrome) |
| Cabinet narration flavour | 5 (chat voice only; never touches files) |

In practice, conflicts are rare — the shelf owns its chrome; aesthetic skills own their iterations; the Cabinet just narrates.

---

## 5. Multi-plugin examples

### Everything active (standalone skills + adjudant vault + Cabinet flavour)

```
[Bostrol]: Reading iteration-shelf.json — project dutchbc-portal, 12 segments.
[Bostrol]: Writing _monster-index.html — full output, no placeholders.
{… generation …}
[Bostrol]: Emitted. 132 cards wired. Session note appended via adjudant; manifest updated.
```

### Standalone skills only, no adjudant

```
I'll generate both shelves from iteration-shelf.json. Following full-output-enforcement
— the output will be complete, no truncation. Generating _iterations.html first, then
_monster-index.html.

{… generation …}

Done. Wrote 23 cards to the curated shelf and 132 cards to the monster index. Both
cross-linked in their headers.
```

### Pure standalone

```
Reading iteration-shelf.json. Generating both shelves.

{… generation …}

Done — 23 curated cards, 132 monster cards, cross-linked.
```

The behavioural differences are in the narration, not the output.
