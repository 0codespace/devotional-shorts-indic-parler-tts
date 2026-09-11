#!/usr/bin/env python3
"""Generate a short devotional Shorts script (Hindi) via OpenRouter (free tier, with fallback models).

The model is a RETELLER, not a source. Every topic must have a grounded story in
stories/ (see story_corpus.py); its canonical narrative is embedded in the prompt
verbatim and the model's only job is to compress it into 70-90 spoken words with a
real story arc. Before this, the prompt carried nothing but a topic string and the
model recalled the story from memory -- which is how "बमलिंग शिवलिंग" and Arjuna in
a Ramayana episode reached production on 2026-08-30.

Refusing to run without a story file is deliberate. An ungrounded generation is
exactly the failure mode this module exists to remove, so there is no fallback to
the old behaviour: pick_topic_scheduled.py only ever hands over grounded topics.
"""
import os, json
import re
import sys
import time
import urllib.error
import urllib.request

import story_corpus

URL = "https://openrouter.ai/api/v1/chat/completions"

# Keys are tried in order for EVERY model. The free-tier 429s are usually
# upstream (provider-wide, e.g. Google AI Studio) rather than per-key, so key
# rotation alone will not rescue a rate-limited model -- that is what the
# multi-model list below is for. Rotation still helps for per-key daily caps.
def _load_keys():
    keys, seen = [], set()
    env = os.path.expanduser("~/.automation.env")
    if os.path.exists(env):
        for line in open(env):
            line = line.strip()
            if line.startswith("OPENROUTER_API_KEY"):
                v = line.split("=", 1)[1].strip().strip('"').strip("'")
                if v and v not in seen:
                    seen.add(v); keys.append(v)
    # Never commit API keys. Configure OPENROUTER_API_KEY in ~/.automation.env.
    return keys

KEYS = _load_keys()

# Ordered best-first. nvidia/nemotron-3-nano-30b-a3b:free was REMOVED -- it now
# 404s ("unavailable for free"). liquid/lfm-2.5-2.6b:free was DEMOTED to last:
# it answers, but at 2.6B it invents facts (it wrote the Sanjeevani story with
# Arjuna wounded by Kaurava arrows -- Mahabharata characters in a Ramayana
# episode), which is worse than a clean failure on a devotional channel.
MODELS = [
    "minimax/minimax-m3:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "minimax/minimax-m2.7:free",
    "google/gemma-4-31b-it:free",
    "google/gemma-4-26b-a4b-it:free",
    "liquid/lfm-2.5-2.6b:free",
]

topic = sys.argv[1] if len(sys.argv) > 1 else "गायत्री मंत्र का अर्थ"

story = story_corpus.load(topic)
if story is None:
    raise SystemExit(
        f"No grounded story for topic {topic!r}. Add a file under stories/ with a "
        f"matching 'topic:' frontmatter line, or let pick_topic_scheduled.py choose "
        f"a grounded topic instead. Refusing to generate ungrounded narration."
    )

names = "、".join(story["names"])
avoid = "、".join(story["avoid"])

prompt = f"""नीचे एक प्रामाणिक पौराणिक कथा दी गई है। आपका काम इसे नया रचना नहीं, बल्कि 20-24 सेकंड की YouTube Shorts के लिए संक्षेप में सुनाना है।

=== मूल कथा (यही एकमात्र सत्य स्रोत है) ===
{story["katha"]}
=== मूल कथा समाप्त ===

संदेश: {story["message"]}

कथा-शिल्प के नियम (सबसे महत्वपूर्ण):
- पहला वाक्य 0.5 सेकंड के भीतर शुरू होने वाला तीखा हुक हो — सीधे संघर्ष, खतरे या असंभव घटना से शुरू करें। "क्या आप जानते हैं" और "आइए जानते हैं" जैसी धीमी शुरुआत कभी न करें।
- पहले वाक्य में कथा का संघर्ष साफ दिखे: किसने क्या असंभव काम किया, कौन हैरान हुआ, या कौन-सा निर्णय सब बदल गया।
- बीच में मोड़ (turn) आए — वह क्षण जहाँ कथा पलटती है।
- अंतिम वाक्य निष्कर्ष हो, जो संदेश को छू ले।
- यह निबंध नहीं, कहानी है। घटनाएँ सुनाएँ, व्याख्या नहीं।
- अंत में comment-bait को narration में न जोड़ें; CTA अलग JSON field में दिया जाएगा।

तथ्य के नियम (इनका उल्लंघन अस्वीकार्य है):
- केवल ऊपर दी गई कथा की घटनाओं का उपयोग करें। अपनी ओर से कोई घटना, नाम, स्थान या विवरण न जोड़ें।
- ये नाम narration में अनिवार्य रूप से आने चाहिए: {names}
- ये शब्द narration में कभी नहीं आने चाहिए (ये इस कथा से संबंधित नहीं हैं): {avoid}

भाषा के नियम:
- वर्णन (narration) शुद्ध हिंदी (देवनागरी लिपि) में, स्वाभाविक बोलचाल की भाषा में। लंबाई अनिवार्य रूप से 42 से 58 शब्दों के बीच हो — यह सबसे कड़ा नियम है। मूल कथा लगभग 180 शब्दों की है; आपको उसे बहुत कसकर समेटना है, इसलिए केवल निर्णायक घटनाएँ रखें और शेष विवरण निर्दयता से हटा दें। 85 शब्दों से अधिक का उत्तर अस्वीकार कर दिया जाएगा।
- कोई अंग्रेज़ी शब्द या रोमन अक्षर narration, key_line या title में न हो (केवल hashtags अंग्रेज़ी में हों)।
- "key_line" (अधिकतम 10-12 शब्द) कथा का निष्कर्ष हो, हिंदी में।
- "cta" में भक्तिपूर्ण कमेंट prompt हो, जैसे "जय बजरंग बली लिखें" / "हर हर महादेव लिखें" / "आपके अनुसार सबसे बड़ा भक्त कौन था?"
- "visual_beats" में 6-8 छोटे हिंदी visual cues दें, हर cue 2-3 सेकंड के दृश्य बदलाव के लिए हो।
- शीर्षक (title) हिंदी में, अधिकतम 60 अक्षर, जिसमें "#Shorts" शामिल हो।
- 5 प्रासंगिक hashtags अंग्रेज़ी में दें।

केवल इस JSON प्रारूप में उत्तर दें, कोई markdown fence या अतिरिक्त पाठ नहीं:
{{"title": "...", "narration": "...", "key_line": "...", "cta": "...", "visual_beats": ["...", "..."], "hashtags": "#tag1 #tag2 #tag3 #tag4 #tag5"}}"""

body_base = {"messages": [{"role": "user", "content": prompt}]}
headers = {
    "Content-Type": "application/json",
    "HTTP-Referer": "http://130.210.1.29",
    "X-Title": "Devotional Shorts Generator",
}

# Devanagari dependent vowel signs / nukta / virama / stress marks: these are
# combining characters and can never legally start a word. Free-tier models
# occasionally drop the leading consonant and emit one of these as the first
# character (e.g. title "ैका..." instead of "कैसे..."), which is invalid Hindi
# but still parses as valid JSON, so a JSON-only check lets it through.
_DEVANAGARI_COMBINING = set(
    "़ािीुूृॄॅॆेै"
    "ॉॊोौ्ॎॏ॒॑॓॔ॕॖॗ"
)


def _malformed(field: str) -> bool:
    s = (field or "").strip()
    return not s or s[0] in _DEVANAGARI_COMBINING


# Spoken fields must be pure Devanagari. Free-tier models sometimes leak a Latin
# word straight into the narration, occasionally glued to the previous word with
# no space -- on 2026-08-30 a model emitted "उन्होंनेagni में तांडव किया", which is
# valid JSON and starts with a legal character, so neither the JSON parse nor the
# combining-character check above caught it. Parler-TTS would have read "agni"
# aloud as garbled English in the middle of the Hindi narration.
_LATIN = re.compile(r"[A-Za-z]")

# Narration length bounds, in words. The TTS reads roughly 2 words/second, so 90
# words is about 45s -- the ceiling for a Short that holds retention. The prompt has
# always asked for 70-90 and nothing enforced it: a grounded run on 2026-08-30
# returned a faithful but 122-word narration, which would have rendered a ~60s video.
NARRATION_MIN_WORDS = 42
NARRATION_MAX_WORDS = 58
# Above the target but still usable. A candidate that is correct in every other way
# and only slightly long is kept aside and used if NO model produces a tight one --
# publishing a slightly long Short beats losing the slot entirely.
NARRATION_HARD_MAX_WORDS = 68

# Hashtags are deliberately English ("#Ganesha #Bhakti"), and the title is
# required by the prompt to carry "#Shorts", so Latin inside a #tag is expected.
_HASHTAG = re.compile(r"#[A-Za-z0-9_]+")


def _stray_latin(text: str) -> str:
    """Return the offending fragment if non-hashtag Latin text is present."""
    stripped = _HASHTAG.sub("", text or "")
    m = _LATIN.search(stripped)
    if not m:
        return ""
    # Report the whole run of Latin plus a little context, so the log says
    # "उन्होंनेagni" rather than just "a".
    run = re.search(r"\S*[A-Za-z]+\S*", stripped)
    return run.group(0) if run else m.group(0)


def _too_long(r: dict) -> bool:
    """True if the only thing wrong with this candidate is that it runs long."""
    n = len((r.get("narration") or "").split())
    return NARRATION_MAX_WORDS < n <= NARRATION_HARD_MAX_WORDS


def _validate(r: dict) -> str:
    if not isinstance(r, dict):
        return "not a JSON object"
    for key in ("title", "narration", "key_line"):
        if _malformed(r.get(key)):
            return f"malformed field '{key}': {r.get(key)!r}"
    # narration and key_line are SPOKEN by the TTS -- any Latin at all is a defect.
    # title is only ever displayed, but a stray Latin word there looks just as wrong.
    for key in ("title", "narration", "key_line"):
        bad = _stray_latin(r.get(key) or "")
        if bad:
            return f"non-Devanagari text in '{key}': {bad!r}"
    if not isinstance(r.get("visual_beats"), list) or not (6 <= len(r.get("visual_beats", [])) <= 8):
        return "visual_beats must contain 6-8 pacing cues"
    for beat in r.get("visual_beats", []):
        if _stray_latin(beat or ""):
            return f"non-Devanagari text in visual beat: {beat!r}"
    if _stray_latin(r.get("cta") or ""):
        return f"non-Devanagari text in 'cta': {r.get('cta')!r}"
    # Faithfulness to the corpus. A rejection here falls through to the next model
    # exactly like a malformed field does -- a model that drifts off the source is
    # no more usable than one that emits broken Devanagari.
    drift = story_corpus.fact_check(r.get("narration") or "", story)
    if drift:
        return drift
    words = len((r.get("narration") or "").split())
    if words < NARRATION_MIN_WORDS:
        return f"narration too short: {words} words (min {NARRATION_MIN_WORDS})"
    if words > NARRATION_MAX_WORDS:
        return f"narration too long: {words} words (max {NARRATION_MAX_WORDS})"
    return ""


result = None
soft_fallback = None  # correct but slightly over-length; used only if nothing better
errors = []
for model in MODELS:
    if result:
        break
    for ki, key in enumerate(KEYS):
        body = {**body_base, "model": model}
        hdrs = {**headers, "Authorization": f"Bearer {key}"}
        req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=hdrs)
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read())
            content = data["choices"][0]["message"]["content"]
            cleaned = re.sub(r"```json|```", "", content).strip()
            candidate = json.loads(cleaned)
            problem = _validate(candidate)
            if problem:
                errors.append(f"{model}[key{ki}]: {problem}")
                if soft_fallback is None and "too long" in problem and _too_long(candidate):
                    soft_fallback = candidate
                time.sleep(2)
                continue
            result = candidate
            break
        except urllib.error.HTTPError as e:
            errors.append(f"{model}[key{ki}]: HTTP {e.code}")
            # 429/403 are usually upstream + provider-wide, so another key on the
            # SAME model rarely helps -- move to the next model instead.
            if e.code in (403, 404, 429):
                break
            time.sleep(2)
        except (urllib.error.URLError, KeyError, json.JSONDecodeError) as e:
            errors.append(f"{model}[key{ki}]: {type(e).__name__}: {e}")
            time.sleep(2)

if result is None and soft_fallback is not None:
    result = soft_fallback
    print(
        f"WARNING: no model produced a {NARRATION_MIN_WORDS}-{NARRATION_MAX_WORDS} word "
        f"narration; using an over-length but factually valid one "
        f"({len(result['narration'].split())} words).",
        file=sys.stderr,
    )

if result is None:
    raise SystemExit("All models failed:\n  " + "\n  ".join(errors))

# Provenance: record which story file and scripture this narration came from, so a
# viewer complaint about a wrong fact leads to one story file instead of a re-guess.
result["story_source"] = story["source"]
result["story_confidence"] = story.get("confidence", "unknown")
if not result.get("cta"):
    result["cta"] = "भक्ति में आपकी राय क्या है? कमेंट करें।"

if len(sys.argv) > 2:
    json.dump(result, open(sys.argv[2], "w"), ensure_ascii=False)
else:
    print(json.dumps(result, ensure_ascii=False))
