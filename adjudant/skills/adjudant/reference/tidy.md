# /adjudant tidy

Mechanical vault sweep. Idempotent — second run with no fresh drift = no changes. **Two-phase preview → apply** (mirrors `/adjudant port`).

## When to run

- Routine — daily/weekly cadence, opposite of `ramasse` (heavy, deliberate)
- Before a `/adjudant sync` if drift has accumulated
- After `/adjudant dream` flags fixable items
- After importing/merging vault content

## The 4 features (locked spec)

1. **Rebuild `_index.md`** in every project subfolder with ≥2 same-type siblings. Chronological reverse-sort for date-prefixed filenames, alphabetical otherwise. Skip `sessions/`, `images/`, `assets/`, `previews/`, `iterations/`, `_archive/`.
2. **Bump `updated:` frontmatter** on touched files where applicable (`doc`, `project`, `note` types). Never adds the field if absent.
3. **Normalise tags** per the locked 2026-05-25 schema in `reference/vault-standards.md` §2 — drop Bucket D (`#ob/*`, vague topicals, project-slug self-tags, crew names, `type/*` tags), migrate Bucket B (`cabinet/decision` → `decision`, etc.). Leave Bucket A + Bucket C untouched.
4. **Fix wikilink form** — rewrite `[text](path.md)` to `[[stem|text]]` IFF `path` resolves to a vault `.md`. Leave external links + non-vault paths alone.

## Run

```bash
# Phase 1 — preview (writes .adjudant-tidy-preview/, never touches live files)
python3 "$(dirname "$0")/../../../scripts/tidy.py" preview \
  --project-dir "$PROJECT_ROOT" \
  --vault-dir "$VAULT_PATH"

# Review the preview
# - .adjudant-tidy-preview/summary.md            human-readable diff
# - .adjudant-tidy-preview/changes.json          structured change list
# - .adjudant-tidy-preview/files/<rel_path>      proposed file contents

# Phase 2 — apply (creates .adjudant-tidy-backup/{timestamp}/, then writes live)
python3 "$(dirname "$0")/../../../scripts/tidy.py" apply --project-dir "$PROJECT_ROOT"

# Or: detect what state we're in without touching anything
python3 "$(dirname "$0")/../../../scripts/tidy.py" detect --project-dir "$PROJECT_ROOT"
# → 'fresh' | 'preview' | 'applied'
```

## Apply: what happens

- Backup live files to `.adjudant-tidy-backup/{ISO-8601-Z-timestamp}/<rel_path>.legacy`
- Copy `.adjudant-tidy-preview/files/<rel_path>` to live position
- Delete `.adjudant-tidy-preview/`

## Fail conditions

| Condition | Action |
|---|---|
| Preview already exists | Error — review or delete first |
| Apply with no preview | Error — run preview first |
| Vault unresolvable | Wikilink-form fix is skipped (other features still apply) |
| Preview `changes.json` missing | Error — preview corrupt, delete and re-run |

## Scope

Default: current project resolved via `.claude/adjudant` breadcrumb (auto-followed by `tidy.py`). Vault-wide variant is **not yet implemented** — invoke per-project for now.

## What tidy does NOT do

- No deep restructure (that's `ramasse`)
- No content edits to existing wikilinks targets (only the form `[text](path.md)` rewrite)
- No new file creation beyond `_index.md` regenerations
- No deletion (only modification + index rebuild)

## See also

- `reference/dream.md` — content/knowledge/memory refresh (semantic tier); dream may spin fixable mechanical items back to tidy
- `reference/ramasse.md` — heavy planning verb
- `scripts/tidy.py`, `scripts/test_tidy.py`
- `docs/superpowers/2026-05-26-adjudant-tidy-ramasse-log.design.md`
