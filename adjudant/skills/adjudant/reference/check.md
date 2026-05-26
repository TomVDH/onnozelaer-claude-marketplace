# /adjudant check

Read-only summary. Never writes.

## The 3 features (locked spec)

1. **Current project state** — brief summary (title, type, status), recent sessions (last 5 by date), decisions count, handoff freshness (timestamp + delta vs `.remember/remember.md`)
2. **Vault snapshot** — project count by status, drift flags from last `/adjudant dream` run
3. **Schema compliance check** — quick frontmatter + tag conformance read across the linked project's files (full audit is `/adjudant dream`'s job)

## Inputs

None. Operates on the project resolved from `.claude/adjudant` breadcrumb at cwd.

## Output shape

Single rendered block with three sections in the order above. No flags to enable/disable sections — always shows all three.

## Fail conditions

- No breadcrumb at cwd → render vault-wide snapshot only (sections 2 + 3 vault-wide)
- Vault path unreachable → exit non-zero with message
