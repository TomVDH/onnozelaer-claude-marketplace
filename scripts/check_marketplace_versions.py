#!/usr/bin/env python3
"""Marketplace version-parity guard (repo-wide).

Every plugin listed in `.claude-plugin/marketplace.json` must declare the same
version in its own `<source>/.claude-plugin/plugin.json`. This catches the
drift class where a plugin bumps its manifest but the marketplace registry
(what Claude Code installs from) is left behind — e.g. gemineye shipping 0.3.2
while the registry still advertised 0.3.1.

Adjudant has its own richer validator (adjudant/scripts/validate.py); this one
is the lightweight, every-plugin safety net. Exit 0 on parity, 1 on any drift.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"


def main() -> int:
    try:
        data = json.loads(MARKETPLACE.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"  ✗ cannot read marketplace.json: {e}")
        return 1

    drift: list[str] = []
    checked = 0
    for plugin in data.get("plugins", []):
        name = plugin.get("name", "?")
        mver = plugin.get("version", "")
        source = plugin.get("source", "")
        plugin_json = ROOT / source / ".claude-plugin" / "plugin.json"
        if not plugin_json.is_file():
            drift.append(f"{name}: plugin.json not found at {plugin_json.relative_to(ROOT)}")
            continue
        try:
            pver = json.loads(plugin_json.read_text()).get("version", "")
        except json.JSONDecodeError as e:
            drift.append(f"{name}: plugin.json invalid JSON: {e}")
            continue
        checked += 1
        if mver != pver:
            drift.append(f"{name}: marketplace={mver!r} != plugin.json={pver!r}")

    if drift:
        print("marketplace version-parity — FAIL")
        for d in drift:
            print(f"  ✗ {d}")
        return 1
    print(f"marketplace version-parity — PASS ({checked} plugins in sync)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
