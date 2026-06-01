#!/usr/bin/env python3
"""Adjudant dream — semantic content/staleness comparator catalog (dream analysis phase).

Scans an adjudant-managed vault project and emits a structured *content*
catalog (JSON) for Claude to JUDGE. Where `ramasse_scan.py` decides
structural facts ("this filename violates §4"), `dream.py` cannot decide
semantics — it surfaces *candidates* (with file · line · excerpt) and
leaves the judgment to Claude. Read-only — never writes.

Catalog (the comparator catalog):
  - staleness_candidates   aged files whose content may be outdated
  - supersession_signals   same-topic decisions, older likely superseded
  - contradiction_pairs    topically-overlapping files with change/negation cues
  - redundancy_clusters    near-duplicate notes/docs (token-set similarity)
  - stale_refs             refs that resolve but point to archived/old targets
  - orphan_questions       aged open-loop markers (TODO/OPEN/TBD/…) never closed
  - orphan_threads         aged notes/docs with no inbound wikilinks

CLI:
    python3 dream.py --project-dir PATH [--vault-dir PATH] [--out FILE]
                     [--today YYYY-MM-DD] [--stale-days N] [--include-legacy]

This is the analysis phase for `/adjudant dream` (the third cleanup tier):
  - tidy    = surface mechanical sweep            (tidy.py)
  - ramasse = deep structural clean               (ramasse_scan.py)
  - dream   = content/knowledge/memory refresh    (this scanner)

See docs/superpowers/2026-05-26-adjudant-tidy-ramasse-log.design.md and
skills/adjudant/reference/dream.md.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Optional

from _vault_walk import (
    BUCKET_A_TYPES,
    VaultFile,
    build_vault_index,
    resolve_vault,
    resolve_wikilink,
    smart_project_dir,
    walk_project,
)


# File types whose prose dream reads (the content layer)
CONTENT_TYPES: frozenset[str] = frozenset({"decision", "note", "session", "doc"})

# Default age threshold (days) past which content is a staleness candidate
DEFAULT_STALE_DAYS = 180
# Open-loop markers go orphan sooner than prose goes stale
DEFAULT_ORPHAN_QUESTION_DAYS = 90

DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
DATE_PREFIX_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})(?:-(.*))?$")

# Lexical cue that one decision/note overturns an earlier position
CHANGE_VERB_RE = re.compile(
    r"\b("
    r"no longer|instead of|switched from|switch from|changed from|change from|"
    r"moved away from|move away from|deprecat\w*|supersed\w*|obsolet\w*|"
    r"replaced? by|replaces|reverted?|abandon\w*|we will not|will no longer|"
    r"rather than|overrid\w*"
    r")\b",
    re.IGNORECASE,
)

# Open-loop / unresolved-thread markers
OPEN_LOOP_RE = re.compile(
    r"(?:^|[\s(>\-*])("
    r"TODO|FIXME|TBD|OPEN:|UNRESOLVED|open question|to decide|to-do|"
    r"follow[ -]?up|needs decision|still unclear|\?\?"
    r")\b",
    re.IGNORECASE,
)

# Ref target segments that mean "archived / parked"
ARCHIVE_HINT_RE = re.compile(r"(?:^|/)(_legacy|_archive|archive|archived|legacy)(?:/|$|#)", re.IGNORECASE)

# Tokenisation stopwords (title + body overlap)
_STOPWORDS: frozenset[str] = frozenset({
    "the", "and", "for", "with", "this", "that", "from", "into", "what", "when",
    "where", "which", "while", "about", "over", "under", "your", "their", "them",
    "then", "than", "have", "has", "had", "are", "was", "were", "will", "would",
    "should", "could", "can", "not", "but", "all", "any", "our", "out", "via",
    "use", "using", "used", "new", "old", "see", "note", "notes", "doc", "docs",
    "decision", "decisions", "session", "sessions", "index", "project", "adjudant",
})


def _parse_date(value: Any) -> Optional[_dt.date]:
    """Parse the first YYYY-MM-DD found in a value (str/date), else None."""
    if isinstance(value, _dt.date):
        return value
    if not isinstance(value, str):
        return None
    m = DATE_RE.search(value)
    if not m:
        return None
    try:
        return _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _file_date(vf: VaultFile) -> Optional[_dt.date]:
    """Best-known date for a file: updated > date frontmatter > filename prefix."""
    fields = vf.frontmatter.fields
    for key in ("updated", "date"):
        d = _parse_date(fields.get(key))
        if d:
            return d
    stem = vf.rel_path.name[:-3] if vf.rel_path.name.endswith(".md") else vf.rel_path.name
    m = DATE_PREFIX_RE.match(stem)
    if m:
        return _parse_date(m.group(1))
    return None


def _age_days(vf: VaultFile, today: _dt.date) -> Optional[int]:
    d = _file_date(vf)
    if d is None:
        return None
    return (today - d).days


def _first_excerpt(body: str, limit: int = 160) -> str:
    """First non-empty, non-heading-only prose line, truncated."""
    for line in body.split("\n"):
        s = line.strip()
        if s and not s.startswith("#"):
            return s[:limit]
    return ""


def _title_tokens(vf: VaultFile) -> set[str]:
    """Significant tokens from the filename (date prefix stripped)."""
    stem = vf.rel_path.name[:-3] if vf.rel_path.name.endswith(".md") else vf.rel_path.name
    m = DATE_PREFIX_RE.match(stem)
    if m and m.group(2):
        stem = m.group(2)
    elif m and not m.group(2):
        stem = ""
    parts = re.split(r"[-_\s]+", stem.lower())
    return {p for p in parts if len(p) >= 3 and p not in _STOPWORDS}


def _body_tokens(vf: VaultFile) -> set[str]:
    """Significant word-set from the prose body (for redundancy similarity)."""
    words = re.findall(r"[a-z0-9][a-z0-9'-]{2,}", vf.body.lower())
    return {w for w in words if len(w) >= 4 and w not in _STOPWORDS}


def _shared_wikilink_targets(a: VaultFile, b: VaultFile) -> list[str]:
    ta = {wl.target for wl in a.wikilinks if wl.target}
    tb = {wl.target for wl in b.wikilinks if wl.target}
    return sorted(ta & tb)


def _cue_line(vf: VaultFile, pattern: re.Pattern) -> Optional[tuple[int, str]]:
    """First body line matching pattern, skipping fenced code blocks."""
    in_fenced = False
    for lineno, line in enumerate(vf.body.split("\n"), start=1):
        if line.lstrip().startswith("```"):
            in_fenced = not in_fenced
            continue
        if in_fenced:
            continue
        if pattern.search(line):
            return lineno, line.strip()[:160]
    return None


def _all_cue_lines(vf: VaultFile, pattern: re.Pattern) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    in_fenced = False
    for lineno, line in enumerate(vf.body.split("\n"), start=1):
        if line.lstrip().startswith("```"):
            in_fenced = not in_fenced
            continue
        if in_fenced:
            continue
        if pattern.search(line):
            out.append((lineno, line.strip()[:160]))
    return out


# ============================================================
# Comparator detectors
# ============================================================


def detect_staleness(
    files: list[VaultFile], today: _dt.date, *, stale_days: int = DEFAULT_STALE_DAYS
) -> list[dict]:
    """Content-type files whose best-known date is older than the threshold."""
    out: list[dict] = []
    for f in files:
        if f.file_type not in CONTENT_TYPES:
            continue
        age = _age_days(f, today)
        if age is None or age <= stale_days:
            continue
        out.append({
            "file": str(f.rel_path),
            "type": f.file_type,
            "date": str(_file_date(f)),
            "age_days": age,
            "excerpt_head": _first_excerpt(f.body),
        })
    out.sort(key=lambda x: x["age_days"], reverse=True)
    return out


def detect_supersession_signals(files: list[VaultFile], today: _dt.date) -> list[dict]:
    """Same-topic decision pairs ordered by date — older likely superseded.

    Mechanical signal only: topical overlap (shared title tokens or shared
    wikilink targets) + date ordering + whether the older file already carries
    a `superseded` marker. Claude confirms and writes the marker.
    """
    decisions = [f for f in files if f.file_type == "decision" and _file_date(f)]
    toks = {id(f): _title_tokens(f) for f in decisions}
    out: list[dict] = []
    for i in range(len(decisions)):
        for j in range(i + 1, len(decisions)):
            a, b = decisions[i], decisions[j]
            shared_tokens = sorted(toks[id(a)] & toks[id(b)])
            shared_links = _shared_wikilink_targets(a, b)
            if len(shared_tokens) < 2 and not shared_links:
                continue
            da, db = _file_date(a), _file_date(b)
            if da == db:
                continue
            older, newer = (a, b) if da < db else (b, a)
            older_marked = (
                "superseded" in older.frontmatter.fields
                or re.search(r"supersed(?:ed|es)\s+by", older.body, re.IGNORECASE) is not None
            )
            out.append({
                "older": {"file": str(older.rel_path), "date": str(_file_date(older))},
                "newer": {"file": str(newer.rel_path), "date": str(_file_date(newer))},
                "shared_terms": shared_tokens,
                "shared_links": shared_links,
                "older_has_superseded_marker": older_marked,
            })
    return out


def detect_contradiction_candidates(files: list[VaultFile], today: _dt.date) -> list[dict]:
    """Topically-overlapping content pairs where a change/negation cue appears.

    Emits "A line X may conflict with B line Y" candidates: a pair shares
    topic (title tokens or wikilink target) and at least one side carries a
    change-verb cue ("switched from", "no longer", "deprecated", …).
    """
    content = [f for f in files if f.file_type in ("decision", "note", "doc")]
    toks = {id(f): _title_tokens(f) for f in content}
    cues = {id(f): _cue_line(f, CHANGE_VERB_RE) for f in content}
    out: list[dict] = []
    for i in range(len(content)):
        for j in range(i + 1, len(content)):
            a, b = content[i], content[j]
            shared_tokens = sorted(toks[id(a)] & toks[id(b)])
            shared_links = _shared_wikilink_targets(a, b)
            if len(shared_tokens) < 2 and not shared_links:
                continue
            ca, cb = cues[id(a)], cues[id(b)]
            if not ca and not cb:
                continue
            out.append({
                "a": {
                    "file": str(a.rel_path),
                    "line": ca[0] if ca else None,
                    "excerpt": ca[1] if ca else _first_excerpt(a.body),
                },
                "b": {
                    "file": str(b.rel_path),
                    "line": cb[0] if cb else None,
                    "excerpt": cb[1] if cb else _first_excerpt(b.body),
                },
                "shared_terms": shared_tokens,
                "shared_links": shared_links,
            })
    return out


def detect_redundancy_clusters(
    files: list[VaultFile], today: _dt.date, *, threshold: float = 0.6
) -> list[dict]:
    """Near-duplicate notes/docs via token-set (Jaccard) similarity, unioned."""
    candidates = [
        f for f in files
        if f.file_type in ("note", "doc") and f.rel_path.name != "_index.md"
    ]
    tokens = {id(f): _body_tokens(f) for f in candidates}

    # Union-find over pairs above threshold
    parent: dict[int, int] = {id(f): id(f) for f in candidates}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x: int, y: int) -> None:
        parent[find(x)] = find(y)

    pair_sim: dict[tuple[int, int], float] = {}
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            a, b = candidates[i], candidates[j]
            ta, tb = tokens[id(a)], tokens[id(b)]
            if not ta or not tb:
                continue
            inter = len(ta & tb)
            if inter == 0:
                continue
            jac = inter / len(ta | tb)
            if jac >= threshold:
                union(id(a), id(b))
                pair_sim[(id(a), id(b))] = jac

    clusters: dict[int, list[VaultFile]] = defaultdict(list)
    for f in candidates:
        clusters[find(id(f))].append(f)

    out: list[dict] = []
    for members in clusters.values():
        if len(members) < 2:
            continue
        member_ids = {id(m) for m in members}
        sims = [s for (x, y), s in pair_sim.items() if x in member_ids and y in member_ids]
        shared = set.intersection(*(tokens[id(m)] for m in members)) if members else set()
        out.append({
            "files": sorted(str(m.rel_path) for m in members),
            "similarity": round(min(sims), 3) if sims else None,
            "shared_terms": sorted(shared)[:15],
        })
    out.sort(key=lambda x: (x["similarity"] or 0.0), reverse=True)
    return out


def detect_stale_refs(
    files: list[VaultFile],
    today: _dt.date,
    vault_index: Optional[set[str]] = None,
    *,
    stale_days: int = DEFAULT_STALE_DAYS,
) -> list[dict]:
    """Refs that point to archived locations or to old dated targets.

    Broken wikilinks stay ramasse's job — these refs RESOLVE (when a vault
    index is available) but point somewhere stale.
    """
    out: list[dict] = []
    for f in files:
        refs: list[tuple[str, int, str]] = []
        for wl in f.wikilinks:
            refs.append((wl.target, wl.line, "wikilink"))
        for text, path, line in f.markdown_md_links:
            refs.append((path.split("#", 1)[0], line, "markdown"))
        for target, line, kind in refs:
            if not target:
                continue
            reason: Optional[str] = None
            if ARCHIVE_HINT_RE.search(target):
                reason = "points to archived/legacy location"
            else:
                td = _parse_date(target.split("/")[-1])
                if td is not None and (today - td).days > stale_days:
                    reason = f"references dated target {(today - td).days}d old"
            if not reason:
                continue
            resolves = resolve_wikilink(target, vault_index) if vault_index else None
            if vault_index is not None and not resolves:
                continue  # unresolved → ramasse territory, not dream
            out.append({
                "file": str(f.rel_path),
                "line": line,
                "ref": target,
                "kind": kind,
                "reason": reason,
                "resolves": resolves,
            })
    return out


def detect_orphan_questions(
    files: list[VaultFile], today: _dt.date, *, orphan_days: int = DEFAULT_ORPHAN_QUESTION_DAYS
) -> list[dict]:
    """Aged open-loop markers (TODO/OPEN/TBD/…) that were never closed."""
    out: list[dict] = []
    for f in files:
        if f.file_type not in CONTENT_TYPES:
            continue
        age = _age_days(f, today)
        if age is not None and age < orphan_days:
            continue  # recent open loops aren't orphans yet
        for line, text in _all_cue_lines(f, OPEN_LOOP_RE):
            out.append({
                "file": str(f.rel_path),
                "line": line,
                "text": text,
                "type": f.file_type,
                "age_days": age,
            })
    return out


def detect_orphan_threads(
    files: list[VaultFile], today: _dt.date, *, stale_days: int = DEFAULT_STALE_DAYS
) -> list[dict]:
    """Aged notes/docs with zero inbound wikilinks (no file points to them)."""
    # Inbound index: every wikilink target's basename + path forms
    linked: set[str] = set()
    file_by_id = {id(f): f for f in files}
    for f in files:
        for wl in f.wikilinks:
            t = wl.target
            if not t:
                continue
            base = t.replace("\\", "/").rstrip("/").split("/")[-1]
            linked.add(t)
            linked.add(base)

    out: list[dict] = []
    for f in files:
        if f.file_type not in ("note", "doc"):
            continue
        if f.rel_path.name == "_index.md":
            continue
        stem = f.rel_path.name[:-3] if f.rel_path.name.endswith(".md") else f.rel_path.name
        rel_no_ext = str(f.rel_path)[:-3] if str(f.rel_path).endswith(".md") else str(f.rel_path)
        if stem in linked or rel_no_ext in linked or str(f.rel_path) in linked:
            continue
        age = _age_days(f, today)
        if age is None or age <= stale_days:
            continue
        out.append({
            "file": str(f.rel_path),
            "type": f.file_type,
            "age_days": age,
            "inbound_links": 0,
        })
    out.sort(key=lambda x: x["age_days"], reverse=True)
    return out


# ============================================================
# Top-level scan
# ============================================================


def run_dream(
    project_dir: Path,
    vault_dir: Optional[Path],
    *,
    today: Optional[_dt.date] = None,
    stale_days: int = DEFAULT_STALE_DAYS,
    orphan_question_days: int = DEFAULT_ORPHAN_QUESTION_DAYS,
    include_legacy: bool = False,
) -> dict[str, Any]:
    """Run all content/staleness detectors. Returns the full JSON report."""
    today = today or _dt.date.today()
    files = list(walk_project(project_dir, include_legacy=include_legacy))
    slug = _project_slug(files, project_dir)
    proj_type = _project_type(files)

    vault_index: Optional[set[str]] = None
    if vault_dir and vault_dir.is_dir():
        vault_index = build_vault_index(vault_dir)

    staleness = detect_staleness(files, today, stale_days=stale_days)
    supersession = detect_supersession_signals(files, today)
    contradiction = detect_contradiction_candidates(files, today)
    redundancy = detect_redundancy_clusters(files, today)
    stale_refs = detect_stale_refs(files, today, vault_index, stale_days=stale_days)
    orphan_questions = detect_orphan_questions(files, today, orphan_days=orphan_question_days)
    orphan_threads = detect_orphan_threads(files, today, stale_days=stale_days)

    candidate_total = (
        len(staleness)
        + len(supersession)
        + len(contradiction)
        + len(redundancy)
        + len(stale_refs)
        + len(orphan_questions)
        + len(orphan_threads)
    )

    return {
        "meta": {
            "project_dir": str(project_dir),
            "project_slug": slug,
            "project_type": proj_type,
            "vault_dir": str(vault_dir) if vault_dir else None,
            "files_scanned": len(files),
            "today": str(today),
            "include_legacy": include_legacy,
            "thresholds": {
                "stale_days": stale_days,
                "orphan_question_days": orphan_question_days,
            },
        },
        "summary": {
            "candidates": candidate_total,
            "staleness": len(staleness),
            "supersession": len(supersession),
            "contradiction": len(contradiction),
            "redundancy_clusters": len(redundancy),
            "stale_refs": len(stale_refs),
            "orphan_questions": len(orphan_questions),
            "orphan_threads": len(orphan_threads),
        },
        "staleness_candidates": staleness,
        "supersession_signals": supersession,
        "contradiction_pairs": contradiction,
        "redundancy_clusters": redundancy,
        "stale_refs": stale_refs,
        "orphan_questions": orphan_questions,
        "orphan_threads": orphan_threads,
    }


def _project_slug(files: list[VaultFile], project_dir: Path) -> Optional[str]:
    for f in files:
        if f.rel_path == Path("brief.md"):
            slug = f.frontmatter.fields.get("slug")
            if isinstance(slug, str) and slug:
                return slug
    return project_dir.name


def _project_type(files: list[VaultFile]) -> Optional[str]:
    for f in files:
        if f.rel_path == Path("brief.md"):
            pt = f.frontmatter.fields.get("project_type")
            if isinstance(pt, str) and pt:
                return pt
    return None


# ============================================================
# CLI
# ============================================================


def cli_main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="dream.py",
        description="Adjudant dream — semantic content/staleness comparator catalog (read-only).",
    )
    parser.add_argument("--project-dir", help="Project root (default: cwd)", default=".")
    parser.add_argument("--vault-dir", help="Vault root (default: resolved from breadcrumb)")
    parser.add_argument("--out", help="Write JSON to FILE instead of stdout")
    parser.add_argument("--today", help="Override 'today' (YYYY-MM-DD) for age math")
    parser.add_argument(
        "--stale-days", type=int, default=DEFAULT_STALE_DAYS,
        help=f"Staleness age threshold in days (default: {DEFAULT_STALE_DAYS})",
    )
    parser.add_argument("--include-legacy", action="store_true", help="Include _legacy/ in scan")
    args = parser.parse_args(argv)

    today: Optional[_dt.date] = None
    if args.today:
        today = _parse_date(args.today)
        if today is None:
            print(f"error: --today not a valid YYYY-MM-DD: {args.today}", file=sys.stderr)
            return 1

    project_dir, vault_hint = smart_project_dir(args.project_dir)
    if not project_dir.is_dir():
        if (Path(args.project_dir).expanduser() / ".claude" / "adjudant").is_file():
            print(
                f"error: breadcrumb at {args.project_dir}/.claude/adjudant points to "
                f"vault project {project_dir} which doesn't exist. Run /adjudant connect first.",
                file=sys.stderr,
            )
        else:
            print(f"error: project-dir not found: {project_dir}", file=sys.stderr)
        return 1

    vault_dir: Optional[Path]
    if args.vault_dir:
        vault_dir = Path(args.vault_dir).expanduser().resolve()
    elif vault_hint:
        vault_dir = vault_hint
    else:
        vault_dir = resolve_vault(project_dir)
    if vault_dir and not vault_dir.is_dir():
        print(f"warn: vault-dir not a directory: {vault_dir}", file=sys.stderr)
        vault_dir = None

    report = run_dream(project_dir, vault_dir, today=today, stale_days=args.stale_days)

    payload = json.dumps(report, indent=2, default=str)
    if args.out:
        Path(args.out).expanduser().write_text(payload + "\n")
        print(f"[dream] wrote {args.out}", file=sys.stderr)
    else:
        print(payload)

    s = report["summary"]
    print(
        f"[dream] {report['meta']['project_slug']}: "
        f"{report['meta']['files_scanned']} files, "
        f"{s['candidates']} candidates "
        f"({s['staleness']} stale, {s['supersession']} supersede, "
        f"{s['contradiction']} contra, {s['redundancy_clusters']} dup-clusters, "
        f"{s['stale_refs']} stale-refs, {s['orphan_questions']} open-loops, "
        f"{s['orphan_threads']} orphans)",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(cli_main())
