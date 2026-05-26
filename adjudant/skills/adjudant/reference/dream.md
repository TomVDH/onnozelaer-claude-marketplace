# /adjudant dream

Diagnostic crawl. **Reports drift, never auto-fixes.** Fix work is `/adjudant ramasse`.

## The 4 features (locked spec)

1. **Drift report** — frontmatter (required fields per `reference/vault-standards.md`), tags (only locked schema allowed), file naming (kebab-case, dates, doc UPPERCASE, `.canvas`/`.base` kebab), folder structure (per-`project_type` defaults + `extra_folders` declared in brief)
2. **Broken-wikilink report** — every `[[...]]` whose target doesn't resolve
3. **Doc-vs-decision mismatch flags** — `type: doc` files with date prefixes; `type: decision` files at project root; docs with append-only "log entry" feel (per the disambiguator in `reference/vault-standards.md`)
4. **Save to vault** — write the report to `{vault}/projects/{slug}/dreams/{YYYY-MM-DD}.md` using `templates/dream-report.md`. The `dreams/` folder is auto-created on first save.

## Inputs

Always current project (resolved from breadcrumb). No `--vault-wide` flag — vault-wide diagnostics need to be invoked per-project deliberately.

## Output

Stdout: the human-readable report (drift items grouped by category). Also saved to `{vault}/projects/{slug}/dreams/{YYYY-MM-DD}.md`.

If today's dream report already exists, it's overwritten (latest snapshot wins).

## Fail conditions

- No breadcrumb at cwd → exit non-zero with "run `/adjudant connect` first"
- Vault unreachable → exit non-zero

## What dream does NOT do

- No edits to vault files (read-only)
- No tag normalization (that's `ramasse`)
- No index rebuilding (that's `ramasse`)
- No CLAUDE.md drift checks beyond noting if AGENTS.md `@`-import is missing — generic CLAUDE.md content checks live in hookify
