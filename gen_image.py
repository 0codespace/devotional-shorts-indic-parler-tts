#!/usr/bin/env python3
"""Generate (and cache) a unique devotional background image for a topic via Gemini image
generation. Falls back across multiple API keys. Usage: gen_image.py <topic> <category>
Prints the local cached image path on success, exits non-zero on failure."""
import base64
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

BASE = os.path.expanduser("~/devotional-shorts")
CACHE_DIR = os.path.join(BASE, "images", "ai")
os.makedirs(CACHE_DIR, exist_ok=True)

# Load keys from the VM environment; never commit API keys in source.
# GEMINI_API_KEYS may contain a comma-separated fallback list.
API_KEYS = [k.strip() for k in os.environ.get("GEMINI_API_KEYS", "").split(",") if k.strip()]
if not API_KEYS and os.environ.get("GEMINI_API_KEY", "").strip():
    API_KEYS = [os.environ["GEMINI_API_KEY"].strip()]
MODEL = "gemini-3.1-flash-image"
URL_TMPL = f"https://generativelanguage.googleapis.com/v1/models/{MODEL}:generateContent?key={{}}"

STYLE = (
    "traditional Indian devotional painting in the style of classical mythological art, "
    "rich warm golden lighting, intricate ornate detail, temple backdrop, vibrant saturated colors, "
    "serene divine atmosphere, vertical portrait composition, no text, no words, no letters, "
    "no watermark, no signature, no logo"
)


def cache_path(topic, category):
    h = hashlib.sha1(f"{category}:{topic}".encode()).hexdigest()[:16]
    return os.path.join(CACHE_DIR, f"{category}_{h}.jpg")


def generate(prompt):
    body = json.dumps({
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
            "imageConfig": {"aspectRatio": "9:16"},
        },
    }).encode()

    last_err = None
    for key in API_KEYS:
        for attempt in range(2):
            try:
                req = urllib.request.Request(
                    URL_TMPL.format(key), data=body,
                    headers={"Content-Type": "application/json"}, method="POST",
                )
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = json.loads(resp.read())
                parts = data["candidates"][0]["content"]["parts"]
                for part in parts:
                    if "inlineData" in part:
                        return base64.b64decode(part["inlineData"]["data"])
                last_err = RuntimeError("no image part in response")
            except urllib.error.HTTPError as e:
                last_err = e
                if e.code in (429, 500, 503):
                    time.sleep(2 * (attempt + 1))
                    continue
                break  # other HTTP errors: try next key, not worth retrying same key
            except Exception as e:
                last_err = e
                time.sleep(1)
        # move to next key
    raise RuntimeError(f"image generation failed on all keys: {last_err}")


def main():
    topic = sys.argv[1]
    category = sys.argv[2]
    dest = cache_path(topic, category)
    if os.path.exists(dest) and os.path.getsize(dest) > 5000:
        print(dest)
        return

    prompt = f"Depict this devotional theme: {topic}\nDeity/subject: {category}\nStyle: {STYLE}"
    img_bytes = generate(prompt)
    tmp = dest + ".tmp"
    with open(tmp, "wb") as f:
        f.write(img_bytes)
    os.replace(tmp, dest)
    print(dest)


if __name__ == "__main__":
    main()
