---
type: handoff-prompt
purpose: Paste into a Claude Code session in a real project (not the marketplace repo) to bootstrap a gemineye test
date: 2026-05-27
companion-session: onnozelaer-claude-marketplace (this repo)
---

# Handoff — gemineye test in an actual project

Paste everything below the line into the first prompt of a fresh Claude Code session in a real project (hubspot-nightly, dff2026-web, anything live). The other session is the one running the test; you (in the marketplace repo) handed off the context.

---

I'm running a cross-project test of the `gemineye` plugin from `onnozelaer-claude-marketplace`. A companion session just shipped two relevant versions:

- **adjudant v0.5.1** (commit `080aa8c`) — bare `/adjudant <verb>` now works (no `:adjudant` doubling) and there's a PreCompact Gemini-harvest hook
- **gemineye v0.3.1** (same commit) — bare `/gemineye <verb>` now works; new `/gemineye harvest <path>` verb extracts 5 durable bullets from any file using the canonical ROLE / DO / DON'T / SCOPE / OUTPUT / CONTEXT template

The companion session already verified everything works on the marketplace repo. Now we want signal from a real project.

## What you should do

1. Confirm the bare-slash works: try `/gemineye review README.md` (or any short doc in this repo). Should fire — no `unknown command: gemineye` error.

2. Run a harvest against a real artifact in this project:
   ```
   /gemineye harvest <pick-a-substantial-file>
   ```
   Good targets: the project's `brief.md` (if there's a linked vault), a long-form README, a significant doc under `docs/`, or a meaty source file. Pick what's most representative of the project's actual work.

3. Observe:
   - **Wiring**: did the slash command fire? (No namespace issue, no missing-plugin error.)
   - **Template discipline**: does the response have the rigid bullet shape, or did Gemini get verbose / sycophantic?
   - **Signal**: are the 5 bullets concrete (named files, decisions, blockers) or vague?
   - **Persistence**: did anything land on disk? Where? (Per gemineye protocol: `${VAULT}/projects/{slug}/gemineye/{YYYY-MM-DD}-{topic}.md` if vault linked, else `docs/gemineye/{YYYY-MM-DD}-{topic}.md`)

4. Report back to Tom: the command you ran, the file you targeted, the verbatim response, any anomalies. Brief — this is a smoke test, not a deep review.

## Why this matters

Two parallel validations:
- The `/gemineye <verb>` bare invocation works on a project that wasn't the one we developed the fix in
- The harvest verb produces useful output on real (non-marketplace, non-test) content

## Hard rules

- **Do NOT modify the gemineye plugin source.** This is a test, not a fix. The plugin install at `~/.claude/plugins/cache/onnozelaer-claude-marketplace/gemineye/0.3.1/` is read-only for this session.
- **Do NOT** push commits to the gemineye repo from this session.
- If you find a bug, capture it (paste of command + response + observations), tell Tom; don't try to patch from here.

## Pointers

- Plugin source on GitHub: `github.com/TomVDH/onnozelaer-claude-marketplace/tree/main/gemineye`
- Verb table + template: `gemineye/skills/gemineye/SKILL.md` + `gemineye/references/invocation-patterns.md`
- Today's reference harvest (the marketplace session): `docs/gemineye/2026-05-27-cc-session-harvest.md` in the marketplace repo (already pushed)
- Gemini CLI: `/opt/homebrew/bin/gemini` v0.41.2, sandboxed, flash by default

Begin when ready.
