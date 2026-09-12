#!/usr/bin/env python3
"""Tests for the grounded story corpus and the fact-check validator.

Fixtures below are REAL defects taken from production runs on 2026-08-30:
  - "बमलिंग शिवलिंग" (run 1788079500) -- garbled बर्फ़ का शिवलिंग
  - Arjuna wounded in a Ramayana episode (recorded in gen_script.py's own
    comment about liquid/lfm-2.5-2.6b)
"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import story_corpus


SAMPLE = """---
topic: हनुमान जी द्वारा संजीवनी पर्वत लाने की कथा
category: hanuman
source: वाल्मीकि रामायण, युद्धकाण्ड
confidence: high
---

## कथा

युद्ध के मैदान में मेघनाद के शक्ति-बाण से लक्ष्मण मूर्छित हो गए।

## मुख्य नाम

- लक्ष्मण
- मेघनाद

## संदेश

भक्ति असंभव को संभव बनाती है।

## सावधानी

- अर्जुन
- महाभारत
"""


class ParseTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.path = os.path.join(self.dir, "sanjeevani.md")
        with open(self.path, "w") as f:
            f.write(SAMPLE)

    def test_parses_frontmatter_and_sections(self):
        s = story_corpus.parse(self.path)
        self.assertEqual(s["topic"], "हनुमान जी द्वारा संजीवनी पर्वत लाने की कथा")
        self.assertEqual(s["category"], "hanuman")
        self.assertEqual(s["source"], "वाल्मीकि रामायण, युद्धकाण्ड")
        self.assertIn("मेघनाद", s["katha"])
        self.assertEqual(s["names"], ["लक्ष्मण", "मेघनाद"])
        self.assertEqual(s["avoid"], ["अर्जुन", "महाभारत"])
        self.assertEqual(s["message"], "भक्ति असंभव को संभव बनाती है।")

    def test_index_maps_topic_to_path(self):
        idx = story_corpus.index(self.dir)
        self.assertEqual(
            idx["हनुमान जी द्वारा संजीवनी पर्वत लाने की कथा"], self.path
        )

    def test_missing_required_section_is_rejected(self):
        bad = os.path.join(self.dir, "bad.md")
        with open(bad, "w") as f:
            f.write("---\ntopic: क\ncategory: x\nsource: y\n---\n\n## कथा\n\nabc\n")
        with self.assertRaises(story_corpus.CorpusError):
            story_corpus.parse(bad)


class FactCheckTest(unittest.TestCase):
    def setUp(self):
        self.story = {
            "names": ["लक्ष्मण", "मेघनाद"],
            "avoid": ["अर्जुन", "महाभारत"],
        }

    def test_accepts_faithful_narration(self):
        good = "मेघनाद के बाण से लक्ष्मण मूर्छित हुए, तब हनुमान पर्वत ले आए।"
        self.assertEqual(story_corpus.fact_check(good, self.story), "")

    def test_rejects_wrong_epic_character(self):
        # The exact liquid/lfm-2.5-2.6b failure: Mahabharata character in Ramayana.
        bad = "अर्जुन घायल हुए, तब हनुमान संजीवनी पर्वत ले आए।"
        self.assertIn("अर्जुन", story_corpus.fact_check(bad, self.story))

    def test_rejects_when_required_name_absent(self):
        bad = "एक योद्धा मूर्छित हुआ, तब हनुमान पर्वत ले आए।"
        problem = story_corpus.fact_check(bad, self.story)
        self.assertIn("लक्ष्मण", problem)

    def test_avoid_check_runs_even_when_names_present(self):
        bad = "मेघनाद के बाण से लक्ष्मण गिरे, जैसे महाभारत में हुआ था।"
        self.assertIn("महाभारत", story_corpus.fact_check(bad, self.story))


if __name__ == "__main__":
    unittest.main(verbosity=2)
