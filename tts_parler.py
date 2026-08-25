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

    # Hindi description steers a calm, clear devotional narration voice.
    description = "Rohit speaks in a calm, clear and natural Hindi voice with a warm devotional narration tone."

    input_ids = desc_tok(description, return_tensors="pt").input_ids.to(DEVICE)
    prompt = tokenizer(text, return_tensors="pt").input_ids.to(DEVICE)
    generation = model.generate(input_ids=input_ids, prompt_input_ids=prompt)
    audio_arr = generation.cpu().numpy().squeeze()

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        wav_path = tf.name
    sf.write(wav_path, audio_arr, model.config.sampling_rate)

    # Convert to mp3 so the downstream ffmpeg/ffprobe steps are unchanged.
    subprocess.run([
        "ffmpeg", "-y", "-i", wav_path, "-c:a", "libmp3lame", "-b:a", "160k", out_mp3
    ], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.remove(wav_path)
    print(f"TTS_OK {out_mp3} ({len(audio_arr)/model.config.sampling_rate:.2f}s audio)")

if __name__ == "__main__":
    main()
