#!/usr/bin/env python3
"""
Generate devotional thumbnail images using Google Imagen 3 via the Gemini API.
Saves up to 4 image variants per prompt as JPGs.

Usage:
  python3 gen_image_api.py "your prompt here" --deity hanuman --count 4
  python3 gen_image_api.py "your prompt here" --deity mahadev --out /tmp/test.jpg

Requires:
  pip install google-genai pillow
  export GEMINI_API_KEY=AIzaSy...
"""
import argparse, base64, os, sys, time
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("prompt", help="Image generation prompt")
    parser.add_argument("--deity", default="hanuman",
                        choices=["hanuman","mahadev","ganesha","shree krishna","rama","durga","lakshmi","saraswati","vishnu"],
                        help="Deity folder to save into")
    parser.add_argument("--count", type=int, default=4,
                        help="Number of image variants (1-4, default 4)")
    parser.add_argument("--out", default=None, help="Override output directory")
    args = parser.parse_args()

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        print("ERROR: google-genai not installed. Run: pip install google-genai")
        sys.exit(1)

    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GEMINI_API_KEY_2")
    if not api_key:
        # try reading from file
        key_file = Path.home() / "gem_key.txt"
        if key_file.exists():
            api_key = key_file.read_text().strip()
    if not api_key:
        print("ERROR: No GEMINI_API_KEY found. Set env var or put key in ~/gem_key.txt")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    # Output folder
    if args.out:
        out_dir = Path(args.out)
    else:
        base = Path.home() / "devotional-shorts" / "images" / "curated" / "hindu_gods" / "hindu gods"
        out_dir = base / args.deity
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Generating {args.count} image(s) for deity='{args.deity}'...")
    print(f"Prompt: {args.prompt[:80]}...")

    try:
        # --- Imagen 3: best quality, generates up to 4 variants ---
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=args.prompt,
            config=types.GenerateImagesConfig(
                number_of_images=min(args.count, 4),
                aspect_ratio="9:16",          # Shorts portrait format
                safety_filter_level="block_only_high",
                person_generation="allow_adult",
            ),
        )
        images = response.generated_images

    except Exception as e:
        if "imagen" in str(e).lower() or "not found" in str(e).lower() or "permission" in str(e).lower():
            print(f"Imagen 3 unavailable ({e}), falling back to Gemini 2.0 Flash image gen...")
            # --- Fallback: Gemini 2.0 Flash native image generation ---
            response = client.models.generate_content(
                model="gemini-2.0-flash-preview-image-generation",
                contents=args.prompt,
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE", "TEXT"],
                )
            )
            saved = 0
            for part in response.candidates[0].content.parts:
                if part.inline_data and part.inline_data.mime_type.startswith("image"):
                    ts = int(time.time())
                    fname = out_dir / f"{args.deity}_{ts}_{saved+1}.jpg"
                    fname.write_bytes(base64.b64decode(part.inline_data.data))
                    print(f"  Saved: {fname} ({fname.stat().st_size // 1024}KB)")
                    saved += 1
            print(f"\nDone — {saved} image(s) saved to {out_dir}")
            return
        else:
            raise

    # Save Imagen 3 results
    for i, img in enumerate(images):
        ts = int(time.time())
        fname = out_dir / f"{args.deity}_{ts}_{i+1}.jpg"
        fname.write_bytes(img.image.image_bytes)
        print(f"  Saved: {fname} ({fname.stat().st_size // 1024}KB)")

    print(f"\nDone — {len(images)} image(s) saved to {out_dir}")
    print("These are immediately usable by the publish workflow on next run.")

if __name__ == "__main__":
    main()
