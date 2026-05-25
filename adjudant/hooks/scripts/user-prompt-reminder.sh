#!/usr/bin/env bash
# user-prompt-reminder.sh — UserPromptSubmit hook for adjudant
# Smart-fire vault reminder when project isn't vault-linked AND prompt mentions vault-y keywords.
# Suppression: ADJUDANT_REMINDER_DISABLE=1 turns it off entirely.
set -euo pipefail

main() {
  [ "${ADJUDANT_REMINDER_DISABLE:-0}" = "1" ] && return 0

  local project_dir="${CLAUDE_PROJECT_DIR:-}"
  [ -z "$project_dir" ] && return 0

  # Already linked → silent exit
  [ -f "$project_dir/.claude/adjudant" ] && return 0

  # Read prompt from stdin JSON
  local input prompt=""
  input=$(cat 2>/dev/null || true)
  [ -z "$input" ] && return 0

  if command -v python3 >/dev/null 2>&1; then
    prompt=$(printf '%s' "$input" | python3 -c 'import json,sys
try:
  print(json.load(sys.stdin).get("prompt",""))
except Exception:
  pass' 2>/dev/null || true)
  fi
  [ -z "$prompt" ] && return 0

  # Vault-y keywords → fire reminder
  if printf '%s' "$prompt" | grep -qiE '\b(vault|decision|brief|handoff|obsidian|cabinet|note this|document this|put in vault|record this)\b'; then
    printf '[adjudant] Vault not linked for this project. Run `/adjudant connect` to capture this work in the vault.\n'
  fi
}

main "$@" || exit 0
