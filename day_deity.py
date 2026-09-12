#!/usr/bin/env python3
"""Day-of-week -> preferred category for the devotional Shorts schedule.

Rule, updated from YouTube analytics on 2026-09-02:
  Sunday, Monday   -> mahadev (Shiva)
  Friday, Saturday -> hanuman
  Tuesday           -> ganesha
  Wednesday         -> hanuman
  Thursday / other  -> weighted random, biased to hanuman and dramatic epics

The ZIP gallery covers: ganesha, hanuman, mahadev, shree krishna.
Pipeline category names: shiva (==mahadev), krishna (==shree krishna).
Prints the pipeline category (e.g. "shiva") for the current day.
"""
import random, datetime

import story_corpus

# weekday(): Monday=0 ... Sunday=6
FORCED = {
    6: "shiva",   # Sunday
    0: "shiva",   # Monday
    4: "hanuman", # Friday
    5: "hanuman", # Saturday
    1: "ganesha", # Tuesday
    2: "hanuman", # Wednesday: analytics showed Hanuman stories outperform
}

# Free days should not be uniform anymore. YouTube's own report showed Hanuman
# stories and high-stakes mythology carrying the channel's strongest results, so
# keep experimental slots biased toward that pattern while still leaving room for
# variety and corpus freshness.
FREE_POOL_WEIGHTED = [
    "hanuman", "hanuman", "hanuman", "hanuman",
    "rama", "vishnu", "krishna", "shiva", "ganesha",
]


def _grounded_categories():
    """Categories that have at least one story file in stories/.

    A category with no grounded story cannot publish at all (pick_topic_scheduled.py
    skips it), so choosing one on a free day burns the slot for nothing. The forced
    days are the owner's schedule and are left alone -- only the free-day random
    choice is narrowed.
    """
    try:
        cats = set()
        for path in story_corpus.index().values():
            cats.add(story_corpus.parse(path)["category"])
        return cats
    except Exception:
        return set()


def day_category(now=None):
    now = now or datetime.datetime.now()
    wd = now.weekday()
    if wd in FORCED:
        return FORCED[wd]
    grounded = _grounded_categories()
    pool = [c for c in FREE_POOL_WEIGHTED if c in grounded] or FREE_POOL_WEIGHTED
    return random.choice(pool)

if __name__ == "__main__":
    print(day_category())
