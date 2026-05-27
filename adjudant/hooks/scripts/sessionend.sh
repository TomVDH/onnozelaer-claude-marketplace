#!/usr/bin/env bash
# sessionend.sh — SessionEnd hook for adjudant
# 1. Append session-ended marker to today's session log
# 2. Run handoff sync via precompact.py (same logic)
set -euo pipefail

main() {
  local project_dir="${CLAUDE_PROJECT_DIR:-}"
  [ -z "$project_dir" ] && return 0

  local breadcrumb="$project_dir/.claude/adjudant"
  [ ! -f "$breadcrumb" ] && return 0

  local vault_path slug
  # Breadcrumb format is `key: value` (YAML-ish, written by connect.py).
  vault_path=$(sed -n 's/^vault_path:[[:space:]]*//p' "$breadcrumb" 2>/dev/null | head -n1 || true)
  slug=$(sed -n 's/^slug:[[:space:]]*//p' "$breadcrumb" 2>/dev/null | head -n1 || true)

  [ -z "$vault_path" ] && return 0
  [ -z "$slug" ] && return 0

  local today ts session_file
  today=$(date +%Y-%m-%d)
  ts=$(date +%H:%M)
  session_file="$vault_path/projects/$slug/sessions/$today.md"

  if [ -f "$session_file" ]; then
    printf -- '- %s · session ended\n' "$ts" >> "$session_file"
  fi

  # Run handoff sync only — no pause marker (best effort, never block)
  if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/hooks/scripts/precompact.py" ]; then
    python3 "$CLAUDE_PLUGIN_ROOT/hooks/scripts/precompact.py" --sync-only 2>/dev/null || true
  fi
}

main "$@" || exit 0
