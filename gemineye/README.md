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

**Requires:** the `gemini` CLI on `PATH`, recent enough to support
`--sandbox`. Install: <https://github.com/google-gemini/gemini-cli>

**Pairs with (optional but recommended):**
- `adjudant` — auto-loads project context from the Obsidian
  vault and routes outputs into the project's `gemineye/` subfolder.
- `cabinet-of-imd` — when active, Bostrol indexes Gemineye outputs
  as documentation artefacts.

## Subcommands

```
/gemineye review <target>              Focused review of one artefact — flash
/gemineye megareview <scope>           Broad sweep across module / feature / plugin — pro
/gemineye wip                          Review uncommitted + current branch work — flash
/gemineye sanity <topic>               Steel-man + failure modes + alternative — flash
/gemineye name <thing(s)>              Naming bikeshed — flash
/gemineye compare <A> <B> [<C>...]     Head-to-head ranking — flash
/gemineye save [topic]                 Persist last in-line review to gemineye/ folder
```

## Behaviour at a glance

| Aspect | Default |
|---|---|
| Trigger | Explicit phrases or `/gemineye` subcommand |
| Sandbox | Always (`--sandbox`). Folder is not trusted by Gemini |
| Permissions | Review-only. No `--yolo`. No write tools |
| Default model | `gemini-3.5-flash` |
| `megareview` model | `gemini-3.5-pro` |
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
