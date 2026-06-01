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
<https://antigravity.google>. The old `gemini` CLI works as a **deprecated
fallback** (Google sunsets it for AI Pro/Ultra and free users on 2026-06-18);
once you're on `agy`, a follow-up release will drop the `gemini` path.

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

`megareview` is the deepest pass; the rest are lighter. Under `agy` there's no
per-call model flag, so "tier" is about prompt scope, not a model switch.

## Behaviour at a glance

| Aspect | Default |
|---|---|
| Trigger | Explicit phrases or `/gemineye` subcommand |
| Backend | `agy` (Antigravity CLI); deprecated `gemini` fallback during transition |
| Containment | Write-sandboxed (`--sandbox`), read-trusted to the project root (`--add-dir "$ROOT"`) |
| Permissions | Review-only. Never `--dangerously-skip-permissions` / `--yolo`. No write tools |
| Model | No per-call flag under `agy` (account/config governs); legacy `gemini` pro uses `-m gemini-2.5-pro` |
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
