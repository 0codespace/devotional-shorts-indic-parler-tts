#!/bin/bash
# CLONE of render_video.sh — TWO upgrades over the original, original untouched:
#   1) TTS -> AI4Bharat Indic Parler-TTS (Rani voice, local, Apache-2.0)
#   2) Background -> AI-generated 3-image crossfade slideshow (gen_images.py / Pollinations)
# Usage: render_video_slideshow.sh <script_json_path> <category> <output_mp4_path>
set -e

SCRIPT_JSON="$1"
CATEGORY="$2"
OUTPUT_MP4="$3"
WORKDIR="$HOME/devotional-shorts"
cd "$WORKDIR"

VENV_PY="$HOME/tts_venv/bin/python"

RUN_ID=$(basename "$OUTPUT_MP4" .mp4)
NARR_MP3="/tmp/narration_${RUN_ID}.mp3"

NARRATION=$(python3 -c "import json;print(json.load(open('$SCRIPT_JSON'))['narration'])")

# === TTS: local Parler (Rani default) ===
"$VENV_PY" "$WORKDIR/tts_parler.py" "$NARRATION" "$NARR_MP3"

# === Background: generate 3 AI images (fallback to category image) ===
IMG_DIR="$WORKDIR/images/ai/run_${RUN_ID}"
python3 gen_images.py "$SCRIPT_JSON" "$CATEGORY" "$IMG_DIR" > /tmp/imgs_${RUN_ID}.json
mapfile -t IMGS < <(python3 -c "import json; [print(p) for p in json.load(open('/tmp/imgs_${RUN_ID}.json'))]")
if [ "${#IMGS[@]}" -lt 1 ]; then
  IMGS=("$WORKDIR/images/${CATEGORY}.jpg")
fi

RAW_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$NARR_MP3")
DURATION=$(python3 -c "print(round(min(float('$RAW_DUR')+1.5, 58.0), 2))")

# === Build + run crossfade slideshow command ===
FFCMD=$(python3 build_slideshow_cmd.py "$NARR_MP3" "$OUTPUT_MP4" "$DURATION" "${IMGS[@]}")
eval "$FFCMD"

THUMB="${OUTPUT_MP4%.mp4}_thumb.jpg"
python3 make_thumbnail.py "${IMGS[0]}" "$SCRIPT_JSON" "$THUMB" 2>/tmp/thumb_err_${RUN_ID}.log || {
  echo "thumbnail with text failed ($(cat /tmp/thumb_err_${RUN_ID}.log)), falling back to plain crop"
  ffmpeg -y -loop 1 -i "${IMGS[0]}" -frames:v 1 \
    -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[vout]" \
    -map "[vout]" "$THUMB" 2>/dev/null || echo "thumbnail skipped"
}
rm -f /tmp/thumb_err_${RUN_ID}.log /tmp/imgs_${RUN_ID}.json "$NARR_MP3"
echo "Rendered: $OUTPUT_MP4 | Thumb: $THUMB | Images: ${IMGS[*]}"
