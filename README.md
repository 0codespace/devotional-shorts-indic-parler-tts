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
- A virtualenv with `torch`, `parler-tts`, `soundfile`, `transformers` installed
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
