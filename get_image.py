#!/usr/bin/env python3
"""Resolve and cache a local background image for a topic.
Usage: get_image.py <script_json_path> <category>
Prints the local image path. Downloads from Wikimedia once (throttled) if not cached.
Falls back to the category deity image already present in images/."""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.expanduser("~/devotional-shorts")
IMG_URLS = os.path.join(BASE, "image_urls.json")
CACHE = os.path.join(BASE, "images", "topic")
os.makedirs(CACHE, exist_ok=True)

def local_for(url):
    fn = urllib.parse.unquote(url).split("/")[-1].split("?")[0]
    if not fn.lower().endswith((".jpg", ".jpeg", ".png")):
        fn += ".jpg"
    return os.path.join(CACHE, fn)

def download(url):
    dest = local_for(url)
    if os.path.exists(dest) and os.path.getsize(dest) > 2000:
        return dest
    # throttle to avoid Wikimedia 429
    time.sleep(2.0)
    req = urllib.request.Request(url, headers={"User-Agent": "DevotionalShortsBot/2.0 (vijay.looprai@gmail.com)"})
    with urllib.request.urlopen(req, timeout=40) as r:
        data = r.read()
    open(dest, "wb").write(data)
    return dest

def main():
    script_path = sys.argv[1]
    category = sys.argv[2]
    d = json.load(open(script_path))
    override_url = d.get("image_override", "")
    local = ""
    if override_url:
        try:
            local = download(override_url)
        except Exception as e:
            print(f"img dl failed: {e}", file=sys.stderr)
            local = ""
    if not local:
        # category fallback (already local)
        cat_img = os.path.join(BASE, "images", f"{category}.jpg")
        local = cat_img if os.path.exists(cat_img) else os.path.join(BASE, "images", "vishnu.jpg")
    print(local)

if __name__ == "__main__":
    main()
