#!/usr/bin/env python3
"""Hindi TTS via AI4Bharat Indic Parler-TTS (Apache 2.0, runs locally/offline).
Usage: tts_parler.py <text> <out_mp3>
Reads HF_TOKEN from env (not required for inference, only for the gated download).
Outputs an MP3 at the requested path.
"""
import os, sys, subprocess, tempfile
import soundfile as sf
from parler_tts import ParlerTTSForConditionalGeneration
from transformers import AutoTokenizer
import torch

MODEL_ID = "ai4bharat/indic-parler-tts"
DEVICE = "cpu"  # this VM has no GPU

def main():
    text = sys.argv[1]
    out_mp3 = sys.argv[2]

    # Load once (caller scripts re-invoke per run; acceptable given batch usage)
    model = ParlerTTSForConditionalGeneration.from_pretrained(MODEL_ID).to(DEVICE)
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    desc_tok = AutoTokenizer.from_pretrained(model.config.text_encoder._name_or_path)

    # Voice policy (TataCurvv channel): ONLY Rani or Divya may be used — no other
    # speakers. $PARLER_SPEAKER must be one of {Rani, Divya}; anything else (or unset)
    # falls back to Rani.
    speaker = os.environ.get("PARLER_SPEAKER", "Rani")
    if speaker not in ("Rani", "Divya"):
        speaker = "Rani"
    description = (
        f"{speaker} speaks in a calm, clear and natural Hindi voice "
        "with a warm devotional narration tone."
    )

    input_ids = desc_tok(description, return_tensors="pt").input_ids.to(DEVICE)
    prompt = tokenizer(text, return_tensors="pt").input_ids.to(DEVICE)

    # Bound generation length. The model's own default generation_config caps
    # at max_length=2610 (~30s of audio) which was already working fine for
    # the ~70-90 word narrations this pipeline generates (the 14:45 UTC run
    # today rendered a similar-length narration in ~15s of actual TTS time).
    # We only need a *slightly* higher ceiling for occasional longer scripts,
    # not double the default — an earlier attempt at max_new_tokens=4306
    # roughly doubled the model's own safe default and made worst-case runs
    # far slower without fixing anything. Cap at ~40s of audio instead.
    MAX_AUDIO_SECONDS = 40
    frames_per_second = model.config.sampling_rate / 512
    max_new_tokens = min(int(frames_per_second * MAX_AUDIO_SECONDS), 2600)

    generation = model.generate(
        input_ids=input_ids,
        prompt_input_ids=prompt,
        max_new_tokens=max_new_tokens,
    )
    audio_arr = generation.cpu().numpy().squeeze()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = tf.name
    sf.write(wav_path, audio_arr, model.config.sampling_rate)

    # Normalize loudness. Parler-TTS's do_sample=True generation has no
    # explicit loudness anchor, so raw output volume varies significantly
    # run-to-run (observed: anywhere from -21 LUFS to -36+ LUFS for the
    # same speaker/description text) even though the description always
    # asks for the same "calm, clear" tone. A quiet run is audible on good
    # headphones but sounds like "no audio" on a phone speaker in a normal
    # environment — which is what happened on the vB73kWtPEQg Short.
    # -16 LUFS matches typical YouTube Shorts/social loudness targets.
    subprocess.run([
        "ffmpeg", "-y", "-i", wav_path,
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-ar", str(model.config.sampling_rate),
        "-c:a", "libmp3lame", "-b:a", "160k", out_mp3
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(wav_path)
    print(f"TTS_OK {out_mp3} ({len(audio_arr)/model.config.sampling_rate:.2f}s audio, loudness-normalized to -16 LUFS)")

if __name__ == "__main__":
    main()
