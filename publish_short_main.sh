#!/bin/bash
# MAIN PRODUCTION publish workflow (TataCurvv devotional Shorts).
# - Picks topic restricted to the day's preferred deity (day_deity.py schedule)
# - Voice: random Rani/Divya (set in pick_topic_scheduled.py, enforced in tts_parler.py)
# - Renders with curated-image crossfade slideshow
# - Uploads to YouTube (public by default) + Telegram alert
# Optional arg 1: "dryrun" -> render only, no upload.
#
# MACHINE-READABLE RESULT: writes runs/result_${RUN_ID}.json with a "status"
# field (dryrun | uploaded | skipped_duplicate | skipped_concurrent | failed)
# and prints its content as the LAST line of stdout (outside the log
# redirection) so callers like n8n's SSH node can parse the real outcome
# instead of trusting exit 0.
#
# CONCURRENCY GUARD: this script takes an exclusive flock on a shared lock
# file for its entire lifetime (both attempts below). That makes the devotional
# and Hindu workflows serialize on one VM: if one is already running, the other
# waits until it finishes instead of overlapping on CPU, TTS RAM, or
# topic_state.json's read-modify-write.
#
# RETRY: the pipeline runs up to twice. A transient failure (LLM 429, a
# flaky TTS/ffmpeg hiccup, a momentary network blip on upload) gets one
# automatic retry after a 2-minute cooldown before we give up and let n8n's
# "Real Failure?" branch alert Telegram. Most day-to-day flakiness should
# resolve on the retry without anyone having to touch the VM.

WORKDIR="$HOME/devotional-shorts"
cd "$WORKDIR"

DRYRUN=${1:-""}

mkdir -p runs logs

# Validate YouTube OAuth before consuming a topic or starting expensive TTS/rendering.
OAUTH_PREFLIGHT=$(python3 youtube_oauth_preflight.py 2>/dev/null)
OAUTH_RC=$?
if [ "$OAUTH_RC" != "0" ]; then
  RUN_ID=$(date +%s)
  RESULT_JSON="runs/result_${RUN_ID}.json"
  python3 -c "import json;json.dump(json.loads(__import__('sys').argv[1]) | {'run_id': __import__('sys').argv[2]}, open(__import__('sys').argv[3],'w'), ensure_ascii=False)" "$OAUTH_PREFLIGHT" "$RUN_ID" "$RESULT_JSON"
  echo "N8N_RESULT $(cat \"$RESULT_JSON\")"
  exit 0
fi

echo "YouTube OAuth preflight passed: $OAUTH_PREFLIGHT"

LOCKFILE="/tmp/youtube-shorts-publish.lock"
exec 200>"$LOCKFILE"
flock 200

write_result() {
  # $1 = JSON string, $2 = destination path
  python3 -c "import json,sys;json.dump(json.loads(sys.argv[1]), open(sys.argv[2],'w'), ensure_ascii=False)" "$1" "$2"
}

# Runs one full attempt of the pipeline for the given RUN_ID. Writes
# runs/result_${RUN_ID}.json (dryrun | uploaded | skipped_duplicate | failed)
# and echoes that result file's path on stdout (real stdout, not the log).
run_attempt() {
  local RUN_ID="$1"
  local SCRIPT_JSON="runs/script_${RUN_ID}.json"
  local OUTPUT_MP4="runs/video_${RUN_ID}.mp4"
  local THUMB="${OUTPUT_MP4%.mp4}_thumb.jpg"
  local LOG="logs/publish_${RUN_ID}.log"
  local RESULT_JSON="runs/result_${RUN_ID}.json"

  (
    set -e
    echo "=== Run $RUN_ID started at $(date -u) ==="

    # pick_topic_scheduled.py exits 4 when the day's category has no GROUNDED topic
    # left (no story file in stories/, or all of them already uploaded). That is a
    # legitimate "nothing to publish", not a fault: report skipped_no_story so n8n's
    # "Real Failure?" branch stays quiet and nobody gets paged for a corpus gap.
    set +e
    TOPIC_JSON=$(python3 pick_topic_scheduled.py)
    PICK_RC=$?
    set -e
    if [ "$PICK_RC" = "4" ]; then
      echo "=== SKIPPED: no grounded story available for today's category ==="
      echo "Picker said: $TOPIC_JSON"
      CAT_SKIPPED=$(echo "$TOPIC_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('category','unknown'))" 2>/dev/null || echo unknown)
      write_result "{\"status\":\"skipped_no_story\",\"run_id\":\"$RUN_ID\",\"category\":\"$CAT_SKIPPED\",\"detail\":\"no grounded story file in stories/ for any remaining topic in this category\"}" "$RESULT_JSON"
      exit 0
    elif [ "$PICK_RC" != "0" ]; then
      echo "FATAL: pick_topic_scheduled.py exited $PICK_RC" >&2
      exit "$PICK_RC"
    fi
    echo "Topic: $TOPIC_JSON"
    TOPIC=$(echo "$TOPIC_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['topic'])")
    CATEGORY=$(echo "$TOPIC_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin)['category'])")
    VOICE=$(echo "$TOPIC_JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('voice','Rani'))")
    echo "$TOPIC_JSON" > "$SCRIPT_JSON.picked"

    python3 gen_script.py "$TOPIC" "$SCRIPT_JSON"

    python3 - "$SCRIPT_JSON" "$SCRIPT_JSON.picked" <<'PY'
import json, sys
script_path, picked_path = sys.argv[1], sys.argv[2]
script = json.load(open(script_path))
picked = json.load(open(picked_path))
for k in ("topic", "category", "image_override", "voice", "festival_event", "festival_date", "scheduled_category"):
    if k in picked:
        script[k] = picked[k]
json.dump(script, open(script_path, "w"), ensure_ascii=False)
PY
    echo "Script generated: $(cat $SCRIPT_JSON) | Voice: $VOICE"

    bash render_video_main.sh "$SCRIPT_JSON" "$CATEGORY" "$OUTPUT_MP4"
    echo "Rendered: $OUTPUT_MP4 (thumb: $THUMB)"

    if [ "$DRYRUN" = "dryrun" ]; then
      echo "=== DRYRUN: skipping YouTube upload. Inspect $OUTPUT_MP4 ==="
      echo "=== Run $RUN_ID dryrun-completed at $(date -u) ==="
      write_result "{\"status\":\"dryrun\",\"run_id\":\"$RUN_ID\",\"topic\":$(python3 -c "import json;print(json.dumps('$TOPIC'))"),\"video_path\":\"$OUTPUT_MP4\"}" "$RESULT_JSON"
      exit 0
    fi

    # Four daily publish slots (IST), aligned to the YouTube analytics report:
    # early devotional window, lunch break, evening browsing, and late-night browsing.
    # One slot per run keeps uploads spread out instead of cannibalising each other.
    PUBLISH_AT=$(TZ="Asia/Kolkata" python3 - <<'PY'
import datetime
now=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=5,minutes=30)))
candidates=[]
for h, m in ((6,30),(13,30),(20,30),(22,30)):
    c=now.replace(hour=h,minute=m,second=0,microsecond=0)
    if c<=now:
        c=c+datetime.timedelta(days=1)
    candidates.append(c)
nxt=min(candidates)
nxt_utc=nxt.astimezone(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
print(nxt_utc)
PY
)

    UPLOAD_RESULT=$(python3 upload_youtube.py "$OUTPUT_MP4" "$SCRIPT_JSON" public "$PUBLISH_AT")
    echo "Upload result: $UPLOAD_RESULT"

    UPLOAD_STATUS=$(echo "$UPLOAD_RESULT" | python3 -c "import json,sys;print(json.load(sys.stdin).get('status','uploaded'))")
    if [ "$UPLOAD_STATUS" = "skipped_duplicate" ]; then
      echo "=== SKIPPED: topic already uploaded before (duplicate) - NOT sending Telegram, NOT setting thumbnail ==="
      echo "=== Run $RUN_ID skipped-duplicate at $(date -u) ==="
      DUP_ID=$(echo "$UPLOAD_RESULT" | python3 -c "import json,sys;print(json.load(sys.stdin).get('id','unknown'))")
      write_result "{\"status\":\"skipped_duplicate\",\"run_id\":\"$RUN_ID\",\"topic\":$(python3 -c "import json;print(json.dumps('$TOPIC'))"),\"existing_video_id\":\"$DUP_ID\"}" "$RESULT_JSON"
      exit 0
    fi

    VIDEO_ID=$(echo "$UPLOAD_RESULT" | python3 -c "import json,sys;print(json.load(sys.stdin).get('id','unknown'))")
    TITLE=$(python3 -c "import json;print(json.load(open('$SCRIPT_JSON'))['title'])")

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
        -H "Authorization: Bearer ${ATOK}" \
        -H "Content-Type: image/jpeg" \
        --data-binary "@${THUMB}" > /dev/null || echo "thumbnail set failed (non-fatal)"
    fi

    TG_TOKEN=$(cat tg_token.txt)
    TG_CHAT_ID="5314505237"
    CHANNEL_NAME="TataCurvv devotional Shorts"
    PUBLISH_SLOTS_IST="06:30, 13:30, 20:30, 22:30 IST"
    MSG="New Short published: ${TITLE}%0AChannel: ${CHANNEL_NAME}%0AScheduled slots: ${PUBLISH_SLOTS_IST}%0Ahttps://youtube.com/shorts/${VIDEO_ID}"
    curl -s "https://api.telegram.org/bot${TG_TOKEN}/sendMessage" \
      -d "chat_id=${TG_CHAT_ID}" -d "text=${MSG}" > /dev/null

    echo "=== Run $RUN_ID completed at $(date -u) ==="
    write_result "{\"status\":\"uploaded\",\"run_id\":\"$RUN_ID\",\"video_id\":\"$VIDEO_ID\",\"topic\":$(python3 -c "import json;print(json.dumps('$TOPIC'))"),\"title\":$(python3 -c "import json;print(json.dumps('$TITLE'))"),\"url\":\"https://youtube.com/shorts/${VIDEO_ID}\"}" "$RESULT_JSON"
  ) >> "$LOG" 2>&1
  local BLOCK_EXIT=$?

  # If the subshell above exited non-zero via `set -e` (an unhandled error, not
  # one of our explicit exit-0 paths), no result file exists yet — write a
  # generic failure marker so the caller always gets exactly one JSON verdict.
  if [ ! -f "$RESULT_JSON" ]; then
    python3 -c "import json;json.dump({'status':'failed','run_id':'$RUN_ID','exit_code':$BLOCK_EXIT,'log':'$LOG'}, open('$RESULT_JSON','w'))"
  fi

  echo "$RESULT_JSON"
}

# PREFLIGHT: the TTS venv is an external dependency living outside this repo
# ($HOME/tts_venv). On 2026-08-30 a disk-cleanup pass deleted it, and the run only
# discovered that AFTER picking a topic and paying for a script generation — the topic
# was consumed and the slot lost. Check (and self-heal) it up front, before any state
# is mutated, and report a specific status instead of a generic "failed".
if ! bash "$WORKDIR/tts_healthcheck.sh" --repair >> logs/tts_health.log 2>&1; then
  RUN_ID=$(date +%s)
  RESULT_JSON="runs/result_${RUN_ID}.json"
  write_result "{\"status\":\"failed\",\"run_id\":\"$RUN_ID\",\"reason\":\"tts_venv_unavailable\",\"detail\":\"TTS venv missing/broken and auto-repair failed; see logs/tts_health.log\",\"log\":\"logs/tts_health.log\"}" "$RESULT_JSON"
  echo "N8N_RESULT $(cat "$RESULT_JSON")"
  exit 0
fi

FINAL_RESULT_JSON=""
for attempt in 1 2; do
  RUN_ID=$(date +%s)
  RESULT_JSON=$(run_attempt "$RUN_ID")
  FINAL_RESULT_JSON="$RESULT_JSON"
  STATUS=$(python3 -c "import json;print(json.load(open('$RESULT_JSON')).get('status','failed'))")
  if [ "$STATUS" != "failed" ]; then
    break
  fi
  if [ "$attempt" = "1" ]; then
    echo "$(date -u) Run $RUN_ID failed, retrying once after 120s cooldown" >> logs/publish_retry.log
    sleep 120
  fi
done

ls -t runs/video_*.mp4 2>/dev/null | tail -n +21 | xargs -r rm -f
ls -t runs/script_*.json 2>/dev/null | tail -n +21 | xargs -r rm -f
ls -t logs/publish_*.log 2>/dev/null | tail -n +50 | xargs -r rm -f
ls -t runs/result_*.json 2>/dev/null | tail -n +50 | xargs -r rm -f

# Thumbnails, .picked scripts and per-run image dirs matched none of the
# globs above, so they outlived their mp4s and leaked (~125M by 2026-08-30).
# Anchor them to the surviving mp4s instead of a separate count, so the
# whole run is retained or dropped as a unit.
KEEP_IDS=$(ls runs/video_*.mp4 2>/dev/null | sed 's|runs/||; s|\.mp4$||')
for f in runs/*_thumb.jpg; do
  [ -e "$f" ] || continue
  grep -qxF "$(basename "$f" _thumb.jpg)" <<< "$KEEP_IDS" || rm -f "$f"
done
for f in runs/script_*.json.picked; do
  [ -e "$f" ] || continue
  grep -qxF "$(basename "$f" .json.picked | sed 's|^script_|video_|')" <<< "$KEEP_IDS" || rm -f "$f"
done
for d in images/ai/run_*; do
  [ -d "$d" ] || continue
  grep -qxF "${d#images/ai/run_}" <<< "$KEEP_IDS" || rm -rf "$d"
done

# Emit the single machine-readable result line LAST, to real stdout.
echo "N8N_RESULT $(cat "$FINAL_RESULT_JSON")"
