# /adjudant dream — RESERVED (v0.4+)

This verb is **not yet implemented**. The name is reserved for the future content/knowledge/memory refresh verb.

## Why it's reserved, not deleted

The 2026-05-26 design lock defines three cleanup tiers:

```
tidy    = surface mechanical    (routine, daily/weekly)
ramasse = deep structural clean (sparing, quarterly)
dream   = content/knowledge/memory refresh (semantic, v0.4+)
```

Dream operates on the **content layer**, not the schema layer:
- Read the actual prose of decisions, notes, sessions
- Identify outdated info, contradictions between decisions, stale references
- Detect redundancy (multiple notes saying the same thing)
- Surface orphan threads (open questions from old sessions never resolved)
- Clean up semantically — mark decisions as superseded, consolidate duplicates, archive stale sessions

This is **LLM-judgment heavy**. The eventual `dream.py` will scan content and emit structured comparators ("decision A line 42 conflicts with decision B line 18"); Claude reads the data + judges semantically + writes the refresh plan.

## What dream is NOT

- **Not** structural drift detection (that's `ramasse_scan.py`, feeding `/adjudant ramasse`)
- **Not** schema conformance checking (that's part of `/adjudant ramasse`)
- **Not** mechanical fixes (that's `/adjudant tidy`)

## v0.3.0 → v0.3.1 history

In v0.3.0, a verb called `dream` shipped that did structural drift detection. The 2026-05-26 design lock clarified that this work belongs to `ramasse`, not `dream`. The Python file was renamed `dream.py` → `ramasse_scan.py` in v0.3.1; the `/adjudant dream` verb was removed from the surface to free the name for the proper semantic dream.

## When you invoke `/adjudant dream` today

Tell the user: "Dream is reserved for v0.4+ (content/knowledge/memory refresh). For structural drift detection, use `/adjudant ramasse` — it consumes `ramasse_scan.py` for its analysis phase."

## See also

- `reference/ramasse.md` — the deep structural verb
- `reference/tidy.md` — the surface mechanical verb
- `scripts/ramasse_scan.py` — the structural drift detector (formerly `dream.py`)
- `docs/superpowers/2026-05-26-adjudant-tidy-ramasse-log.design.md` — design lock
