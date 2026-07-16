# /adjudant sitrep

Read-only orientation briefing. Never writes. Backed by `sitrep.py`, which scans the
project mechanically and emits structured JSON; this skill consumes the JSON and
renders **four short, plain-language lines**.

`sitrep` answers "I've been away — catch me up": *where were we, what's done, where's
the vault, where do I start.* It is the ELI5 cousin of `check` (which reports schema
compliance). When in doubt about which to use: `sitrep` to re-orient a human fast,
`check` to audit vault validity.

## Run

```bash
python3 "$(dirname "$0")/../../../scripts/sitrep.py" \
  --project-dir "$PROJECT_ROOT" \
  --vault-dir "$VAULT_PATH" \
  --out /tmp/sitrep-{slug}.json
```

JSON output shape (top-level keys):
- `project` — brief fields (slug, title, project_type, status, updated)
- `vault_path` — absolute path to the resolved vault (breadcrumb hint, or a
  `Home.md` walk-up fallback in direct-path mode; null only if both fail)
- `purpose` — one-line project title/purpose
- `freshness` — `{light: 🟢/🟡/🔴/⚪, age: "3h", last_activity: ISO or null}`
- `were_doing` — timestamp of the most recent real activity (from `.remember/today-*.md`)
- `whats_done` — `{last_session, last_decision, counts, total_files}`
- `next_step` — the single NEXT action parsed from `_handoff.md` (or null)
- `open_signals` — latest dream drift signal, if any

## Render — the ELI5 briefing

> Render the JSON `cost` block as one line: `cost: ~{est_read_tokens/1000}k tokens, {files} files`.

Output **at most four labeled lines**. Plain words a newcomer understands; no schema
jargon (don't say "frontmatter", "wikilink", "drift"). Lead with the traffic-light.
One sentence per line. Concise, yet very clear.

```
{freshness.light} 🧭 Where we are — {purpose}; last touched {freshness.age} ago.
✅ What's done — {counts summarised in plain words, e.g. "12 notes, 4 decisions, 3 work sessions"}; last session {whats_done.last_session}.
📁 The vault — {vault_path} ({whats_done.total_files} files).
👉 Start here — {next_step, in plain imperative}.
```

Rules:
- If `next_step` is null: say "No next step written down — skim the last session note to pick up the thread." (name the file: `sessions/{last_session}.md`).
- If `freshness.light` is 🔴 or age is large: add a half-clause noting it's been a while.
- If `open_signals` shows pending drift: append a gentle "(housekeeping waiting: run /adjudant tidy)" — never alarm.
- Keep the whole thing scannable in five seconds. Prose over tables.

Adapt phrasing to be conversational; the shape above is the data layout, not a rigid
template.

## Inputs

None. Operates on the project resolved from the `.claude/adjudant` breadcrumb at cwd.

## Fail conditions

- No breadcrumb / project dir missing → exit non-zero with a message pointing at
  `/adjudant connect`.
- Missing `_handoff.md` → `next_step` is null; render the fallback line above.

## See also

- `scripts/sitrep.py`, `scripts/test_sitrep.py`
- `reference/check.md` — compliance-oriented sibling
- `scripts/_handoff_freshness.py` — the shared freshness primitives sitrep reuses
