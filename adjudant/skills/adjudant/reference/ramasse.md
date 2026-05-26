# /adjudant ramasse

Tidy the vault — full sweep, always. No sub-modes, no `--dry-run`.

*Ramasse* (French): pick up, gather, tidy.

## The 4 features (locked spec)

1. **Rebuild `_index.md`** — walk every folder under the project that holds ≥2 sibling files of the same conceptual type; rewrite its `_index.md` Entries section (chronological where dates are in filenames, alphabetical otherwise). Skip exception folders: `sessions/`, `images/`, `assets/`, `previews/`.
2. **`updated:` field bump** — for files touched in this run, update the `updated:` frontmatter field where applicable (doc, project brief, note types).
3. **Normalize tags** — strip deprecated tags per locked schema. Rename Bucket B tags (`cabinet/recon` → `recon-item`, `cabinet/portal-concept` → `portal-concept`, `cabinet/preview` → `preview`, `cabinet/asset-index` → `index`, `cabinet/dev-doc` → `doc`). Drop Bucket C/D tags (`ob/*`, project-slug tags, vague topicals, crew names).
4. **Fix wikilink form violations** — within vault files, rewrite markdown-style links `[text](path)` to `[[wikilink|text]]` IFF the target path resolves to a `.md` file inside the vault. Leave external/code links and heading anchors alone.

## Inputs

By default operates on the current project (resolved from breadcrumb). To run vault-wide, pass `--vault`:

```
/adjudant ramasse              # current project
/adjudant ramasse --vault      # all projects
```

## Idempotent behavior

Running twice in a row should produce zero further changes. The first run is the migration; the second is the no-op confirmation.

## Fail conditions

- No vault resolvable → exit non-zero
- A file's frontmatter is unparseable YAML → skip that file, log warning, continue
