# Devotional Shorts — Indic Parler-TTS (Hindi)

A Hindi **devotional YouTube Shorts** automation pipeline that generates a script,
synthesizes **natural Hindi narration locally and offline** with
[AI4Bharat Indic Parler-TTS](https://huggingface.co/ai4bharat/indic-parler-tts)
(Apache-2.0, commercial-safe), renders a Ken-Burns zoom video, and publishes to YouTube.

This repo is a **drop-in clone** of the original `devotional-shorts` workflow.
**The only change is the TTS engine**: the original uses `edge-tts`
(`hi-IN-SwaraNeural`, online, Microsoft ToS) — this version replaces that single
step with local Indic Parler-TTS. Image selection, Ken-Burns render, thumbnail,
upload, and Telegram alert logic are byte-identical to the original.

## Why this fork

- **Commercial-safe**: Indic Parler-TTS is Apache-2.0. `edge-tts` forbids
  commercial use in its ToS.
- **Offline / no per-call API**: runs entirely on the VM once weights are cached.
- **Better Hindi prosody** than the cloud neural voice for devotional narration.

## Files in this repo (the Parler variant only)

| File | Purpose |
|------|---------|
| `tts_parler.py` | Hindi TTS via Indic Parler-TTS → MP3 (replaces `edge-tts`) |
| `render_video_parler.sh` | Clone of `render_video.sh` — only TTS line swapped |
| `publish_short_parler.sh` | Clone of `publish_short.sh` — only render call swapped |

The original `publish_short.sh`, `render_video.sh`, and supporting scripts
(`pick_topic.py`, `gen_script.py`, `get_image.py`, `make_thumbnail.py`,
`upload_youtube.py`, `images/`) are part of the parent pipeline and are **not**
modified by this variant. This repo ships only the three Parler-specific files so
the original workflow is never touched.

## Requirements

- Python 3.10+ (tested on 3.12)
- A virtualenv at `~/tts_venv` with `torch`, `parler-tts`, `soundfile`, `transformers`
  installed. **Rebuild it with `bash setup_tts_venv.sh`** — it is an external dependency
  that lives outside this repo and has been lost to a disk cleanup before (2026-08-30).
  `tts_healthcheck.sh --repair` verifies it (and the HF model cache) and rebuilds if
  needed; it runs from cron before each publish slot and as a preflight inside
  `publish_short_main.sh`, so a missing venv self-heals instead of burning a slot.
  (the model is gated — accept the license on the HF repo and provide `HF_TOKEN`)
- `ffmpeg` with `libx264` + `libmp3lame`
- The Indic Parler-TTS weights (auto-downloaded on first run after accepting the
  gated license at https://huggingface.co/ai4bharat/indic-parler-tts)

## Usage

```bash
# One-time: accept the gated model license, then
export HF_TOKEN=hf_xxx
. /path/to/tts_venv/bin/activate

# Render a short (dry-run, no upload):
bash publish_short_parler.sh dryrun

# Full pipeline (renders + uploads to YouTube + Telegram alert):
bash publish_short_parler.sh
```

The n8n workflow clone **"Devotional Shorts Auto-Publisher (Hindi) [Indic Parler-TTS]"**
calls `bash /home/ubuntu/devotional-shorts/publish_short_parler.sh` via its SSH node.
The original n8n workflow (`dvShortsWorkflow01`) is left active and untouched.

## Performance note (measured on a 2-core ARM VM, no GPU)

- Model load: ~40 s (once per process)
- Synthesis: ~120 s for ~6–9 s of audio (real-time factor ≈ 19×)
- A 30 s Short takes ~10 min to render. Suitable for batched/offline generation,
  not real-time.

## License

- TTS model: Apache-2.0 (AI4Bharat Indic Parler-TTS)
- Pipeline code in this repo: MIT

## Grounded story corpus (`stories/`)

Narration is no longer recalled by the LLM — it is **retold from a source file**.

Before this, `gen_script.py` sent a free-tier model nothing but a topic string and
asked it to remember the story. Nothing grounded it, and the validators only caught
encoding defects, so wrong facts shipped: `बमलिंग शिवलिंग` (garbled बर्फ़ का शिवलिंग),
`ॐ ब्रह्मांड की मूल कंपनी` (should be कंपन), and Arjuna appearing inside a Ramayana
episode.

Now every publishable topic has a markdown file under `stories/<category>/`:

```markdown
---
topic: <exact string from topics.json — this is the join key>
category: <matches topics.json>
source: <scripture + section>
confidence: high | medium
---

## कथा       — canonical narrative, 150–250 words. Ground truth, NOT a script.
## मुख्य नाम  — names that MUST appear in the narration (keep to 2–4; all are enforced)
## संदेश      — the moral, one line
## सावधानी    — terms that must NEVER appear (this story's known confusions)
```

`gen_script.py` embeds `## कथा` verbatim and asks only for compression into 70–90
spoken words with a hook → turn → payoff arc. Three checks then gate the result,
each falling through to the next model on failure:

| check | rejects |
|---|---|
| `story_corpus.fact_check` | a `सावधानी` term present, or a `मुख्य नाम` missing |
| length | narration outside 55–95 words |
| existing Devanagari checks | stray Latin, leading combining characters |

A narration that is factually clean but slightly long (96–115 words) is held as a
fallback and used only if no model produces a tight one — a slightly long Short
beats losing the slot.

Each generated script records `story_source` and `story_confidence`, so a complaint
about a wrong fact leads to one story file rather than a re-guess.

### The grounding gate

`pick_topic_scheduled.py` only ever hands out topics that have a story file. If the
day's category has none left it exits **4**, and `publish_short_main.sh` reports
`skipped_no_story` — a clean skip, not a failure, so n8n's "Real Failure?" branch
stays quiet. There is deliberately **no fallback to ungrounded generation**.

`day_deity.py` narrows only its free-day random pool to grounded deities (the forced
weekday schedule is untouched), so a free day never burns its slot on a deity that
cannot publish.

### Adding a story

1. Write `stories/<category>/<slug>.md` in the format above.
2. `python3 story_corpus.py` — coverage report; confirms the topic is now grounded.
3. `python3 tests/test_story_corpus.py && python3 tests/test_picker_gate.py`
4. `python3 gen_script.py "<topic>"` — read the Hindi before it ships.

The `topic:` line must match `topics.json` **byte for byte** or the topic stays
ungrounded and gets skipped. A malformed story file is skipped, not fatal — it just
stops grounding its own topic.

**Current coverage: 15/119** (shiva, ganesha, hanuman: 5 each). The other six
deities have no story files, so they are skipped if scheduled — `krishna`, `rama`,
`vishnu`, `durga`, `lakshmi`, `saraswati` all need entries before they can publish.
