"""Tests for adjudant/scripts/_handoff_freshness.py.

The shared freshness primitives used by both the PreCompact hook and the
`/adjudant sync` verb.
"""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

import _handoff_freshness as pc

NOW = datetime(2026, 6, 1, 14, 0)


def _write(p: Path, text: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


# ============================================================
# parse_next_line
# ============================================================


class TestParseNextLine(unittest.TestCase):

    def test_inline_plain(self):
        self.assertEqual(pc.parse_next_line("NEXT: wire the UI steps"), "wire the UI steps")

    def test_inline_bold(self):
        self.assertEqual(pc.parse_next_line("**NEXT:** ship the thing"), "ship the thing")

    def test_inline_bulleted(self):
        self.assertEqual(pc.parse_next_line("- NEXT — review the PR"), "review the PR")

    def test_heading_form(self):
        text = "## NEXT\n\n- finish the migration\n- later thing\n"
        self.assertEqual(pc.parse_next_line(text), "finish the migration")

    def test_first_inline_wins_over_body(self):
        text = "intro\nNEXT: do A\nmore\n## NEXT\n- do B\n"
        self.assertEqual(pc.parse_next_line(text), "do A")

    def test_none_when_absent(self):
        self.assertIsNone(pc.parse_next_line("just some notes\nno next here"))


# ============================================================
# traffic light + age formatting
# ============================================================


class TestTrafficLightAndAge(unittest.TestCase):

    def test_green_under_2h(self):
        self.assertEqual(pc.traffic_light(1.5), "\U0001f7e2")

    def test_yellow_2_to_8h(self):
        self.assertEqual(pc.traffic_light(6.0), "\U0001f7e1")

    def test_red_over_8h(self):
        self.assertEqual(pc.traffic_light(11.0), "\U0001f534")

    def test_white_when_unknown(self):
        self.assertEqual(pc.traffic_light(None), "⚪")

    def test_age_minutes_hours_days(self):
        self.assertEqual(pc.fmt_age(0.5), "30m")
        self.assertEqual(pc.fmt_age(6.0), "6h")
        self.assertEqual(pc.fmt_age(72.0), "3d")
        self.assertEqual(pc.fmt_age(None), "unknown")

    def test_age_hours_never_negative(self):
        future = datetime(2026, 6, 1, 15, 0)
        self.assertEqual(pc.age_hours(future, NOW), 0.0)


# ============================================================
# latest_today_activity
# ============================================================


class TestLatestTodayActivity(unittest.TestCase):

    def test_reads_last_time_with_date_from_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp) / ".remember"
            _write(rd / "today-2026-06-01.md", "- 09:00 started\n- 13:30 did a thing\n")
            dt = pc.latest_today_activity(rd)
            self.assertEqual(dt, datetime(2026, 6, 1, 13, 30))

    def test_picks_newest_across_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp) / ".remember"
            _write(rd / "today-2026-05-30.md", "- 18:00 old\n")
            _write(rd / "today-2026-06-01.md", "- 08:15 newer\n")
            dt = pc.latest_today_activity(rd)
            self.assertEqual(dt, datetime(2026, 6, 1, 8, 15))

    def test_none_when_no_today_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd = Path(tmp) / ".remember"
            rd.mkdir(parents=True)
            self.assertIsNone(pc.latest_today_activity(rd))


# ============================================================
# latest_session_activity (markers ignored)
# ============================================================


class TestLatestSessionActivity(unittest.TestCase):

    def test_ignores_hook_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            sf = Path(tmp) / "2026-06-01.md"
            _write(sf, "- 10:00 · Added: [[x]]\n- 23:59 · paused (compaction)\n")
            dt = pc.latest_session_activity(sf, NOW)
            self.assertEqual(dt, datetime(2026, 6, 1, 10, 0))  # 23:59 marker ignored

    def test_none_when_only_markers(self):
        with tempfile.TemporaryDirectory() as tmp:
            sf = Path(tmp) / "2026-06-01.md"
            _write(sf, "- 09:00 · session ended\n")
            self.assertIsNone(pc.latest_session_activity(sf, NOW))


# ============================================================
# compute_freshness (stale logic + end-to-end header)
# ============================================================


class TestComputeFreshness(unittest.TestCase):

    def _project(self, tmp, today_lines, session_lines):
        root = Path(tmp)
        _write(root / ".remember" / "today-2026-06-01.md", today_lines)
        _write(root / ".remember" / "remember.md", "NEXT: do the next thing\n\nbody")
        sf = root / "sessions" / "2026-06-01.md"
        _write(sf, session_lines)
        return root, sf

    def test_fresh_not_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sf = self._project(tmp, "- 13:30 worked\n", "- 12:00 · Added: [[x]]\n")
            light, age, nxt, stale = pc.compute_freshness(
                root, (root / ".remember" / "remember.md").read_text(),
                root / ".remember" / "remember.md", sf, NOW)
            self.assertEqual(nxt, "do the next thing")
            self.assertFalse(stale)            # session 12:00 < activity 13:30
            self.assertEqual(light, "\U0001f7e2")  # 30m old → green

    def test_stale_when_session_newer_than_handoff(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, sf = self._project(tmp, "- 09:00 worked\n", "- 13:45 · Added: [[y]]\n")
            light, age, nxt, stale = pc.compute_freshness(
                root, (root / ".remember" / "remember.md").read_text(),
                root / ".remember" / "remember.md", sf, NOW)
            self.assertTrue(stale)             # session 13:45 > activity 09:00

    def test_header_renders_light_age_next_and_stale(self):
        block = pc.freshness_header("\U0001f534", "11h", "ship it", True)
        self.assertIn("handoff age: 11h", block)
        self.assertIn("NEXT: ship it", block)
        self.assertIn("STALE", block)

    def test_header_next_not_set(self):
        block = pc.freshness_header("\U0001f7e2", "1h", None, False)
        self.assertIn("NEXT: (not set)", block)
        self.assertNotIn("STALE", block)


if __name__ == "__main__":
    unittest.main()
