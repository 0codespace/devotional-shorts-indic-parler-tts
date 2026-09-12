#!/usr/bin/env python3
"""Pick the next devotional topic+category, cycling through topics.json without near-term repeats.
Also resolves a per-topic background image from image_urls.json (category or topic-keyed)."""
import json
import os
import random

BASE = os.path.expanduser("~/devotional-shorts")
TOPICS_PATH = os.path.join(BASE, "topics.json")
STATE_PATH = os.path.join(BASE, "topic_state.json")
IMG_PATH = os.path.join(BASE, "image_urls.json")

topics = json.load(open(TOPICS_PATH))
image_urls = {}
if os.path.exists(IMG_PATH):
    image_urls = json.load(open(IMG_PATH))

if os.path.exists(STATE_PATH):
    state = json.load(open(STATE_PATH))
else:
    state = {"remaining": []}

# Handle new "queues" format from pick_topic_scheduled.py
if "remaining" not in state:
    state["remaining"] = []

if not state["remaining"]:
    remaining = topics[:]
    random.shuffle(remaining)
    state["remaining"] = remaining

item = state["remaining"].pop(0)
json.dump(state, open(STATE_PATH, "w"))

# Resolve best background image: prefer an entry keyed by topic string, then category, else category default
topic_str = item.get("topic", "")
cat = item.get("category", "")
img = ""
if topic_str in image_urls:
    img = image_urls[topic_str]
elif cat in image_urls:
    img = image_urls[cat]
item_out = dict(item)
if img:
    item_out["image_override"] = img
print(json.dumps(item_out, ensure_ascii=False))
