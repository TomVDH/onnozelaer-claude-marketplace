# Adjudant v0.14.0 Implementation Plan: cost gate, shelf lifecycle, connect contract, voice layer

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship adjudant 0.14.0 with token-cost estimation + confirm gate, a six-state project lifecycle behind a new `shelf` verb with status-driven vault zones, a standardized `connect` contract (infer, confirm once, receipt, GEMINI.md), and an enforceable voice layer.

**Architecture:** All new logic lands in the existing stdlib-only Python helper layer under `adjudant/scripts/`, following the established patterns: shared primitives in `_vault_walk.py` / new `_cost.py`, per-verb helper CLIs emitting JSON for Claude to render, two-phase preview→apply with backups for anything that writes, and drift defense via `validate.py` validators. The SKILL.md router carries the locked cost-gate and voice rules.

**Tech Stack:** Python 3 stdlib only (no pip deps). Tests: `unittest`, run via `python3 -m unittest discover -p 'test_*.py'` from `adjudant/scripts/`. Validators: `python3 adjudant/scripts/validate.py`.

**Spec:** `docs/superpowers/specs/2026-07-16-adjudant-cost-status-voice-design.md` (approved 2026-07-16).

## Global Constraints

- Stdlib only in `adjudant/scripts/` — no third-party imports.
- All commands below run from `adjudant/scripts/` unless a path is shown.
- Full suite must stay green: `python3 -m unittest discover -p 'test_*.py'` (479 tests before this plan).
- Validators must stay green after every task: `python3 adjudant/scripts/validate.py` (22 before this plan, 24 after).
- Status vocabulary (locked): `active | stale | fridge | done | dead | seed`.
- Zones (locked): `projects/` holds active+stale+seed, `projects/_fridge/` holds fridge, `projects/_archive/` holds done+dead.
- Cost heuristic (locked): `est_tokens = bytes // 4`; default warn threshold 30000; breadcrumb keys `cost_warn_tokens`, `stale_after_days` (default 30).
- Machines suggest status only along the active↔stale axis. Never write a status transition automatically.
- Voice: no em dashes in `templates/*.md` (validator-enforced) or in any NEW prose this plan adds to templates; new reference/SKILL prose should also avoid them. No banned-lexicon terms in `templates/`, `SKILL.md`, `reference/*.md` (except `voice.md` itself).
- Commit after every task, conventional-commits style, scope `adjudant`. Do NOT use `--no-verify`.
- Version files are only ever bumped via `python3 scripts/bump_plugin_version.py adjudant 0.14.0` (repo root), in the final task.
- `--estimate-only` walks must use `stat()` only — never open file contents.

---

### Task 1: `_cost.py` primitives + verb weights in command-metadata

**Files:**
- Create: `adjudant/scripts/_cost.py`
- Create: `adjudant/scripts/test_cost.py`
- Modify: `adjudant/scripts/command-metadata.json` (add `"weight"` to all 10 existing verbs)

**Interfaces:**
- Consumes: `_vault_walk.DEFAULT_SKIP`, `_vault_walk.parse_breadcrumb` (both exist).
- Produces: `est_tokens(n_bytes: int) -> int`, `stat_walk(root: Path, exts: tuple = (".md",), skip: tuple = DEFAULT_SKIP) -> tuple[int, int]`, `breadcrumb_int(code_root: Optional[Path], key: str, default: int) -> int`, `read_threshold(code_root: Optional[Path]) -> int`, `cost_block(files: int, n_bytes: int, threshold: int) -> dict`, `verb_weights() -> dict[str, str]`, constants `DEFAULT_WARN_TOKENS = 30000`, `VALID_WEIGHTS = ("light", "medium", "heavy")`. Tasks 2, 3, 7 import these.

- [ ] **Step 1: Write the failing tests**

Create `adjudant/scripts/test_cost.py`:

```python
"""Tests for adjudant/scripts/_cost.py."""

import json
import tempfile
import unittest
from pathlib import Path

from _cost import (
    DEFAULT_WARN_TOKENS,
    VALID_WEIGHTS,
    breadcrumb_int,
    cost_block,
    est_tokens,
    read_threshold,
    stat_walk,
    verb_weights,
)


class TestEstTokens(unittest.TestCase):

    def test_bytes_div_4(self):
        self.assertEqual(est_tokens(400), 100)

    def test_zero_and_negative(self):
        self.assertEqual(est_tokens(0), 0)
        self.assertEqual(est_tokens(-10), 0)


class TestStatWalk(unittest.TestCase):

    def test_counts_md_only_by_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("x" * 100)
            (root / "b.md").write_text("y" * 50)
            (root / "c.py").write_text("z" * 999)
            files, n_bytes = stat_walk(root)
            self.assertEqual(files, 2)
            self.assertEqual(n_bytes, 150)

    def test_skips_default_dirs_and_legacy(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            (root / ".git" / "x.md").write_text("skip")
            (root / "_legacy").mkdir()
            (root / "_legacy" / "y.md").write_text("skip")
            (root / "keep.md").write_text("1234")
            files, n_bytes = stat_walk(root)
            self.assertEqual(files, 1)
            self.assertEqual(n_bytes, 4)

    def test_exts_parameter(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.md").write_text("aaaa")
            (root / "b.py").write_text("bbbb")
            (root / "c.json").write_text("cccc")
            files, n_bytes = stat_walk(root, exts=(".md", ".py", ".json"))
            self.assertEqual(files, 3)
            self.assertEqual(n_bytes, 12)

    def test_missing_root(self):
        self.assertEqual(stat_walk(Path("/nonexistent-adjudant-test")), (0, 0))


class TestThreshold(unittest.TestCase):

    def test_default_when_no_breadcrumb(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(read_threshold(Path(tmp)), DEFAULT_WARN_TOKENS)

    def test_default_when_none(self):
        self.assertEqual(read_threshold(None), DEFAULT_WARN_TOKENS)

    def test_breadcrumb_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "adjudant").write_text(
                "vault_name: V\nslug: s\ncost_warn_tokens: 90000\n")
            self.assertEqual(read_threshold(root), 90000)

    def test_breadcrumb_garbage_falls_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "adjudant").write_text("cost_warn_tokens: lots\n")
            self.assertEqual(read_threshold(root), DEFAULT_WARN_TOKENS)

    def test_breadcrumb_int_generic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude").mkdir()
            (root / ".claude" / "adjudant").write_text("stale_after_days: 45\n")
            self.assertEqual(breadcrumb_int(root, "stale_after_days", 30), 45)
            self.assertEqual(breadcrumb_int(root, "missing_key", 7), 7)


class TestCostBlock(unittest.TestCase):

    def test_below_threshold(self):
        block = cost_block(10, 4000, 30000)
        self.assertEqual(block, {
            "est_read_tokens": 1000, "files": 10, "bytes": 4000,
            "threshold": 30000, "warn": False,
        })

    def test_at_threshold_warns(self):
        block = cost_block(1, 120000, 30000)
        self.assertEqual(block["est_read_tokens"], 30000)
        self.assertTrue(block["warn"])


class TestVerbWeights(unittest.TestCase):

    def test_every_verb_has_valid_weight(self):
        weights = verb_weights()
        meta = json.loads(
            (Path(__file__).resolve().parent / "command-metadata.json").read_text())
        self.assertEqual(set(weights), {v["name"] for v in meta["verbs"]})
        for verb, w in weights.items():
            self.assertIn(w, VALID_WEIGHTS, f"{verb} has invalid weight {w!r}")

    def test_locked_heavy_set(self):
        weights = verb_weights()
        self.assertEqual(weights["dream"], "heavy")
        self.assertEqual(weights["ramasse"], "heavy")
        self.assertEqual(weights["connect"], "light")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_cost -v`
Expected: FAIL / ERROR with `ModuleNotFoundError: No module named '_cost'`

- [ ] **Step 3: Write `_cost.py`**

Create `adjudant/scripts/_cost.py`:

```python
#!/usr/bin/env python3
"""Adjudant cost primitives: token-cost estimation for heavy verbs.

Stdlib-only. Read-only: uses stat() sizes exclusively, never opens files.

The estimate approximates what Claude will READ back into context (the
helper's JSON plus prose the verb sends Claude to read), not what Python
scans. `bytes // 4` is the locked heuristic (ASCII-dominant markdown).

Public API:
    est_tokens(n_bytes) -> int
    stat_walk(root, exts=(".md",), skip=DEFAULT_SKIP) -> (files, bytes)
    breadcrumb_int(code_root, key, default) -> int
    read_threshold(code_root) -> int          # breadcrumb cost_warn_tokens or 30000
    cost_block(files, n_bytes, threshold) -> dict
    verb_weights() -> dict[str, str]           # verb name -> light|medium|heavy
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from _vault_walk import DEFAULT_SKIP, parse_breadcrumb

DEFAULT_WARN_TOKENS = 30000
VALID_WEIGHTS = ("light", "medium", "heavy")
METADATA_PATH = Path(__file__).resolve().parent / "command-metadata.json"


def est_tokens(n_bytes: int) -> int:
    """bytes // 4: the locked chars-per-token heuristic."""
    return max(0, int(n_bytes)) // 4


def stat_walk(
    root: Path,
    exts: tuple[str, ...] = (".md",),
    skip: tuple[str, ...] = DEFAULT_SKIP,
) -> tuple[int, int]:
    """(file_count, total_bytes) for files under root with the given suffixes.

    stat() only, never opens a file. Skips DEFAULT_SKIP dirs plus _legacy/.
    """
    skip_set = set(skip) | {"_legacy"}
    if not root.is_dir():
        return 0, 0
    files = 0
    total = 0
    for f in root.rglob("*"):
        if not f.is_file() or f.suffix not in exts:
            continue
        try:
            rel = f.relative_to(root)
        except ValueError:
            continue
        if any(part in skip_set for part in rel.parts):
            continue
        try:
            total += f.stat().st_size
        except OSError:
            continue
        files += 1
    return files, total


def breadcrumb_int(code_root: Optional[Path], key: str, default: int) -> int:
    """Integer breadcrumb field with fallback (bad values fall back silently)."""
    if code_root:
        bc = parse_breadcrumb(Path(code_root))
        if bc and key in bc:
            try:
                return max(1, int(bc[key]))
            except (TypeError, ValueError):
                pass
    return default


def read_threshold(code_root: Optional[Path]) -> int:
    return breadcrumb_int(code_root, "cost_warn_tokens", DEFAULT_WARN_TOKENS)


def cost_block(files: int, n_bytes: int, threshold: int) -> dict:
    est = est_tokens(n_bytes)
    return {
        "est_read_tokens": est,
        "files": files,
        "bytes": n_bytes,
        "threshold": threshold,
        "warn": est >= threshold,
    }


def verb_weights() -> dict[str, str]:
    meta = json.loads(METADATA_PATH.read_text())
    return {v["name"]: v.get("weight", "") for v in meta.get("verbs", [])}
```

- [ ] **Step 4: Add `weight` to every verb in `command-metadata.json`**

In `adjudant/scripts/command-metadata.json`, add a `"weight"` key to each verb object (after `"reference"`), exactly these values:

| verb | weight |
|---|---|
| connect | light |
| port | medium |
| sync | light |
| check | medium |
| sitrep | medium |
| tidy | medium |
| ramasse | heavy |
| dream | heavy |
| draw | light |
| board | light |

Example for one entry (repeat the pattern for all 10):

```json
    {
      "name": "dream",
      "description": "Content/knowledge/memory refresh — the third, semantic cleanup tier. dream.py (read-only) emits a 10-category staleness/contradiction/redundancy catalog; Claude judges, superpowers executes with backups.",
      "argumentHint": "(no args)",
      "reference": "reference/dream.md",
      "weight": "heavy"
    },
```

(`check` is `medium`; the `all` target's heavy handling is a router rule in Task 4, not a metadata value.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest test_cost -v`
Expected: PASS (all tests OK)

- [ ] **Step 6: Run full suite + validators**

Run: `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -2` — expected `OK`.
Run: `python3 validate.py 2>&1 | tail -2` — expected `PASS`. (Validator 5 checks verb names, not extra keys; `weight` is additive.)

- [ ] **Step 7: Commit**

```bash
git add adjudant/scripts/_cost.py adjudant/scripts/test_cost.py adjudant/scripts/command-metadata.json
git commit -m "feat(adjudant): _cost.py primitives — bytes//4 estimator, stat-only walk, breadcrumb threshold, verb weights"
```

---

### Task 2: cost wiring in `check.py` + `sitrep.py`

**Files:**
- Modify: `adjudant/scripts/check.py` (imports, `cli_main` around line 153-189)
- Modify: `adjudant/scripts/sitrep.py` (imports, `cli_main` around line 96-130)
- Modify: `adjudant/scripts/test_check.py`, `adjudant/scripts/test_sitrep.py` (append test classes)

**Interfaces:**
- Consumes: `_cost.stat_walk`, `_cost.cost_block`, `_cost.read_threshold` (Task 1).
- Produces: each helper's JSON gains a top-level `"cost"` object; each CLI gains `--estimate-only` which prints ONLY `{"cost": {...}}` and exits 0. Tasks 3 and 4 replicate/reference this exact pattern.

- [ ] **Step 1: Write the failing tests**

Append to `adjudant/scripts/test_check.py`:

```python
import io
import json as _json
import contextlib

from check import cli_main as check_cli


class TestCheckCost(unittest.TestCase):

    def _project(self, root: Path) -> None:
        _write(root / "brief.md",
            "---\ntype: project\nslug: t\nproject_type: coding\nstatus: active\n---\n\n# T\n")
        _write(root / "notes" / "a.md", "x" * 4000)

    def test_estimate_only_prints_cost_block_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_cli(["--project-dir", str(root), "--estimate-only"])
            self.assertEqual(rc, 0)
            payload = _json.loads(buf.getvalue())
            self.assertEqual(set(payload), {"cost"})
            self.assertEqual(
                set(payload["cost"]),
                {"est_read_tokens", "files", "bytes", "threshold", "warn"})
            self.assertEqual(payload["cost"]["files"], 2)

    def test_normal_run_includes_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._project(root)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = check_cli(["--project-dir", str(root)])
            self.assertEqual(rc, 0)
            payload = _json.loads(buf.getvalue())
            self.assertIn("cost", payload)
            self.assertIn("project", payload)
```

Append to `adjudant/scripts/test_sitrep.py` (same shape; adjust imports to that file's conventions):

```python
import io
import json as _json
import contextlib
import tempfile
import unittest
from pathlib import Path

from sitrep import cli_main as sitrep_cli


class TestSitrepCost(unittest.TestCase):

    def test_estimate_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "brief.md").write_text(
                "---\ntype: project\nslug: t\nproject_type: coding\nstatus: active\n---\n\n# T\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = sitrep_cli(["--project-dir", str(root), "--estimate-only"])
            self.assertEqual(rc, 0)
            payload = _json.loads(buf.getvalue())
            self.assertEqual(set(payload), {"cost"})

    def test_normal_run_includes_cost(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "brief.md").write_text(
                "---\ntype: project\nslug: t\nproject_type: coding\nstatus: active\n---\n\n# T\n")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = sitrep_cli(["--project-dir", str(root)])
            self.assertEqual(rc, 0)
            self.assertIn("cost", _json.loads(buf.getvalue()))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_check.TestCheckCost test_sitrep.TestSitrepCost -v`
Expected: FAIL (`unrecognized arguments: --estimate-only`, exit code 2 → SystemExit)

- [ ] **Step 3: Implement in `check.py`**

Add to imports (line 22 area):

```python
from _cost import cost_block, read_threshold, stat_walk
```

In `cli_main`, add the argument after `--out`:

```python
    parser.add_argument("--estimate-only", action="store_true",
                        help="Print only the cost block (stat-only walk) and exit")
```

After the `project_dir` resolution and the `not project_dir.is_dir()` error block (i.e. immediately before `report = run_check(project_dir)`), insert:

```python
    code_root = Path(args.project_dir).expanduser().resolve()
    files, n_bytes = stat_walk(project_dir)
    cost = cost_block(files, n_bytes, read_threshold(code_root))
    if args.estimate_only:
        print(json.dumps({"cost": cost}, indent=2))
        return 0
```

And after `report = run_check(project_dir)`:

```python
    report["cost"] = cost
```

(`code_root` only carries a breadcrumb when `--project-dir` pointed at a code root; when it pointed at the vault project directly, `parse_breadcrumb` finds nothing and the default threshold applies. That is correct behavior.)

- [ ] **Step 4: Implement in `sitrep.py`**

Same three edits: import line, `--estimate-only` argument, and the identical block inserted after `project_dir` resolution in `cli_main` (before `run_sitrep` is called), attaching `report["cost"] = cost` to the emitted dict.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest test_check test_sitrep -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add adjudant/scripts/check.py adjudant/scripts/sitrep.py adjudant/scripts/test_check.py adjudant/scripts/test_sitrep.py
git commit -m "feat(adjudant): cost block + --estimate-only on check and sitrep"
```

---

### Task 3: cost wiring in `tidy.py`, `dream.py`, `ramasse_scan.py`, `repo_scan.py`

**Files:**
- Modify: `adjudant/scripts/tidy.py` (`cli_main` around line 701), `adjudant/scripts/dream.py` (`cli_main` around line 790), `adjudant/scripts/ramasse_scan.py` (`cli_main` around line 440), `adjudant/scripts/repo_scan.py` (`cli_main` around line 121)
- Modify: `adjudant/scripts/test_tidy.py`, `test_dream.py`, `test_ramasse_scan.py`, `test_repo_scan.py` (append one test class each)

**Interfaces:**
- Consumes: `_cost.stat_walk`, `_cost.cost_block`, `_cost.read_threshold` (Task 1).
- Produces: `--estimate-only` on all four CLIs printing only `{"cost": {...}}`; `"cost"` in each normal JSON payload. `repo_scan.py` uses `exts=(".md", ".py", ".json")` since repo audits read code and manifests.

- [ ] **Step 1: Write the failing tests**

Append to each of the four test files a class following this exact template (shown for `test_dream.py`; replicate with the right module import and a minimal valid fixture for each — every one of these helpers accepts a bare project dir containing `brief.md`):

```python
import io
import json as _json
import contextlib

from dream import cli_main as dream_cli


class TestDreamCost(unittest.TestCase):

    def test_estimate_only_is_cost_only_and_stat_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "brief.md").write_text(
                "---\ntype: project\nslug: t\nproject_type: coding\nstatus: active\n---\n\n# T\n")
            (root / "notes").mkdir()
            (root / "notes" / "big.md").write_text("x" * 8000)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = dream_cli(["--project-dir", str(root), "--estimate-only"])
            self.assertEqual(rc, 0)
            payload = _json.loads(buf.getvalue())
            self.assertEqual(set(payload), {"cost"})
            self.assertGreaterEqual(payload["cost"]["est_read_tokens"], 2000)
```

For `test_tidy.py` the CLI takes a positional phase; use `tidy_cli(["detect", "--project-dir", str(root), "--estimate-only"])` and assert the cost block is the only output.

For `test_repo_scan.py`, build a fixture with one `.md`, one `.py`, one `.json` file and assert `payload["cost"]["files"] == 3` (proving the wider `exts`).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_tidy.TestTidyCost test_dream.TestDreamCost test_ramasse_scan.TestRamasseCost test_repo_scan.TestRepoScanCost -v`
Expected: FAIL (`unrecognized arguments: --estimate-only`)

- [ ] **Step 3: Implement**

In each of the four files:
1. Add import: `from _cost import cost_block, read_threshold, stat_walk`
2. Add `parser.add_argument("--estimate-only", action="store_true", help="Print only the cost block (stat-only walk) and exit")`
3. Insert immediately after the scan-dir resolution in `cli_main` (after `smart_project_dir(...)` for tidy/dream/ramasse_scan; after the repo root is resolved for repo_scan):

For `tidy.py`, `dream.py`, `ramasse_scan.py` (identical block):

```python
    code_root = Path(args.project_dir).expanduser().resolve()
    files_n, n_bytes = stat_walk(project_dir)
    cost = cost_block(files_n, n_bytes, read_threshold(code_root))
    if args.estimate_only:
        print(json.dumps({"cost": cost}, indent=2))
        return 0
```

For `repo_scan.py`:

```python
    code_root = Path(args.project_dir).expanduser().resolve()
    files_n, n_bytes = stat_walk(code_root, exts=(".md", ".py", ".json"))
    cost = cost_block(files_n, n_bytes, read_threshold(code_root))
    if args.estimate_only:
        print(json.dumps({"cost": cost}, indent=2))
        return 0
```

4. Attach `"cost"` to the normal JSON payload each helper emits: tidy adds it to the `detect` phase JSON dict; dream and ramasse_scan add `report["cost"] = cost` before dumping; repo_scan adds it to `run_scan`'s returned dict at the CLI layer (`scan["cost"] = cost`).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest test_tidy test_dream test_ramasse_scan test_repo_scan -v`
Expected: PASS

- [ ] **Step 5: Full suite + commit**

Run: `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -2` — expected `OK`.

```bash
git add adjudant/scripts/tidy.py adjudant/scripts/dream.py adjudant/scripts/ramasse_scan.py adjudant/scripts/repo_scan.py adjudant/scripts/test_tidy.py adjudant/scripts/test_dream.py adjudant/scripts/test_ramasse_scan.py adjudant/scripts/test_repo_scan.py
git commit -m "feat(adjudant): cost block + --estimate-only on tidy, dream, ramasse_scan, repo_scan"
```

---

### Task 4: the cost gate in SKILL.md + reference docs

**Files:**
- Modify: `adjudant/skills/adjudant/SKILL.md` (new section after "## The locked three-tier model")
- Modify: `adjudant/skills/adjudant/reference/dream.md`, `reference/ramasse.md`, `reference/check.md`, `reference/tidy.md`, `reference/sitrep.md` (one short pre-flight/cost note each)

**Interfaces:**
- Consumes: the `--estimate-only` flags (Tasks 2-3) and `weight` metadata (Task 1).
- Produces: the locked router rule every future verb obeys.

- [ ] **Step 1: Add the SKILL.md section**

Insert after the "## The locked three-tier model" section:

```markdown
## Cost gate (locked)

Verb weights live in `scripts/command-metadata.json` (`weight: light | medium | heavy`). The estimate approximates what Claude will read back into context; helpers compute it with a stat-only walk (`bytes // 4`).

- **Heavy verbs** (`dream`, `ramasse`, `check all`): run the backing helper with `--estimate-only` FIRST. If `cost.warn` is true, stop and show the numbers ("dream would pull ~85k tokens into context: 210 files, 1.1 MB prose") and ask the user to choose: proceed, scope down (offer only where the verb has a real scoping flag), or abort. Proceed only on explicit confirmation. If `warn` is false, run normally and include the estimate as one line in the rendered output.
- **Medium verbs** (`check`, `sitrep`, `tidy`, `port`): no pre-flight. The helper's JSON carries a `cost` block; render it as one line ("cost: ~12k tokens, 96 files").
- **Light verbs** (`connect`, `sync`, `draw`, `board`, `shelf`): no estimate; the static weight badge is enough.
- `check all` sums two estimates: `check.py --estimate-only` plus `repo_scan.py --estimate-only`.
- If an estimate cannot be computed (unresolvable vault or breadcrumb), treat it as `warn: true` and ask before proceeding.
- Threshold default is 30000 estimated read tokens; per-project override via `cost_warn_tokens:` in `.claude/adjudant`.
```

(Note: `shelf` appears in the light list; the verb itself lands in Tasks 7-9. Harmless forward reference within the same release.)

- [ ] **Step 2: Add one pre-flight note per reference doc**

In `reference/dream.md` and `reference/ramasse.md`, at the top of the flow/phases section, add:

```markdown
> **Cost pre-flight (locked).** Run the analyser with `--estimate-only` before the real scan. If `cost.warn` is true, stop and confirm with the user per the SKILL.md cost gate.
```

In `reference/check.md`, `reference/tidy.md`, `reference/sitrep.md`, in the rendering guidance, add:

```markdown
> Render the JSON `cost` block as one line: `cost: ~{est_read_tokens/1000}k tokens, {files} files`.
```

- [ ] **Step 3: Validate and commit**

Run: `python3 validate.py 2>&1 | tail -2` — expected `PASS` (validators 14/16 confirm reference files and links still resolve).

```bash
git add adjudant/skills/adjudant/SKILL.md adjudant/skills/adjudant/reference/
git commit -m "docs(adjudant): locked cost-gate rule in SKILL router + reference pre-flight notes"
```

---

### Task 5: status/zone primitives in `_vault_walk.py`

**Files:**
- Modify: `adjudant/scripts/_vault_walk.py` (new constants + functions in the schema-constants region around line 620; `DEFAULT_SKIP` at line 310; `resolve_project_from_cwd` at line 554)
- Modify: `adjudant/scripts/test__vault_walk.py` (append test classes)

**Interfaces:**
- Consumes: existing `parse_frontmatter`, `parse_breadcrumb`, `resolve_vault`.
- Produces (Tasks 6-10 depend on these exact names):
  - `PROJECT_STATUS_VALUES: tuple[str, ...] = ("active", "stale", "fridge", "done", "dead", "seed")`
  - `ZONE_FOR_STATUS: dict[str, str]` (active/stale/seed → `""`, fridge → `"_fridge"`, done/dead → `"_archive"`)
  - `PROJECT_ZONES: tuple[str, ...] = ("", "_fridge", "_archive")`
  - `DEFAULT_STALE_DAYS = 30`, `FRIDGE_NUDGE_DAYS = 180`
  - `newest_dated_stem(folder: Path) -> Optional[str]`
  - `suggest_status(declared: Optional[str], project_dir: Path, today: date, stale_after_days: int = DEFAULT_STALE_DAYS) -> dict`
  - `find_project_dir(vault: Path, slug: str) -> Optional[Path]`
  - `zone_of(project_dir: Path) -> str`
  - `zone_matches_status(status: Optional[str], zone: str) -> bool`
  - `enumerate_projects_all_zones(vault: Path) -> list[tuple[str, Path, str]]`
  - zone-aware `resolve_project_from_cwd` (vault_project_dir found across zones)

- [ ] **Step 1: Write the failing tests**

Append to `adjudant/scripts/test__vault_walk.py`:

```python
from datetime import date

from _vault_walk import (
    DEFAULT_STALE_DAYS,
    PROJECT_STATUS_VALUES,
    PROJECT_ZONES,
    ZONE_FOR_STATUS,
    enumerate_projects_all_zones,
    find_project_dir,
    newest_dated_stem,
    resolve_project_from_cwd,
    suggest_status,
    zone_matches_status,
    zone_of,
)


def _mk_project(vault: Path, slug: str, zone: str = "", status: str = "active",
                sessions: list = ()) -> Path:
    pdir = vault / "projects" / zone / slug if zone else vault / "projects" / slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "brief.md").write_text(
        f"---\ntype: project\nslug: {slug}\nproject_type: coding\nstatus: {status}\n---\n\n# {slug}\n")
    if sessions:
        (pdir / "sessions").mkdir(exist_ok=True)
        for d in sessions:
            (pdir / "sessions" / f"{d}.md").write_text("---\ntype: session\n---\n")
    return pdir


class TestStatusVocabulary(unittest.TestCase):

    def test_locked_values(self):
        self.assertEqual(PROJECT_STATUS_VALUES,
                         ("active", "stale", "fridge", "done", "dead", "seed"))

    def test_zone_map_total(self):
        self.assertEqual(set(ZONE_FOR_STATUS), set(PROJECT_STATUS_VALUES))
        self.assertEqual(ZONE_FOR_STATUS["fridge"], "_fridge")
        self.assertEqual(ZONE_FOR_STATUS["done"], "_archive")
        self.assertEqual(ZONE_FOR_STATUS["dead"], "_archive")
        self.assertEqual(ZONE_FOR_STATUS["active"], "")


class TestSuggestStatus(unittest.TestCase):

    def test_active_goes_stale_after_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = _mk_project(Path(tmp), "p", sessions=["2026-05-01"])
            out = suggest_status("active", pdir, date(2026, 7, 16))
            self.assertEqual(out["suggested"], "stale")
            self.assertEqual(out["days_quiet"], 76)
            self.assertIn("76 days", out["reason"])

    def test_active_stays_when_recent(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = _mk_project(Path(tmp), "p", sessions=["2026-07-10"])
            out = suggest_status("active", pdir, date(2026, 7, 16))
            self.assertIsNone(out["suggested"])

    def test_stale_suggests_active_on_new_activity(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = _mk_project(Path(tmp), "p", status="stale", sessions=["2026-07-15"])
            out = suggest_status("stale", pdir, date(2026, 7, 16))
            self.assertEqual(out["suggested"], "active")

    def test_deliberate_states_never_suggested_away(self):
        with tempfile.TemporaryDirectory() as tmp:
            for status in ("seed", "done", "dead"):
                pdir = _mk_project(Path(tmp), f"p-{status}", status=status,
                                   sessions=["2020-01-01"])
                out = suggest_status(status, pdir, date(2026, 7, 16))
                self.assertIsNone(out["suggested"], status)

    def test_fridge_nudges_after_180_days(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = _mk_project(Path(tmp), "p", status="fridge", sessions=["2025-06-01"])
            out = suggest_status("fridge", pdir, date(2026, 7, 16))
            self.assertIsNone(out["suggested"])
            self.assertIn("still intentional", out["nudge"])

    def test_invalid_declared_flagged_and_treated_active(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = _mk_project(Path(tmp), "p", status="paused", sessions=["2026-01-01"])
            out = suggest_status("paused", pdir, date(2026, 7, 16))
            self.assertFalse(out["declared_valid"])
            self.assertEqual(out["suggested"], "stale")

    def test_no_sessions_no_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = _mk_project(Path(tmp), "p")
            out = suggest_status("active", pdir, date(2026, 7, 16))
            self.assertIsNone(out["days_quiet"])
            self.assertIsNone(out["suggested"])

    def test_custom_threshold(self):
        with tempfile.TemporaryDirectory() as tmp:
            pdir = _mk_project(Path(tmp), "p", sessions=["2026-07-06"])
            out = suggest_status("active", pdir, date(2026, 7, 16), stale_after_days=7)
            self.assertEqual(out["suggested"], "stale")


class TestZones(unittest.TestCase):

    def test_find_project_dir_across_zones(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "alive")
            _mk_project(vault, "cold", zone="_fridge", status="fridge")
            _mk_project(vault, "gone", zone="_archive", status="dead")
            self.assertEqual(zone_of(find_project_dir(vault, "alive")), "")
            self.assertEqual(zone_of(find_project_dir(vault, "cold")), "_fridge")
            self.assertEqual(zone_of(find_project_dir(vault, "gone")), "_archive")
            self.assertIsNone(find_project_dir(vault, "nope"))

    def test_zone_matches_status(self):
        self.assertTrue(zone_matches_status("fridge", "_fridge"))
        self.assertFalse(zone_matches_status("fridge", ""))
        self.assertTrue(zone_matches_status("active", ""))
        self.assertFalse(zone_matches_status("dead", ""))
        self.assertTrue(zone_matches_status("not-a-status", "_archive"))

    def test_enumerate_all_zones(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "a")
            _mk_project(vault, "b", zone="_fridge", status="fridge")
            (vault / "projects" / "_index.md").write_text("idx")
            rows = enumerate_projects_all_zones(vault)
            self.assertEqual([(s, z) for s, _p, z in rows], [("a", ""), ("b", "_fridge")])

    def test_resolve_project_from_cwd_finds_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            _mk_project(vault, "proj", zone="_archive", status="done")
            code = root / "code"
            (code / ".claude").mkdir(parents=True)
            (code / ".claude" / "adjudant").write_text(
                f"vault_path: {vault}\nvault_name: vault\nslug: proj\nmode: project\n")
            ctx = resolve_project_from_cwd(code)
            self.assertTrue(ctx.is_connected)
            self.assertEqual(ctx.vault_project_dir,
                             vault / "projects" / "_archive" / "proj")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test__vault_walk -v 2>&1 | tail -5`
Expected: ImportError on the new names.

- [ ] **Step 3: Implement in `_vault_walk.py`**

Add `from datetime import date, datetime` to the imports at the top. Extend `DEFAULT_SKIP` (line ~310) with the two shelf scratch dirs:

```python
    ".adjudant-shelf-preview", ".adjudant-shelf-backup",
```

Add to the schema-constants region (after `INDEX_EXEMPT_FOLDERS`):

```python
# ============================================================
# Project status lifecycle + zones (locked 2026-07-16)
# ============================================================

PROJECT_STATUS_VALUES: tuple[str, ...] = ("active", "stale", "fridge", "done", "dead", "seed")
ZONE_FOR_STATUS: dict[str, str] = {
    "active": "", "stale": "", "seed": "",
    "fridge": "_fridge", "done": "_archive", "dead": "_archive",
}
PROJECT_ZONES: tuple[str, ...] = ("", "_fridge", "_archive")
DEFAULT_STALE_DAYS = 30
FRIDGE_NUDGE_DAYS = 180

_DATED_STEM_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})")


def newest_dated_stem(folder: Path) -> Optional[str]:
    """Most recent YYYY-MM-DD stem prefix among .md files in folder, else None."""
    if not folder.is_dir():
        return None
    dates: list[str] = []
    for f in folder.iterdir():
        if f.is_file() and f.suffix == ".md":
            m = _DATED_STEM_RE.match(f.stem)
            if m:
                dates.append(m.group(1))
    return max(dates) if dates else None


def suggest_status(
    declared: Optional[str],
    project_dir: Path,
    today: date,
    stale_after_days: int = DEFAULT_STALE_DAYS,
) -> dict[str, Any]:
    """Machine suggestion along the active/stale axis ONLY.

    fridge gets a nudge string after FRIDGE_NUDGE_DAYS; seed, done, dead are
    never suggested away. An invalid declared value is flagged
    (declared_valid=False) and treated as active for suggestion purposes.
    Never writes.
    """
    last = newest_dated_stem(project_dir / "sessions")
    days_quiet: Optional[int] = None
    if last:
        try:
            days_quiet = (today - datetime.strptime(last, "%Y-%m-%d").date()).days
        except ValueError:
            days_quiet = None
    valid = declared in PROJECT_STATUS_VALUES
    effective = declared if valid else "active"
    out: dict[str, Any] = {
        "declared": declared,
        "declared_valid": valid,
        "last_session": last,
        "days_quiet": days_quiet,
        "suggested": None,
        "reason": None,
        "nudge": None,
    }
    if effective == "active" and days_quiet is not None and days_quiet >= stale_after_days:
        out["suggested"] = "stale"
        out["reason"] = f"{days_quiet} days without a session note (threshold {stale_after_days})"
    elif effective == "stale" and days_quiet is not None and days_quiet < stale_after_days:
        out["suggested"] = "active"
        out["reason"] = f"session activity {days_quiet} days ago (threshold {stale_after_days})"
    elif effective == "fridge" and days_quiet is not None and days_quiet >= FRIDGE_NUDGE_DAYS:
        out["nudge"] = f"in the fridge {days_quiet} days, still intentional?"
    return out


def find_project_dir(vault: Path, slug: str) -> Optional[Path]:
    """Locate a project across zones. Prefers a dir containing brief.md."""
    candidates = [
        (vault / "projects" / zone / slug) if zone else (vault / "projects" / slug)
        for zone in PROJECT_ZONES
    ]
    for c in candidates:
        if (c / "brief.md").is_file():
            return c
    for c in candidates:
        if c.is_dir():
            return c
    return None


def zone_of(project_dir: Path) -> str:
    """'' | '_fridge' | '_archive' from the path shape projects[/zone]/slug."""
    parent = project_dir.parent.name
    return parent if parent in ("_fridge", "_archive") else ""


def zone_matches_status(status: Optional[str], zone: str) -> bool:
    """True when the folder zone agrees with the declared status.

    Unknown status values return True: the vocabulary problem is reported
    separately (declared_valid), not double-counted as a zone mismatch.
    """
    if status not in PROJECT_STATUS_VALUES:
        return True
    return ZONE_FOR_STATUS[status] == zone


def enumerate_projects_all_zones(vault: Path) -> list[tuple[str, Path, str]]:
    """Every project (slug, dir, zone) across projects/, _fridge/, _archive/.

    A project is a directory containing brief.md. Leading-underscore and dot
    dirs are skipped inside each zone. Sorted by zone order then slug.
    """
    out: list[tuple[str, Path, str]] = []
    base = vault / "projects"
    for zone in PROJECT_ZONES:
        zdir = (base / zone) if zone else base
        if not zdir.is_dir():
            continue
        for d in sorted(zdir.iterdir(), key=lambda p: p.name):
            if not d.is_dir() or d.name.startswith("_") or d.name.startswith("."):
                continue
            if (d / "brief.md").is_file():
                out.append((d.name, d, zone))
    return out
```

Then make `resolve_project_from_cwd` zone-aware — replace its return statement with:

```python
    vpd = find_project_dir(vault, bc["slug"]) or (vault / "projects" / bc["slug"])
    return ProjectContext(
        code_root=root,
        vault_path=vault,
        slug=bc["slug"],
        vault_project_dir=vpd,
    )
```

(`find_project_dir` is defined later in the file than `resolve_project_from_cwd`; module-level function resolution at call time makes that fine.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest test__vault_walk -v 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Full suite + commit**

Run: `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -2` — expected `OK`.

```bash
git add adjudant/scripts/_vault_walk.py adjudant/scripts/test__vault_walk.py
git commit -m "feat(adjudant): status vocabulary, zones, suggestion engine, zone-aware resolution in _vault_walk"
```

---

### Task 6: zone/status consumers — board, check, sitrep, sync

**Files:**
- Modify: `adjudant/scripts/board.py` (`enumerate_projects`, line 177-194)
- Modify: `adjudant/scripts/check.py` (`run_check`, line 134-150)
- Modify: `adjudant/scripts/sitrep.py` (`run_sitrep`, line 52-94)
- Modify: `adjudant/scripts/sync.py` (status guard at line 206)
- Modify: `adjudant/scripts/test_board.py`, `test_check.py`, `test_sitrep.py`, `test_sync.py`

**Interfaces:**
- Consumes: Task 5 primitives.
- Produces: `run_check`/`run_sitrep` JSON gains a `"status"` object `{declared, declared_valid, last_session, days_quiet, suggested, reason, nudge, zone, zone_matches}`; `board.enumerate_projects` sees all zones (signature unchanged); `sync` summary gains `"warnings"` list when the brief status is off-vocabulary.

- [ ] **Step 1: Write the failing tests**

`test_board.py` — append:

```python
class TestEnumerateZones(unittest.TestCase):

    def test_sees_fridge_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            for zone, slug in (("", "a"), ("_fridge", "b"), ("_archive", "c")):
                d = vault / "projects" / zone / slug if zone else vault / "projects" / slug
                d.mkdir(parents=True)
                (d / "brief.md").write_text("---\ntype: project\n---\n")
            slugs = [s for s, _ in enumerate_projects(vault)]
            self.assertEqual(slugs, ["a", "b", "c"])
```

`test_check.py` — append to `TestRunCheck`:

```python
    def test_status_block_with_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _write(root / "brief.md",
                "---\ntype: project\nslug: t\nproject_type: coding\nstatus: active\n---\n\n# T\n")
            (root / "sessions").mkdir()
            (root / "sessions" / "2026-01-01.md").write_text("---\ntype: session\n---\n")
            report = run_check(root)
            self.assertEqual(report["status"]["declared"], "active")
            self.assertEqual(report["status"]["suggested"], "stale")
            self.assertIn("zone", report["status"])
            self.assertIn("zone_matches", report["status"])
```

`test_sitrep.py` — append the analogous assertion on `run_sitrep(root)["status"]`.

`test_sync.py` — append (note: sync's CLI flag is `--project-dir`; it emits the summary JSON on stdout):

```python
import contextlib
import io
import json

from sync import cli_main as sync_cli


class TestStatusVocabularyGuard(unittest.TestCase):

    def _fixture(self, tmp: str, status: str, zone: str = "") -> Path:
        root = Path(tmp)
        vault = root / "vault"
        proj = vault / "projects" / zone / "p" if zone else vault / "projects" / "p"
        proj.mkdir(parents=True)
        (proj / "brief.md").write_text(
            f"---\ntype: project\nslug: p\nproject_type: coding\nstatus: {status}\n---\n\n# P\n")
        code = root / "code"
        (code / ".claude").mkdir(parents=True)
        (code / ".claude" / "adjudant").write_text(
            f"vault_path: {vault}\nvault_name: vault\nslug: p\nmode: project\n")
        return code

    def test_off_vocabulary_status_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = self._fixture(tmp, "paused")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                rc = sync_cli(["--project-dir", str(code)])
            self.assertEqual(rc, 0)
            summary = json.loads(buf.getvalue())
            self.assertTrue(any("paused" in w for w in summary.get("warnings", [])),
                            summary)

    def test_fridged_project_row_still_refreshes(self):
        with tempfile.TemporaryDirectory() as tmp:
            code = self._fixture(tmp, "fridge", zone="_fridge")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                rc = sync_cli(["--project-dir", str(code)])
            self.assertEqual(rc, 0)
            summary = json.loads(buf.getvalue())
            self.assertNotEqual(summary["steps"]["projects_index_row"], "project-missing")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_board test_check test_sitrep test_sync 2>&1 | tail -3`
Expected: FAIL (missing `status` key, missing zone enumeration, no warnings list)

- [ ] **Step 3: Implement**

`board.py` — replace the body of `enumerate_projects` with a delegation (keep name and signature; board's own callers and tests continue to work):

```python
from _vault_walk import enumerate_projects_all_zones  # add to existing import block


def enumerate_projects(vault: Path) -> list[tuple[str, Path]]:
    """Every project across projects/, projects/_fridge/, projects/_archive/.

    Filesystem truth (a dir containing brief.md); the _index.md table is
    never consulted. Sorted by zone order then slug.
    """
    return [(slug, path) for slug, path, _zone in enumerate_projects_all_zones(vault)]
```

`check.py` — extend imports:

```python
from datetime import date
from _cost import breadcrumb_int
from _vault_walk import (
    DEFAULT_STALE_DAYS, parse_frontmatter, resolve_vault, smart_project_dir,
    suggest_status, zone_matches_status, zone_of, VaultUnresolvableError,
)
```

Change `run_check` signature and body:

```python
def run_check(project_dir: Path, code_root: Optional[Path] = None,
              today: Optional[date] = None) -> dict[str, Any]:
    brief = _read_brief(project_dir)
    ...existing body unchanged...
    stale_days = breadcrumb_int(code_root, "stale_after_days", DEFAULT_STALE_DAYS)
    sug = suggest_status(
        brief.get("status") if brief.get("present") else None,
        project_dir, today or date.today(), stale_days)
    zone = zone_of(project_dir)
    status = {**sug, "zone": zone,
              "zone_matches": zone_matches_status(brief.get("status"), zone)}
    return {
        "project": brief,
        "counts": counts,
        "recent": recent,
        "handoff": handoff,
        "drift_signal": drift_signal,
        "status": status,
    }
```

In `cli_main`, pass the code root: `report = run_check(project_dir, code_root=code_root)`.

`sitrep.py` — same pattern inside `run_sitrep` (it already takes `now`; use `now.date()` as `today`, and thread `code_root` which the function already receives). Add the same `"status"` key to its returned dict.

`sync.py` — two changes, both in the zone/vocabulary axis:

1. `refresh_projects_index_row` (line 197) currently hardcodes `proj_dir = vault_path / "projects" / slug`, which reports `project-missing` for fridged/archived projects. Make it zone-aware:

```python
    proj_dir = find_project_dir(vault_path, slug) or (vault_path / "projects" / slug)
```

adding `find_project_dir` and `PROJECT_STATUS_VALUES` to sync's `_vault_walk` import block.

2. In `run_sync` (line 220), after the three steps are recorded, add the vocabulary guard (the brief lives at `ctx.vault_project_dir`, which Task 5 already made zone-aware):

```python
    fm, _ = parse_frontmatter(brief_path.read_text(errors="replace")) if brief_path.is_file() else (None, "")
    if fm is not None:
        status = fm.fields.get("status")
        if isinstance(status, str) and status not in PROJECT_STATUS_VALUES:
            summary.setdefault("warnings", []).append(
                f"brief status {status!r} is off-vocabulary "
                f"({' | '.join(PROJECT_STATUS_VALUES)}); row written as-is, fix via /adjudant shelf")
```

(`parse_frontmatter` is already imported in sync.py.)

- [ ] **Step 4: Run tests, full suite, commit**

Run: `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -2` — expected `OK`.

```bash
git add adjudant/scripts/board.py adjudant/scripts/check.py adjudant/scripts/sitrep.py adjudant/scripts/sync.py adjudant/scripts/test_board.py adjudant/scripts/test_check.py adjudant/scripts/test_sitrep.py adjudant/scripts/test_sync.py
git commit -m "feat(adjudant): zone-aware board enumeration, status suggestions in check/sitrep, sync vocabulary guard"
```

---

### Task 7: `shelf.py` — list phase

**Files:**
- Create: `adjudant/scripts/shelf.py`
- Create: `adjudant/scripts/test_shelf.py`

**Interfaces:**
- Consumes: Task 5 primitives; `_cost.breadcrumb_int`.
- Produces: `run_list(vault: Path, stale_days: int, today: date) -> dict` and `cli_main(argv) -> int` with phase `list`. Task 8 extends this same file with `plan_transition` / `write_preview` / `apply_transition`.

- [ ] **Step 1: Write the failing tests**

Create `adjudant/scripts/test_shelf.py`:

```python
"""Tests for adjudant/scripts/shelf.py."""

import contextlib
import io
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from shelf import cli_main as shelf_cli, run_list


def _mk_project(vault: Path, slug: str, zone: str = "", status: str = "active",
                sessions: list = ()) -> Path:
    pdir = vault / "projects" / zone / slug if zone else vault / "projects" / slug
    pdir.mkdir(parents=True, exist_ok=True)
    (pdir / "brief.md").write_text(
        f"---\ntype: project\nslug: {slug}\nproject_type: coding\nstatus: {status}\n"
        f"created: 2026-01-01\nupdated: 2026-01-01\ntags:\n  - project\n---\n\n# {slug}\n")
    if sessions:
        (pdir / "sessions").mkdir(exist_ok=True)
        for d in sessions:
            (pdir / "sessions" / f"{d}.md").write_text("---\ntype: session\n---\n")
    return pdir


class TestRunList(unittest.TestCase):

    def test_lists_all_zones_with_suggestions(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "hot", sessions=["2026-07-15"])
            _mk_project(vault, "quiet", sessions=["2026-03-01"])
            _mk_project(vault, "cold", zone="_fridge", status="fridge")
            _mk_project(vault, "shipped", zone="_archive", status="done")
            out = run_list(vault, stale_days=30, today=date(2026, 7, 16))
            rows = {r["slug"]: r for r in out["projects"]}
            self.assertEqual(set(rows), {"hot", "quiet", "cold", "shipped"})
            self.assertIsNone(rows["hot"]["suggested"])
            self.assertEqual(rows["quiet"]["suggested"], "stale")
            self.assertEqual(rows["cold"]["zone"], "_fridge")
            self.assertTrue(rows["cold"]["zone_matches"])
            self.assertTrue(rows["shipped"]["zone_matches"])

    def test_zone_mismatch_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "misfiled", status="dead")  # dead but in living zone
            out = run_list(vault, stale_days=30, today=date(2026, 7, 16))
            self.assertFalse(out["projects"][0]["zone_matches"])


class TestListCli(unittest.TestCase):

    def test_cli_list_via_vault_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "p", sessions=["2026-07-10"])
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = shelf_cli(["list", "--vault-dir", str(vault),
                                "--today", "2026-07-16"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertEqual(payload["projects"][0]["slug"], "p")
            self.assertEqual(payload["stale_after_days"], 30)


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_shelf -v`
Expected: `ModuleNotFoundError: No module named 'shelf'`

- [ ] **Step 3: Write `shelf.py` (list phase + CLI skeleton)**

Create `adjudant/scripts/shelf.py`:

```python
#!/usr/bin/env python3
"""Adjudant shelf — project lifecycle manager (verb #11).

list:    read-only status table of every project across zones, with the
         machine suggestion (active/stale axis only) beside the declared state.
preview: plan one transition; writes {vault}/.adjudant-shelf-preview/.
apply:   execute the transition — brief status + dated status-log line +
         zone folder move + vault-wide wikilink prefix rewrite +
         projects/_index.md row refresh. Backs up every modified file first.

CLI:
    python3 shelf.py list    (--project-dir PATH | --vault-dir PATH) [--stale-days N] [--today YYYY-MM-DD]
    python3 shelf.py preview (--project-dir PATH | --vault-dir PATH) --slug SLUG --to STATE [--reason TEXT]
    python3 shelf.py apply   (--project-dir PATH | --vault-dir PATH) --slug SLUG --to STATE [--reason TEXT]

--project-dir points at the code project root (breadcrumb flow); --vault-dir
names the vault directly. Machines never call apply without a prior preview.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from _cost import breadcrumb_int
from _vault_walk import (
    DEFAULT_SKIP,
    DEFAULT_STALE_DAYS,
    PROJECT_STATUS_VALUES,
    ZONE_FOR_STATUS,
    VaultUnresolvableError,
    enumerate_projects_all_zones,
    find_project_dir,
    parse_frontmatter,
    resolve_vault,
    smart_project_dir,
    suggest_status,
    zone_matches_status,
    zone_of,
)
from connect import (
    count_non_index_files,
    newest_session_date,
    upsert_projects_index_row,
)

PREVIEW_DIR = ".adjudant-shelf-preview"
BACKUP_DIR = ".adjudant-shelf-backup"
STATUS_LOG_HEADING = "## Status log"


def _resolve_vault_dir(project_dir_arg: str, vault_dir_arg: Optional[str]) -> Path:
    """Vault root from --vault-dir, the breadcrumb flow, or an upward walk."""
    if vault_dir_arg:
        v = Path(vault_dir_arg).expanduser().resolve()
        if v.is_dir():
            return v
        raise VaultUnresolvableError(f"--vault-dir not found: {v}")
    _scan_dir, hint = smart_project_dir(project_dir_arg)
    if hint:
        return hint
    arg = Path(project_dir_arg).expanduser().resolve()
    v = resolve_vault(arg)
    if v:
        return v
    raise VaultUnresolvableError(
        f"cannot resolve a vault from {project_dir_arg}; pass --vault-dir")


def run_list(vault: Path, stale_days: int, today: date) -> dict[str, Any]:
    """Read-only lifecycle table across all zones."""
    rows: list[dict[str, Any]] = []
    for slug, pdir, zone in enumerate_projects_all_zones(vault):
        fm, _ = parse_frontmatter((pdir / "brief.md").read_text(errors="replace"))
        declared = fm.fields.get("status")
        declared = declared if isinstance(declared, str) else None
        sug = suggest_status(declared, pdir, today, stale_days)
        rows.append({
            "slug": slug,
            "zone": zone,
            "zone_matches": zone_matches_status(declared, zone),
            **sug,
        })
    return {"vault": str(vault), "stale_after_days": stale_days, "projects": rows}


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="shelf.py",
        description="Adjudant shelf — project lifecycle (list / preview / apply).")
    parser.add_argument("phase", choices=["list", "preview", "apply"])
    parser.add_argument("--project-dir", default=".",
                        help="Code project root, breadcrumb flow (default: cwd)")
    parser.add_argument("--vault-dir", help="Vault root (bypasses breadcrumb)")
    parser.add_argument("--slug", help="Project slug (preview/apply)")
    parser.add_argument("--to", dest="to_state", help="Target state (preview/apply)")
    parser.add_argument("--reason", help="Optional reason recorded in the status log")
    parser.add_argument("--stale-days", type=int,
                        help="Override stale_after_days (list)")
    parser.add_argument("--today", help="YYYY-MM-DD override (testing/determinism)")
    args = parser.parse_args(argv)

    try:
        vault = _resolve_vault_dir(args.project_dir, args.vault_dir)
    except VaultUnresolvableError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    today = date.fromisoformat(args.today) if args.today else date.today()

    if args.phase == "list":
        stale_days = args.stale_days or breadcrumb_int(
            Path(args.project_dir).expanduser().resolve(),
            "stale_after_days", DEFAULT_STALE_DAYS)
        print(json.dumps(run_list(vault, stale_days, today), indent=2))
        return 0

    # preview / apply — implemented in Task 8
    print("error: preview/apply not yet implemented", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(cli_main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest test_shelf -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adjudant/scripts/shelf.py adjudant/scripts/test_shelf.py
git commit -m "feat(adjudant): shelf.py list phase — lifecycle table across vault zones"
```

---

### Task 8: `shelf.py` — preview + apply transitions

**Files:**
- Modify: `adjudant/scripts/shelf.py`
- Modify: `adjudant/scripts/test_shelf.py`

**Interfaces:**
- Consumes: Task 7 skeleton, `connect.upsert_projects_index_row(vault_path, slug, project_type, status, decisions_n, sessions_n, last_session) -> str`.
- Produces: `plan_transition(vault, slug, to_state, reason, today_str) -> dict`, `write_preview(vault, plan) -> Path`, `apply_transition(vault, plan) -> dict`, `set_brief_status(text, new_status, today_str) -> str`, `append_status_log(text, from_state, to_state, today_str, reason) -> str`. Reference doc (Task 9) documents this flow.

- [ ] **Step 1: Write the failing tests**

Append to `adjudant/scripts/test_shelf.py`:

```python
from shelf import (
    append_status_log,
    apply_transition,
    plan_transition,
    set_brief_status,
    write_preview,
)


class TestBriefEdits(unittest.TestCase):

    BRIEF = ("---\ntype: project\nslug: p\nproject_type: coding\nstatus: active\n"
             "created: 2026-01-01\nupdated: 2026-01-01\ntags:\n  - project\n---\n\n# P\n")

    def test_set_brief_status_rewrites_frontmatter_only(self):
        text = self.BRIEF + "\nBody mentions status: active in prose.\n"
        out = set_brief_status(text, "fridge", "2026-07-16")
        self.assertIn("status: fridge", out)
        self.assertIn("updated: 2026-07-16", out)
        self.assertIn("Body mentions status: active in prose.", out)
        self.assertEqual(out.count("status: fridge"), 1)

    def test_append_status_log_creates_section(self):
        out = append_status_log(self.BRIEF, "active", "fridge", "2026-07-16", "summer break")
        self.assertIn("## Status log", out)
        self.assertIn("- 2026-07-16: active → fridge (summer break)", out)

    def test_append_status_log_prepends_to_existing_section(self):
        first = append_status_log(self.BRIEF, "active", "fridge", "2026-07-01", None)
        second = append_status_log(first, "fridge", "active", "2026-07-16", None)
        self.assertEqual(second.count("## Status log"), 1)
        idx_new = second.index("2026-07-16: fridge → active")
        idx_old = second.index("2026-07-01: active → fridge")
        self.assertLess(idx_new, idx_old)


class TestTransition(unittest.TestCase):

    def _vault(self, tmp: str) -> Path:
        vault = Path(tmp)
        _mk_project(vault, "p", sessions=["2026-07-01"])
        other = vault / "projects" / "other"
        other.mkdir(parents=True)
        (other / "brief.md").write_text(
            "---\ntype: project\nslug: other\nproject_type: coding\nstatus: active\n---\n\n"
            "# Other\n\nSee [[projects/p/brief|p]] and [[projects/p/notes/idea]].\n")
        return vault

    def test_plan_counts_link_rewrites_and_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            plan = plan_transition(vault, "p", "fridge", "pause", "2026-07-16")
            self.assertTrue(plan["move_required"])
            self.assertEqual(plan["to_dir"], "projects/_fridge/p")
            files = {r["file"]: r["count"] for r in plan["link_rewrites"]}
            self.assertEqual(files.get("projects/other/brief.md"), 2)

    def test_plan_rejects_bad_state_and_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            with self.assertRaises(ValueError):
                plan_transition(vault, "p", "paused", None, "2026-07-16")
            with self.assertRaises(ValueError):
                plan_transition(vault, "ghost", "fridge", None, "2026-07-16")

    def test_same_zone_transition_needs_no_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            plan = plan_transition(vault, "p", "stale", None, "2026-07-16")
            self.assertFalse(plan["move_required"])
            self.assertEqual(plan["link_rewrites"], [])

    def test_apply_end_to_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            plan = plan_transition(vault, "p", "fridge", "pause", "2026-07-16")
            write_preview(vault, plan)
            result = apply_transition(vault, plan)
            new_dir = vault / "projects" / "_fridge" / "p"
            self.assertTrue(new_dir.is_dir())
            self.assertFalse((vault / "projects" / "p").exists())
            brief = (new_dir / "brief.md").read_text()
            self.assertIn("status: fridge", brief)
            self.assertIn("- 2026-07-16: active → fridge (pause)", brief)
            other = (vault / "projects" / "other" / "brief.md").read_text()
            self.assertIn("[[projects/_fridge/p/brief|p]]", other)
            self.assertIn("[[projects/_fridge/p/notes/idea]]", other)
            idx = (vault / "projects" / "_index.md").read_text()
            self.assertIn("| fridge |", idx)
            backups = list((vault / ".adjudant-shelf-backup").iterdir())
            self.assertEqual(len(backups), 1)
            self.assertTrue((backups[0] / "manifest.json").is_file())
            self.assertTrue((backups[0] / "projects" / "other" / "brief.md").is_file())
            self.assertFalse((vault / ".adjudant-shelf-preview").exists())
            self.assertEqual(result["moved"], True)

    def test_apply_refuses_existing_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            (vault / "projects" / "_fridge" / "p").mkdir(parents=True)
            plan = plan_transition(vault, "p", "fridge", None, "2026-07-16")
            with self.assertRaises(RuntimeError):
                apply_transition(vault, plan)
            # original untouched
            self.assertTrue((vault / "projects" / "p" / "brief.md").is_file())

    def test_apply_rolls_back_on_midflight_failure(self):
        from unittest import mock
        with tempfile.TemporaryDirectory() as tmp:
            vault = self._vault(tmp)
            before = (vault / "projects" / "other" / "brief.md").read_text()
            plan = plan_transition(vault, "p", "fridge", None, "2026-07-16")
            with mock.patch("shelf.shutil.move", side_effect=OSError("disk says no")):
                with self.assertRaises(RuntimeError):
                    apply_transition(vault, plan)
            # link rewrites reverted, folder never moved, brief untouched
            self.assertEqual(
                (vault / "projects" / "other" / "brief.md").read_text(), before)
            self.assertTrue((vault / "projects" / "p" / "brief.md").is_file())
            self.assertFalse((vault / "projects" / "_fridge" / "p").exists())


class TestTransitionCli(unittest.TestCase):

    def test_apply_without_preview_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "p")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
                rc = shelf_cli(["apply", "--vault-dir", str(vault),
                                "--slug", "p", "--to", "fridge"])
            self.assertEqual(rc, 1)

    def test_preview_then_apply(self):
        with tempfile.TemporaryDirectory() as tmp:
            vault = Path(tmp)
            _mk_project(vault, "p")
            for phase in ("preview", "apply"):
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = shelf_cli([phase, "--vault-dir", str(vault),
                                    "--slug", "p", "--to", "done",
                                    "--today", "2026-07-16"])
                self.assertEqual(rc, 0)
            self.assertTrue((vault / "projects" / "_archive" / "p" / "brief.md").is_file())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_shelf -v 2>&1 | tail -3`
Expected: ImportError on the new names.

- [ ] **Step 3: Implement in `shelf.py`**

Add after `run_list`:

```python
def set_brief_status(text: str, new_status: str, today_str: str) -> str:
    """Rewrite status: and updated: inside the frontmatter block only."""
    fm, body = parse_frontmatter(text)
    lines = fm.raw.split("\n") if fm.has_block else []
    replaced = bumped = False
    for i, ln in enumerate(lines):
        if ln.startswith("status:"):
            lines[i] = f"status: {new_status}"
            replaced = True
        elif ln.startswith("updated:"):
            lines[i] = f"updated: {today_str}"
            bumped = True
    if not replaced:
        lines.append(f"status: {new_status}")
    if not bumped:
        lines.append(f"updated: {today_str}")
    return "---\n" + "\n".join(lines) + "\n---\n" + body


def append_status_log(text: str, from_state: Optional[str], to_state: str,
                      today_str: str, reason: Optional[str]) -> str:
    """Dated transition line under ## Status log (newest first; section
    created at end of file on first transition)."""
    entry = f"- {today_str}: {from_state or 'unset'} → {to_state}"
    if reason:
        entry += f" ({reason})"
    lines = text.split("\n")
    for i, ln in enumerate(lines):
        if ln.strip() == STATUS_LOG_HEADING:
            j = i + 1
            while j < len(lines) and lines[j].strip() == "":
                j += 1
            lines.insert(j, entry)
            return "\n".join(lines)
    tail = "" if text.endswith("\n") else "\n"
    return text + tail + f"\n{STATUS_LOG_HEADING}\n\n{entry}\n"


def plan_transition(vault: Path, slug: str, to_state: str,
                    reason: Optional[str], today_str: str) -> dict[str, Any]:
    """Read-only plan: zones, folder move, vault-wide wikilink rewrites."""
    if to_state not in PROJECT_STATUS_VALUES:
        raise ValueError(
            f"invalid state {to_state!r}; one of: {', '.join(PROJECT_STATUS_VALUES)}")
    pdir = find_project_dir(vault, slug)
    if pdir is None or not (pdir / "brief.md").is_file():
        raise ValueError(
            f"project {slug!r} not found in projects/, projects/_fridge/, projects/_archive/")
    from_zone = zone_of(pdir)
    to_zone = ZONE_FOR_STATUS[to_state]
    fm, _ = parse_frontmatter((pdir / "brief.md").read_text(errors="replace"))
    from_state = fm.fields.get("status")
    old_prefix = f"[[projects/{from_zone + '/' if from_zone else ''}{slug}/"
    new_prefix = f"[[projects/{to_zone + '/' if to_zone else ''}{slug}/"
    move_required = old_prefix != new_prefix
    to_dir = (vault / "projects" / to_zone / slug) if to_zone else (vault / "projects" / slug)

    link_rewrites: list[dict[str, Any]] = []
    if move_required:
        skip_set = set(DEFAULT_SKIP) | {"_legacy"}
        for f in sorted(vault.rglob("*.md")):
            rel = f.relative_to(vault)
            if any(part in skip_set for part in rel.parts):
                continue
            try:
                n = f.read_text(errors="replace").count(old_prefix)
            except OSError:
                continue
            if n:
                link_rewrites.append({"file": str(rel), "count": n})

    return {
        "slug": slug,
        "reason": reason,
        "from_state": from_state if isinstance(from_state, str) else None,
        "to_state": to_state,
        "from_zone": from_zone,
        "to_zone": to_zone,
        "from_dir": str(pdir.relative_to(vault)),
        "to_dir": str(to_dir.relative_to(vault)),
        "move_required": move_required,
        "old_link_prefix": old_prefix,
        "new_link_prefix": new_prefix,
        "link_rewrites": link_rewrites,
        "today": today_str,
    }


def write_preview(vault: Path, plan: dict[str, Any]) -> Path:
    pdir = vault / PREVIEW_DIR
    if pdir.exists():
        shutil.rmtree(pdir)
    pdir.mkdir(parents=True)
    (pdir / "changes.json").write_text(json.dumps(plan, indent=2))
    (pdir / "summary.md").write_text("\n".join([
        f"# shelf preview: {plan['slug']} to {plan['to_state']}",
        "",
        f"- from: {plan['from_state']} ({plan['from_dir']})",
        f"- to:   {plan['to_state']} ({plan['to_dir']})",
        f"- folder move: {'yes' if plan['move_required'] else 'no'}",
        f"- files with links to rewrite: {len(plan['link_rewrites'])}",
        f"- reason: {plan['reason'] or '(none)'}",
        "",
    ]))
    return pdir


def apply_transition(vault: Path, plan: dict[str, Any]) -> dict[str, Any]:
    """Execute a planned transition. Backup first; abort before any write
    if the move target already exists."""
    slug = plan["slug"]
    from_dir = vault / plan["from_dir"]
    to_dir = vault / plan["to_dir"]
    if plan["move_required"] and to_dir.exists():
        raise RuntimeError(f"target dir already exists: {to_dir}")

    # 1. backup every file that will be modified (rewrites + the brief)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = vault / BACKUP_DIR / ts
    to_back_up = [r["file"] for r in plan["link_rewrites"]]
    brief_rel = f"{plan['from_dir']}/brief.md"
    if brief_rel not in to_back_up:
        to_back_up.append(brief_rel)
    backup_root.mkdir(parents=True)
    for rel in to_back_up:
        src = vault / rel
        dst = backup_root / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    (backup_root / "manifest.json").write_text(json.dumps(
        {"plan": plan, "backed_up": to_back_up, "timestamp": ts}, indent=2))

    # 2-4 are atomic from the caller's view: any failure restores from the
    # backup taken above (spec: no half-moved project).
    links_rewritten = 0
    moved = False
    try:
        # 2. vault-wide wikilink prefix rewrite
        for r in plan["link_rewrites"]:
            f = vault / r["file"]
            text = f.read_text(errors="replace")
            new_text = text.replace(plan["old_link_prefix"], plan["new_link_prefix"])
            if new_text != text:
                f.write_text(new_text)
                links_rewritten += r["count"]

        # 3. zone folder move
        if plan["move_required"]:
            to_dir.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(from_dir), str(to_dir))
            moved = True
        final_dir = to_dir if moved else from_dir

        # 4. brief: status + updated + status log
        brief = final_dir / "brief.md"
        text = brief.read_text(errors="replace")
        text = set_brief_status(text, plan["to_state"], plan["today"])
        text = append_status_log(text, plan["from_state"], plan["to_state"],
                                 plan["today"], plan["reason"])
        brief.write_text(text)
    except (OSError, RuntimeError) as exc:
        if moved and to_dir.exists() and not from_dir.exists():
            shutil.move(str(to_dir), str(from_dir))
        for rel in to_back_up:
            src = backup_root / rel
            if src.is_file():
                (vault / rel).parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, vault / rel)
        raise RuntimeError(
            f"apply failed and was rolled back from {backup_root.name}: {exc}") from exc

    # 5. projects/_index.md row refresh
    fm, _ = parse_frontmatter(brief.read_text(errors="replace"))
    ptype = fm.fields.get("project_type") or "coding"
    row = upsert_projects_index_row(
        vault, slug, ptype, plan["to_state"],
        count_non_index_files(final_dir / "decisions"),
        count_non_index_files(final_dir / "sessions"),
        newest_session_date(final_dir / "sessions"),
    )

    # 6. clear the consumed preview
    preview = vault / PREVIEW_DIR
    if preview.exists():
        shutil.rmtree(preview)

    return {
        "slug": slug,
        "from_state": plan["from_state"],
        "to_state": plan["to_state"],
        "moved": moved,
        "final_dir": str(final_dir.relative_to(vault)),
        "links_rewritten": links_rewritten,
        "index_row": row,
        "backup": str(backup_root.relative_to(vault)),
    }
```

Replace the `preview / apply` stub in `cli_main` with:

```python
    if not args.slug or not args.to_state:
        print("error: preview/apply need --slug and --to", file=sys.stderr)
        return 1
    today_str = today.isoformat()
    try:
        plan = plan_transition(vault, args.slug, args.to_state, args.reason, today_str)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1

    if args.phase == "preview":
        pdir = write_preview(vault, plan)
        print(json.dumps({"preview_dir": str(pdir), "plan": plan}, indent=2))
        return 0

    # apply: require a matching prior preview, then execute the FRESH plan
    changes = vault / PREVIEW_DIR / "changes.json"
    if not changes.is_file():
        print("error: no shelf preview found; run the preview phase first",
              file=sys.stderr)
        return 1
    prior = json.loads(changes.read_text())
    if prior.get("slug") != args.slug or prior.get("to_state") != args.to_state:
        print("error: existing preview is for a different transition; re-run preview",
              file=sys.stderr)
        return 1
    try:
        result = apply_transition(vault, plan)
    except (RuntimeError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest test_shelf -v 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Full suite + commit**

Run: `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -2` — expected `OK`.

```bash
git add adjudant/scripts/shelf.py adjudant/scripts/test_shelf.py
git commit -m "feat(adjudant): shelf preview/apply — status transition, zone move, wikilink rewrite, backup"
```

---

### Task 9: wire the `shelf` verb into the surface

**Files:**
- Modify: `adjudant/scripts/command-metadata.json` (11th verb)
- Modify: `adjudant/skills/adjudant/SKILL.md` (frontmatter description + argument-hint, router table row, helper-layer table row)
- Create: `adjudant/skills/adjudant/reference/shelf.md`
- Modify: `adjudant/.claude-plugin/plugin.json` (description: verb list + count)
- Modify: `adjudant/README.md` (verb table + counts)
- Modify: `.claude-plugin/marketplace.json` (adjudant entry description)
- Modify: `AGENTS.md` (repo tree comment: "ten verbs" line)

**Interfaces:**
- Consumes: `shelf.py` (Tasks 7-8).
- Produces: validator-clean 11-verb surface. Validators 5, 14, 15, 17 enforce agreement.

- [ ] **Step 1: Add the metadata entry**

In `command-metadata.json`, append after the `board` entry:

```json
    {
      "name": "shelf",
      "description": "Project lifecycle — status table across vault zones (list) and confirmed transitions (preview/apply): brief + status log + zone move + wikilink rewrite + index row.",
      "argumentHint": "[<slug> <state>] [--reason \"...\"]",
      "reference": "reference/shelf.md",
      "weight": "light"
    }
```

- [ ] **Step 2: Create `reference/shelf.md`**

```markdown
# shelf — project lifecycle

One small verb for the six-state lifecycle: `active | stale | fridge | done | dead | seed`.
Physical placement follows status: `projects/` holds active+stale+seed, `projects/_fridge/`
holds fridge, `projects/_archive/` holds done+dead.

## Flow

**`/adjudant shelf`** (no args): run

    python3 {plugin}/scripts/shelf.py list --project-dir {code root}

Render the JSON as one table: slug, zone, declared, suggested, days quiet, last session.
Flag rows where `zone_matches` is false or `declared_valid` is false. Suggestions come
only from the active/stale axis; fridge rows can carry a `nudge` string. Never write
anything from list mode.

**`/adjudant shelf <slug> <state> [reason]`**: two-phase, always with explicit user
confirmation between phases.

1. `python3 {plugin}/scripts/shelf.py preview --project-dir {code root} --slug S --to STATE [--reason "..."]`
2. Show the plan: from/to state, folder move yes/no, how many files get wikilink
   rewrites. Ask the user to confirm.
3. On confirmation: `python3 {plugin}/scripts/shelf.py apply ...` (same args).
4. Render the apply summary: final dir, links rewritten, index row action, backup path.

## Rules

- Machines suggest only along the active/stale axis. `fridge`, `done`, `dead`, `seed`
  are set by the user, through this verb, never automatically.
- Apply refuses to run without a matching preview, and aborts untouched if the target
  zone dir already exists.
- Every modified file is backed up under `{vault}/.adjudant-shelf-backup/{timestamp}/`
  with a manifest.json (plan + file list) for manual rollback.
- Working on a fridged or archived project? Shelf it back to `active` first; session
  hooks write notes to the living zone only.
- Transitions land in the brief: `status:` + `updated:` frontmatter, and a dated line
  under `## Status log` (newest first).
```

- [ ] **Step 3: SKILL.md wiring**

1. Frontmatter `description:`: change the verb enumeration to `{connect|port|sync|check|sitrep|tidy|ramasse|dream|draw|board|shelf}` and adjust any "ten verbs" phrasing to "eleven verbs".
2. Frontmatter `argument-hint:`: `"[connect|port|sync|check|sitrep|tidy|ramasse|dream|draw|board|shelf] [args]"`.
3. Intro line: "One skill, one command, eleven verbs."
4. Router table: add:

```markdown
| `shelf` | `reference/shelf.md` | Project lifecycle: status table across zones (list) and confirmed transitions (preview/apply): brief + status log + zone move + wikilink rewrite + index row |
```

5. Helper-layer table: add:

```markdown
| `shelf` | `shelf.py` + `_vault_walk.py` | lifecycle list JSON across zones; two-phase transition (preview/apply with backup): brief status + status log + zone folder move + vault-wide wikilink prefix rewrite + `projects/_index.md` row refresh |
```

- [ ] **Step 4: Parity updates**

- `adjudant/.claude-plugin/plugin.json`: add `shelf` to the description's verb list; if it spells a count, make it eleven.
- `adjudant/README.md`: add `shelf` to the verb table (same one-liner as the router row) and fix any spelled count.
- `.claude-plugin/marketplace.json`: adjudant entry description gains `shelf` (and the count if spelled).
- `AGENTS.md` (repo root): the adjudant tree line says "ten verbs"; make it eleven.

- [ ] **Step 5: Validate, test, commit**

Run: `python3 validate.py 2>&1 | tail -2` — expected `PASS` (validators 5/14/15/17 now cover shelf).
Run: `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -2` — expected `OK`.

```bash
git add adjudant/scripts/command-metadata.json adjudant/skills/adjudant/SKILL.md adjudant/skills/adjudant/reference/shelf.md adjudant/.claude-plugin/plugin.json adjudant/README.md .claude-plugin/marketplace.json AGENTS.md
git commit -m "feat(adjudant): shelf verb #11 wired into command-metadata, SKILL router, reference, parity surfaces"
```

---

### Task 10: status vocabulary lock — templates, vault-standards, validator 23

**Files:**
- Modify: `adjudant/skills/adjudant/templates/project-brief-coding.md`, `project-brief-knowledge.md`, `project-brief-plugin.md`, `project-brief-tinkerage.md` (line 7 in each)
- Modify: `adjudant/skills/adjudant/reference/vault-standards.md` (new section)
- Modify: `adjudant/scripts/validate.py` (validator 23 + docstring + `main()` registration)
- Modify: `adjudant/scripts/test_validate.py`

**Interfaces:**
- Consumes: `_vault_walk.PROJECT_STATUS_VALUES`.
- Produces: `validate_status_vocabulary(r: Result) -> None`, registered in `main()`.

- [ ] **Step 1: Write the failing test**

Append to `adjudant/scripts/test_validate.py`, following that file's existing conventions for invoking a single validator against the real repo tree:

```python
class TestStatusVocabulary(unittest.TestCase):

    def test_validator_passes_on_repo(self):
        r = validate.Result()
        validate.validate_status_vocabulary(r)
        self.assertEqual(r.failures, [], r.failures)
        self.assertIn("status-vocabulary", r.passes)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest test_validate.TestStatusVocabulary -v`
Expected: `AttributeError: module 'validate' has no attribute 'validate_status_vocabulary'`

- [ ] **Step 3: Template + standards edits**

In each of the four `project-brief-*.md` templates, change line 7 from `status: active` to:

```yaml
status: active                # active | stale | fridge | done | dead | seed
```

In `reference/vault-standards.md`, add a new numbered section (after the naming section, renumber nothing — use the next free number):

```markdown
## Project status and zones (locked 2026-07-16)

`status:` on a brief takes exactly one of: `active` | `stale` | `fridge` | `done` | `dead` | `seed`.

- `active`: being worked
- `stale`: declared active but quiet past `stale_after_days` (the only machine-suggested state)
- `fridge`: deliberately paused, intent to return
- `done`: shipped and complete (a success, not an abandonment)
- `dead`: abandoned
- `seed`: captured idea, not yet started

Physical placement follows status:

| Zone | Holds |
|---|---|
| `projects/` | active, stale, seed |
| `projects/_fridge/` | fridge |
| `projects/_archive/` | done, dead |

Transitions run through `/adjudant shelf` (two-phase preview/apply): brief frontmatter,
a dated `## Status log` line (newest first), the zone folder move, a vault-wide
`[[projects/...]]` prefix rewrite, and a `projects/_index.md` row refresh. Full-path
wikilinks into a project therefore survive zone moves; the `[[{slug}/brief\|{slug}]]`
index-row form resolves across zones by Obsidian suffix matching and is never rewritten.
Machines suggest only along the active/stale axis; `fridge`, `done`, `dead`, `seed`
are deliberate, user-set states. Breadcrumb key `stale_after_days:` (default 30)
tunes the staleness threshold per project.
```

- [ ] **Step 4: Implement validator 23**

In `validate.py`: add near the top (after existing imports):

```python
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _vault_walk import PROJECT_STATUS_VALUES  # noqa: E402
```

Add the validator:

```python
def validate_status_vocabulary(r: Result) -> None:
    """23. status-vocabulary — _vault_walk constants, vault-standards, and brief
    templates all agree on the six-state vocabulary."""
    name = "status-vocabulary"
    expected = ("active", "stale", "fridge", "done", "dead", "seed")
    if PROJECT_STATUS_VALUES != expected:
        r.add_fail(name, f"_vault_walk.PROJECT_STATUS_VALUES is {PROJECT_STATUS_VALUES}")
        return
    vs = (REFERENCE / "vault-standards.md").read_text()
    missing = [s for s in expected if f"`{s}`" not in vs]
    if missing:
        r.add_fail(name, f"vault-standards.md missing states: {missing}")
        return
    enum_comment = " | ".join(expected)
    for t in sorted(TEMPLATES.glob("project-brief-*.md")):
        text = t.read_text()
        m = re.search(r"^status:\s*(\S+)", text, re.MULTILINE)
        if not m or m.group(1) not in expected:
            r.add_fail(name, f"{t.name}: status value missing or off-vocabulary")
            return
        if enum_comment not in text:
            r.add_fail(name, f"{t.name}: enum comment '{enum_comment}' missing")
            return
    r.add_pass(name)
```

Register `validate_status_vocabulary(r)` in `main()` after `validate_gitignore_includes_repo_tidy_dirs(r)`, and add line 23 to the module docstring list.

- [ ] **Step 5: Run tests + validators + commit**

Run: `python3 -m unittest test_validate -v 2>&1 | tail -3` — expected PASS.
Run: `python3 validate.py 2>&1 | tail -2` — expected `PASS — 23 validator(s) green`.

```bash
git add adjudant/skills/adjudant/templates/ adjudant/skills/adjudant/reference/vault-standards.md adjudant/scripts/validate.py adjudant/scripts/test_validate.py
git commit -m "feat(adjudant): validator 23 status-vocabulary — templates enum comment + vault-standards zone section"
```

---

### Task 11: connect inference + `--contract`

**Files:**
- Modify: `adjudant/scripts/connect.py`
- Modify: `adjudant/scripts/test_connect.py`

**Interfaces:**
- Consumes: existing `detect_state`, `resolve_vault_for_connect`, `parse_breadcrumb`.
- Produces: `infer_project_type(project_root: Path) -> tuple[str, str]`, `infer_initial_status(project_root: Path) -> tuple[str, str]`, `build_contract(...) -> dict`, CLI flags `--contract`, `--purpose TEXT`, `--initial-status {active,seed,fridge,done,dead}`. Task 12 consumes the flags in the apply path.

- [ ] **Step 1: Write the failing tests**

Append to `adjudant/scripts/test_connect.py`:

```python
from connect import build_contract, infer_initial_status, infer_project_type


class TestInference(unittest.TestCase):

    def test_plugin_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".claude-plugin").mkdir()
            (root / ".claude-plugin" / "plugin.json").write_text("{}")
            ptype, signal = infer_project_type(root)
            self.assertEqual(ptype, "plugin")
            self.assertIn("plugin.json", signal)

    def test_coding_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "main.py").write_text("print('x')")
            self.assertEqual(infer_project_type(root)[0], "coding")

    def test_knowledge_signal(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for i in range(4):
                (root / f"n{i}.md").write_text("# note")
            self.assertEqual(infer_project_type(root)[0], "knowledge")

    def test_tinkerage_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(infer_project_type(Path(tmp))[0], "tinkerage")

    def test_initial_status_seed_when_nearly_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("x")
            self.assertEqual(infer_initial_status(root)[0], "seed")

    def test_initial_status_active_otherwise(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ("a.py", "b.py", "c.md", "d.md"):
                (root / name).write_text("x")
            self.assertEqual(infer_initial_status(root)[0], "active")


class TestContract(unittest.TestCase):

    def test_contract_shape_and_artifact_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            (vault / "projects").mkdir(parents=True)
            code = root / "my-proj"
            code.mkdir()
            (code / "AGENTS.md").write_text("# existing")
            contract = build_contract(
                project_root=code, vault_path=vault, vault_name="vault",
                slug="my-proj", project_type="coding", type_signal="test",
                initial_status="active", status_signal="test", purpose=None)
            self.assertEqual(
                set(contract["required"]),
                {"vault", "vault_name", "slug", "project_type",
                 "initial_status", "purpose"})
            states = {a["artifact"]: a["state"] for a in contract["artifacts"]}
            self.assertEqual(states["AGENTS.md"], "already-present")
            self.assertEqual(states["GEMINI.md"], "will-create")
            self.assertEqual(states["vault scaffold"], "will-create")
            self.assertEqual(contract["state"], "fresh")

    def test_contract_cli_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            vault = root / "vault"
            (vault / "projects").mkdir(parents=True)
            code = root / "proj"
            code.mkdir()
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = connect_cli([
                    "--project-root", str(code), "--vault-path", str(vault),
                    "--contract"])
            self.assertEqual(rc, 0)
            payload = json.loads(buf.getvalue())
            self.assertIn("contract", payload)
            self.assertFalse((code / ".claude" / "adjudant").exists())
            self.assertFalse((vault / "projects" / "proj").exists())
```

(Add `import io, contextlib, json` and `from connect import cli_main as connect_cli` to the test file's imports if not present.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_connect -v 2>&1 | tail -3`
Expected: ImportError on the new names.

- [ ] **Step 3: Implement in `connect.py`**

Add after the slug helpers:

```python
# ============================================================
# Contract inference (v0.14.0)
# ============================================================

_CODE_EXTS = {".py", ".ts", ".js", ".tsx", ".jsx", ".go", ".rs", ".rb",
              ".sh", ".swift", ".c", ".cpp", ".java"}
_INFER_SKIP = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def infer_project_type(project_root: Path) -> tuple[str, str]:
    """(project_type, signal) from repo signals. Cheapest signal first."""
    if (project_root / ".claude-plugin" / "plugin.json").is_file() or \
       (project_root / "plugin.json").is_file():
        return "plugin", "plugin.json present"
    code = md = 0
    for f in project_root.rglob("*"):
        if not f.is_file():
            continue
        if any(p in _INFER_SKIP for p in f.relative_to(project_root).parts):
            continue
        if f.suffix in _CODE_EXTS:
            code += 1
        elif f.suffix == ".md":
            md += 1
    if code > 0:
        return "coding", f"{code} code file(s)"
    if md >= 3:
        return "knowledge", f"{md} markdown files, no code"
    return "tinkerage", "no dominant signal"


def infer_initial_status(project_root: Path) -> tuple[str, str]:
    """seed when the repo is nearly empty (fewer than 3 visible top-level
    entries), else active."""
    n = 0
    for f in project_root.iterdir():
        if f.name.startswith("."):
            continue
        n += 1
        if n >= 3:
            return "active", "3+ top-level entries"
    return "seed", f"{n} top-level entr{'y' if n == 1 else 'ies'}"


ARTIFACT_READERS: list[tuple[str, str]] = [
    ("AGENTS.md", "Codex, Gemini/agy, any agent"),
    ("CLAUDE.md", "Claude Code"),
    ("GEMINI.md", "agy / Antigravity"),
    (".claude/adjudant", "adjudant helpers"),
    ("vault scaffold", "the user, in Obsidian"),
    (".gitignore entries", "git"),
]


def _gitignore_has_breadcrumb(project_root: Path) -> bool:
    gi = project_root / ".gitignore"
    if not gi.is_file():
        return False
    return any(line.strip() == ".claude/adjudant" for line in gi.read_text().splitlines())


def build_contract(
    project_root: Path,
    vault_path: Optional[Path],
    vault_name: Optional[str],
    slug: str,
    project_type: str,
    type_signal: str,
    initial_status: str,
    status_signal: str,
    purpose: Optional[str],
) -> dict[str, Any]:
    """The connect contract: five required fields + per-agent artifact
    disclosure. Read-only."""
    vault_proj = (vault_path / "projects" / slug) if vault_path else None
    present = {
        "AGENTS.md": (project_root / "AGENTS.md").exists(),
        "CLAUDE.md": (project_root / "CLAUDE.md").exists(),
        "GEMINI.md": (project_root / "GEMINI.md").exists(),
        ".claude/adjudant": (project_root / ".claude" / "adjudant").is_file(),
        "vault scaffold": bool(vault_proj and vault_proj.is_dir()),
        ".gitignore entries": _gitignore_has_breadcrumb(project_root),
    }
    return {
        "required": {
            "vault": str(vault_path) if vault_path else None,
            "vault_name": vault_name,
            "slug": slug,
            "project_type": project_type,
            "initial_status": initial_status,
            "purpose": purpose,
        },
        "inferred_from": {
            "slug": "dirname / breadcrumb",
            "project_type": type_signal,
            "initial_status": status_signal,
        },
        "artifacts": [
            {"artifact": a, "reader": rdr,
             "state": "already-present" if present[a] else "will-create"}
            for a, rdr in ARTIFACT_READERS
        ],
        "state": detect_state(project_root, vault_path, slug),
    }
```

In `cli_main`, add the three arguments:

```python
    parser.add_argument("--contract", action="store_true",
                        help="Print the init contract (inferred fields + artifact disclosure) and exit; writes nothing")
    parser.add_argument("--purpose", help="One-line project purpose (lands in AGENTS.md + brief INTRO)")
    parser.add_argument("--initial-status",
                        choices=[s for s in ("active", "seed", "fridge", "done", "dead")],
                        help="Initial brief status (default: inferred seed|active)")
```

After the slug validation block (and before `--detect-only` handling), insert:

```python
    if args.contract:
        ptype_arg = args.project_type
        existing_brief = vault_path / "projects" / slug / "brief.md"
        ptype = derive_project_type(ptype_arg, existing_brief if existing_brief.is_file() else None)
        if ptype:
            type_signal = "explicit --project-type or existing brief"
        else:
            ptype, type_signal = infer_project_type(project_root)
        if args.initial_status:
            istatus, status_signal = args.initial_status, "explicit --initial-status"
        else:
            istatus, status_signal = infer_initial_status(project_root)
        contract = build_contract(
            project_root, vault_path, vault_name, slug,
            ptype, type_signal, istatus, status_signal, args.purpose)
        print(json.dumps({"contract": contract}, indent=2, default=str))
        return 0
```

Also relax the hard `--project-type required` failure for the normal apply path: when `derive_project_type` returns None, fall back to `infer_project_type(project_root)[0]` instead of erroring (the contract phase surfaces the inference for the user to confirm; the apply path uses the same inference when still unspecified).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m unittest test_connect -v 2>&1 | tail -3`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add adjudant/scripts/connect.py adjudant/scripts/test_connect.py
git commit -m "feat(adjudant): connect --contract — project_type/status inference + artifact disclosure, read-only"
```

---

### Task 12: connect apply-side — GEMINI.md, purpose, initial status, breadcrumb keys, receipt

**Files:**
- Create: `adjudant/skills/adjudant/templates/GEMINI.md`
- Modify: `adjudant/scripts/connect.py` (`write_breadcrumb`, `provision_context_files`, `scaffold_vault_project`, `run_connect`, `cli_main`)
- Modify: `adjudant/scripts/test_connect.py`
- Modify: `adjudant/skills/adjudant/reference/connect.md` (contract flow section)
- Modify: `adjudant/scripts/command-metadata.json` (connect description mentions the contract)

**Interfaces:**
- Consumes: Task 11 flags and inference.
- Produces: `build_receipt(summary: dict) -> list[dict]`; breadcrumb now carries `cost_warn_tokens` + `stale_after_days` (existing values preserved on re-connect); `provision_context_files(project_root, slug, project_type, project_name, purpose)` renders template placeholders and includes GEMINI.md; `scaffold_vault_project(..., initial_status, purpose)` honors both.

- [ ] **Step 1: Write the failing tests**

Append to `adjudant/scripts/test_connect.py`:

```python
from connect import build_receipt


class TestApplyContract(unittest.TestCase):

    def _connect(self, root: Path, vault: Path, extra: list = ()) -> dict:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(io.StringIO()):
            rc = connect_cli([
                "--project-root", str(root), "--vault-path", str(vault),
                "--slug", "proj", "--project-type", "coding",
                *extra])
        assert rc == 0, buf.getvalue()
        return json.loads(buf.getvalue())

    def test_gemini_md_created_and_breadcrumb_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root / "vault"
            (vault / "projects").mkdir(parents=True)
            code = root / "proj"; code.mkdir()
            summary = self._connect(code, vault)
            self.assertTrue((code / "GEMINI.md").is_file())
            bc = (code / ".claude" / "adjudant").read_text()
            self.assertIn("cost_warn_tokens: 30000", bc)
            self.assertIn("stale_after_days: 30", bc)
            self.assertIn("receipt", summary)
            states = {r["artifact"]: r["state"] for r in summary["receipt"]}
            self.assertEqual(states["GEMINI.md"], "created")

    def test_breadcrumb_overrides_preserved_on_reconnect(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root / "vault"
            (vault / "projects").mkdir(parents=True)
            code = root / "proj"; code.mkdir()
            self._connect(code, vault)
            bc_path = code / ".claude" / "adjudant"
            bc_path.write_text(bc_path.read_text().replace(
                "cost_warn_tokens: 30000", "cost_warn_tokens: 99000"))
            self._connect(code, vault)
            self.assertIn("cost_warn_tokens: 99000", bc_path.read_text())

    def test_purpose_and_initial_status_land(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root / "vault"
            (vault / "projects").mkdir(parents=True)
            code = root / "proj"; code.mkdir()
            self._connect(code, vault,
                          extra=["--purpose", "Track the garden irrigation build.",
                                 "--initial-status", "seed"])
            agents = (code / "AGENTS.md").read_text()
            self.assertIn("> Track the garden irrigation build.", agents)
            self.assertNotIn("{Project Name}", agents)
            self.assertNotIn("{slug}", agents)
            brief = (vault / "projects" / "proj" / "brief.md").read_text()
            self.assertIn("status: seed", brief)
            self.assertIn("Track the garden irrigation build.", brief)

    def test_reconnect_receipt_all_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); vault = root / "vault"
            (vault / "projects").mkdir(parents=True)
            code = root / "proj"; code.mkdir()
            self._connect(code, vault)
            summary = self._connect(code, vault)
            states = {r["artifact"]: r["state"] for r in summary["receipt"]}
            self.assertEqual(states["AGENTS.md"], "already-present")
            self.assertEqual(states["GEMINI.md"], "already-present")
            self.assertEqual(states["session note"], "already-present")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m unittest test_connect -v 2>&1 | tail -3`
Expected: FAIL (no GEMINI.md, no receipt, breadcrumb keys missing)

- [ ] **Step 3: Create the GEMINI.md template**

Create `adjudant/skills/adjudant/templates/GEMINI.md`:

```markdown
# Gemini-specific overrides

Canonical project context lives in `AGENTS.md`, next to this file. Read it first; everything there applies.

This file is for **Gemini / Antigravity-specific overrides only**:
- agy invocation preferences
- Gemini-only tool guidance

**If you're about to add generic project context here, move it to `AGENTS.md` instead.**
```

- [ ] **Step 4: Implement in `connect.py`**

`write_breadcrumb` — preserve overrides, add the two keys:

```python
def write_breadcrumb(
    project_root: Path,
    vault_path: Path,
    vault_name: str,
    slug: str,
) -> Path:
    existing = parse_breadcrumb(project_root) or {}
    cwt = existing.get("cost_warn_tokens", "30000")
    sad = existing.get("stale_after_days", "30")
    bc_dir = project_root / ".claude"
    bc_dir.mkdir(parents=True, exist_ok=True)
    bc = bc_dir / "adjudant"
    bc.write_text(
        f"vault_path: {vault_path}\n"
        f"vault_name: {vault_name}\n"
        f"slug: {slug}\n"
        f"mode: project\n"
        f"cost_warn_tokens: {cwt}\n"
        f"stale_after_days: {sad}\n"
    )
    return bc
```

`provision_context_files` — add GEMINI.md and placeholder rendering:

```python
def provision_context_files(
    project_root: Path,
    slug: str = "",
    project_type: str = "",
    project_name: str = "",
    purpose: Optional[str] = None,
) -> dict[str, str]:
    """Copy AGENTS.md + CLAUDE.md + GEMINI.md from templates if missing,
    rendering placeholders in AGENTS.md. Existing files are never touched."""
    actions: dict[str, str] = {}
    for fname in ("AGENTS.md", "CLAUDE.md", "GEMINI.md"):
        live = project_root / fname
        if live.exists():
            actions[fname] = "preserved"
            continue
        template = TEMPLATES / fname
        if not template.is_file():
            actions[fname] = f"template missing: {template}"
            continue
        text = template.read_text()
        if fname == "AGENTS.md":
            if project_name:
                text = text.replace("{Project Name}", project_name)
            if slug:
                text = text.replace("{slug}", slug)
            if project_type:
                text = text.replace("{coding|knowledge|plugin|tinkerage}", project_type)
            if purpose:
                text = text.replace("> One-line purpose of this project.", f"> {purpose}")
        live.write_text(text)
        actions[fname] = "created"
    return actions
```

`scaffold_vault_project` — add `initial_status: str = "active"` and `purpose: Optional[str] = None` parameters; in the brief-creation branch, after the existing `.replace(...)` chain:

```python
        text = text.replace("status: active", f"status: {initial_status}", 1)
        if purpose:
            text = text.replace("## INTRO\n", f"## INTRO\n\n{purpose}\n", 1)
```

(The enum comment from Task 10 rides along because the replace targets the `status: active` prefix; verify the template line is `status: active                # active | ...` and use `text.replace("status: active", f"status: {initial_status}", 1)` which preserves the trailing comment.)

`run_connect` — accept and thread `initial_status: str = "active"` and `purpose: Optional[str] = None`; record breadcrumb pre-existence for the receipt:

```python
    bc_existed = (project_root / ".claude" / "adjudant").is_file()
    write_breadcrumb(project_root, vault_path, vault_name, slug)
    summary["steps"]["breadcrumb"] = "updated" if bc_existed else "created"
    summary["steps"]["context_files"] = provision_context_files(
        project_root, slug, project_type, project_name, purpose)
    summary["steps"]["vault_scaffold"] = scaffold_vault_project(
        vault_path, slug, project_type, project_name, today,
        initial_status=initial_status, purpose=purpose)
```

Add the receipt builder and attach it at the end of `run_connect` (`summary["receipt"] = build_receipt(summary)`):

```python
_RECEIPT_MARK = {
    "created": "created", "preserved": "already-present",
    "added": "updated", "updated": "updated", "inserted": "updated",
    "created-index": "created",
}


def build_receipt(summary: dict[str, Any]) -> list[dict[str, str]]:
    steps = summary["steps"]
    cf = steps["context_files"]
    scaffold = steps["vault_scaffold"]
    return [
        {"artifact": "AGENTS.md", "state": _RECEIPT_MARK.get(cf.get("AGENTS.md", ""), cf.get("AGENTS.md", "missing"))},
        {"artifact": "CLAUDE.md", "state": _RECEIPT_MARK.get(cf.get("CLAUDE.md", ""), cf.get("CLAUDE.md", "missing"))},
        {"artifact": "GEMINI.md", "state": _RECEIPT_MARK.get(cf.get("GEMINI.md", ""), cf.get("GEMINI.md", "missing"))},
        {"artifact": ".claude/adjudant", "state": steps["breadcrumb"]},
        {"artifact": "vault scaffold", "state": "created" if scaffold["created"] else "already-present"},
        {"artifact": "session note", "state": _RECEIPT_MARK.get(steps["session_note"], steps["session_note"])},
        {"artifact": ".gitignore entries", "state": _RECEIPT_MARK.get(steps["gitignore"], steps["gitignore"])},
        {"artifact": "projects/_index.md row", "state": _RECEIPT_MARK.get(steps["projects_index_row"], steps["projects_index_row"])},
    ]
```

`cli_main` — resolve initial status before calling `run_connect` and pass both new args:

```python
    if args.initial_status:
        initial_status = args.initial_status
    else:
        initial_status, _sig = infer_initial_status(project_root)
    summary = run_connect(
        ...existing args...,
        initial_status=initial_status,
        purpose=args.purpose,
    )
```

- [ ] **Step 5: Update `reference/connect.md` and the metadata description**

In `reference/connect.md`, add a "## Contract flow (locked)" section at the top of the flow description:

```markdown
## Contract flow (locked)

connect is three phases; the card in the middle is the only thing the user must read.

1. **Infer.** Run `connect.py --contract --project-root {code root} [flags]`. The JSON
   contract carries the five required fields (vault, slug, project_type, initial_status,
   purpose) with inferred values pre-filled, plus the per-agent artifact disclosure
   (AGENTS.md, CLAUDE.md, GEMINI.md, breadcrumb, vault scaffold, .gitignore) each marked
   already-present or will-create.
2. **Confirm.** Render the contract as ONE card, both halves. Ask the user to approve or
   correct the five fields once. purpose is the one field with no inference: ask for it
   if empty; it becomes the brief's opening line and what sitrep orients from.
3. **Apply + receipt.** Run connect.py with the confirmed values (`--purpose`,
   `--initial-status`, plus the usual flags). Render `summary.receipt` back as the same
   card with per-artifact marks: created / already-present / updated. A re-run on a
   healthy project shows all already-present and writes nothing new.

Config knobs land in the breadcrumb at init with defaults visible on the card:
`cost_warn_tokens: 30000`, `stale_after_days: 30`. Existing overrides survive re-connect.
```

In `command-metadata.json`, update the connect description (stay ≤ 220 chars):

```
"Onboard project to vault — contract flow: infer (slug/type/status/vault), confirm one card (5 required fields + per-agent artifact disclosure incl. GEMINI.md), apply with receipt. Idempotent."
```

- [ ] **Step 6: Run tests, full suite, validators, commit**

Run: `python3 -m unittest test_connect -v 2>&1 | tail -3` — expected PASS.
Run: `python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -2` — expected `OK`.
Run: `python3 validate.py 2>&1 | tail -2` — expected `PASS`.

```bash
git add adjudant/skills/adjudant/templates/GEMINI.md adjudant/scripts/connect.py adjudant/scripts/test_connect.py adjudant/skills/adjudant/reference/connect.md adjudant/scripts/command-metadata.json
git commit -m "feat(adjudant): connect contract apply side — GEMINI.md, purpose, initial status, breadcrumb knobs, receipt"
```

---

### Task 13: `reference/voice.md` + validator 24 + lexicon sweep

**Files:**
- Create: `adjudant/skills/adjudant/reference/voice.md`
- Modify: `adjudant/scripts/validate.py` (validator 24 + docstring + registration)
- Modify: `adjudant/scripts/test_validate.py`
- Modify: any `templates/*.md`, `SKILL.md`, `reference/*.md` files the sweep flags

**Interfaces:**
- Consumes: nothing new.
- Produces: `validate_voice_lexicon(r: Result) -> None`; `_parse_voice_lists() -> tuple[list[str], list[str]]`.

- [ ] **Step 1: Create `reference/voice.md`**

```markdown
# Voice

Canonical language and tone contract for every adjudant surface: rendered verb output,
vault writes, templates, and reference docs. The `voice-lexicon` validator enforces the
machine-checkable subset; the rest is a standing instruction to the rendering model.
Loaded alongside every verb reference. Small on purpose.

## Banned lexicon

Never in adjudant output or vault writes. The validator matches these case-insensitively
as whole words across templates/, SKILL.md, and reference/ (this file excepted). Extend
by adding bullets; a trailing parenthetical is a note, not part of the matched term.

- forward-thinking
- load-bearing
- leverage (as a verb; add inflections as separate bullets if they slip through)
- deep dive
- double-click (figurative)
- game-changer
- cutting-edge
- seamless
- journey (figurative)
- empower
- unlock (figurative)
- elevate (figurative)
- circle back
- synergy
- at the end of the day

## Glazing phrases

- You're absolutely right
- Great question
- Excellent point
- Perfect!

## Pushback contract

The user can be wrong, impatient, or insistent. The duty is to say so: clearly,
concisely, evidence first, one short paragraph. No hedging, no ceremony. State
disagreement once; if overruled, proceed without sulking.

## Explanation modes

Request tokens, recognized on any verb:

| Mode | Register |
|---|---|
| `ELI5` | Stepped plan, cause and effect, top level only |
| `ELI12` | Granular steps with the architectural and strategic layer; top to mid plus a bit of low |
| `ELICTO` | Trench detail and big picture together; no hand-holding |

Defaults: `sitrep` renders ELI5, `check` renders ELI12, `dream` and `ramasse` judging
render ELICTO. A mode token in the user's request overrides the default.

## Typography

- No em dashes in rendered output or vault writes. Use a colon, comma, or parentheses.
- Flourishes irregular and rare: an occasional fleuron (❦), sparse emoji, room for
  easter eggs. Never per message.
```

- [ ] **Step 2: Write the failing test**

Append to `adjudant/scripts/test_validate.py`:

```python
class TestVoiceLexicon(unittest.TestCase):

    def test_parse_voice_lists(self):
        banned, glazing = validate._parse_voice_lists()
        self.assertIn("forward-thinking", banned)
        self.assertIn("leverage", banned)          # qualifier stripped
        self.assertIn("You're absolutely right", glazing)

    def test_validator_passes_on_repo(self):
        r = validate.Result()
        validate.validate_voice_lexicon(r)
        self.assertEqual(r.failures, [], r.failures)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python3 -m unittest test_validate.TestVoiceLexicon -v`
Expected: `AttributeError` (no `_parse_voice_lists`)

- [ ] **Step 4: Implement validator 24**

Add to `validate.py`:

```python
VOICE_MD = REFERENCE / "voice.md"


def _parse_voice_lists() -> tuple[list[str], list[str]]:
    """(banned_lexicon, glazing) bullets parsed from reference/voice.md.
    A trailing parenthetical on a bullet is a note, stripped before matching."""
    banned: list[str] = []
    glazing: list[str] = []
    current = None
    for line in VOICE_MD.read_text().splitlines():
        if line.startswith("## "):
            h = line[3:].strip().lower()
            current = ("banned" if h.startswith("banned lexicon")
                       else "glazing" if h.startswith("glazing") else None)
            continue
        m = re.match(r"^-\s+(.+)$", line.strip())
        if m and current:
            term = re.sub(r"\s*\([^)]*\)\s*$", "", m.group(1).strip())
            (banned if current == "banned" else glazing).append(term)
    return banned, glazing


def validate_voice_lexicon(r: Result) -> None:
    """24. voice-lexicon — no banned/glazing terms in templates/, SKILL.md,
    reference/ (voice.md excepted); no em dashes in templates/."""
    name = "voice-lexicon"
    if not VOICE_MD.is_file():
        r.add_fail(name, "reference/voice.md missing")
        return
    banned, glazing = _parse_voice_lists()
    if not banned or not glazing:
        r.add_fail(name, "voice.md lists are empty")
        return
    surfaces = ([CANONICAL / "SKILL.md"]
                + sorted(TEMPLATES.glob("*.md"))
                + [p for p in sorted(REFERENCE.glob("*.md")) if p.name != "voice.md"])
    patterns = [(t, re.compile(r"(?<![\w-])" + re.escape(t) + r"(?![\w-])", re.IGNORECASE))
                for t in banned + glazing]
    hits: list[str] = []
    for f in surfaces:
        text = f.read_text()
        for term, rx in patterns:
            if rx.search(text):
                hits.append(f"{f.relative_to(ROOT)}: {term!r}")
    for t in sorted(TEMPLATES.glob("*.md")):
        if "—" in t.read_text():
            hits.append(f"{t.relative_to(ROOT)}: em dash")
    if hits:
        shown = "; ".join(hits[:8])
        more = f" (+{len(hits) - 8} more)" if len(hits) > 8 else ""
        r.add_fail(name, shown + more)
    else:
        r.add_pass(name)
```

Register `validate_voice_lexicon(r)` in `main()` after `validate_status_vocabulary(r)`; add line 24 to the docstring.

- [ ] **Step 5: Run the sweep**

Run: `python3 validate.py 2>&1 | grep voice-lexicon`

If it fails, fix every listed hit by rewording (replace the banned term with plain language; replace template em dashes with a colon, comma, or parentheses). Re-run until green. Typical expected hits: em dashes inside `templates/*.md` comment lines and any stray lexicon in reference docs. Do not weaken the list to pass; fix the prose.

- [ ] **Step 6: Run tests, full suite, commit**

Run: `python3 -m unittest test_validate -v 2>&1 | tail -3` — expected PASS.
Run: `python3 validate.py 2>&1 | tail -2` — expected `PASS — 24 validator(s) green`.

```bash
git add adjudant/skills/adjudant/reference/voice.md adjudant/scripts/validate.py adjudant/scripts/test_validate.py adjudant/skills/adjudant/templates/ adjudant/skills/adjudant/reference/ adjudant/skills/adjudant/SKILL.md
git commit -m "feat(adjudant): voice.md contract + validator 24 voice-lexicon + banned-term sweep"
```

---

### Task 14: SKILL.md voice section, README, release 0.14.0

**Files:**
- Modify: `adjudant/skills/adjudant/SKILL.md` (voice section)
- Modify: `adjudant/README.md` (test count, new features summary)
- Modify (via bump script): `adjudant/.claude-plugin/plugin.json`, `adjudant/scripts/command-metadata.json`, `adjudant/skills/adjudant/SKILL.md` frontmatter, `.claude-plugin/marketplace.json`

**Interfaces:**
- Consumes: everything above.
- Produces: released v0.14.0.

- [ ] **Step 1: Add the SKILL.md voice section**

Insert after the cost-gate section (Task 4):

```markdown
## Voice (locked)

Load `reference/voice.md` with every verb (the one exception to
load-only-the-matching-reference; it is small). It defines the banned lexicon, the
glazing ban, the pushback contract, the ELI5/ELI12/ELICTO explanation modes with
per-verb defaults, and typography (no em dashes in rendered output or vault writes).
The `voice-lexicon` validator enforces the machine-checkable subset.
```

- [ ] **Step 2: README refresh**

Update `adjudant/README.md`: the tests row (`479` becomes the new suite count from the final run), the validators row (22 becomes 24), and add `shelf`, cost gate, connect contract, voice to the feature summary in the existing style.

- [ ] **Step 3: Bump the version everywhere at once**

Run from the repo root:

```bash
python3 scripts/bump_plugin_version.py adjudant 0.14.0
```

Expected: plugin.json, command-metadata.json, SKILL.md frontmatter, marketplace.json all report 0.14.0.

- [ ] **Step 4: Final verification**

```bash
cd adjudant/scripts
python3 -m unittest discover -p 'test_*.py' 2>&1 | tail -2   # expected OK, count > 479
python3 validate.py 2>&1 | tail -2                            # expected PASS — 24 validator(s) green
python3 ../../scripts/check_marketplace_versions.py 2>&1 | tail -1 || true  # run from repo root if path differs; expected in-sync
```

Also smoke-test the two new CLIs against a scratch fixture:

```bash
cd "$(mktemp -d)" && mkdir -p vault/projects/demo && printf -- '---\ntype: project\nslug: demo\nproject_type: coding\nstatus: active\n---\n\n# Demo\n' > vault/projects/demo/brief.md
python3 "<repo>/adjudant/scripts/shelf.py" list --vault-dir "$PWD/vault"
python3 "<repo>/adjudant/scripts/check.py" --project-dir "$PWD/vault/projects/demo" --estimate-only
```

Expected: a one-project JSON table; a bare `{"cost": {...}}` block.

- [ ] **Step 5: Release commit**

```bash
git add -A
git commit -m "release(adjudant): v0.14.0 — cost gate, shelf lifecycle + vault zones, connect contract, voice layer"
```

---

## Plan self-review notes (resolved inline)

- **Spec coverage:** cost gate (Tasks 1-4), status lifecycle + shelf + zones (5-10), connect contract (11-12), voice (13-14), cross-cutting/release (9, 14). The hookify tom-voice extension is out of this repo per the spec (side task in iCloud).
- **Type consistency:** `suggest_status` returns the same dict keys consumed by `run_list`, `run_check`, `run_sitrep`; `cost_block` keys asserted identically in every helper test; `upsert_projects_index_row` signature taken verbatim from `connect.py:395`.
- **Known judgment calls encoded:** apply recomputes a fresh plan but requires a matching prior preview (stale-preview safety); index-row wikilinks are not rewritten on zone moves (Obsidian suffix matching, documented in vault-standards); `check` stays `medium` in metadata with `check all` heaviness handled as a router rule.
