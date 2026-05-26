---
description: Vault editor/writer and project initializer — connect|port|sync|check|ramasse|dream|draw
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: "[connect|port|sync|check|ramasse|dream|draw] [args]"
---

Adjudant — vault editor/writer and project initializer.

Routes to the `adjudant` skill. Available verbs:

- `/adjudant connect` — onboard project to vault (rigid 5-step init: breadcrumb, AGENTS.md+CLAUDE.md, vault scaffold, session note, .gitignore)
- `/adjudant port` — migrate a legacy project (raw / obsidian-bridge / hand-authored) to adjudant compliance (two-phase preview → apply, auto-detects flavor)
- `/adjudant sync` — push brief + handoff to vault
- `/adjudant check` — read-only project + vault summary
- `/adjudant ramasse` — reindex + housekeeping sweep
- `/adjudant dream` — diagnostic crawl (drift report, no auto-fix)
- `/adjudant draw <canvas|base|diagram> <name>` — create visual artefact

If no verb provided, list available verbs and exit.

Dispatch to the `adjudant` skill with `{verb} {args}`.
