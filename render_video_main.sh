#!/bin/bash
# MAIN PRODUCTION render: Indic Parler-TTS (Rani/Divya, random per run) + curated-image
# crossfade slideshow. This is the production path (original workflow now points here).
# Voice comes from the "voice" field in the script JSON (set by pick_topic_scheduled.py),
# restricted to Rani/Divya only (tts_parler.py enforces).
# Usage: render_video_main.sh <script_json_path> <category> <output_mp4_path>
set -e

SCRIPT_JSON="$1"
CATEGORY="$2"
OUTPUT_MP4="$3"
WORKDIR="$HOME/devotional-shorts"
cd "$WORKDIR"

VENV_PY="${TTS_VENV:-$HOME/tts_venv}/bin/python"

# Second line of defence behind publish_short_main.sh's preflight (this script is also
# run by hand). Without it, a missing venv surfaces as the near-useless
# `timeout: failed to run command '/home/ubuntu/tts_venv/bin/python'` — which is exactly
# what run 1788079626 reported on 2026-08-30 after a disk cleanup deleted the venv.
if [ ! -x "$VENV_PY" ]; then
  echo "FATAL: TTS venv interpreter not found at $VENV_PY" >&2
  echo "The Parler-TTS environment is missing (deleted, or never built on this host)." >&2
  echo "Rebuild it with: bash $WORKDIR/setup_tts_venv.sh" >&2
  exit 3
fi

RUN_ID=$(basename "$OUTPUT_MP4" .mp4)
NARR_MP3="/tmp/narration_${RUN_ID}.mp3"

NARRATION=$(python3 -c "import json;print(json.load(open('$SCRIPT_JSON'))['narration'])")
VOICE=$(python3 -c "import json;print(json.load(open('$SCRIPT_JSON')).get('voice','Rani'))")

# === TTS: local Parler, voice from schedule (Rani/Divya only) ===
# Hard timeout: this VM is CPU-only (no GPU) with 2 cores, so a hung or
# starved TTS process must not be able to block a publish slot forever.
# 900s (15 min) headroom: observed solo end-to-end pipeline runs (topic pick +
# script + TTS + render + thumbnail) already take 10-13 min on this hardware,
# so an 8-min cap on the TTS step ALONE was too tight and false-killed a
# genuinely-still-working run (exit 124) during testing on 2026-08-29.
PARLER_SPEAKER="$VOICE" timeout 1800 "$VENV_PY" "$WORKDIR/tts_parler.py" "$NARRATION" "$NARR_MP3"

# === Background: curated local images (your ZIP gallery) ===
IMG_DIR="$WORKDIR/images/ai/run_${RUN_ID}"
python3 gen_images.py "$SCRIPT_JSON" "$CATEGORY" "$IMG_DIR" > /tmp/imgs_${RUN_ID}.json
mapfile -t IMGS < <(python3 -c "import json; [print(p) for p in json.load(open('/tmp/imgs_${RUN_ID}.json'))]")
if [ "${#IMGS[@]}" -lt 1 ]; then
  IMGS=("$WORKDIR/images/${CATEGORY}.jpg")
fi

RAW_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$NARR_MP3")
DURATION=$(python3 -c "print(round(min(float('$RAW_DUR')+1.5, 58.0), 2))")

FFCMD=$(python3 build_slideshow_cmd.py "$NARR_MP3" "$OUTPUT_MP4" "$DURATION" "${IMGS[@]}")
timeout 360 bash -c "$FFCMD"


THUMB="${OUTPUT_MP4%.mp4}_thumb.jpg"
python3 make_thumbnail.py "${IMGS[0]}" "$SCRIPT_JSON" "$THUMB" 2>/tmp/thumb_err_${RUN_ID}.log || {
  echo "thumbnail with text failed ($(cat /tmp/thumb_err_${RUN_ID}.log)), falling back to plain crop"
  ffmpeg -y -loop 1 -i "${IMGS[0]}" -frames:v 1 \
    -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[vout]" \
    -map "[vout]" "$THUMB" 2>/dev/null || echo "thumbnail skipped"
}
rm -f /tmp/thumb_err_${RUN_ID}.log /tmp/imgs_${RUN_ID}.json "$NARR_MP3"
echo "Rendered: $OUTPUT_MP4 | Thumb: $THUMB | Voice: $VOICE | Images: ${IMGS[*]}"
