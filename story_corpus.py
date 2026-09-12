#!/usr/bin/env python3
"""Grounded story corpus for the devotional Shorts pipeline.

WHY THIS EXISTS
---------------
gen_script.py used to hand a free-tier LLM nothing but a topic string and ask it
to recall the story from memory. Nothing grounded it, and the existing validators
only caught *encoding* defects (stray Latin, leading combining characters), never
wrong facts. Production runs on 2026-08-30 shipped "बमलिंग शिवलिंग" (garbled
बर्फ़ का शिवलिंग) and, earlier, Arjuna wounded inside a Ramayana episode.

The corpus flips the model's job from recall to retell. Each topic gets one
markdown file holding the canonical narrative, the names that must survive into
the narration, and the confusions that must not. A story the model cannot see is
a story it cannot get wrong -- and a topic with no file is skipped rather than
guessed at (see pick_topic_scheduled.py).

FILE FORMAT
-----------
    ---
    topic: <exact string from topics.json -- this is the join key>
    category: <matches topics.json>
    source: <scripture + section, so a wrong story is traceable>
    confidence: high | medium
    ---

    ## कथा       -- canonical narrative, 150-250 words. Ground truth, NOT a script.
    ## मुख्य नाम  -- names that MUST appear in the narration. Keep to 2-4; every
                    one is enforced, and a 70-90 word Short cannot carry more.
    ## संदेश      -- the moral, one line.
    ## सावधानी    -- terms that must NEVER appear. Known confusions for THIS story.
"""
import os
import re

BASE = os.path.dirname(os.path.abspath(__file__))
STORIES_DIR = os.path.join(BASE, "stories")

# Section heading -> key in the parsed dict. Devanagari headings keep the files
# readable to a Hindi-speaking reviewer, which is the whole point of the corpus.
_SECTIONS = {
    "कथा": "katha",
    "मुख्य नाम": "names",
    "संदेश": "message",
    "सावधानी": "avoid",
}
_LIST_SECTIONS = {"names", "avoid"}
_REQUIRED = ("topic", "category", "source", "katha", "names", "message", "avoid")


class CorpusError(Exception):
    """A story file is missing or malformed."""


def parse(path):
    """Parse one story markdown file into a dict. Raises CorpusError if invalid."""
    with open(path, encoding="utf-8") as f:
        raw = f.read()

    m = re.match(r"\s*---\n(.*?)\n---\n(.*)", raw, re.S)
    if not m:
        raise CorpusError(f"{path}: missing --- frontmatter block")
    front, body = m.group(1), m.group(2)

    story = {}
    for line in front.splitlines():
        line = line.strip()
        if not line or ":" not in line:
            continue
        k, v = line.split(":", 1)
        story[k.strip()] = v.strip()

    # Split the body on level-2 headings, keeping each heading with its content.
    for chunk in re.split(r"^##\s+", body, flags=re.M)[1:]:
        head, _, content = chunk.partition("\n")
        key = _SECTIONS.get(head.strip())
        if not key:
            continue
        if key in _LIST_SECTIONS:
            story[key] = [
                ln.strip().lstrip("-").strip()
                for ln in content.splitlines()
                if ln.strip().startswith("-") and ln.strip().lstrip("-").strip()
            ]
        else:
            story[key] = " ".join(content.split())

    missing = [k for k in _REQUIRED if not story.get(k)]
    if missing:
        raise CorpusError(f"{path}: missing or empty section(s): {', '.join(missing)}")
    return story


def index(stories_dir=None):
    """Map every valid story's topic string -> its file path.

    A malformed file is skipped rather than fatal: one bad file must not take the
    whole night's schedule down. It simply stops grounding its own topic, and that
    topic then gets skipped like any ungrounded one.
    """
    stories_dir = stories_dir or STORIES_DIR
    found = {}
    for root, _dirs, files in os.walk(stories_dir):
        for name in sorted(files):
            if not name.endswith(".md"):
                continue
            path = os.path.join(root, name)
            try:
                story = parse(path)
            except CorpusError:
                continue
            found[story["topic"]] = path
    return found


def load(topic, stories_dir=None):
    """Return the parsed story for a topic, or None if it isn't in the corpus."""
    path = index(stories_dir).get(topic)
    return parse(path) if path else None


def fact_check(narration, story):
    """Return '' if the narration is faithful to the story, else why it isn't.

    Two rules, both cheap and both catching real production failures:
      1. no term in `सावधानी` may appear -- these are the specific confusions
         this story is known to attract;
      2. every name in `मुख्य नाम` must appear -- a retelling that drops the
         protagonist has drifted off the source.

    The forbidden-term check runs FIRST on purpose. A narration that swaps in the
    wrong character (Arjuna for Lakshmana) also drops the required names, so
    checking names first would report the vague "name missing" instead of naming
    the actual defect -- and the log line is what tells a human which story file
    needs fixing.
    """
    text = narration or ""
    for bad in story.get("avoid", []):
        if bad in text:
            return f"forbidden term in narration: {bad!r}"
    absent = [n for n in story.get("names", []) if n not in text]
    if absent:
        return "required name(s) missing from narration: " + ", ".join(absent)
    return ""


def _coverage_report():
    """Print grounded/ungrounded topic counts per category. `python3 story_corpus.py`"""
    import collections
    import json as _json

    topics = _json.load(open(os.path.join(BASE, "topics.json"), encoding="utf-8"))
    grounded = index()
    per_cat = collections.defaultdict(lambda: {"grounded": [], "missing": []})
    for t in topics:
        bucket = "grounded" if t["topic"] in grounded else "missing"
        per_cat[t.get("category", "?")][bucket].append(t["topic"])

    print(f"{len(grounded)}/{len(topics)} topics grounded\n")
    for cat in sorted(per_cat, key=lambda c: -len(per_cat[c]["grounded"])):
        g, m = per_cat[cat]["grounded"], per_cat[cat]["missing"]
        flag = "" if g else "   <-- publishing BLOCKED for this deity"
        print(f"{cat:10} {len(g):3} grounded, {len(m):3} missing{flag}")

    blocked = [c for c, v in per_cat.items() if not v["grounded"]]
    if blocked:
        print("\nCategories with no story files (runs for these days will be skipped):")
        for cat in sorted(blocked):
            print(f"  {cat}: {len(per_cat[cat]['missing'])} topics waiting")


if __name__ == "__main__":
    _coverage_report()
