# /adjudant connect

Onboard project to vault. **One rigid path — no flags, no branching, idempotent.**

## The 5 features (locked spec)

1. **Breadcrumb** — write `.claude/adjudant` at project root containing `vault_path`, `vault_name`, `slug`, `mode`
2. **Context files** — provision `AGENTS.md` + `CLAUDE.md` at project root from `templates/AGENTS.md` and `templates/CLAUDE.md` (skip if files exist)
3. **Vault scaffold** — create `{vault}/projects/{slug}/` with `brief.md` (from `templates/project-brief-{project_type}.md`), per-`project_type` default subfolders, `_index.md` per subfolder
4. **Session note** — create today's `{vault}/projects/{slug}/sessions/{YYYY-MM-DD}.md` from `templates/session.md` with frontmatter filled in
5. **Gitignore** — append `.claude/adjudant` to project `.gitignore` (create file if missing)

Also: append project row to `{vault}/projects/_index.md`.

## Inputs

`/adjudant connect` takes no arguments. Resolves everything from environment:

| Need | Resolution order |
|---|---|
| Vault path | `OB_VAULT` env var → existing breadcrumb → walk parent dirs for `Home.md` with `type: vault-home` → prompt once |
| Project slug | existing breadcrumb → cwd basename (enforce kebab-case) |
| `project_type` | existing brief → prompt once (`coding | knowledge | plugin | tinkerage`) |
| Project display name | prompt once if creating new |

## Idempotent behavior

Re-running on an already-connected project fills gaps; never overwrites user content.

- Existing `AGENTS.md` / `CLAUDE.md` untouched
- Existing `brief.md` untouched
- Missing subfolders created; existing untouched
- Today's session note: if exists, no-op (the SessionStart hook handles append-on-resume separately)
- `projects/_index.md` row: updated in place, not duplicated

## Fail conditions

- Vault path can't be resolved AND user declines to provide one → exit non-zero with message
- `project_type` not provided and not promptable → exit non-zero
- Slug contains invalid characters (spaces, dots, uppercase) → exit non-zero with rename suggestion

## Per-`project_type` default subfolders

Per `reference/vault-standards.md` (single source of truth). Summary:

| project_type | default subfolders |
|---|---|
| `coding` | `decisions/`, `notes/`, `tasks/`, `references/`, `sessions/`, `images/` |
| `plugin` | coding + `releases/` |
| `knowledge` | `notes/`, `sources/`, `references/`, `sessions/` |
| `tinkerage` | `sessions/` (optional) |

Folders beyond defaults require declaration in brief's `extra_folders: []` frontmatter field.
