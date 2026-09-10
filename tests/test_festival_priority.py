#!/usr/bin/env python3
"""Tests for festival-aware devotional topic priority."""
import datetime
import os
import sys
import unittest
from unittest import mock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import festival_priority  # noqa: E402


class FestivalPriorityTest(unittest.TestCase):
    def test_active_window_finds_ganesh_chaturthi(self):
        events = festival_priority.active_events(now=datetime.date(2026, 9, 10))
        self.assertTrue(events)
        self.assertEqual(events[0]["name"], "Ganesh Chaturthi")
        self.assertEqual(events[0]["category"], "ganesha")

    def test_can_disable_with_env(self):
        with mock.patch.dict(os.environ, {"FESTIVAL_PRIORITY": "0"}):
            self.assertEqual(festival_priority.active_events(now=datetime.date(2026, 9, 10)), [])

    def test_pick_event_requires_fresh_grounded_content(self):
        by_cat = {"ganesha": [{"topic": "गणेश चतुर्थी मनाने के पीछे की कथा", "category": "ganesha"}]}
        picked = festival_priority.pick_event(
            by_cat,
            grounded_topics={"गणेश चतुर्थी मनाने के पीछे की कथा"},
            used_topics=set(),
            now=datetime.date(2026, 9, 10),
        )
        self.assertEqual(picked["category"], "ganesha")
        self.assertEqual(picked["priority_topics"], ["गणेश चतुर्थी मनाने के पीछे की कथा"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
