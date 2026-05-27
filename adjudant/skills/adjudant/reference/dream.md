# /adjudant dream

Diagnostic crawl. **Reports drift, never auto-fixes.** Fix work is `/adjudant tidy` (mechanical) or `/adjudant ramasse` (deep). v0.3.0 backed by `dream.py` which scans the project mechanically and emits structured JSON; this skill consumes the JSON and renders the narrative.

## The 4 features (locked spec)

1. **Drift report** — frontmatter (required fields per `reference/vault-standards.md`), tags (only locked schema allowed), file naming (kebab-case, dates, doc UPPERCASE, `.canvas`/`.base` kebab), folder structure (per-`project_type` defaults + `extra_folders` declared in brief)
2. **Broken-wikilink report** — every `[[...]]` whose target doesn't resolve
3. **Doc-vs-decision mismatch flags** — `type: doc` files with date prefixes; `type: decision` files at project root; other §3 disambiguator hits
4. **Save to vault** — write the report to `{vault}/projects/{slug}/dreams/{YYYY-MM-DD}.md` using `templates/dream-report.md`

## Run

```bash
# Scan + emit JSON
python3 "$(dirname "$0")/../../../scripts/dream.py" \
  --project-dir "$PROJECT_ROOT" \
  --vault-dir "$VAULT_PATH" \
  --out /tmp/dream-{slug}.json
```

JSON output shape (top-level keys):
- `meta` — project_dir, slug, project_type, files_scanned
- `summary` — drift_items, wikilinks_broken_pct
- `folder_drift` — list of unexpected folders
- `index_gaps` — folders missing `_index.md`
- `frontmatter_drift` — `: null` values, missing FM blocks, parse errors
- `tag_drift` — bucket_d_total_occurrences, bucket_d_by_category, bucket_b_migrations_needed
- `type_drift` — non-canonical `type:` values with counts + examples
- `naming_violations` — UPPERCASE doc, decision missing date prefix, etc.
- `wikilink_form_violations` — `[text](*.md)` to vault files (`/adjudant tidy` fixes)
- `broken_wikilinks` — total, broken_count, top_broken_targets, samples
- `doc_decision_flags` — disambiguator hits

## Render

Read the JSON. Write the narrative report file at `{vault}/projects/{slug}/dreams/{YYYY-MM-DD}.md` using `templates/dream-report.md`. Group findings by category (one `##` section per category). Lead with a headline block:

```
- N files scanned (excluding _legacy/ unless --include-legacy)
- N distinct drift items across K categories
- X.XX% broken wikilinks
```

For each section, lead with counts then examples. Don't dump the full JSON — distill. If a category has no findings, omit it.

End with a "Health verdict" paragraph: structural state + most interesting non-mechanical observation.

If today's dream report already exists, overwrite (latest snapshot wins).

## Inputs

Always current project (resolved from `.claude/adjudant` breadcrumb). No `--vault-wide` flag — vault-wide diagnostics need per-project invocation.

## Fail conditions

- No breadcrumb at cwd → exit non-zero with "run `/adjudant connect` first"
- Vault unreachable → exit non-zero
- `dream.py` exits non-zero → render the stderr message verbatim, do not invent findings

## What dream does NOT do

- No edits to vault files (read-only)
- No tag normalisation (that's `tidy`)
- No index rebuilding (that's `tidy`)
- No structural recommendations (that's `ramasse`)

## See also

- `scripts/dream.py`, `scripts/test_dream.py`
- `reference/tidy.md` — the mechanical-fix verb
- `templates/dream-report.md` — the canonical narrative shape
