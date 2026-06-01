---
name: gemineye
description: Sandboxed second opinion from a Gemini-family model via the Antigravity CLI (`agy`). `/gemineye {review|megareview|wip|sanity|name|compare|save|harvest}` or phrases like "ask Gemini" / "second opinion". Review-only — Claude applies any proposed edits.
allowed-tools: Bash, Read, Write, Edit, Glob, Grep
version: 0.5.0
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

**Tier under `agy` is informational.** The Antigravity CLI exposes **no
per-invocation model flag** — model tier is governed by your Antigravity
account/config, not by gemineye. So all subcommands use the same `agy`
invocation; `megareview` differs only in prompt scope and depth, not in a
model string. The plugin pins **no model IDs** under `agy`. (Legacy `gemini`
fallback still honours `-m gemini-2.5-pro` for `pro` — see CLI backend below.)

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
   `--dangerously-skip-permissions` (agy) or `--yolo` (gemini), and
   never grant write tools. Edits come back as code blocks; Claude applies.
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

## CLI backend — `agy` (Antigravity), with deprecated `gemini` fallback

Gemineye drives a sandboxed CLI as its review oracle. **Antigravity CLI
(`agy`) is the backend.** The old `gemini` CLI is **deprecated** — Google
sunsets it for AI Pro/Ultra and free users on **2026-06-18** (it survives
only on paid Gemini Code Assist Standard/Enterprise + API keys). gemineye
keeps a `gemini` fallback **only as a transition crutch**.

> ⚠️ **The `gemini` fallback is temporary.** Once you're on `agy`, a follow-up
> gemineye release will remove the `gemini` path entirely. Do not build new
> behaviour on it.

**Backend detection (every invocation):**

```bash
if command -v agy >/dev/null 2>&1; then
  GEMEYE_CLI=agy
elif command -v gemini >/dev/null 2>&1; then
  GEMEYE_CLI=gemini
  echo "⚠️  gemineye: using DEPRECATED 'gemini' CLI. Install Antigravity CLI" \
       "(agy) before 2026-06-18 — a future gemineye update will drop gemini." >&2
else
  echo "gemineye: no review CLI found. Install Antigravity CLI (agy): https://antigravity.google" >&2
  exit 1
fi
```

If neither is present, stop. Don't improvise. Tell Tom.

---

## Pre-flight

Run the backend-detection block above. On `agy`, no version pinning is needed
(no model flag). On the `gemini` fallback, the pro tier still uses
`-m gemini-2.5-pro` — update that one string if ever needed.

---

## Standard invocation

```bash
# Antigravity CLI (agy) — all subcommands. Read-trusted to the project root,
# write-sandboxed. $ROOT is the project/repo root being reviewed.
agy --sandbox --add-dir "$ROOT" -p "$(cat prompt.txt)"

# Deprecated gemini fallback (transition only):
#   fast tier — gemini --sandbox -p "$(cat prompt.txt)"
#   pro tier  — gemini --sandbox -m gemini-2.5-pro -p "$(cat prompt.txt)"
```

**The posture: read-trusted, write-sandboxed.** `--add-dir "$ROOT"` lets the
reviewer *read* adjacent files inside the project root when a finding needs
them; `--sandbox` keeps it from writing the host fs or escaping. The prepared
bundle (see Context sourcing) stays the **primary** feed — `--add-dir` is for
pulling supporting context within the root, not a licence to crawl.

**Never pass `--dangerously-skip-permissions`** (agy) or `--yolo` (gemini),
never grant write tools, never drop `--sandbox`, never `--add-dir` outside the
project root. The reviewer reads the building; it holds no keys.

### Folder trust (one-time per project)

A headless `agy -p` call in an **untrusted** folder can block on a trust
prompt. Establish trust once, interactively, then headless calls work:

```bash
cd "$ROOT" && agy        # answer the trust prompt once; agy remembers it
```

> **Verify on this machine** (decides whether the handshake is even needed):
> ```bash
> agy help                                              # look for a trust/settings subcommand
> echo | agy --sandbox --add-dir "$PWD" -p "name one file you can see here"
> ```
> If it prints a filename, `--add-dir` is enough. If it hangs / asks to trust
> the folder, run the one-time handshake above (or add the root to agy's
> trusted-folders config).

> **`agy -p` stdout note:** the non-interactive `--print` mode has a reported
> non-TTY stdout bug ([#27466](https://github.com/google-gemini/gemini-cli/issues/27466)).
> If a call returns empty stdout, re-run interactively or read the response
> from agy's latest session transcript.

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

When `adjudant` is active:

1. **Read** — pull project brief, recent decisions, last session note
   into the bundle automatically.
2. **Write** — persisted reviews go to `${VAULT}/projects/{slug}/gemineye/`.
3. **Cross-link** — append a line under `## Gemini reviews` in the
   current session note.

Standalone (no vault): persisted reviews go to `docs/gemineye/`.

---

## Failure modes

| Symptom | Likely cause | Action |
|---|---|---|
| Neither `agy` nor `gemini` on PATH | No review CLI installed | Tell Tom, link Antigravity install, stop |
| Using `gemini` fallback | `agy` not installed | Works, but warn: gemini is deprecated (sunset 2026-06-18); install `agy` |
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

- **Antigravity CLI (`agy`) on `PATH`** — the review backend. Install: <https://antigravity.google>
- Deprecated fallback: `gemini` CLI (transition only; sunset 2026-06-18).
- Optional: `adjudant` (vault context auto-loading).
