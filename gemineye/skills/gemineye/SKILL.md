---
name: gemineye
description: >
  A sandboxed second opinion from Gemini. Use for the /gemineye
  subcommands (review, megareview, wip, sanity, name, compare, save) or
  phrases like "ask Gemini", "second opinion", "Gemini's take". Gemini
  reviews only — it never writes files; it proposes edits as code blocks
  and Claude applies them.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
version: 0.3.0
user-invocable: true
argument-hint: "[review|megareview|wip|sanity|name|compare|save|harvest] [args]"
---

# Gemineye

Gemini as a sandboxed review partner — invoked deliberately, fed
structured prompts, contained to a tiny writable footprint.

**Mental model:** Claude is the architect. Gemini is the visiting
reviewer — sandboxed, read-only, no keys to the building. Reviewer
reads what's prepared, writes notes, leaves. No drawings on the walls.

---

## Subcommands

| Command | Scope | Model |
|---|---|---|
| `/gemineye review <target>` | one artefact | flash |
| `/gemineye megareview <scope>` | module / feature / plugin | **pro** |
| `/gemineye wip` | uncommitted + current branch diff | flash |
| `/gemineye sanity <topic>` | idea / plan / decision | flash |
| `/gemineye name <thing(s)>` | one or many | flash |
| `/gemineye compare <A> <B> [<C>...]` | 2+ options | flash |
| `/gemineye save [topic]` | last review | — (file write) |
| `/gemineye harvest <path>` | extract 5 durable bullets from any file | flash |

Models: `gemini-3.5-flash` is default. Only `megareview` switches to
`gemini-3.5-pro` — it's the one mode that needs the deeper pass.

Natural-language triggers ("ask Gemini", "second opinion", "Gemini
take") default to `review` if a target is named, otherwise ask for
the target.

For the filled-in prompt templates per subcommand, read
`${CLAUDE_PLUGIN_ROOT}/references/invocation-patterns.md`.

---

## Core rules

1. **Sandboxed.** Every Gemini call passes `--sandbox`. The folder
   is not trusted yet. Gemini cannot run tools outside the sandbox.
2. **Review-only.** Gemini never writes project files. Never call it
   with `--yolo` or write-permission flags.
3. **Edits as code blocks.** When Gemini proposes a change, the
   change appears in an elaborate code block (file, language, before
   / after, full surrounding context). Claude reviews and applies.
4. **The Template is mandatory.** Every prompt is wrapped in
   ROLE / DO / DON'T / SCOPE — IN / SCOPE — OUT / OUTPUT / CONTEXT.
   No loose prose prompts. Ever.
5. **Context-disciplined.** Bundle is prepared, not crawled. Focused
   500-token bundle outperforms 5,000-token dump nine times of ten.
6. **Outputs are contained.** Persisted reviews go to `gemineye/`
   subfolders only. Never source paths.

---

## The Prompt Template

```
ROLE
<one-line statement of what Gemini is for this pass>

DO
- <specific behaviours>

DON'T
- <specific behaviours forbidden>

SCOPE — IN
- <what's being reviewed>

SCOPE — OUT
- <what to ignore even if visible>

OUTPUT
<required shape — bullets, severity tags, ranking, edit-blocks, etc.>

CONTEXT
<excerpts / files / briefs Claude has prepared>
```

Sections in order. Headers in caps. Hyphens for bullets. No softening
language. Each subcommand has DO / DON'T / SCOPE / OUTPUT pre-filled
in `invocation-patterns.md`. Claude assembles CONTEXT.

The rigidity is the point. Loose prompts produce loose reviews.

---

## Pre-flight

```bash
command -v gemini >/dev/null 2>&1 || {
  echo "gemini CLI not found. Install: https://github.com/google-gemini/gemini-cli"
  exit 1
}
```

If missing, stop. Don't fall back. Tell Tom.

---

## Standard invocation

```bash
# Default (review, wip, sanity, name, compare)
gemini --sandbox -m gemini-3.5-flash -p "$(cat prompt.txt)"

# Megareview only
gemini --sandbox -m gemini-3.5-pro   -p "$(cat prompt.txt)"
```

Never pass `--yolo`, never grant write tools, never drop `--sandbox`.

---

## Context sourcing

Source in order:

1. **Claude-prepared context** — anything Claude just generated or
   discussed. Primary feed.
2. **Project Markdown** — `docs/`, `README.md`, `CHANGELOG.md`,
   architecture notes. Pass relevant excerpts only.
3. **Vault context** (if `adjudant` active) — read from
   `${VAULT}/projects/{slug}/`: `brief.md`, `decisions/`, `sessions/`,
   `references/`, `gemineye/` (prior reviews).
4. **Source code** — only when Tom names files or the review target
   *is* the source. No codebase crawls.
5. **Cross-project** — `${VAULT}/gemineye/` if it exists at vault
   root, for recurring critique patterns Tom has agreed with.

---

## Output protocol

| Mode | Destination |
|------|-------------|
| In-line review | Conversation only |
| Persisted, vault available | `${VAULT}/projects/{slug}/gemineye/{YYYY-MM-DD}-{topic}.md` |
| Persisted, no vault | `docs/gemineye/{YYYY-MM-DD}-{topic}.md` |
| Cross-project pattern | `${VAULT}/gemineye/{topic}.md` (Tom's request only) |

`/gemineye save` is the explicit persist trigger. In-line stays
in-line until that command runs.

**Hard rule:** never write Gemini output into source folders. The
one allowed scaffold is creating `docs/gemineye/`.

### Persisted file template

```markdown
---
type: gemineye-review
date: YYYY-MM-DD
topic: <one-line topic>
target: <file or area reviewed>
subcommand: <review|megareview|wip|sanity|name|compare>
model: <gemini-3.5-flash|gemini-3.5-pro>
---

# Gemini review — <topic>

## Prompt
<full filled-in template, including CONTEXT>

## Response
<Gemini's response, lightly cleaned of preamble>

## Claude's read
<one paragraph: what to act on, what to discard, open questions>
```

"Claude's read" is required. Never persist a raw Gemini response
without Claude's filter on it.

---

## What Gemineye is NOT

- Not a code generator. Gemini's output never lands in source files
  without Claude reviewing and applying.
- Not a project scaffolder. Only `docs/gemineye/` is allowed.
- Not a replacement for Claude. Disagreements surface to Tom; not
  silently resolved.
- Not autonomous. Every call is initiated by Tom's request.

---

## Override clauses

Default containment relaxes only when Tom explicitly says so:

| Phrase | What it allows |
|---|---|
| "let Gemini scaffold X" | Output may create files inside `X` (Claude still routes) |
| "Gemini full project review" | Read across the codebase, not just prepared context |
| "have Gemini write the X file" | One source file may be written from Gemini's response (Claude reviews first) |
| "skip the gemineye folder, just paste it" | In-line only, no persistence |
| "drop the sandbox" | Run without `--sandbox` (asks for confirmation each time) |

Log overrides in the persisted file's frontmatter (`override: <phrase>`).

---

## Pairing with adjudant

When `adjudant` is active:

1. **Read** — pull project brief, recent decisions, last session note
   into the bundle automatically.
2. **Write** — persisted reviews go to `${VAULT}/projects/{slug}/gemineye/`.
3. **Cross-link** — append a line under `## Gemini reviews` in the
   current session note.
4. **Bostrol** — if `cabinet-of-imd` is also active, treat persisted
   reviews as documentation artefacts under Bostrol's indexing.

Standalone (no vault): persisted reviews go to `docs/gemineye/`.

---

## Failure modes

| Symptom | Likely cause | Action |
|---|---|---|
| `gemini: command not found` | CLI not installed | Tell Tom, link install docs, stop |
| `--sandbox: unknown option` | Older CLI version | Tell Tom to upgrade; do not run without sandbox |
| Empty / very short response | Template missing fields or context too thin | Re-run with the template fully filled |
| Response contradicts Claude | Genuine disagreement | Surface both views to Tom; do not auto-resolve |
| Response wants to scaffold | Gemini ignored the constraint | Filter in "Claude's read" |
| Edit suggestion not in code block | Format violation | Re-prompt with stricter OUTPUT spec |
| Output would land in src | Bug — stop | Never silently overwrite source paths |

---

## Dependencies

- `gemini` CLI on `PATH`, recent enough to support `--sandbox`.
- Optional: `adjudant` (vault context auto-loading).
- Optional: `cabinet-of-imd` (Bostrol-mediated indexing).
