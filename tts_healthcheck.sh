#!/usr/bin/env bash
# Verifies the Indic Parler-TTS venv is usable, and (with --repair) rebuilds it if not.
#
# Exit codes: 0 = healthy (possibly after a repair), 1 = broken and not repaired.
#
# Run standalone by cron so the expensive rebuild happens BETWEEN publish slots
# rather than inside one, and called as a preflight by publish_short_main.sh so a
# missing venv is caught before a topic is consumed.
set -uo pipefail

WORKDIR="$HOME/devotional-shorts"
VENV="${TTS_VENV:-$HOME/tts_venv}"
REPAIR="${1:-}"
LOG="$WORKDIR/logs/tts_health.log"
mkdir -p "$WORKDIR/logs"

log() { echo "[$(date -u '+%Y-%m-%dT%H:%M:%SZ')] $*" | tee -a "$LOG"; }

check() {
  [ -x "$VENV/bin/python" ] || { echo "missing interpreter $VENV/bin/python"; return 1; }
  local err
  err=$("$VENV/bin/python" -c "import torch, soundfile, parler_tts, transformers" 2>&1) \
    || { echo "imports failed: ${err##*$'\n'}"; return 1; }
  # The model weights live in ~/.cache/huggingface, which is a separate deletion
  # target from the venv - check it too, since losing it fails just as hard.
  [ -d "$HOME/.cache/huggingface/hub/models--ai4bharat--indic-parler-tts" ] \
    || { echo "missing HF model cache for ai4bharat/indic-parler-tts"; return 1; }
  return 0
}

# Serialise with any other healthcheck/repair. A rebuild takes ~15 min; without this
# a cron repair overlapping a publish preflight would look "broken" mid-install to the
# preflight and kick off a second, competing rebuild. Waiting up to 25 min means the
# preflight simply blocks on an in-progress repair and then re-checks.
exec 201>"$WORKDIR/.tts_health.lock"
flock -w 1500 201 || { log "could not acquire repair lock within 25m"; exit 1; }

REASON=$(check) && { log "OK: TTS venv healthy"; exit 0; }

log "UNHEALTHY: $REASON"

if [ "$REPAIR" != "--repair" ]; then
  log "not repairing (pass --repair to rebuild)"
  exit 1
fi

log "repairing: running setup_tts_venv.sh --force"
if bash "$WORKDIR/setup_tts_venv.sh" --force >>"$LOG" 2>&1; then
  if REASON=$(check); then
    log "REPAIRED: TTS venv rebuilt and healthy"
    exit 0
  fi
  log "repair ran but still unhealthy: $REASON"
else
  log "repair FAILED (see $LOG)"
fi

# Repairs that fail need a human - the pipeline cannot self-heal a broken network
# or an upstream package break. Reuse the pipeline's existing Telegram alerting.
TG_TOKEN_FILE="$WORKDIR/tg_token.txt"
TG_CHAT_ID="${TG_CHAT_ID:-5314505237}"   # same chat the publish script alerts
if [ -f "$TG_TOKEN_FILE" ]; then
  curl -s -X POST "https://api.telegram.org/bot$(cat "$TG_TOKEN_FILE")/sendMessage" \
    -d chat_id="${TG_CHAT_ID}" \
    -d text="⚠️ Devotional Shorts: TTS venv is broken and auto-repair failed. Publishing is down until fixed. Reason: ${REASON}" >/dev/null || true
fi
exit 1
