#!/bin/bash
# CLONE of publish_short.sh — ONLY the render step is swapped to the Parler-TTS variant.
# The ORIGINAL publish_short.sh is NOT modified.
# Full pipeline: pick topic -> generate script -> render video (Indic Parler-TTS Hindi)
#                -> upload to YouTube -> notify Telegram.
# Optional arg 1: "dryrun" -> stops before real YouTube upload (renders to /tmp for inspection).
set -e

WORKDIR="$HOME/devotional-shorts"
cd "$WORKDIR"

DRYRUN=${1:-""}

RUN_ID=$(date +%s)
SCRIPT_JSON="runs/script_${RUN_ID}.json"
OUTPUT_MP4="runs/video_${RUN_ID}.mp4"
THUMB="${OUTPUT_MP4%.mp4}_thumb.jpg"
LOG="logs/publish_${RUN_ID}.log"

mkdir -p runs logs

{
  echo "=== Run $RUN_ID started at $(date -u) ==="

  TOPIC_JSON=$(python3 pick_topic.py)
  echo "Topic: $TOPIC_JSON"
  TOPIC=$(echo "$TOPIC_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['topic'])")
  CATEGORY=$(echo "$TOPIC_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['category'])")
  # stash full picked item (with image_override) for render/upload
  echo "$TOPIC_JSON" > "$SCRIPT_JSON.picked"

  python3 gen_script.py "$TOPIC" "$SCRIPT_JSON"

  # Merge topic/category/image_override from the picked item into the script JSON.
  python3 - "$SCRIPT_JSON" "$SCRIPT_JSON.picked" <<'PY'
import json, sys
script_path, picked_path = sys.argv[1], sys.argv[2]
script = json.load(open(script_path))
picked = json.load(open(picked_path))
for k in ("topic", "category", "image_override"):
    if k in picked:
        script[k] = picked[k]
json.dump(script, open(script_path, "w"), ensure_ascii=False)
PY
  echo "Script generated: $(cat $SCRIPT_JSON)"

  # === ONLY CHANGE vs original: Parler render variant ===
  bash render_video_parler.sh "$SCRIPT_JSON" "$CATEGORY" "$OUTPUT_MP4"
  echo "Rendered: $OUTPUT_MP4 (thumb: $THUMB)"

  if [ "$DRYRUN" = "dryrun" ]; then
    echo "=== DRYRUN: skipping YouTube upload. Inspect $OUTPUT_MP4 ==="
    echo "=== Run $RUN_ID dryrun-completed at $(date -u) ==="
    exit 0
  fi

  # Schedule at next India prime time (08:00 or 19:00 Asia/Kolkata) for better reach
  PUBLISH_AT=$(TZ="Asia/Kolkata" python3 - <<'PY'
import datetime
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5,minutes=30)))
candidates=[]
for h in (8,19):
    c=now.replace(hour=h,minute=0,second=0,microsecond=0)
    if c<=now:
        c=c+datetime.timedelta(days=1)
    candidates.append(c)
nxt=min(candidates)
# convert to UTC RFC3339
nxt_utc=nxt.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
print(nxt_utc)
PY
)

  UPLOAD_RESULT=$(python3 upload_youtube.py "$OUTPUT_MP4" "$SCRIPT_JSON" public "$PUBLISH_AT")
  echo "Upload result: $UPLOAD_RESULT"

  VIDEO_ID=$(echo "$UPLOAD_RESULT" | python3 -c "import json,sys;print(json.load(sys.stdin).get('id','unknown'))")
  TITLE=$(python3 -c "import json;print(json.load(open('$SCRIPT_JSON'))['title'])")

  # Set custom thumbnail (best-effort) using a freshly refreshed token
  if [ -f "$THUMB" ]; then
    ATOK=$(python3 - "$WORKDIR/yt_config.json" <<'PY'
import json,sys,urllib.parse,urllib.request
cfg=json.load(open(sys.argv[1]))
body=urllib.parse.urlencode({"client_id":cfg["client_id"],"client_secret":cfg["client_secret"],"refresh_token":cfg["refresh_token"],"grant_type":"refresh_token"}).encode()
req=urllib.request.Request("https://oauth2.googleapis.com/token",data=body,method="POST")
print(json.loads(urllib.request.urlopen(req,timeout=20).read())["access_token"])
PY
)
    curl -s -X POST "https://www.googleapis.com/upload/youtube/v3/thumbnails/set?videoId=${VIDEO_ID}" \
      -H "Authorization: Bearer ***" \
      -H "Content-Type: image/jpeg" \
      --data-binary "@${THUMB}" > /dev/null || echo "thumbnail set failed (non-fatal)"
  fi

  TG_TOKEN=$(cat tg_token.txt)
  TG_CHAT_ID="5314505237"
  MSG="New Short published: ${TITLE}%0Ahttps://youtube.com/shorts/${VIDEO_ID}"
  curl -s "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
    -d "chat_id=${TG_CHAT_ID}" -d "text=${MSG}" > /dev/null

  echo "=== Run $RUN_ID completed at $(date -u) ==="
} >> "$LOG" 2>&1

# keep only last 20 rendered videos + scripts to avoid disk creep
ls -t runs/video_*.mp4 2>/dev/null | tail -n +21 | xargs -r rm -f
ls -t runs/script_*.json 2>/dev/null | tail -n +21 | xargs -r rm -f
ls -t logs/publish_*.log 2>/dev/null | tail -n +50 | xargs -r rm -f
