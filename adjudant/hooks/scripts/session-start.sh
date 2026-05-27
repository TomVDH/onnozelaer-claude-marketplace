#!/usr/bin/env bash
# session-start.sh — SessionStart hook for adjudant
# 1. Discover vault from .claude/adjudant breadcrumb
# 2. Detect AGENTS.md + CLAUDE.md presence, warn if missing
# 3. Create or resume today's session note
set -euo pipefail

main() {
  local project_dir="${CLAUDE_PROJECT_DIR:-}"
  [ -z "$project_dir" ] && return 0

  # --- 1. Read breadcrumb ---
  local breadcrumb="$project_dir/.claude/adjudant"
  [ ! -f "$breadcrumb" ] && return 0

  local vault_path slug
  # Breadcrumb format is `key: value` (YAML-ish, written by connect.py).
  vault_path=$(sed -n 's/^vault_path:[[:space:]]*//p' "$breadcrumb" 2>/dev/null | head -n1 || true)
  slug=$(sed -n 's/^slug:[[:space:]]*//p' "$breadcrumb" 2>/dev/null | head -n1 || true)

  [ -z "$vault_path" ] && return 0
  [ -z "$slug" ] && return 0
  [ ! -d "$vault_path" ] && return 0

  # --- 2. Inject context block ---
  printf '## Adjudant\n\n'
  printf -- '- Vault: `%s` (linked to project `%s`)\n' "$(basename "$vault_path")" "$slug"

  # AGENTS.md + CLAUDE.md detection
  local has_agents=0 has_claude=0
  [ -f "$project_dir/AGENTS.md" ] && has_agents=1
  [ -f "$project_dir/CLAUDE.md" ] && has_claude=1

  if [ "$has_agents" = "1" ] && [ "$has_claude" = "1" ]; then
    printf -- '- Project context: AGENTS.md (canonical) + CLAUDE.md (Claude-only overrides). **Write context to AGENTS.md.**\n'
  elif [ "$has_agents" = "1" ]; then
    printf -- '- Project context: AGENTS.md present. CLAUDE.md absent (fine if no Claude-specific overrides yet).\n'
  elif [ "$has_claude" = "1" ]; then
    printf -- '- ⚠️ CLAUDE.md present but AGENTS.md missing — run `/adjudant connect` to provision AGENTS.md.\n'
  else
    printf -- '- ⚠️ Neither AGENTS.md nor CLAUDE.md found — run `/adjudant connect` to provision both.\n'
  fi

  # --- 3. Session note: create or resume ---
  local today ts session_dir session_file
  today=$(date +%Y-%m-%d)
  ts=$(date +%H:%M)
  session_dir="$vault_path/projects/$slug/sessions"
  session_file="$session_dir/$today.md"

  mkdir -p "$session_dir" 2>/dev/null || true

  if [ ! -f "$session_file" ]; then
    cat > "$session_file" <<EOF
---
type: session
project: "[[projects/$slug/brief|$slug]]"
date: $today
started: $ts
tags:
  - session
---

> {One-line intent. Frozen after first write.}

## Log

- $ts · session started
EOF
    printf -- '- Session note created: `projects/%s/sessions/%s.md`\n' "$slug" "$today"
  else
    {
      printf '\n--- %s session resumed ---\n\n' "$ts"
    } >> "$session_file"
    printf -- '- Session note resumed: `projects/%s/sessions/%s.md`\n' "$slug" "$today"
  fi
}

main "$@" || exit 0
