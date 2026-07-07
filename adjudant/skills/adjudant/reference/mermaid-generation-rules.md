# Mermaid generation rules

Discipline for **producing** new mermaid diagrams (companion to
`content-mermaid.md`, which covers syntax). Eight rule groups. Apply all of
them every time a fence is generated — by hand or via `graph.py`.

## 1. Topology

- **One terminal per path.** Don't funnel more than 2 branches into a single
  `End` node — split terminals or drop them.
- **Pure DAGs only** for flowcharts. A cycle means the wrong diagram type —
  use `stateDiagram-v2` for anything that loops.
- **Mirror parallel branches**: if `A` splits into three lanes, the lanes
  should re-merge (or terminate) at the same depth, not straggle.
- **No hub nodes**: a node with more than 5 edges is a smell — group its
  spokes into a subgraph or split the diagram.
- **Subgraphs express ownership, not layout.** Never add a subgraph just to
  force positioning; Dagre will fight you.

## 2. Label parser safety

- **Quote every label**: `A["Label"]` — always, even when it looks safe.
  Colons, parens, `<`, `>`, `#`, and `"` inside unquoted labels break parsing.
- **No markdown-list prefixes** (`- `, `* `, `1. `) inside labels.
- **`<br>` not `<br/>`** for explicit line breaks — the XHTML self-closing
  form is unreliable across mermaid versions.
- **Escape `<`, `>`, `&`** in labels as `&lt;`, `&gt;`, `&amp;` when the
  literal characters are needed.

## 3. Label visual cleanliness

- **Uniform width**: keep labels in a diagram within ~2× of each other's
  length; pad meaning into a note below the diagram, not into one huge node.
- **Two-line max** per label (`<br>` once, never twice).
- **Terse edge labels**: 1–3 words. A sentence on an edge means the diagram
  is doing prose's job.

## 4. Direction heuristics

| Shape of the content | Use |
|---|---|
| Sequential process, < 8 steps | `flowchart LR` |
| Deep hierarchy / decision tree | `flowchart TD` |
| Anything with retry/loop semantics | `stateDiagram-v2` |
| Actor-to-actor message passing | `sequenceDiagram` |
| Point-in-time composition | `flowchart` with subgraphs |

## 5. Styling

- **One `classDef` per role** (not per node): stamp roles at generation time
  (`class n1,n4 decision`). `graph.py` does this automatically.
- **Palette ≤ 6 colours** per diagram; prefer role-consistent hues across the
  vault (decisions green, docs blue, notes amber).
- Never inline-style individual nodes (`style n1 fill:...`) — that's classDef's
  job and it drifts.

## 6. Renderer config

- Prefer **front-matter config** (` ```mermaid` then `---\nconfig: ...\n---`)
  over `%%{init: ...}%%` directives when a per-diagram override is truly
  needed. Usually leave theme alone — Obsidian follows the app theme.
- Default **Dagre layout**; don't reach for ELK/experimental layouts inside a
  vault — they don't render on older Obsidian versions.

## 7. Anti-patterns — refuse to emit

- A single `End` node with more than 2 inbound edges.
- A hub node with more than 5 edges.
- More than ~30 nodes in one fence (split by theme, or use a Canvas — see
  `content-canvas.md`).
- A flowchart that encodes a loop with a back-edge.
- Unquoted labels of any kind.

## 8. Validation before write

- **Pre-flight parse**: read the fence back top-to-bottom — first line is a
  valid diagram-type keyword, every bracket pairs, every quote closes.
- **Anti-pattern check** against §7.
- For generated diagrams, prefer `graph.py` (relations / board / tiers) over
  hand-drawing — it applies §2 label quoting and §5 role classDefs
  mechanically and caps node count. It does NOT check topology: review the
  emitted fence against §1/§7 (cycles, hub nodes) before pasting — a vault
  where notes link each other both ways WILL produce back-edges.
