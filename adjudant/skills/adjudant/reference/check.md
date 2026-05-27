# /adjudant check

Read-only summary. Never writes. v0.3.0 backed by `check.py` which scans the project mechanically and emits structured JSON; this skill consumes the JSON and renders the 3-section block.

## The 3 features (locked spec)

1. **Current project state** — brief summary (title, type, status), recent sessions (last by date), decisions count, handoff freshness (timestamp + delta vs now)
2. **Vault snapshot** — project counts by status, drift flags from last `/adjudant dream` run
3. **Schema compliance check** — quick frontmatter + tag conformance (full audit is `/adjudant dream`)

## Run

```bash
python3 "$(dirname "$0")/../../../scripts/check.py" \
  --project-dir "$PROJECT_ROOT" \
  --vault-dir "$VAULT_PATH" \
  --out /tmp/check-{slug}.json
```

JSON output shape (top-level keys):
- `project` — brief fields (slug, project_type, status, title, created, updated, codename)
- `counts` — non-_index .md per common folder (decisions, sessions, dreams, notes, etc.)
- `recent` — last_session, last_decision, last_dream (YYYY-MM-DD)
- `handoff` — present, updated, stale_hours
- `drift_signal` — latest dream date + drift_items count if parseable

## Render

Output a single rendered block:

```
## Project — {slug}

{title}
Type: {project_type} · Status: {status} · Codename: {codename or none}
Created: {created} · Updated: {updated}

## Activity

- Last session: {last_session}
- Last decision: {last_decision}
- Last dream:    {last_dream}
- Handoff:       {updated} ({stale_hours}h stale)
- Counts:        {decisions} decisions, {sessions} sessions, {dreams} dreams, {notes} notes

## Drift signal

{drift_signal.drift_items} items per dream {drift_signal.date}
  (or "Run /adjudant dream — no recent diagnostic" if absent)
```

Adapt phrasing to be conversational; the shape above is the data layout, not a rigid template.

## Inputs

None. Operates on the project resolved from `.claude/adjudant` breadcrumb at cwd.

## Fail conditions

- No breadcrumb at cwd → render vault-wide snapshot only (sections 2 + 3 vault-wide); skip section 1
- Vault path unreachable → exit non-zero with message

## See also

- `scripts/check.py`, `scripts/test_check.py`
- `reference/dream.md` — full diagnostic; use when `drift_signal` looks elevated
