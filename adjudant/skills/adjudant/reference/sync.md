# /adjudant sync

Push current project state to the linked vault. Always runs the full pass — no sub-modes.

## The 3 features (locked spec)

1. **Brief refresh** — update `{vault}/projects/{slug}/brief.md` frontmatter (`updated:` field to today, `status:` if changed in working tree)
2. **Handoff mirror** — copy `.remember/remember.md` body into `{vault}/projects/{slug}/_handoff.md` (preserve handoff frontmatter; update `updated:` + attribution line)
3. **Index refresh** — refresh `{vault}/projects/{slug}/_index.md` entries from current sibling files

## Inputs

None. Operates on the project resolved from `.claude/adjudant` breadcrumb at cwd.

## Fail conditions

- No breadcrumb at cwd → exit non-zero with "run `/adjudant connect` first"
- Vault path in breadcrumb no longer resolves → exit non-zero
- `.remember/remember.md` missing → skip handoff step, still do brief + index, log a warning

## Idempotent behavior

Sync is overwrite-by-design for the handoff body (it mirrors `.remember`). For brief and index, only frontmatter fields and structured rows are touched — user-authored content preserved.
