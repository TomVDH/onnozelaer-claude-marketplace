"""Tests for adjudant/scripts/sync.py and adjudant/hooks/scripts/precompact.py."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Allow importing precompact from the sibling hooks/scripts directory
_HOOKS_SCRIPTS = Path(__file__).parent.parent / "hooks" / "scripts"
if str(_HOOKS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_HOOKS_SCRIPTS))

from precompact import (
    HARVEST_MAX_CHARS,
    HARVEST_N_MSGS,
    extract_transcript_text,
    harvest_with_gemini,
    sync_handoff,
)

from sync import (
    find_remember_source,
    mirror_handoff,
    refresh_brief_updated,
    refresh_projects_index_row,
    run_sync,
)


def _w(p: Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)


def _connected_setup(tmp: Path, slug: str = "p") -> tuple[Path, Path]:
    """Create a code project + connected vault."""
    proj = tmp / "code"; proj.mkdir()
    vault = tmp / "vault"; vault.mkdir()
    (vault / "Home.md").write_text("---\ntype: vault-home\n---\n")
    (vault / "projects").mkdir()
    (vault / "projects" / slug).mkdir()
    _w(vault / "projects" / slug / "brief.md",
       f"---\ntype: project\nproject_type: coding\nslug: {slug}\nstatus: active\nupdated: 2026-05-01\n---\n\n# Test\n")
    (vault / "projects" / slug / "sessions").mkdir()
    _w(proj / ".claude" / "adjudant",
       f"vault_path: {vault}\nvault_name: vault\nslug: {slug}\nmode: project\n")
    return proj, vault


# ============================================================
# Brief refresh
# ============================================================


class TestRefreshBriefUpdated(unittest.TestCase):

    def test_bumps_existing_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief = Path(tmp) / "brief.md"
            brief.write_text("---\nupdated: 2026-05-01\n---\nbody")
            r = refresh_brief_updated(brief, "2026-05-27")
            self.assertEqual(r, "bumped")
            self.assertIn("updated: 2026-05-27", brief.read_text())

    def test_unchanged_when_same(self):
        with tempfile.TemporaryDirectory() as tmp:
            brief = Path(tmp) / "brief.md"
            brief.write_text("---\nupdated: 2026-05-27\n---\nbody")
            r = refresh_brief_updated(brief, "2026-05-27")
            self.assertEqual(r, "unchanged")

    def test_missing_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(refresh_brief_updated(Path(tmp) / "nope.md", "2026-05-27"), "missing")


# ============================================================
# Handoff mirror
# ============================================================


class TestFindRememberSource(unittest.TestCase):

    def test_prefers_remember_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            _w(proj / ".remember" / "remember.md", "canonical")
            _w(proj / ".remember" / "now.md", "fallback")
            self.assertEqual(find_remember_source(proj).name, "remember.md")

    def test_falls_back_to_now_md(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            _w(proj / ".remember" / "now.md", "fallback")
            self.assertEqual(find_remember_source(proj).name, "now.md")

    def test_none_when_absent(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(find_remember_source(Path(tmp)))


class TestMirrorHandoff(unittest.TestCase):

    def test_creates_handoff_from_remember(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "code"; proj.mkdir()
            _w(proj / ".remember" / "now.md", "current state\n")
            handoff = Path(tmp) / "_handoff.md"
            r = mirror_handoff(proj, handoff, "p", "2026-05-27")
            self.assertEqual(r, "mirrored")
            content = handoff.read_text()
            self.assertIn("type: handoff", content)
            self.assertIn("updated: 2026-05-27", content)
            self.assertIn("current state", content)

    def test_no_source_when_remember_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp) / "code"; proj.mkdir()
            handoff = Path(tmp) / "_handoff.md"
            r = mirror_handoff(proj, handoff, "p", "2026-05-27")
            self.assertEqual(r, "no-source")


# ============================================================
# Projects index row refresh
# ============================================================


class TestRefreshProjectsIndexRow(unittest.TestCase):

    def test_updates_row_with_current_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, vault = _connected_setup(Path(tmp), "p")
            # Add a session + a decision
            _w(vault / "projects" / "p" / "sessions" / "2026-05-27.md", "---\ntype: session\n---\n")
            (vault / "projects" / "p" / "decisions").mkdir()
            _w(vault / "projects" / "p" / "decisions" / "2026-05-27-x.md", "---\ntype: decision\n---\n")
            r = refresh_projects_index_row(vault, "p")
            self.assertIn(r, ("inserted", "created-index", "updated"))
            text = (vault / "projects" / "_index.md").read_text()
            self.assertIn("p/brief", text)
            self.assertIn("2026-05-27", text)


# ============================================================
# End-to-end run_sync
# ============================================================


class TestRunSyncEndToEnd(unittest.TestCase):

    def test_full_sync(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, vault = _connected_setup(Path(tmp), "p")
            _w(proj / ".remember" / "now.md", "live state body\n")
            summary = run_sync(proj)
            # All three steps should produce useful outputs
            self.assertEqual(summary["slug"], "p")
            self.assertEqual(summary["steps"]["brief_refresh"], "bumped")
            self.assertEqual(summary["steps"]["handoff_mirror"], "mirrored")
            self.assertIn(summary["steps"]["projects_index_row"], ("inserted", "created-index", "updated"))
            # Handoff actually exists with the body
            handoff_content = (vault / "projects" / "p" / "_handoff.md").read_text()
            self.assertIn("live state body", handoff_content)

    def test_unconnected_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            # No breadcrumb
            with self.assertRaises(RuntimeError):
                run_sync(Path(tmp))


# ============================================================
# PreCompact: harvest_with_gemini failure modes
# ============================================================


class TestHarvestMissingTranscript(unittest.TestCase):

    def test_harvest_returns_empty_on_missing_transcript(self):
        result = harvest_with_gemini(Path("/nonexistent/path/transcript.jsonl"))
        self.assertEqual(result, "")


class TestHarvestUnparseableTranscript(unittest.TestCase):

    def test_harvest_returns_empty_on_unparseable_transcript(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "transcript.jsonl"
            t.write_text("this is not valid jsonl\njust plain text\n")
            result = harvest_with_gemini(t)
            self.assertEqual(result, "")


class TestHarvestGeminiTimeout(unittest.TestCase):

    def test_harvest_returns_empty_on_gemini_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "transcript.jsonl"
            t.write_text(
                json.dumps({"role": "user", "content": "Hello, world"}) + "\n"
            )
            with patch("precompact.subprocess.run",
                       side_effect=subprocess.TimeoutExpired(cmd="gemini", timeout=30)):
                result = harvest_with_gemini(t)
        self.assertEqual(result, "")


class TestHarvestNonZeroExit(unittest.TestCase):

    def test_harvest_returns_empty_on_non_zero_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "transcript.jsonl"
            t.write_text(
                json.dumps({"role": "user", "content": "Hello, world"}) + "\n"
            )
            mock_result = MagicMock()
            mock_result.returncode = 1
            mock_result.stdout = "- some bullet"
            with patch("precompact.subprocess.run", return_value=mock_result):
                result = harvest_with_gemini(t)
        self.assertEqual(result, "")


class TestHarvestNonBulletOutput(unittest.TestCase):

    def test_harvest_returns_empty_on_non_bullet_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "transcript.jsonl"
            t.write_text(
                json.dumps({"role": "user", "content": "Hello, world"}) + "\n"
            )
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = "I'm sorry, I can't help with that."
            with patch("precompact.subprocess.run", return_value=mock_result):
                result = harvest_with_gemini(t)
        self.assertEqual(result, "")


class TestHarvestSuccess(unittest.TestCase):

    def test_harvest_returns_bullets_on_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "transcript.jsonl"
            t.write_text(
                json.dumps({"role": "user", "content": "Implement the feature"}) + "\n"
                + json.dumps({"role": "assistant", "content": "Done"}) + "\n"
            )
            expected = "- decision 1\n- decision 2"
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = expected
            with patch("precompact.subprocess.run", return_value=mock_result):
                result = harvest_with_gemini(t)
        self.assertEqual(result, expected)


# ============================================================
# PreCompact: sync_handoff harvest injection
# ============================================================


class TestSyncHandoffHarvestInjection(unittest.TestCase):

    def _make_env(self, tmp: str) -> tuple:
        proj = Path(tmp) / "code"
        proj.mkdir()
        vault = Path(tmp) / "vault"
        vault.mkdir()
        (vault / "projects").mkdir()
        (vault / "projects" / "p").mkdir()
        (proj / ".remember").mkdir()
        (proj / ".remember" / "now.md").write_text("state body\n")
        return proj, vault

    def test_sync_handoff_includes_harvest_when_provided(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, vault = self._make_env(tmp)
            sync_handoff(proj, vault, "p", "2026-05-27", "14:00",
                         harvest="- decision made\n- blocker found")
            content = (vault / "projects" / "p" / "_handoff.md").read_text()
            self.assertIn("## Gemini harvest", content)
            self.assertIn("- decision made", content)
            self.assertIn("- blocker found", content)

    def test_sync_handoff_omits_harvest_when_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj, vault = self._make_env(tmp)
            sync_handoff(proj, vault, "p", "2026-05-27", "14:00", harvest="")
            content = (vault / "projects" / "p" / "_handoff.md").read_text()
            self.assertNotIn("## Gemini harvest", content)


# ============================================================
# PreCompact: extract_transcript_text
# ============================================================


class TestExtractTranscriptText(unittest.TestCase):

    def test_extract_transcript_text_strips_tool_calls(self):
        """tool_use and tool_result content blocks are excluded; only text survives."""
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "transcript.jsonl"
            lines = [
                json.dumps({"role": "user", "content": "plain text message"}),
                json.dumps({"role": "assistant", "content": [
                    {"type": "tool_use", "name": "Bash", "input": {"command": "ls"}},
                    {"type": "text", "text": "visible assistant text"},
                ]}),
                json.dumps({"role": "tool", "content": [
                    {"type": "tool_result", "content": "tool output here"},
                ]}),
            ]
            t.write_text("\n".join(lines) + "\n")
            result = extract_transcript_text(t)
            self.assertIn("plain text message", result)
            self.assertIn("visible assistant text", result)
            # tool_use name and tool_result content should not appear as text
            self.assertNotIn("tool output here", result)

    def test_extract_transcript_text_truncates_to_max_chars(self):
        """Output must not exceed HARVEST_MAX_CHARS characters."""
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp) / "transcript.jsonl"
            # Write enough messages to exceed the limit
            lines = [
                json.dumps({"role": "user", "content": "x" * 1000})
                for _ in range(20)
            ]
            t.write_text("\n".join(lines) + "\n")
            result = extract_transcript_text(t)
            self.assertLessEqual(len(result), HARVEST_MAX_CHARS)


if __name__ == "__main__":
    unittest.main()
