# /adjudant draw

Create visual artefacts in the vault. Sub-verb router for canvas / base / diagram.

## The 3 features (locked spec)

1. `/adjudant draw canvas <name>` — create or open `{vault}/projects/{slug}/canvases/{kebab-name}.canvas`. Loads `reference/content-canvas.md`.
2. `/adjudant draw base <name>` — create or open `{vault}/projects/{slug}/bases/{kebab-name}.base`. Loads `reference/content-bases.md`.
3. `/adjudant draw diagram [type]` — insert a fenced `mermaid` block into the current note. `type` optional: `flowchart | sequence | class | state | erd | gantt | mindmap | timeline | gitGraph | pie | quadrant | journey | C4`. Loads `reference/content-mermaid.md`.

## Inputs

```
/adjudant draw canvas user-flow          # creates user-flow.canvas
/adjudant draw base research-targets     # creates research-targets.base
/adjudant draw diagram flowchart         # inserts a flowchart mermaid block
/adjudant draw diagram                   # asks for type, then inserts
```

## Naming

Per `reference/vault-standards.md`: `.canvas` and `.base` files use **strict kebab-case** (`my-cool-canvas.canvas` ✓ — `MyCoolCanvas.canvas` ✗). Validator enforces.

## Fail conditions

- No breadcrumb at cwd → exit non-zero with "run `/adjudant connect` first"
- `canvases/` or `bases/` subfolder doesn't exist and project_type doesn't list it as default → declare it in the brief's `extra_folders` first, then create it
- File already exists at target path → open for editing, don't recreate

## What draw does NOT do

- No design/layout intelligence (that's the user's job)
- No content generation inside canvases or bases (only scaffolds the file)
