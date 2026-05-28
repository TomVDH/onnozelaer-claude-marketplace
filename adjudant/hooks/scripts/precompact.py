#!/usr/bin/env python3
"""PreCompact hook for adjudant.

1. Append a pause marker to today's session log.
2. Optionally harvest 5 durable bullets from the CC transcript via Gemini.
3. Mirror .remember/remember.md to vault _handoff.md (sync action).
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


HARVEST_PROMPT_TEMPLATE = """ROLE
You are a session-end archivist for a Claude Code working session about to be compacted.

DO
- Extract concrete decisions, problems solved, blockers, and unresolved questions
- One bullet per item, max 25 words
- Reference specific files/commits/issues by name when possible

DON'T
- Summarise the chat
- Include code blocks
- Use softening language ("we discussed", "considered")
- Output anything except the bullets

SCOPE — IN
- The most recent {n_msgs} messages of the transcript (provided below)

SCOPE — OUT
- Greetings, tool-call mechanics, status pings, hook output
- Anything older than what's included

OUTPUT
- Exactly 5 bullets, no preamble, no trailing text. If fewer than 5 concrete items exist, output fewer.
- Format: `- <bullet text>`

CONTEXT
{transcript_chunk}
"""

HARVEST_MAX_CHARS = 10_000
HARVEST_TIMEOUT_SECS = 30
HARVEST_N_MSGS = 30


def read_payload() -> dict:
    """Read the JSON payload CC sends on stdin. Returns {} on any failure."""
    try:
        if sys.stdin.isatty():
            return {}
        data = sys.stdin.read()
        if not data.strip():
            return {}
        return json.loads(data)
    except (json.JSONDecodeError, OSError):
        return {}


def extract_transcript_text(transcript_path: Path, n_msgs: int = HARVEST_N_MSGS) -> str:
    """Read last n_msgs * 2 lines from the .jsonl transcript, strip tool internals.
    Returns plain text suitable for a Gemini prompt, capped at HARVEST_MAX_CHARS."""
    if not transcript_path.is_file():
        return ""
    try:
        lines = transcript_path.read_text().splitlines()[-(n_msgs * 2):]
    except OSError:
        return ""
    out = []
    for line in lines:
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        role = msg.get("role") or msg.get("type", "")
        content = msg.get("content", "")
        if isinstance(content, list):
            content = " ".join(
                c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text"
            )
        if not isinstance(content, str):
            continue
        content = re.sub(r"\s+", " ", content).strip()
        if not content:
            continue
        out.append(f"[{role}] {content[:1000]}")
    text = "\n".join(out)
    return text[-HARVEST_MAX_CHARS:]


def harvest_with_gemini(transcript_path: Path) -> str:
    """Return bullet block on success, '' on any failure. Always fails closed."""
    chunk = extract_transcript_text(transcript_path)
    if not chunk:
        return ""
    prompt = HARVEST_PROMPT_TEMPLATE.format(n_msgs=HARVEST_N_MSGS, transcript_chunk=chunk)
    try:
        result = subprocess.run(
            ["gemini", "--sandbox", "-m", "gemini-2.5-flash", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=HARVEST_TIMEOUT_SECS,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return ""
    if result.returncode != 0:
        return ""
    output = result.stdout.strip()
    # Sanity: only return if it looks like a bullet list
    if not output.startswith("- ") and not output.startswith("• "):
        return ""
    return output


def read_breadcrumb(project_dir: Path) -> dict:
    """Read `.claude/adjudant` breadcrumb (`key: value` per line, YAML-ish).

    Format written by connect.py — uses `:` separator. Old `=` format
    (pre-v0.4.0) also tolerated for transition.
    """
    breadcrumb = project_dir / ".claude" / "adjudant"
    if not breadcrumb.exists():
        return {}
    info = {}
    for line in breadcrumb.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sep = ":" if ":" in line else ("=" if "=" in line else None)
        if not sep:
            continue
        k, v = line.split(sep, 1)
        info[k.strip()] = v.strip()
    return info


def find_remember_source(project_dir: Path) -> Path:
    """Locate the best `.remember/` file to mirror.

    Priority:
      1. `.remember/remember.md` (canonical per sync runbook)
      2. `.remember/now.md` (newer convention on some machines)

    Returns the chosen Path or None.
    """
    canonical = project_dir / ".remember" / "remember.md"
    if canonical.is_file():
        return canonical
    now_file = project_dir / ".remember" / "now.md"
    if now_file.is_file():
        return now_file
    return None


def sync_handoff(
    project_dir: Path,
    vault: Path,
    slug: str,
    today: str,
    ts: str,
    harvest: str = "",
) -> None:
    source = find_remember_source(project_dir)
    if source is None:
        return

    handoff = vault / "projects" / slug / "_handoff.md"
    body = source.read_text()
    source_name = source.name  # 'remember.md' or 'now.md'

    header = (
        "---\n"
        "type: handoff\n"
        f'project: "[[projects/{slug}/brief|{slug}]]"\n'
        f"updated: {today}\n"
        f"source: {source.stem}\n"
        "tags:\n"
        "  - handoff\n"
        "---\n"
    )

    harvest_section = ""
    if harvest:
        harvest_section = (
            f"\n## Gemini harvest — {today} {ts} (model: gemini-2.5-flash)\n\n"
            f"{harvest}\n"
        )

    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        f"{header}\n"
        f"# Handoff — {slug}\n\n"
        f"*Mirrored from `.remember/{source_name}` on {today} {ts}.*\n"
        f"{harvest_section}\n"
        f"---\n\n"
        f"{body}\n"
    )


def main() -> int:
    # Read stdin payload first (before any other reads consume stdin)
    payload = read_payload()

    project_dir_str = os.environ.get("CLAUDE_PROJECT_DIR")
    if not project_dir_str:
        return 0

    project_dir = Path(project_dir_str)
    info = read_breadcrumb(project_dir)
    vault_path = info.get("vault_path", "")
    slug = info.get("slug", "")
    if not vault_path or not slug:
        return 0

    vault = Path(vault_path)
    today = datetime.now().strftime("%Y-%m-%d")
    ts = datetime.now().strftime("%H:%M")

    # SessionEnd reuses this script for the handoff sync only. With --sync-only
    # we skip the pause marker — the session ended, it did not pause for compaction.
    sync_only = "--sync-only" in sys.argv[1:]

    # 1. Append pause marker (PreCompact only)
    if not sync_only:
        session_file = vault / "projects" / slug / "sessions" / f"{today}.md"
        if session_file.exists():
            with session_file.open("a") as f:
                f.write(f"- {ts} · paused (compaction)\n")

    # 2. Harvest from Gemini (PreCompact only, fails closed)
    harvest = ""
    if not sync_only:
        transcript_path_str = payload.get("transcript_path", "")
        if transcript_path_str:
            harvest = harvest_with_gemini(Path(transcript_path_str))

    # 3. Sync handoff
    sync_handoff(project_dir, vault, slug, today, ts, harvest=harvest)

    return 0


if __name__ == "__main__":
    sys.exit(main())
