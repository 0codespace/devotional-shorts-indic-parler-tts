#!/usr/bin/env bash
# Rebuilds ~/tts_venv, the Indic Parler-TTS environment used by render_video_main.sh.
#
# WHY THIS EXISTS: on 2026-08-30 a disk-cleanup pass deleted /home/ubuntu/tts_venv
# (5.8G) because the directory's top-level mtime was days old and it "looked" like a
# stale cache. Nothing recorded how to rebuild it, so the 08:47 publish slot died with
# `timeout: failed to run command '/home/ubuntu/tts_venv/bin/python'`. This script makes
# the venv disposable: if it ever goes missing again, one command brings it back.
#
# Usage: bash setup_tts_venv.sh [--force]
set -euo pipefail

VENV="${TTS_VENV:-$HOME/tts_venv}"
FORCE="${1:-}"

if [ "$FORCE" = "--force" ]; then
  echo "[setup] --force: removing existing $VENV"
  rm -rf "$VENV"
fi

if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c "import parler_tts, soundfile, torch" 2>/dev/null; then
  echo "[setup] $VENV already healthy, nothing to do."
  exit 0
fi

echo "[setup] building $VENV (this downloads ~2.5G and takes 10-20 min on this VM)"
python3 -m venv "$VENV"
"$VENV/bin/pip" install --upgrade pip wheel

# CPU-only wheels: this VM has no GPU, and the CUDA wheels are ~2G larger.
"$VENV/bin/pip" install --index-url https://download.pytorch.org/whl/cpu torch torchaudio
"$VENV/bin/pip" install git+https://github.com/huggingface/parler-tts.git
"$VENV/bin/pip" install soundfile sentencepiece protobuf

# Marker file so a future "free up disk space" pass can see this is production state,
# not a regenerable cache. Also gives the healthcheck something cheap to stat.
cat > "$VENV/DO_NOT_DELETE.txt" <<'MARK'
PRODUCTION DEPENDENCY - DO NOT DELETE.

This virtualenv is the TTS engine for the devotional-shorts publishing pipeline
(~/devotional-shorts/render_video_main.sh). It is invoked only by cron/n8n, so its
directory mtime looks stale even while it is in daily use. Deleting it breaks every
scheduled publish slot until it is rebuilt.

Rebuild with: bash ~/devotional-shorts/setup_tts_venv.sh
MARK

echo "[setup] verifying imports"
"$VENV/bin/python" - <<'PY'
import torch, soundfile, parler_tts, transformers
print("torch", torch.__version__)
print("transformers", transformers.__version__)
print("parler_tts OK")
PY
echo "[setup] done: $VENV"
