---
name: gemineye
description: Sandboxed second opinion from a Gemini-family model via the Antigravity CLI (`agy`). `/gemineye {review|megareview|wip|sanity|name|compare|save|harvest}` or phrases like "ask Gemini" / "second opinion". Review-only — Claude applies any proposed edits.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
version: 0.6.0
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

| Command | Scope | Tier |
|---|---|---|
| `/gemineye review <target>` | one artefact | fast |
| `/gemineye megareview <scope>` | module / feature / plugin | **pro** |
| `/gemineye wip` | uncommitted + current branch diff | fast |
| `/gemineye sanity <topic>` | idea / plan / decision | fast |
| `/gemineye name <thing(s)>` | one or many | fast |
| `/gemineye compare <A> <B> [<C>...]` | 2+ options | fast |
| `/gemineye save [topic]` | last review | — (file write) |
| `/gemineye harvest <path>` | extract 5 durable bullets from any file | fast |

**Tier maps to a pinned `--model`.** The `agy` roster mixes model families
(Gemini, Claude, GPT-OSS), so an unpinned call can silently be served by a
Claude model, which defeats the point of a cross-family second opinion.
Gemineye therefore pins Gemini models explicitly:

- fast tier (every verb except `megareview`): `--model "Gemini 3.5 Flash (Medium)"`
- pro tier (`megareview`): `--model "Gemini 3.1 Pro (High)"`

One-line override: swap the `--model` value for any other Gemini-family entry
from `agy models`. Never pin a non-Gemini model; that breaks the contract.

Natural-language triggers ("ask Gemini", "second opinion", "Gemini
take") default to `review` if a target is named, otherwise ask for
the target.

For the filled-in prompt templates per subcommand, read
`${CLAUDE_PLUGIN_ROOT}/references/invocation-patterns.md`.

---

## Core rules

1. **Write-sandboxed, read-trusted.** Every call passes `--sandbox`
   (terminal/write restrictions) and `--add-dir "$ROOT"` (read access
   to the project root only). The reviewer can read the project; it
   cannot write the host or reach outside the root.
2. **Review-only.** The CLI never writes project files. Never pass
   `--dangerously-skip-permissions`, and never grant write tools.
   Edits come back as code blocks; Claude applies.
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

## CLI backend: `agy` (Antigravity), sole backend

Gemineye drives a sandboxed CLI as its review oracle. **Antigravity CLI
(`agy`) is the only backend.** The old `gemini` CLI is gone: Google sunset
it for AI Pro/Ultra and free users on 2026-06-18, and gemineye v0.6.0
removed the fallback path entirely.

**Backend check (every invocation):**

```bash
if ! command -v agy >/dev/null 2>&1; then
  echo "gemineye: Antigravity CLI (agy) not found on PATH. There is no fallback." \
       "Install it: https://antigravity.google" >&2
  exit 1
fi
```

If `agy` is absent, stop. Don't improvise. Tell Tom.

---

## Pre-flight

Run the backend check above. Confirm the two pinned models still appear in
`agy models` output; if Google rotates names, update the pinned strings
(fast and pro) here and in `invocation-patterns.md`. Replacements must be
Gemini-family entries.

---

## Standard invocation

```bash
# Read-trusted to the project root, write-sandboxed, model pinned to the
# Gemini family. $ROOT is the project/repo root being reviewed.

# fast tier (review, wip, sanity, name, compare, harvest)
agy --sandbox --add-dir "$ROOT" --model "Gemini 3.5 Flash (Medium)" -p "$(cat prompt.txt)"

# pro tier (megareview)
agy --sandbox --add-dir "$ROOT" --model "Gemini 3.1 Pro (High)" -p "$(cat prompt.txt)"
```

**The posture: read-trusted, write-sandboxed.** `--add-dir "$ROOT"` lets the
reviewer *read* adjacent files inside the project root when a finding needs
them; `--sandbox` keeps it from writing the host fs or escaping. The prepared
bundle (see Context sourcing) stays the **primary** feed — `--add-dir` is for
pulling supporting context within the root, not a licence to crawl.

**Never pass `--dangerously-skip-permissions`**, never grant write tools,
never drop `--sandbox`, never `--add-dir` outside the project root, never
pin a non-Gemini model. The reviewer reads the building; it holds no keys.

### Folder trust

**Confirmed on macOS:** a headless `agy --sandbox --add-dir "$ROOT" -p` call
returns to stdout and can read files in the added dir **without a blocking
trust prompt** — no setup needed. `--add-dir "$ROOT"` is sufficient.

Fallback (other setups only): if a headless call ever hangs on a trust prompt,
establish trust once interactively, then headless calls work:

```bash
cd "$ROOT" && agy        # answer the trust prompt once; agy remembers it
```

> **`agy -p` stdout note:** the non-interactive `--print` mode has a reported
> stdout bug **on Windows / non-TTY** ([#27466](https://github.com/google-gemini/gemini-cli/issues/27466));
> macOS is unaffected (verified). If a call ever returns empty stdout, re-run
> interactively or read the response from agy's latest session transcript.

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

Vault destinations resolve via the adjudant breadcrumb, and the vault
`gemineye/` folder must be declared in the project brief; see "Pairing
with adjudant" below.

**Hard rule:** never write Gemini output into source folders. The
one allowed scaffold is creating `docs/gemineye/`.

### Persisted file template

```markdown
---
type: gemineye-review
date: YYYY-MM-DD
topic: <one-line topic>
target: <file or area reviewed>
subcommand: <review|megareview|wip|sanity|name|compare|harvest>
model: <fast|pro>
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

When `adjudant` is active (a `.claude/adjudant` breadcrumb exists at the
project root):

1. **Resolve:** read `vault_path` and `slug` from the breadcrumb; the
   project's vault folder is `{vault_path}/projects/{slug}/`.
2. **Read:** pull project brief, recent decisions, last session note
   into the bundle automatically.
3. **Write:** persisted reviews go to `{vault_path}/projects/{slug}/gemineye/`.
   `gemineye` is not one of adjudant's default subfolders, so on first save
   declare it in the brief's `extra_folders:` frontmatter list. Per adjudant
   vault-standards, a folder that is neither a default nor declared in
   `extra_folders` is drift that `/adjudant dream` flags.
4. **Cross-link:** append a line under the `## Log` section of today's
   session note. `## Log` is the section adjudant's session template
   actually has; do not invent a reviews section.

Standalone (no breadcrumb): persisted reviews go to `docs/gemineye/`.

---

## Failure modes

| Symptom | Likely cause | Action |
|---|---|---|
| `agy` not on PATH | Antigravity CLI not installed | Tell Tom, link Antigravity install, stop; there is no fallback |
| Pinned model missing from `agy models` | Google rotated model names | Update the pinned strings (fast + pro); replacement must be Gemini-family |
| `agy -p` prints nothing | Non-TTY stdout bug (#27466) | Re-run interactively, or read the latest agy session transcript |
| `agy -p` hangs / asks to trust folder | Folder not trusted | Run one-time `cd "$ROOT" && agy` handshake, or add root to trusted-folders config |
| `--sandbox: unknown option` | Older/odd CLI build | Tell Tom to update (`agy update`); do not run without sandbox |
| Empty / very short response | Template missing fields or context too thin | Re-run with the template fully filled |
| Response contradicts Claude | Genuine disagreement | Surface both views to Tom; do not auto-resolve |
| Response wants to scaffold | Gemini ignored the constraint | Filter in "Claude's read" |
| Edit suggestion not in code block | Format violation | Re-prompt with stricter OUTPUT spec |
| Output would land in src | Bug — stop | Never silently overwrite source paths |

---

## Dependencies

- **Antigravity CLI (`agy`) on `PATH`**: the sole review backend. Install: <https://antigravity.google>
- Optional: `adjudant` (vault context auto-loading).
