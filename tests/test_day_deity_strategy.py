#!/usr/bin/env python3
"""Tests for the analytics-informed category schedule."""
import datetime
import os
import sys
import unittest
from unittest import mock

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

import day_deity  # noqa: E402


class DayDeityStrategyTest(unittest.TestCase):
    def test_wednesday_now_prefers_hanuman(self):
        now = datetime.datetime(2026, 9, 2, 6, 0)  # Wednesday
        self.assertEqual(day_deity.day_category(now), "hanuman")

    def test_tuesday_keeps_ganesha_slot(self):
        now = datetime.datetime(2026, 9, 1, 6, 0)  # Tuesday
        self.assertEqual(day_deity.day_category(now), "ganesha")

    def test_free_day_uses_analytics_weighted_pool(self):
        now = datetime.datetime(2026, 9, 3, 6, 0)  # Thursday
        with mock.patch.object(day_deity, "_grounded_categories", return_value={"hanuman"}):
            self.assertEqual(day_deity.day_category(now), "hanuman")


if __name__ == "__main__":
    unittest.main(verbosity=2)
