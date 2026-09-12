#!/bin/bash
# Render a Hindi devotional short from an existing script JSON, using a deity background image
# with a slow Ken Burns zoom. No on-screen text/subtitles (clean audio-only visual).
# Usage: render_video.sh <script_json_path> <category> <output_mp4_path>
set -e

SCRIPT_JSON="$1"
CATEGORY="$2"
OUTPUT_MP4="$3"
WORKDIR="$HOME/devotional-shorts"
cd "$WORKDIR"

EDGE_TTS="$HOME/.local/bin/edge-tts"
VOICE="hi-IN-SwaraNeural"

# Background image: resolve per-topic (download+cache on demand) > category image > fallback
BG_IMAGE=$(python3 get_image.py "$SCRIPT_JSON" "$CATEGORY" 2>/dev/null) || true
[ -f "$BG_IMAGE" ] || BG_IMAGE="images/${CATEGORY}.jpg"
[ -f "$BG_IMAGE" ] || BG_IMAGE="images/vishnu.jpg"

RUN_ID=$(basename "$OUTPUT_MP4" .mp4)
NARR_MP3="/tmp/narration_${RUN_ID}.mp3"

NARRATION=$(python3 -c "import json;print(json.load(open('$SCRIPT_JSON'))['narration'])")

"$EDGE_TTS" --voice "$VOICE" --text "$NARRATION" --write-media "$NARR_MP3"

RAW_DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$NARR_MP3")
# Cap total video length to 58s (Shorts-safe margin under 60s)
DURATION=$(python3 -c "print(round(min(float('$RAW_DUR')+1.5, 58.0), 2))")
FPS=25
FRAMES=$(python3 -c "print(int(round($DURATION * $FPS)))")

# Clean Ken Burns zoom only — no text overlays
ffmpeg -y \
  -loop 1 -i "$BG_IMAGE" \
  -i "$NARR_MP3" \
  -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,scale=1620:2880,zoompan=z='min(zoom+0.0009,1.20)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=${FRAMES}:s=1080x1920:fps=${FPS},format=yuv420p[vout]" \
  -map "[vout]" -map 1:a \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 160k \
  -t "$DURATION" \
  -movflags +faststart \
  "$OUTPUT_MP4"

# Thumbnail: deity/category image + Hindi hook-line overlay.
# Rendered with Pillow+raqm (proper Devanagari conjunct shaping) instead of ffmpeg's
# drawtext, whose text_shaping option has a real bug that drops/corrupts glyphs.
THUMB="${OUTPUT_MP4%.mp4}_thumb.jpg"
python3 make_thumbnail.py "$BG_IMAGE" "$SCRIPT_JSON" "$THUMB" 2>/tmp/thumb_err_${RUN_ID}.log || {
  echo "thumbnail with text failed ($(cat /tmp/thumb_err_${RUN_ID}.log)), falling back to plain crop"
  ffmpeg -y -loop 1 -i "$BG_IMAGE" -frames:v 1 \
    -filter_complex "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920[vout]" \
    -map "[vout]" "$THUMB" 2>/dev/null || echo "thumbnail skipped"
}
rm -f /tmp/thumb_err_${RUN_ID}.log

rm -f "$NARR_MP3"
echo "Rendered: $OUTPUT_MP4 | Thumb: $THUMB"
