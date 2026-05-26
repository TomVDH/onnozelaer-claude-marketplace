"""Tests for adjudant/scripts/port.py."""

import tempfile
import unittest
from pathlib import Path

from port import detect_flavor


class TestDetectFlavor(unittest.TestCase):
    def test_raw_repo_returns_x(self):
        """An empty project dir (no breadcrumb, no AGENTS.md) is flavor X."""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(detect_flavor(Path(tmp)), "X")


if __name__ == "__main__":
    unittest.main()
