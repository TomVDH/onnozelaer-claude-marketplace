---
description: Vault editor/writer and project initializer — connect|port|sync|check|tidy|ramasse|draw
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
argument-hint: "[connect|port|sync|check|tidy|ramasse|draw] [args]"
---

Adjudant — vault editor/writer and project initializer.

Routes to the `adjudant` skill. Available verbs:

- `/adjudant connect` — onboard project to vault (rigid 5-step init: breadcrumb, AGENTS.md+CLAUDE.md, vault scaffold, session note, .gitignore)
- `/adjudant port` — migrate a legacy project (raw / obsidian-bridge / hand-authored) to adjudant compliance (two-phase preview → apply, auto-detects flavor)
- `/adjudant sync` — push brief + handoff to vault
- `/adjudant check` — read-only project + vault summary
- `/adjudant tidy` — surface mechanical sweep (rebuild indexes, normalise tags, fix wikilink form); routine cadence; two-phase preview → apply
- `/adjudant ramasse` — deep structural clean (folder shape, schema, file types, naming); sparing cadence; superpowers-driven planning
- `/adjudant draw <canvas|base|diagram> <name>` — create visual artefact

NOTE: `/adjudant dream` was a v0.3.0 verb; renamed in v0.3.1 to clarify the model. The structural drift detector now feeds ramasse. The dream name is reserved for the future content/knowledge/memory refresh verb (v0.4+).

If no verb provided, list available verbs and exit.

Dispatch to the `adjudant` skill with `{verb} {args}`.
