# Gemineye

Invoke Gemini as a **sandboxed review partner** from inside Claude Code.

Gemineye gives Claude a controlled way to consult Gemini for second
opinions, focused reviews, and reasoning checks — without letting
Gemini sprawl across the project. Context goes in deliberately.
Every prompt follows a rigid template. Gemini reviews only — Claude
applies any edits.

## Install

Ships as part of the `onnozelaer-claude-marketplace`. Once installed,
the `gemineye` skill activates on the `/gemineye` command, its
subcommands, or natural-language phrases ("ask Gemini", "second
opinion", "Gemini review").

**Requires:** the **Antigravity CLI (`agy`)** on `PATH`. Install:
<https://antigravity.google>. There is no fallback backend: the old `gemini`
CLI was sunset for AI Pro/Ultra and free users on 2026-06-18, and v0.6.0
removed its code path.

**Pairs with (optional but recommended):**
- `adjudant` — auto-loads project context from the Obsidian
  vault and routes outputs into the project's `gemineye/` subfolder.

## Subcommands

```
/gemineye review <target>              Focused review of one artefact
/gemineye megareview <scope>           Broad sweep across module / feature / plugin (deepest)
/gemineye wip                          Review uncommitted + current branch work
/gemineye sanity <topic>               Steel-man + failure modes + alternative
/gemineye name <thing(s)>              Naming bikeshed
/gemineye compare <A> <B> [<C>...]     Head-to-head ranking
/gemineye save [topic]                 Persist last in-line review to gemineye/ folder
/gemineye harvest <path>               Extract 5 durable bullets from any file
```

`megareview` is the deepest pass; the rest are lighter. Tiers map to pinned
Gemini models: fast verbs run `--model "Gemini 3.5 Flash (Medium)"`,
`megareview` runs `--model "Gemini 3.1 Pro (High)"`. The pin matters because
the `agy` roster also serves Claude and GPT-OSS models; an unpinned call can
silently land on a Claude model, which defeats a cross-family second opinion.
To use another Gemini model for one call, swap the `--model` value for any
Gemini-family entry from `agy models`.

## Behaviour at a glance

| Aspect | Default |
|---|---|
| Trigger | Explicit phrases or `/gemineye` subcommand |
| Backend | `agy` (Antigravity CLI), sole backend; no fallback |
| Containment | Write-sandboxed (`--sandbox`), read-trusted to the project root (`--add-dir "$ROOT"`) |
| Permissions | Review-only. Never `--dangerously-skip-permissions`. No write tools |
| Model | Pinned: `Gemini 3.5 Flash (Medium)` for fast verbs, `Gemini 3.1 Pro (High)` for `megareview`; override per call with any Gemini entry from `agy models` |
| Prompt shape | Rigid ROLE / DO / DON'T / SCOPE / OUTPUT / CONTEXT |
| Edits | Returned as elaborate code blocks; Claude applies |
| Context | Claude-prepared bundle, project Markdown, vault if available |
| Source-code reads | Only when explicitly named or *is* the target |
| Output destination | `docs/gemineye/` or `${VAULT}/projects/{slug}/gemineye/` |
| Persistence | In-line by default; `save` for explicit persist |

## What it is not

- Not an autonomous agent — every call is initiated in response to a Tom request.
- Not a code generator — Gemini's output never lands in source files
  without Claude's review and Tom's approval.
- Not a project scaffolder — the one allowed scaffold is `docs/gemineye/`.

See `skills/gemineye/SKILL.md` for full operating protocol and
`references/invocation-patterns.md` for filled-in templates per
subcommand.

## Author

Onnozelaer
