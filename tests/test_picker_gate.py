#!/usr/bin/env python3
"""Integration test for the grounding gate in pick_topic_scheduled.py.

Runs the real script in-process with only two things stubbed: the day->deity
subprocess (so we can force a category) and Telegram (so a test never pages
anyone). Everything else -- topics.json, the real stories/ corpus, the real
uploads log -- is production data, which is the point: this asserts the gate
against the corpus as it actually is.

The forced category 'unknown' has no topics, so it exercises the skip path without
needing a fixture corpus.
"""
import io
import os
import subprocess
import sys
import unittest
from contextlib import redirect_stdout
from unittest import mock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
PICKER = os.path.join(BASE, "pick_topic_scheduled.py")

import json  # noqa: E402
import story_corpus  # noqa: E402


def run_picker(forced_category):
    """Exec the picker with the day's deity forced. Returns (exit_code, stdout)."""
    src = open(PICKER, encoding="utf-8").read()
    buf = io.StringIO()
    code = 0
    with mock.patch.dict(os.environ, {"FESTIVAL_PRIORITY": "0"}), \
         mock.patch.object(subprocess, "check_output",
                           return_value=(forced_category + "\n").encode()), \
         mock.patch("urllib.request.urlopen", side_effect=RuntimeError("no telegram in tests")):
        try:
            with redirect_stdout(buf):
                exec(compile(src, PICKER, "exec"), {"__name__": "__main__"})
        except SystemExit as e:
            code = e.code or 0
    return code, buf.getvalue().strip()


class GroundingGateTest(unittest.TestCase):
    def test_ungrounded_category_skips_cleanly(self):
        # An unknown category has no topics -> must skip, not guess.
        code, out = run_picker("unknown")
        self.assertEqual(code, 4, "expected EXIT_NO_GROUNDED_TOPIC")
        self.assertEqual(json.loads(out)["status"], "no_grounded_topic")

    def test_grounded_category_returns_grounded_topic(self):
        grounded = story_corpus.index()
        for cat in ("shiva", "ganesha", "hanuman"):
            with self.subTest(category=cat):
                code, out = run_picker(cat)
                # A category can have grounded stories but no fresh topics left.
                # That is a clean exhaustion skip, not a reason to repeat one.
                if code == 4:
                    self.assertEqual(json.loads(out)["status"], "no_grounded_topic")
                    continue
                self.assertEqual(code, 0, f"{cat} should have grounded topics")
                item = json.loads(out)
                self.assertEqual(item["category"], cat)
                self.assertIn(item["topic"], grounded,
                              "picker handed out a topic with no story file")

    def test_never_hands_out_an_ungrounded_topic_over_many_picks(self):
        # Drains the shiva queue repeatedly; every pick must stay grounded, and the
        # run must never fall back to another deity's pool.
        grounded = story_corpus.index()
        for _ in range(12):
            code, out = run_picker("shiva")
            if code == 4:
                break
            item = json.loads(out)
            self.assertIn(item["topic"], grounded)
            self.assertEqual(item["category"], "shiva")


if __name__ == "__main__":
    unittest.main(verbosity=2)
