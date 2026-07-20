#!/usr/bin/env bash
# sessionend.sh — SessionEnd hook for adjudant
# 1. Append session-ended marker to today's session log
# 2. Run handoff sync via precompact.py (same logic)
#
# Resolution parity: same chain as session-start.sh — Python resolve_vault
# when reachable, OB_VAULT + local vault_path in pure-bash degraded mode.
set -euo pipefail

main() {
  local project_dir="${CLAUDE_PROJECT_DIR:-}"
  [ -z "$project_dir" ] && return 0

  local breadcrumb="$project_dir/.claude/adjudant"
  [ ! -f "$breadcrumb" ] && return 0

  local vault_path slug
  # Breadcrumb format is `key: value` (YAML-ish, written by connect.py);
  # legacy pre-v0.4.0 `key=value` tolerated, matching the Python hooks.
  # tr -d '\r' matches session-start.sh — no CRLF leakage into paths/slugs.
  vault_path=$(sed -n 's/^vault_path[:=][[:space:]]*//p' "$breadcrumb" 2>/dev/null | head -n1 | tr -d '\r' || true)
  slug=$(sed -n 's/^slug[:=][[:space:]]*//p' "$breadcrumb" 2>/dev/null | head -n1 | tr -d '\r' || true)

  [ -z "$slug" ] && return 0
  vault_path="${vault_path/#\~/$HOME}"

  # Full-chain resolution via the Python layer when available (same vault as
  # every other hook and the verbs).
  if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/scripts/_vault_walk.py" ] \
     && command -v python3 >/dev/null 2>&1; then
    local resolved
    resolved=$(python3 -c 'import sys
sys.path.insert(0, sys.argv[1])
from pathlib import Path
from _vault_walk import resolve_vault
v = resolve_vault(Path(sys.argv[2]))
print(v or "")' "$CLAUDE_PLUGIN_ROOT/scripts" "$project_dir" 2>/dev/null || true)
    [ -n "$resolved" ] && vault_path="$resolved"
  elif [ -n "${OB_VAULT:-}" ] && [ -d "${OB_VAULT/#\~/$HOME}" ]; then
    vault_path="${OB_VAULT/#\~/$HOME}"
  fi

  [ -z "$vault_path" ] && return 0
  [ ! -d "$vault_path" ] && return 0  # stale breadcrumb: never write to a phantom path

  local today ts session_dir session_file
  # Single clock read so date and time can't straddle midnight between calls.
  read -r today ts <<< "$(date '+%Y-%m-%d %H:%M')"
  session_dir="$vault_path/projects/$slug/sessions"
  session_file="$session_dir/$today.md"

  # Midnight straddle: a session started 23:40 and ended 00:10 targets the new
  # day's note, which doesn't exist yet — fall back to the latest daily note
  # so the end marker isn't silently dropped. Digit classes, not ?: a stray
  # abcd-ef-gh.md must never lexically outrank a real date.
  if [ ! -f "$session_file" ]; then
    session_file=$(ls "$session_dir"/[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9].md 2>/dev/null | tail -n1 || true)
  fi

  if [ -n "$session_file" ] && [ -f "$session_file" ]; then
    # Skip the marker when nothing was logged since the last hook marker: a
    # bare started/resumed/paused/ended tail means the pair would be pure
    # churn (quick open/close sessions used to stack noise lines daily).
    local last_line
    last_line=$(grep -v '^[[:space:]]*$' "$session_file" 2>/dev/null | tail -n 1 || true)
    case "$last_line" in
      *"· session started"*|*"session resumed ---"*|*"· session ended"*|*"paused (compaction)"*)
        : ;;
      *)
        # brace group so stderr is silenced BEFORE the >> open (redirections
        # are processed left→right; a read-only vault must stay noiseless)
        { printf -- '- %s · session ended\n' "$ts" >> "$session_file"; } 2>/dev/null || true ;;
    esac
  fi

  # Run handoff sync only — no pause marker (best effort, never block)
  if [ -n "${CLAUDE_PLUGIN_ROOT:-}" ] && [ -f "$CLAUDE_PLUGIN_ROOT/hooks/scripts/precompact.py" ] \
     && command -v python3 >/dev/null 2>&1; then
    python3 "$CLAUDE_PLUGIN_ROOT/hooks/scripts/precompact.py" --sync-only 2>/dev/null || true
  fi
}

main "$@" || exit 0
