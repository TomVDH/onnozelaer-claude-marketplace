# Adjudant repo-target (v2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give `/adjudant check` and `/adjudant tidy` a `[vault|repo|all]` target so adjudant audits (read-only) and safely repairs (symlink repair) the code repo, not just the vault.

**Architecture:** Three new stdlib-only helpers mirror the vault trio one-for-one — `repo_walk.py` (primitives ← `_vault_walk.py`), `repo_scan.py` (detectors + `run_scan()` ← `ramasse_scan.py`), `repo_tidy.py` (two-phase preview→apply ← `tidy.py`). Detection is layered: a general core (repo-root context files, stale plans) plus a marketplace layer that auto-activates when `.claude-plugin/marketplace.json` is present (version coherence via reused `check_marketplace_versions` logic, symlink integrity, registration). `tidy repo` does symlink repair only. The verbs dispatch by reading their reference docs; no Python router. `ramasse repo` and any version-sync fixer are out of scope (deferred).

**Tech Stack:** Python 3 stdlib only (`argparse`, `json`, `re`, `pathlib`, `dataclasses`, `datetime`, `shutil`, `os`), `unittest`. Markdown reference docs. Pre-commit runs `adjudant/scripts/validate.py` + `scripts/check_marketplace_versions.py`.

## Global Constraints

- **Stdlib only.** No third-party imports in any script.
- **Commits go directly to `main`** (this repo does not use PRs — see `AGENTS.md`). Do not push without the user's say-so.
- **Every commit message ends with** the trailer `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- **Run adjudant tests:** `python3 -m unittest discover -s adjudant/scripts -p 'test_*.py'` (from repo root; the `-s` puts `adjudant/scripts` on `sys.path`, which bare imports like `import repo_walk` require).
- **Run validators:** `python3 adjudant/scripts/validate.py` (exit 0 = pass).
- **Version lockstep (critical):** `validate.py`'s `version-consistency` check requires `plugin.json` / `command-metadata.json` / `SKILL.md` frontmatter / `marketplace.json` to all carry the same adjudant version. Pre-commit runs `validate.py` on **every** commit. Tasks 1–6 must leave all four at **0.12.0** (consistent) so their commits pass. The single 0.13.0 bump lands in Task 7 via `python3 scripts/bump_plugin_version.py adjudant 0.13.0` — never hand-edit versions.
- **Canonical skill dir only.** `adjudant/skills/adjudant/` is real; `source/`, `.claude/`, `.gemini/` under it are symlinks. Edit reference/SKILL files at the canonical path only.
- **Verb descriptions ≤ 220 chars** (`verb-description-length` validator). Reference docs must have no dead relative links (`reference-doc-links` validator).
- **Quote paths** — the repo root contains a space (`VIBE CODING`).

## File structure

| File | New/Modify | Responsibility |
|---|---|---|
| `adjudant/scripts/repo_walk.py` | Create | Repo primitives: marketplace detection, plugin discovery, symlink-integrity status, context-file status, plan-file ages. Read-only. |
| `adjudant/scripts/repo_scan.py` | Create | Detectors + `run_scan()` → JSON with `drift_items`. Feeds `check repo`. Read-only. |
| `adjudant/scripts/repo_tidy.py` | Create | Two-phase `detect`/`preview`/`apply` for symlink repair. |
| `adjudant/scripts/test_repo_walk.py` | Create | Unit tests for `repo_walk`. |
| `adjudant/scripts/test_repo_scan.py` | Create | Unit tests for `repo_scan`. |
| `adjudant/scripts/test_repo_tidy.py` | Create | Unit tests for `repo_tidy` (preview→apply, idempotency, repair). |
| `adjudant/skills/adjudant/reference/repo-standards.md` | Create | Single source of truth for repo conventions (the detector categories). |
| `adjudant/skills/adjudant/reference/check.md` | Modify | Add `[target]` dimension + `check repo` render section. |
| `adjudant/skills/adjudant/reference/tidy.md` | Modify | Add `[target]` dimension + `tidy repo` run section. |
| `adjudant/scripts/command-metadata.json` | Modify | `argumentHint` → `[vault\|repo\|all]` for check + tidy (version stays 0.12.0 until Task 7). |
| `adjudant/skills/adjudant/SKILL.md` | Modify | Router target notes; content-authoring list gains `repo-standards.md`; `argument-hint` frontmatter. |
| `adjudant/scripts/validate.py` | Modify | Add 5 validators (repo-helper-parity, repo-standards-coverage, repo-tidy preview/backup/gitignore). |
| `adjudant/scripts/test_validate.py` | Modify | Tests for the 5 new validators. |
| `.gitignore` | Modify | Add `.adjudant-repo-tidy-preview/` + `.adjudant-repo-tidy-backup/`. |
| `adjudant/README.md` | Modify | Verb table target notes; helper list; validator/test counts. |
| `AGENTS.md` | Modify | Tree line adjudant → v0.13.0. |

---

## Task 1: `repo_walk.py` — repo-side primitives

**Files:**
- Create: `adjudant/scripts/repo_walk.py`
- Test: `adjudant/scripts/test_repo_walk.py`

**Interfaces produced** (later tasks rely on these exact names):
- `is_marketplace_repo(root: Path) -> bool`
- `walk_plugins(root: Path) -> list[PluginInfo]` where `PluginInfo` is a dataclass `{name: str, dir: Path, version: str, has_skills: bool, source: str}` (`source` = the plugin dir name; `version` from its plugin.json or `""`).
- `parse_plugin_json(plugin_dir: Path) -> dict` (empty dict on missing/invalid)
- `parse_marketplace_json(root: Path) -> dict` (empty dict on missing/invalid)
- `plugin_symlink_status(plugin: PluginInfo) -> dict` → `{adopted: bool, links: {"source": str, ".claude": str, ".gemini": str}}` where each value is one of `"ok"`, `"missing"`, `"dangling"`, or `"n/a"` (n/a when the plugin has no skills). `adopted` = has_skills AND ≥1 link is `"ok"`.
- `context_files_status(root: Path) -> dict` → `{agents: bool, claude: bool, claude_imports_agents: bool}`
- `plan_file_ages(root: Path, today: date, stale_days: int = 30) -> list[dict]` → `[{path, age_days, stale: bool}]` for `docs/superpowers/**/*.md` with no completion marker (`status: done`/`status: complete`/`✅` in first 400 chars). `today` is injected (never call `date.today()` inside — keeps tests deterministic).

- [ ] **Step 1: Write the failing test** — `adjudant/scripts/test_repo_walk.py`:

```python
"""Tests for repo_walk primitives."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repo_walk as rw


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def _make_plugin(root: Path, name: str, version: str, *, skills: bool = False, adopt: bool = False) -> None:
    pdir = root / name
    _write(pdir / ".claude-plugin" / "plugin.json",
           '{\n  "name": "%s",\n  "version": "%s"\n}\n' % (name, version))
    if skills:
        canon = pdir / "skills" / name
        _write(canon / "SKILL.md", "---\nname: %s\n---\n# %s\n" % (name, name))
        if adopt:
            for h in ("source", ".claude", ".gemini"):
                d = pdir / h / "skills"
                d.mkdir(parents=True)
                (d / name).symlink_to(Path("../../skills") / name)


def _marketplace(root: Path, entries: list[tuple[str, str]]) -> None:
    plugins = ",\n".join(
        '    {"name": "%s", "version": "%s", "source": "./%s"}' % (n, v, n) for n, v in entries)
    _write(root / ".claude-plugin" / "marketplace.json",
           '{\n  "plugins": [\n%s\n  ]\n}\n' % plugins)


class TestRepoWalk(unittest.TestCase):

    def test_is_marketplace_repo(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertFalse(rw.is_marketplace_repo(root))
            _marketplace(root, [("a", "1.0.0")])
            self.assertTrue(rw.is_marketplace_repo(root))

    def test_walk_plugins_discovers_and_reads_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.2.3", skills=True, adopt=True)
            _make_plugin(root, "beta", "0.1.0", skills=False)
            _marketplace(root, [("alpha", "1.2.3"), ("beta", "0.1.0")])
            plugins = {p.name: p for p in rw.walk_plugins(root)}
            self.assertEqual(set(plugins), {"alpha", "beta"})
            self.assertEqual(plugins["alpha"].version, "1.2.3")
            self.assertTrue(plugins["alpha"].has_skills)
            self.assertFalse(plugins["beta"].has_skills)

    def test_symlink_status_ok_when_adopted(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            p = next(p for p in rw.walk_plugins(root) if p.name == "alpha")
            st = rw.plugin_symlink_status(p)
            self.assertTrue(st["adopted"])
            self.assertEqual(st["links"], {"source": "ok", ".claude": "ok", ".gemini": "ok"})

    def test_symlink_status_missing_and_dangling(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            # remove one harness symlink (missing) and break another (dangling)
            (root / "alpha" / ".gemini" / "skills" / "alpha").unlink()
            (root / "alpha" / "skills" / "alpha").rename(root / "alpha" / "skills" / "alpha-moved")
            p = next(p for p in rw.walk_plugins(root) if p.name == "alpha")
            st = rw.plugin_symlink_status(p)
            self.assertEqual(st["links"][".gemini"], "missing")
            self.assertEqual(st["links"]["source"], "dangling")  # canonical moved
            self.assertTrue(st["adopted"])  # still adopted: .claude link present

    def test_symlink_status_na_without_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "beta", "1.0.0", skills=False)
            p = next(p for p in rw.walk_plugins(root) if p.name == "beta")
            st = rw.plugin_symlink_status(p)
            self.assertFalse(st["adopted"])
            self.assertEqual(set(st["links"].values()), {"n/a"})

    def test_context_files_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.assertEqual(rw.context_files_status(root),
                             {"agents": False, "claude": False, "claude_imports_agents": False})
            _write(root / "AGENTS.md", "# repo\n")
            _write(root / "CLAUDE.md", "@AGENTS.md\n\n# overrides\n")
            self.assertEqual(rw.context_files_status(root),
                             {"agents": True, "claude": True, "claude_imports_agents": True})

    def test_plan_file_ages_flags_old_unmarked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "docs" / "superpowers" / "plans" / "old.md", "# plan\nwork\n")
            _write(root / "docs" / "superpowers" / "specs" / "done.md",
                   "---\nstatus: done\n---\n# spec\n")
            import os, time
            old = root / "docs" / "superpowers" / "plans" / "old.md"
            past = time.time() - 60 * 86400
            os.utime(old, (past, past))
            ages = {a["path"]: a for a in rw.plan_file_ages(root, date(2026, 7, 7), stale_days=30)}
            self.assertTrue(any("old.md" in k and v["stale"] for k, v in ages.items()))
            # a doc with a completion marker is not listed as stale
            self.assertFalse(any("done.md" in k and v["stale"] for k, v in ages.items()))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure** — `python3 -m unittest test_repo_walk -v` (run from `adjudant/scripts`). Expected: `ModuleNotFoundError: No module named 'repo_walk'`.

- [ ] **Step 3: Implement `adjudant/scripts/repo_walk.py`**

```python
#!/usr/bin/env python3
"""Adjudant repo_walk — read-only primitives for the repo cleanup target.

Mirrors _vault_walk.py's role for the code repo: plugin discovery, marketplace
detection, Impeccable-symlink integrity, context-file presence, plan-file age.
Stdlib only, never writes.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Optional

HARNESS_DIRS = ("source", ".claude", ".gemini")
COMPLETION_MARKERS = ("status: done", "status: complete", "status: shipped", "✅")


@dataclass
class PluginInfo:
    name: str
    dir: Path
    version: str
    has_skills: bool
    source: str  # the plugin dir name


def _read_json(p: Path) -> dict:
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def parse_plugin_json(plugin_dir: Path) -> dict:
    return _read_json(plugin_dir / ".claude-plugin" / "plugin.json")


def parse_marketplace_json(root: Path) -> dict:
    return _read_json(root / ".claude-plugin" / "marketplace.json")


def is_marketplace_repo(root: Path) -> bool:
    return (root / ".claude-plugin" / "marketplace.json").is_file()


def walk_plugins(root: Path) -> list[PluginInfo]:
    """Every subdir with a .claude-plugin/plugin.json. Sorted by name."""
    out: list[PluginInfo] = []
    for d in sorted(root.iterdir(), key=lambda p: p.name):
        if not d.is_dir() or d.name.startswith(".") or d.name.startswith("_"):
            continue
        pj = d / ".claude-plugin" / "plugin.json"
        if not pj.is_file():
            continue
        meta = parse_plugin_json(d)
        skills_dir = d / "skills"
        has_skills = skills_dir.is_dir() and any(skills_dir.iterdir())
        out.append(PluginInfo(
            name=meta.get("name", d.name),
            dir=d,
            version=meta.get("version", ""),
            has_skills=has_skills,
            source=d.name,
        ))
    return out


def _canonical_skill_dirs(plugin: PluginInfo) -> list[Path]:
    base = plugin.dir / "skills"
    if not base.is_dir():
        return []
    return [c for c in base.iterdir() if c.is_dir() and not c.name.startswith(".")]


def plugin_symlink_status(plugin: PluginInfo) -> dict:
    """Per-harness-dir link status for a plugin's canonical skill(s).

    A plugin with no skills needs no harness → all links "n/a", adopted False.
    Otherwise, for the first canonical skill dir, each of source/.claude/.gemini
    is "ok" (symlink resolves to canonical), "dangling" (symlink exists but
    resolves elsewhere / to a missing target), or "missing" (no such symlink).
    adopted = has_skills AND at least one link is "ok".
    """
    links = {h: "n/a" for h in HARNESS_DIRS}
    canon_dirs = _canonical_skill_dirs(plugin)
    if not plugin.has_skills or not canon_dirs:
        return {"adopted": False, "links": links}
    canon = canon_dirs[0]
    canon_name = canon.name
    for h in HARNESS_DIRS:
        link = plugin.dir / h / "skills" / canon_name
        if not link.is_symlink():
            links[h] = "missing"
            continue
        try:
            resolved = link.resolve()
        except OSError:
            resolved = None
        links[h] = "ok" if (resolved is not None and resolved == canon.resolve()) else "dangling"
    adopted = any(v == "ok" for v in links.values())
    return {"adopted": adopted, "links": links}


def context_files_status(root: Path) -> dict:
    agents = (root / "AGENTS.md").is_file()
    claude_p = root / "CLAUDE.md"
    claude = claude_p.is_file()
    imports = False
    if claude:
        try:
            first = next((ln.strip() for ln in claude_p.read_text().splitlines() if ln.strip()), "")
            imports = first == "@AGENTS.md"
        except OSError:
            imports = False
    return {"agents": agents, "claude": claude, "claude_imports_agents": imports}


def _has_completion_marker(text: str) -> bool:
    head = text[:400].lower()
    return any(m.lower() in head for m in COMPLETION_MARKERS)


def plan_file_ages(root: Path, today: date, stale_days: int = 30) -> list[dict]:
    """docs/superpowers/**/*.md with no completion marker, with age in days.

    Age is from mtime. `today` is injected for deterministic tests.
    """
    base = root / "docs" / "superpowers"
    if not base.is_dir():
        return []
    out: list[dict] = []
    for f in sorted(base.rglob("*.md")):
        try:
            text = f.read_text(errors="replace")
        except OSError:
            continue
        if _has_completion_marker(text):
            continue
        try:
            mtime = datetime.fromtimestamp(f.stat().st_mtime).date()
        except OSError:
            continue
        age = (today - mtime).days
        out.append({"path": str(f.relative_to(root)), "age_days": age, "stale": age >= stale_days})
    return out
```

- [ ] **Step 4: Run to verify pass** — `python3 -m unittest test_repo_walk -v`. Expected: all tests PASS.
- [ ] **Step 5: Commit**

```bash
git add adjudant/scripts/repo_walk.py adjudant/scripts/test_repo_walk.py
git commit -m "feat(adjudant): repo_walk primitives — plugin/marketplace/symlink/context/plan-age (repo target)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 2: `repo_scan.py` — detectors + `run_scan()`

**Files:**
- Create: `adjudant/scripts/repo_scan.py`
- Test: `adjudant/scripts/test_repo_scan.py`

**Interfaces:**
- Consumes: everything from Task 1's `repo_walk`.
- Produces: `run_scan(root: Path, *, today: date, stale_days: int = 30) -> dict` — JSON-serializable report `{meta, summary: {drift_items}, version_coherence, symlink_integrity, registration, context_files, plan_ages}`. `drift_items` = count of version mismatches + un-repaired symlink issues on adopted plugins + registration gaps + stale plans. Per-plugin context files are informational and NOT in `drift_items`.

- [ ] **Step 1: Write the failing test** — `adjudant/scripts/test_repo_scan.py`:

```python
"""Tests for repo_scan detectors + run_scan."""
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repo_scan as rs
from test_repo_walk import _make_plugin, _marketplace, _write


class TestRepoScan(unittest.TestCase):

    def test_clean_repo_zero_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            _marketplace(root, [("alpha", "1.0.0")])
            _write(root / "AGENTS.md", "# r\n")
            _write(root / "CLAUDE.md", "@AGENTS.md\n")
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertEqual(report["summary"]["drift_items"], 0)

    def test_version_mismatch_counts_as_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.1", skills=False)
            _marketplace(root, [("alpha", "1.0.0")])  # registry behind
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertTrue(report["version_coherence"]["mismatches"])
            self.assertGreaterEqual(report["summary"]["drift_items"], 1)

    def test_broken_symlink_on_adopted_plugin_is_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            _marketplace(root, [("alpha", "1.0.0")])
            (root / "alpha" / ".gemini" / "skills" / "alpha").unlink()  # missing
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertGreaterEqual(report["summary"]["drift_items"], 1)
            self.assertTrue(report["symlink_integrity"]["issues"])

    def test_skillless_plugin_not_symlink_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "beta", "1.0.0", skills=False)
            _marketplace(root, [("beta", "1.0.0")])
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertEqual(report["symlink_integrity"]["issues"], [])

    def test_registration_gap_is_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=False)
            _make_plugin(root, "ghost", "1.0.0", skills=False)  # not in marketplace
            _marketplace(root, [("alpha", "1.0.0")])
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertIn("ghost", str(report["registration"]))
            self.assertGreaterEqual(report["summary"]["drift_items"], 1)

    def test_context_files_informational_not_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=False)
            _marketplace(root, [("alpha", "1.0.0")])
            _write(root / "AGENTS.md", "# r\n")
            _write(root / "CLAUDE.md", "@AGENTS.md\n")
            # plugin has no per-plugin AGENTS/CLAUDE — must NOT add drift
            report = rs.run_scan(root, today=date(2026, 7, 7))
            self.assertEqual(report["summary"]["drift_items"], 0)

    def test_report_is_json_serializable(self):
        import json
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            _marketplace(root, [("alpha", "1.0.0")])
            report = rs.run_scan(root, today=date(2026, 7, 7))
            json.loads(json.dumps(report, default=str))


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure** — `python3 -m unittest test_repo_scan -v`. Expected: `ModuleNotFoundError: No module named 'repo_scan'`.

- [ ] **Step 3: Implement `adjudant/scripts/repo_scan.py`**

```python
#!/usr/bin/env python3
"""Adjudant repo_scan — read-only structural drift detectors for the repo target.

Mirrors ramasse_scan.py for the code repo. Emits a JSON report on stdout that
`check repo` renders. Layered: a general core (context files, plan age) plus a
marketplace layer (version coherence, symlink integrity, registration) that
auto-activates when .claude-plugin/marketplace.json is present.

drift_items is cardinality-based: version mismatches + symlink issues on adopted
plugins + registration gaps + stale plans. Per-plugin context files are
informational only (never counted).

CLI:  python3 repo_scan.py --project-dir PATH [--json] [--stale-days N] [--today YYYY-MM-DD]
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, Optional

from repo_walk import (
    context_files_status,
    is_marketplace_repo,
    parse_marketplace_json,
    plan_file_ages,
    plugin_symlink_status,
    walk_plugins,
)


def detect_version_coherence(root: Path) -> dict:
    """Marketplace entry version vs each plugin.json. Reuses the parity rule of
    scripts/check_marketplace_versions.py (read-only display here)."""
    market = parse_marketplace_json(root)
    plugins = {p.source: p for p in walk_plugins(root)}
    mismatches = []
    for entry in market.get("plugins", []):
        name = entry.get("name", "?")
        mver = entry.get("version", "")
        source = (entry.get("source", "") or "").lstrip("./")
        p = plugins.get(source)
        pver = p.version if p else None
        if pver is None:
            mismatches.append({"plugin": name, "issue": "source plugin.json not found", "source": source})
        elif mver != pver:
            mismatches.append({"plugin": name, "marketplace": mver, "plugin_json": pver})
    return {"mismatches": mismatches}


def detect_symlink_integrity(root: Path) -> dict:
    """Broken/missing harness symlinks on ADOPTED plugins only."""
    issues = []
    matrix = {}
    for p in walk_plugins(root):
        st = plugin_symlink_status(p)
        matrix[p.name] = st
        if st["adopted"]:
            for h, state in st["links"].items():
                if state in ("missing", "dangling"):
                    issues.append({"plugin": p.name, "harness": h, "state": state})
    return {"issues": issues, "matrix": matrix}


def detect_registration(root: Path) -> dict:
    """Every plugin dir registered in marketplace.json, and every registered
    source path exists."""
    market = parse_marketplace_json(root)
    registered = {(e.get("source", "") or "").lstrip("./") for e in market.get("plugins", [])}
    on_disk = {p.source for p in walk_plugins(root)}
    unregistered = sorted(on_disk - registered)
    dangling_sources = sorted(s for s in registered if s and not (root / s).is_dir())
    return {"unregistered": unregistered, "dangling_sources": dangling_sources}


def run_scan(root: Path, *, today: date, stale_days: int = 30) -> dict[str, Any]:
    marketplace = is_marketplace_repo(root)
    version = detect_version_coherence(root) if marketplace else {"mismatches": []}
    symlinks = detect_symlink_integrity(root) if marketplace else {"issues": [], "matrix": {}}
    registration = detect_registration(root) if marketplace else {"unregistered": [], "dangling_sources": []}
    context = context_files_status(root)
    plans = plan_file_ages(root, today, stale_days=stale_days)
    stale_plans = [p for p in plans if p["stale"]]

    # Per-plugin context files: informational only.
    per_plugin_context = []
    if marketplace:
        for p in walk_plugins(root):
            per_plugin_context.append({
                "plugin": p.name,
                "agents": (p.dir / "AGENTS.md").is_file(),
                "claude": (p.dir / "CLAUDE.md").is_file(),
            })

    drift_items = (
        len(version["mismatches"])
        + len(symlinks["issues"])
        + len(registration["unregistered"])
        + len(registration["dangling_sources"])
        + len(stale_plans)
    )

    return {
        "meta": {
            "root": str(root),
            "is_marketplace_repo": marketplace,
            "plugins_scanned": len(walk_plugins(root)),
            "stale_days": stale_days,
        },
        "summary": {"drift_items": drift_items, "stale_plan_count": len(stale_plans)},
        "version_coherence": version,
        "symlink_integrity": symlinks,
        "registration": registration,
        "context_files": {"repo_root": context, "per_plugin_informational": per_plugin_context},
        "plan_ages": plans,
    }


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="repo_scan.py", description="Adjudant repo drift scan (read-only).")
    parser.add_argument("--project-dir", default=".", help="Repo root (default: cwd)")
    parser.add_argument("--stale-days", type=int, default=30)
    parser.add_argument("--today", help="YYYY-MM-DD override (testing/determinism)")
    parser.add_argument("--json", action="store_true", help="(default) emit JSON on stdout")
    parser.add_argument("--out", help="Write JSON to FILE instead of stdout")
    args = parser.parse_args(argv)

    root = Path(args.project_dir).expanduser().resolve()
    if not root.is_dir():
        print(f"error: project-dir not found: {root}", file=sys.stderr)
        return 1
    today = date.fromisoformat(args.today) if args.today else date.today()
    report = run_scan(root, today=today, stale_days=args.stale_days)
    payload = json.dumps(report, indent=2, default=str)
    if args.out:
        Path(args.out).expanduser().write_text(payload + "\n")
        print(f"[repo_scan] wrote {args.out}", file=sys.stderr)
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
```

- [ ] **Step 4: Run to verify pass** — `python3 -m unittest test_repo_scan -v`. Expected: all PASS.
- [ ] **Step 5: Sanity-run on this repo** — `python3 adjudant/scripts/repo_scan.py --project-dir . --today 2026-07-07` (from repo root). Expected: valid JSON; `version_coherence.mismatches` empty; `symlink_integrity.issues` empty (adjudant intact); `registration.unregistered` empty.
- [ ] **Step 6: Commit**

```bash
git add adjudant/scripts/repo_scan.py adjudant/scripts/test_repo_scan.py
git commit -m "feat(adjudant): repo_scan detectors — version/symlink/registration/plan-age + run_scan JSON

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 3: `repo_tidy.py` — symlink repair (two-phase)

**Files:**
- Create: `adjudant/scripts/repo_tidy.py`
- Test: `adjudant/scripts/test_repo_tidy.py`

**Interfaces:**
- Consumes: Task 1 `repo_walk` (`walk_plugins`, `plugin_symlink_status`, `HARNESS_DIRS`).
- Produces: `detect_repairs(root) -> list[dict]` (`[{plugin, harness, state, canonical_rel}]` for adopted plugins with missing/dangling links); `PREVIEW_DIR_NAME`, `BACKUP_DIR_NAME`; `write_preview(root, repairs) -> Path`; `apply_preview(root) -> Path`.

- [ ] **Step 1: Write the failing test** — `adjudant/scripts/test_repo_tidy.py`:

```python
"""Tests for repo_tidy symlink repair (preview -> apply, idempotent)."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import repo_tidy as rt
from test_repo_walk import _make_plugin


class TestRepoTidy(unittest.TestCase):

    def _adopted_with_missing_link(self, root: Path) -> Path:
        _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
        (root / "alpha" / ".gemini" / "skills" / "alpha").unlink()  # missing
        return root

    def test_detect_finds_missing_link(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._adopted_with_missing_link(Path(tmp))
            reps = rt.detect_repairs(root)
            self.assertEqual(len(reps), 1)
            self.assertEqual(reps[0]["harness"], ".gemini")

    def test_clean_repo_no_repairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=True)
            self.assertEqual(rt.detect_repairs(root), [])

    def test_non_adopted_plugin_not_repaired(self):
        # skills present but ZERO harness symlinks -> not adopted -> left alone
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _make_plugin(root, "alpha", "1.0.0", skills=True, adopt=False)
            self.assertEqual(rt.detect_repairs(root), [])

    def test_preview_then_apply_repairs_and_backs_up(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._adopted_with_missing_link(Path(tmp))
            preview = rt.write_preview(root, rt.detect_repairs(root))
            self.assertTrue((preview / "summary.md").is_file())
            self.assertTrue((preview / "changes.json").is_file())
            self.assertTrue((preview / "files").is_dir())
            # live still broken before apply
            self.assertFalse((root / "alpha" / ".gemini" / "skills" / "alpha").is_symlink())
            backup = rt.apply_preview(root)
            link = root / "alpha" / ".gemini" / "skills" / "alpha"
            self.assertTrue(link.is_symlink())
            self.assertEqual(link.resolve(), (root / "alpha" / "skills" / "alpha").resolve())
            self.assertTrue(backup.is_dir())
            self.assertFalse((root / rt.PREVIEW_DIR_NAME).exists())  # preview consumed

    def test_idempotent_second_detect_empty_after_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = self._adopted_with_missing_link(Path(tmp))
            rt.write_preview(root, rt.detect_repairs(root))
            rt.apply_preview(root)
            self.assertEqual(rt.detect_repairs(root), [])


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure** — `python3 -m unittest test_repo_tidy -v`. Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `adjudant/scripts/repo_tidy.py`**

```python
#!/usr/bin/env python3
"""Adjudant repo_tidy — safe two-phase repo repair (symlink repair only).

Mirrors tidy.py: `preview` writes .adjudant-repo-tidy-preview/, `apply` backs
the live state up to .adjudant-repo-tidy-backup/{ts}/*.legacy then repairs.
Only repairs harness symlinks on ALREADY-ADOPTED plugins — never auto-adopts
a harness where none exists (that is ramasse-tier, deferred). Stdlib only.

CLI:  python3 repo_tidy.py {detect|preview|apply} --project-dir PATH
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from repo_walk import HARNESS_DIRS, plugin_symlink_status, walk_plugins

PREVIEW_DIR_NAME = ".adjudant-repo-tidy-preview"
BACKUP_DIR_NAME = ".adjudant-repo-tidy-backup"


def detect_repairs(root: Path) -> list[dict[str, Any]]:
    """Missing/dangling harness symlinks on adopted plugins, with the relative
    target the repaired symlink should point at (../../skills/<name>)."""
    repairs: list[dict[str, Any]] = []
    for p in walk_plugins(root):
        st = plugin_symlink_status(p)
        if not st["adopted"]:
            continue
        # canonical skill dir name = the first real dir under skills/
        canon = next((c for c in sorted((p.dir / "skills").iterdir())
                      if c.is_dir() and not c.name.startswith(".")), None)
        if canon is None:
            continue
        for h, state in st["links"].items():
            if state in ("missing", "dangling"):
                repairs.append({
                    "plugin": p.name,
                    "source_dir": p.source,
                    "harness": h,
                    "state": state,
                    "canon_name": canon.name,
                    "link_rel": str(Path(p.source) / h / "skills" / canon.name),
                    "target_rel": str(Path("../../skills") / canon.name),
                })
    return repairs


def write_preview(root: Path, repairs: list[dict[str, Any]]) -> Path:
    preview = root / PREVIEW_DIR_NAME
    if preview.exists():
        shutil.rmtree(preview)
    (preview / "files").mkdir(parents=True)
    (preview / "changes.json").write_text(json.dumps({"repairs": repairs}, indent=2) + "\n")
    lines = ["# repo-tidy preview", "", f"{len(repairs)} symlink repair(s):", ""]
    for r in repairs:
        lines.append(f"- `{r['link_rel']}` → `{r['target_rel']}` (was {r['state']})")
    (preview / "summary.md").write_text("\n".join(lines) + "\n")
    # record intended targets as plain files under files/ (audit trail)
    for i, r in enumerate(repairs):
        (preview / "files" / f"repair-{i:03d}.txt").write_text(
            f"{r['link_rel']} -> {r['target_rel']}\n")
    return preview


def apply_preview(root: Path) -> Path:
    preview = root / PREVIEW_DIR_NAME
    if not preview.is_dir():
        raise FileNotFoundError(f"no preview at {preview} — run preview first")
    changes = json.loads((preview / "changes.json").read_text())
    repairs = changes.get("repairs", [])
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_dir = root / BACKUP_DIR_NAME / timestamp
    backup_dir.mkdir(parents=True, exist_ok=True)
    for r in repairs:
        link = root / r["link_rel"]
        # back up the current state of the link path (dangling target record)
        rec = backup_dir / (r["link_rel"].replace("/", "__") + ".legacy")
        prior = ""
        if link.is_symlink():
            try:
                prior = os.readlink(link)
            except OSError:
                prior = ""
        rec.write_text(f"state-before: {r['state']}\nprior-target: {prior}\n")
        # repair: remove any existing (dangling) link, recreate relative symlink
        link.parent.mkdir(parents=True, exist_ok=True)
        if link.is_symlink() or link.exists():
            try:
                link.unlink()
            except OSError:
                pass
        os.symlink(r["target_rel"], link)
    shutil.rmtree(preview)
    return backup_dir


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="repo_tidy.py", description="Adjudant repo tidy — symlink repair.")
    parser.add_argument("phase", choices=["detect", "preview", "apply"])
    parser.add_argument("--project-dir", default=".", help="Repo root (default: cwd)")
    args = parser.parse_args(argv)
    root = Path(args.project_dir).expanduser().resolve()
    if not root.is_dir():
        print(f"error: project-dir not found: {root}", file=sys.stderr)
        return 1
    if args.phase == "detect":
        print(json.dumps({"repairs": detect_repairs(root)}, indent=2))
    elif args.phase == "preview":
        p = write_preview(root, detect_repairs(root))
        print(f"[repo_tidy] preview at {p}", file=sys.stderr)
        print(str(p))
    else:
        try:
            b = apply_preview(root)
        except FileNotFoundError as e:
            print(f"error: {e}", file=sys.stderr)
            return 1
        print(f"[repo_tidy] applied; backup at {b}", file=sys.stderr)
        print(str(b))
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
```

- [ ] **Step 4: Run to verify pass** — `python3 -m unittest test_repo_tidy -v`. Expected: all PASS.
- [ ] **Step 5: Commit**

```bash
git add adjudant/scripts/repo_tidy.py adjudant/scripts/test_repo_tidy.py
git commit -m "feat(adjudant): repo_tidy — two-phase symlink repair on adopted plugins (never auto-adopts)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 4: `repo-standards.md` + check.md/tidy.md target sections

**Files:**
- Create: `adjudant/skills/adjudant/reference/repo-standards.md`
- Modify: `adjudant/skills/adjudant/reference/check.md`, `adjudant/skills/adjudant/reference/tidy.md`

- [ ] **Step 1: Create `reference/repo-standards.md`** — must name each detector category (for `repo-standards-coverage` validator) and contain NO dead relative links (for `reference-doc-links`). Required category headings (exact substrings the validator will look for): `version coherence`, `symlink integrity`, `context files`, `plan age`, `registration`. Content: describe the marketplace conventions (marketplace.json ↔ plugin.json version parity, the Impeccable symlink pattern with `source`/`.claude`/`.gemini` → canonical `skills/<name>`, repo-root AGENTS.md+CLAUDE.md with `@AGENTS.md` import, plan-age policy, every plugin registered). Cross-links only to existing files or external URLs.

- [ ] **Step 2: Edit `reference/check.md`** — add a `## Target [vault|repo|all]` section: default `vault` (unchanged behavior); `repo` runs `python3 .../scripts/repo_scan.py --project-dir "$REPO_ROOT"` and renders the JSON (version-coherence table, symlink-integrity matrix for skills-bearing plugins, registration gaps, stale-plan list, repo-root context-file check, `drift_items`); `all` runs both the vault check and the repo scan and renders both. Note `repo`/`all` never write.

- [ ] **Step 3: Edit `reference/tidy.md`** — add a `## Target [vault|repo|all]` section: `repo` runs the two-phase `repo_tidy.py preview` then (on confirmation) `apply`, repairs adopted-plugin harness symlinks only, backs up to `.adjudant-repo-tidy-backup/{ts}/`. State plainly that `tidy repo` never auto-adopts a harness (that is deferred `ramasse` work) and that on a clean repo it is a no-op repair arm of `check repo`.

- [ ] **Step 4: Verify no dead links** — `python3 adjudant/scripts/validate.py` (the existing `reference-doc-links` validator must stay green with the new file present).
- [ ] **Step 5: Commit**

```bash
git add adjudant/skills/adjudant/reference/repo-standards.md adjudant/skills/adjudant/reference/check.md adjudant/skills/adjudant/reference/tidy.md
git commit -m "docs(adjudant): repo-standards.md + check/tidy [vault|repo|all] target sections

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 5: Five validators + tests + .gitignore

**Files:**
- Modify: `adjudant/scripts/validate.py`, `adjudant/scripts/test_validate.py`, `.gitignore`

**Interfaces:** mirror existing validators exactly. `repo-helper-parity` checks `repo_walk.py`/`repo_scan.py`/`repo_tidy.py` + their `test_*.py` exist. `repo-standards-coverage` checks `reference/repo-standards.md` exists and contains each category substring. The three repo-tidy validators mirror `tidy-preview-coherence` (#11), `tidy-backup-integrity` (#12), `gitignore-includes-tidy-dirs` (#13) with `.adjudant-repo-tidy-preview`/`.adjudant-repo-tidy-backup`.

- [ ] **Step 1: Add tests to `test_validate.py`** — for each of the 5 validators: a pass case and a fail case, following the existing `_PatchedTree`/temp-tree pattern (e.g. `repo-helper-parity` fails when a `repo_*.py` lacks its test; `repo-standards-coverage` fails when a category substring is missing; the three tidy-mirror validators fail on an incoherent preview / a backup dir with files but no `.legacy` / a missing gitignore entry). Assert on the failure-message substrings you choose.
- [ ] **Step 2: Run to verify failure** — `python3 -m unittest test_validate -v`. Expected: new tests FAIL (validators not defined).
- [ ] **Step 3: Implement the 5 validators in `validate.py`** — add `validate_repo_helper_parity`, `validate_repo_standards_coverage`, `validate_repo_tidy_preview_coherence`, `validate_repo_tidy_backup_integrity`, `validate_gitignore_includes_repo_tidy_dirs`; call them in `main()`; extend the module docstring's numbered list to 22. Reuse `_gitignore_active_entries` for the gitignore check. `repo-helper-parity`:

```python
def validate_repo_helper_parity(r: Result) -> None:
    name = "repo-helper-parity"
    scripts = ROOT / "scripts"
    missing = []
    for base in ("repo_walk", "repo_scan", "repo_tidy"):
        if not (scripts / f"{base}.py").is_file():
            missing.append(f"{base}.py")
        if not (scripts / f"test_{base}.py").is_file():
            missing.append(f"test_{base}.py")
    if missing:
        r.add_fail(name, f"missing repo helper/test files: {missing}")
        return
    r.add_pass(name)
```

`repo-standards-coverage`:

```python
REPO_STANDARD_CATEGORIES = ("version coherence", "symlink integrity", "context files", "plan age", "registration")

def validate_repo_standards_coverage(r: Result) -> None:
    name = "repo-standards-coverage"
    f = REFERENCE / "repo-standards.md"
    if not f.is_file():
        r.add_fail(name, "reference/repo-standards.md missing")
        return
    text = f.read_text().lower()
    missing = [c for c in REPO_STANDARD_CATEGORIES if c not in text]
    if missing:
        r.add_fail(name, f"repo-standards.md missing categories: {missing}")
        return
    r.add_pass(name)
```

The three tidy-mirror validators copy `validate_tidy_preview_coherence` / `validate_tidy_backup_integrity` / `validate_gitignore_includes_tidy_dirs` verbatim, swapping the dir constants to `.adjudant-repo-tidy-preview` / `.adjudant-repo-tidy-backup`.

- [ ] **Step 4: Add `.gitignore` entries** — append `.adjudant-repo-tidy-preview/` and `.adjudant-repo-tidy-backup/` to the repo-root `.gitignore` (near the existing `.adjudant-tidy-*` entries).
- [ ] **Step 5: Run to verify pass** — `python3 -m unittest test_validate -v` (all PASS) and `python3 adjudant/scripts/validate.py` (prints `PASS — 22 validator(s) green`).
- [ ] **Step 6: Commit**

```bash
git add adjudant/scripts/validate.py adjudant/scripts/test_validate.py .gitignore
git commit -m "feat(adjudant): validators 18-22 — repo-helper-parity, repo-standards-coverage, repo-tidy preview/backup/gitignore

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 6: Dispatch surface (command-metadata + SKILL router)

**Files:**
- Modify: `adjudant/scripts/command-metadata.json`, `adjudant/skills/adjudant/SKILL.md`

**Constraint:** do NOT change any version field here (all stay 0.12.0 → version-consistency passes).

- [ ] **Step 1: Edit `command-metadata.json`** — change `check` and `tidy` `argumentHint` from `"(no args)"` to `"[vault|repo|all]"`. Update their `description` fields to mention the repo target while staying ≤220 chars (e.g. check: `"Read-only summary — project + vault snapshot, schema compliance; [vault|repo|all] also audits repo structure (versions, symlinks, registration, stale plans). Never writes."`). Leave version at `0.12.0`.
- [ ] **Step 2: Edit `SKILL.md`** — in the verb-router table, note the `[vault|repo|all]` target on the `check` and `tidy` rows; add `- \`reference/repo-standards.md\` — repo conventions (check/tidy repo target)` to the Content authoring list; update the `argument-hint` frontmatter's check/tidy hints if enumerated. Leave frontmatter `version: 0.12.0`.
- [ ] **Step 3: Verify gates** — `python3 adjudant/scripts/validate.py` (22 green: `command-metadata-coherence`, `reference-files-exist` for the new repo-standards.md path, `verb-description-length` all pass) and `python3 -m unittest discover -s adjudant/scripts -p 'test_*.py'`.
- [ ] **Step 4: Commit**

```bash
git add adjudant/scripts/command-metadata.json adjudant/skills/adjudant/SKILL.md
git commit -m "feat(adjudant): wire check/tidy [vault|repo|all] into command-metadata + SKILL router

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Task 7: Version bump 0.13.0 + docs + final gates

**Files:**
- Modify (via script): `plugin.json`, `command-metadata.json`, `SKILL.md`, `marketplace.json`
- Modify: `adjudant/README.md`, `AGENTS.md`

- [ ] **Step 1: Bump** — `python3 scripts/bump_plugin_version.py adjudant 0.13.0` (rewrites all four version files atomically).
- [ ] **Step 2: Update README** — verb table: note the `[vault|repo|all]` target on check/tidy and add `repo_walk.py`/`repo_scan.py`/`repo_tidy.py` to the Python-helpers list; bump the Drift-defense count to `22 validators` and the Tests count to the new total (run the suite to get the exact number).
- [ ] **Step 3: Update AGENTS.md** — the Project Structure tree line for adjudant → `# v0.13.0 — …`.
- [ ] **Step 4: Full gates** —
  - `python3 -m unittest discover -s adjudant/scripts -p 'test_*.py'` → OK
  - `python3 adjudant/scripts/validate.py` → `PASS — 22 validator(s) green`
  - `python3 scripts/check_marketplace_versions.py` → PASS
  - `python3 -m unittest discover -s scripts -p 'test_*.py'` → OK (bump-script tests)
- [ ] **Step 5: End-to-end smoke** — `python3 adjudant/scripts/repo_scan.py --project-dir . --today <today>` renders clean; `python3 adjudant/scripts/repo_tidy.py detect --project-dir .` → `{"repairs": []}` (nothing to fix on the clean repo).
- [ ] **Step 6: Commit release**

```bash
git add -A
git commit -m "release(adjudant): v0.13.0 — repo as a second audit/repair target (check/tidy [vault|repo|all])

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-review notes (author)

- **Spec coverage:** check repo (Tasks 2+4+6), tidy repo symlink-repair (Tasks 3+4+6), layered detectors (Task 2), version reuse read-only (Task 2 `detect_version_coherence`), informational per-plugin context (Task 2 test), 5 validators (Task 5), repo-standards.md (Task 4), back-compat default vault (Tasks 4+6 keep default), version bump 0.13.0 (Task 7), housekeeping of superseded docs (done at design-commit time). `ramasse repo` / version-fixer explicitly out of scope — no task, by design.
- **Version lockstep:** Tasks 1–6 never touch a version field; Task 7 is the sole bump. Pre-commit `version-consistency` stays green throughout.
- **Ordering dependency:** Task 5's `repo-helper-parity` needs Tasks 1–3; `repo-standards-coverage` needs Task 4 — Task 5 is correctly placed after both.
- **Type consistency:** `PluginInfo` fields, `plugin_symlink_status` return shape, and `PREVIEW_DIR_NAME`/`BACKUP_DIR_NAME` are used identically across repo_scan/repo_tidy/tests.
