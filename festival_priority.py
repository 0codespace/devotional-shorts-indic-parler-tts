#!/usr/bin/env python3
"""Festival-aware topic priority for the devotional Shorts pipeline.

The regular day_deity.py schedule is still the baseline. This module only raises
priority when a major Hindu festival is inside its promotion window, so the
channel publishes deity/event-relevant Shorts before search demand peaks.

Calendar dates are India/Panchang oriented and should be refreshed yearly. Set
FESTIVAL_PRIORITY=0 to disable, or FESTIVAL_TODAY=YYYY-MM-DD for tests/dry runs.
"""
import datetime as _dt
import json
import os

BASE = os.path.dirname(os.path.abspath(__file__))
CALENDAR_PATH = os.path.join(BASE, "festival_calendar.json")
IST = _dt.timezone(_dt.timedelta(hours=5, minutes=30))


def today_ist():
    override = os.environ.get("FESTIVAL_TODAY", "").strip()
    if override:
        return _dt.date.fromisoformat(override)
    return _dt.datetime.now(IST).date()


def enabled():
    return os.environ.get("FESTIVAL_PRIORITY", "1").lower() not in ("0", "false", "no", "off")


def load_events(path=CALENDAR_PATH):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def active_events(now=None, events=None):
    """Return festival events active for promotion today.

    An event is active from date-lead_days through one day after the festival.
    Sorting favours higher priority, then nearer date, then longer event-topic
    specificity.
    """
    if not enabled():
        return []
    now = now or today_ist()
    out = []
    for ev in events if events is not None else load_events():
        try:
            event_date = _dt.date.fromisoformat(ev["date"])
        except Exception:
            continue
        lead = int(ev.get("lead_days", 14))
        post = int(ev.get("post_days", 1))
        delta = (event_date - now).days
        if -post <= delta <= lead:
            row = dict(ev)
            row["days_until"] = delta
            out.append(row)
    out.sort(key=lambda e: (-int(e.get("priority", 0)), abs(int(e.get("days_until", 999))), -len(e.get("topics") or [])))
    return out


def pick_event(by_cat, grounded_topics, used_topics, now=None):
    """Pick the best active event that can actually publish a fresh story.

    Returns {event, category, priority_topics}. priority_topics contains exact
    event topics that are in topics.json, grounded, and not previously uploaded.
    If no exact event topic is fresh but the category has fresh grounded backlog,
    category is still returned so the picker can publish deity-relevant content.
    """
    grounded_topics = set(grounded_topics)
    used_topics = set(used_topics)
    for ev in active_events(now=now):
        cat = ev.get("category")
        if not cat:
            continue
        category_topics = by_cat.get(cat, [])
        category_names = {t.get("topic") for t in category_topics}
        fresh_category = [t for t in category_topics if t.get("topic") in grounded_topics and t.get("topic") not in used_topics]
        priority_topics = [
            topic for topic in ev.get("topics", [])
            if topic in category_names and topic in grounded_topics and topic not in used_topics
        ]
        if priority_topics or fresh_category:
            return {"event": ev, "category": cat, "priority_topics": priority_topics}
    return None


if __name__ == "__main__":
    print(json.dumps(active_events(), ensure_ascii=False, indent=2))
