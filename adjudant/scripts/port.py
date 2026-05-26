#!/usr/bin/env python3
"""Adjudant port verb — migrate legacy projects to adjudant compliance.

Run from the project root (or via `python3 adjudant/scripts/port.py`).
Detects project flavor (X/Y/Z) or port phase (preview/applied) and
dispatches accordingly. See docs/superpowers/specs/2026-05-26-adjudant-port-verb-design.md.
"""

from pathlib import Path


def detect_flavor(project_root: Path) -> str:
    """Detect the legacy flavor of a project.

    Returns one of: "X" (raw repo), "Y" (obsidian-bridge legacy),
    "Z" (hand-authored AGENTS.md/CLAUDE.md), "preview" (port preview
    pending apply), "applied" (already ported).
    """
    return "X"
