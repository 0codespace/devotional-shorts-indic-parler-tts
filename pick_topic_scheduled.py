#!/usr/bin/env python3
"""Pick the next devotional topic, preferring the day's preferred deity.

Day rule lives in day_deity.py. Topic rotation is tracked PER CATEGORY. When the
preferred deity's fresh grounded pool is exhausted, roll over to the category with
the largest fresh grounded backlog instead of wasting the publishing slot.
Sets a random Rani/Divya voice (enforced in tts_parler.py). Prints item JSON with
an added "voice" field.

GROUNDING GATE: only topics that have a story file in stories/ are eligible. An
ungrounded topic is skipped, never guessed at -- see story_corpus.py for why. If the
day's category has no grounded topic left, this exits 4 and publish_short_main.sh
turns that into a "skipped_no_story" result rather than a failure, so n8n does not
raise a false alarm on what is really just a corpus that needs more entries.
"""
import json, os, random, subprocess, sys, time, urllib.parse, urllib.request

import festival_priority
import story_corpus

BASE = os.path.expanduser("~/devotional-shorts")
TOPICS_PATH = os.path.join(BASE, "topics.json")
STATE_PATH = os.path.join(BASE, "topic_state.json")
IMG_PATH = os.path.join(BASE, "image_urls.json")
UPLOADS_PATH = os.path.join(BASE, "uploads.jsonl")
TG_TOKEN_PATH = os.path.join(BASE, "tg_token.txt")
TG_CHAT_ID = "5314505237"
LOW_POOL_WARN_THRESHOLD = 5
EXIT_NO_GROUNDED_TOPIC = 4


def notify_low_pool(category, remaining):
    # Best-effort only - never let a Telegram hiccup break topic picking.
    try:
        token = open(TG_TOKEN_PATH).read().strip()
        if remaining > 0:
            text = (f"⚠️ Devotional Shorts: '{category}' topic pool running low "
                     f"({remaining} fresh topic(s) left before repeats resume). "
                     "Consider adding more topics to topics.json.")
        else:
            text = (f"⚠️ Devotional Shorts: '{category}' fresh grounded topic pool is EXHAUSTED - "
                    "every eligible topic has been uploaded before. Add matching story files "
                    "for new topics (and entries in topics.json) before this category can resume.")
        body = urllib.parse.urlencode({"chat_id": TG_CHAT_ID, "text": text}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                      data=body, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def notify_rollover(category, replacement, remaining):
    # Exhaustion of a forced category should not waste a publishing slot. Use a
    # fresh grounded topic from another category and make the rollover visible.
    try:
        token = open(TG_TOKEN_PATH).read().strip()
        text = (f"ℹ️ Devotional Shorts: '{category}' is exhausted, so this slot "
                f"rolled over to '{replacement}' ({remaining} fresh grounded topic(s)).")
        body = urllib.parse.urlencode({"chat_id": TG_CHAT_ID, "text": text}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                      data=body, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def notify_no_grounded(category):
    try:
        token = open(TG_TOKEN_PATH).read().strip()
        text = (f"⏭️ Devotional Shorts: no grounded story left for '{category}' — this "
                f"slot was SKIPPED (no video published). Every topic in this category "
                f"either has no file in stories/ or has already been uploaded. "
                f"Add a story file to resume publishing for this deity.")
        body = urllib.parse.urlencode({"chat_id": TG_CHAT_ID, "text": text}).encode()
        req = urllib.request.Request(f"https://api.telegram.org/bot{token}/sendMessage",
                                      data=body, method="POST")
        urllib.request.urlopen(req, timeout=10)
    except Exception:
        pass


def ever_uploaded_topics():
    # upload_youtube.py's dedup guard (already_uploaded()) treats a topic as a
    # permanent duplicate the instant it's ever been uploaded once - no time
    # window. Match that here so the picker never hands out a topic that will
    # just get skipped at upload time.
    seen = set()
    if os.path.exists(UPLOADS_PATH):
        for line in open(UPLOADS_PATH):
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("status") == "uploaded":
                seen.add(rec.get("topic", ""))
    return seen

forced = subprocess.check_output(["python3", os.path.join(BASE, "day_deity.py")]).decode().strip()

topics = json.load(open(TOPICS_PATH))
image_urls = json.load(open(IMG_PATH)) if os.path.exists(IMG_PATH) else {}

# group topics by category
by_cat = {}
for t in topics:
    by_cat.setdefault(t.get("category", "?"), []).append(t)

# Only grounded topics are eligible. Note this also fixes stale queues for free:
# pool_ids below is grounded-only, so any queue in topic_state.json still holding an
# ungrounded topic fails the "all items still in pool" check and gets rebuilt.
grounded = story_corpus.index()
used = ever_uploaded_topics()

# Prefer the scheduled deity, but let major festivals temporarily override it
# when that festival can actually publish a fresh grounded story. This captures
# demand around Ganesh Chaturthi, Janmashtami, Navratri, Diwali, etc. without
# weakening the no-repeat or grounded-corpus guarantees.
def fresh_grounded(category):
    return [t for t in by_cat.get(category, [])
            if t.get("topic") in grounded and t.get("topic") not in used]

scheduled_forced = forced
festival_pick = festival_priority.pick_event(by_cat, grounded.keys(), used)
priority_topic_names = []
if festival_pick:
    forced = festival_pick["category"]
    priority_topic_names = festival_pick.get("priority_topics", [])
    if forced != scheduled_forced:
        ev = festival_pick["event"]
        notify_rollover(scheduled_forced, f"{forced} ({ev['name']} {ev['date']})", len(fresh_grounded(forced)))

pool = [t for t in by_cat.get(forced, []) if t.get("topic") in grounded]
fresh_forced = fresh_grounded(forced)
if not fresh_forced:
    if not pool:
        notify_no_grounded(forced)
        print(json.dumps({"status": "no_grounded_topic", "category": forced}, ensure_ascii=False))
        sys.exit(EXIT_NO_GROUNDED_TOPIC)
    # Prefer the category with the largest fresh grounded backlog; this keeps the
    # channel publishing while retaining the no-repeat and grounding guarantees.
    alternatives = [(len(fresh_grounded(cat)), cat)
                    for cat in by_cat if cat != forced and fresh_grounded(cat)]
    if alternatives:
        remaining, replacement = max(alternatives)
        notify_rollover(forced, replacement, remaining)
        forced = replacement
        pool = [t for t in by_cat.get(forced, []) if t.get("topic") in grounded]

# per-category rotation queue in state
state = json.load(open(STATE_PATH)) if os.path.exists(STATE_PATH) else {}
queues = state.get("queues", {})
q = queues.get(forced, [])
used = ever_uploaded_topics()
# rebuild queue if empty or stale (contains topics no longer in pool)
pool_ids = [json.dumps(t, sort_keys=True, ensure_ascii=False) for t in pool]
if not q or priority_topic_names or not all(item in pool_ids for item in q):
    # Exclude any topic ever uploaded before - upload_youtube.py's dedup guard
    # is permanent (no time window). Once the fresh pool is empty, leave the
    # queue empty so the slot is skipped cleanly instead of rendering a duplicate.
    fresh_pool_ids = [pid for pid in pool_ids if json.loads(pid).get("topic") not in used]
    if len(fresh_pool_ids) < LOW_POOL_WARN_THRESHOLD:
        notify_low_pool(forced, len(fresh_pool_ids))
    if priority_topic_names:
        priority = [pid for pid in fresh_pool_ids if json.loads(pid).get("topic") in priority_topic_names]
        rest = [pid for pid in fresh_pool_ids if json.loads(pid).get("topic") not in priority_topic_names]
        random.shuffle(priority)
        random.shuffle(rest)
        q = priority + rest
    else:
        q = fresh_pool_ids
        random.shuffle(q)
else:
    # A queue can remain structurally valid after another scheduled slot uploads
    # one of its items.  Filter those permanent duplicates on every run, not only
    # when the queue is rebuilt; otherwise later slots can render and upload the
    # same topic again before upload_youtube.py catches it.
    q = [item for item in q if json.loads(item).get("topic") not in used]

# Do not deliberately hand a known duplicate to the uploader when this category
# has no fresh grounded topic left.  The caller treats exit 4 as a clean slot
# skip, and the next run can resume once topics/stories are added.
if not q:
    notify_low_pool(forced, 0)
    queues[forced] = []
    json.dump({"queues": queues}, open(STATE_PATH, "w"))
    print(json.dumps({"status": "no_grounded_topic", "category": forced}, ensure_ascii=False))
    sys.exit(EXIT_NO_GROUNDED_TOPIC)

# Pop-time guard. The rebuild above already filters, but a story file can be
# deleted or broken between the rebuild and this run, and a queue persisted by an
# older version of this script predates the filter entirely.
item = None
while q:
    candidate = json.loads(q.pop(0))
    if candidate.get("topic") in grounded:
        item = candidate
        break
if item is None:
    queues[forced] = q
    json.dump({"queues": queues}, open(STATE_PATH, "w"))
    notify_no_grounded(forced)
    print(json.dumps({"status": "no_grounded_topic", "category": forced}, ensure_ascii=False))
    sys.exit(EXIT_NO_GROUNDED_TOPIC)

queues[forced] = q
json.dump({"queues": queues}, open(STATE_PATH, "w"))

topic_str = item.get("topic", "")
cat = item.get("category", "")
img = ""
if topic_str in image_urls:
    img = image_urls[topic_str]
elif cat in image_urls:
    img = image_urls[cat]

voice = random.choice(["Rani", "Divya"])
item_out = dict(item)
if img:
    item_out["image_override"] = img
item_out["voice"] = voice
if festival_pick:
    ev = festival_pick["event"]
    item_out["festival_event"] = ev.get("name")
    item_out["festival_date"] = ev.get("date")
    item_out["scheduled_category"] = scheduled_forced
print(json.dumps(item_out, ensure_ascii=False))
