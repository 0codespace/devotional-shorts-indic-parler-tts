#!/usr/bin/env python3
"""Resolve background images for a devotional Short from the curated ZIP gallery.

Source priority (sharpest + license-clean for monetization):
  1) Curated ZIP: images/curated/hindu_gods/hindu gods/<deity>/*.jpg
     Folders: ganesha, hanuman, mahadev(=shiva), shree krishna(=krishna), rama
  2) Existing local curated art (deity JPG + Raja Ravi Varma) for deities not in the zip.
  3) Wikimedia topic image (cached) as last resort.

Picks up to 8 distinct images per run so the slideshow can change every 2-3 seconds.
Usage: gen_images.py <script_json_path> <category> <out_dir>
Prints a JSON list of 3 local image paths for the slideshow.
"""
import json, os, sys, shutil, glob
from PIL import Image

BASE = os.path.expanduser("~/devotional-shorts")
IMG = os.path.join(BASE, "images")
ZIP_ROOT = os.path.join(BASE, "images", "curated", "hindu_gods", "hindu gods")

# pipeline category -> ZIP folder name
ZIP_MAP = {
    "shiva": "mahadev",
    "krishna": "shree krishna",
    "ganesha": "ganesha",
    "hanuman": "hanuman",
    "rama": "rama",
}
# existing local curated art (deity JPG + Ravi Varma) for categories absent from the zip
EXTRA_ART = {
    "shiva":   ["topic/Siva-parvati-by-raja-ravi-varma.jpg"],
    "lakshmi": ["topic/Raja_Ravi_Varma,_Goddess_Lakshmi,_1896.jpg"],
    "durga":   ["topic/Durga_by_Raja_Ravi_Varma.jpg"],
    "krishna": ["topic/Yashoda_with_Krishna,_Raja_Ravi_Varma.jpg"],
    "ganesha": ["topic/Rebirth_of_Ganesha.jpg"],
    "rama":    ["topic/Dashavatara.jpg"],
}
SYMBOLIC = ["topic/Om.svg.jpg", "topic/Diya.jpg", "topic/Meditation.jpg"]

def good(p):
    if not os.path.exists(p) or os.path.getsize(p) < 5000:
        return False
    try:
        im = Image.open(p); w,h = im.size
        return w >= 600 and h >= 600  # reject thumbs
    except Exception:
        return False

def zip_images(category):
    folder = ZIP_MAP.get(category)
    if not folder:
        return []
    
    import random
    
    # 1) Old zip gallery
    d1 = os.path.join(ZIP_ROOT, folder)
    imgs1 = [f for f in glob.glob(os.path.join(d1, "*")) if good(f)] if os.path.isdir(d1) else []
    
    # 2) New AI thumbnails batch
    d2 = os.path.join(BASE, "images", "curated", "new_ai_thumbnails", folder)
    imgs2 = [f for f in glob.glob(os.path.join(d2, "*")) if good(f)] if os.path.isdir(d2) else []
    
    combined = imgs1 + imgs2
    # Shuffle so every video gets a fresh mix of old and new images
    random.shuffle(combined)
    return combined

def pick(category):
    out, seen = [], set()
    def add(p):
        if p and good(p) and p not in seen:
            seen.add(p); out.append(p)
    # 1) ZIP gallery for this deity (up to 8)
    for f in zip_images(category):
        if len(out) >= 8: break
        add(f)
    # 2) existing local curated art
    add(os.path.join(IMG, f"{category}.jpg"))
    for a in EXTRA_ART.get(category, []):
        if len(out) >= 8: break
        add(os.path.join(IMG, a))
    # 3) symbolic fillers
    for s in SYMBOLIC:
        if len(out) >= 8: break
        add(os.path.join(IMG, s))
    if not out:
        add(os.path.join(IMG, "vishnu.jpg"))
    return out[:8]

def main():
    script_path, category, out_dir = sys.argv[1], sys.argv[2], sys.argv[3]
    os.makedirs(out_dir, exist_ok=True)
    chosen = pick(category)
    final = []
    for i, src in enumerate(chosen):
        dst = os.path.join(out_dir, f"bg_{i}.jpg")
        shutil.copy(src, dst)
        final.append(dst)
    print(json.dumps(final, ensure_ascii=False))

if __name__ == "__main__":
    main()
