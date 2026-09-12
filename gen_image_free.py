#!/usr/bin/env python3
"""
Generate devotional thumbnail images for FREE using Pollinations.ai (FLUX model).
No API key, no account, no cost. Works immediately.

Usage:
  python3 gen_image_free.py --deity hanuman --count 8
  python3 gen_image_free.py --deity mahadev --count 5
  python3 gen_image_free.py --deity hanuman --prompt "your custom prompt" --count 4
  python3 gen_image_free.py --all --count 5    # generate for all deities

Images are saved directly into the workflow's curated image folders.
"""
import argparse, os, time, urllib.parse, urllib.request
from pathlib import Path

BASE = Path.home() / "devotional-shorts" / "images" / "curated" / "hindu_gods" / "hindu gods"

# Built-in viral-optimised prompts per deity
DEITY_PROMPTS = {
    "hanuman": [
        "Lord Hanuman close-up portrait, fierce devotion in eyes, glowing amber saffron divine aura, dark storm cloud background, sacred tilak on forehead, traditional Indian devotional painting style, cinematic rim lighting, rich jewel tones, 9:16 portrait, no text, no watermark",
        "Powerful Lord Hanuman raising iron mace overhead, roaring expression, thunderstorm background with lightning bolts, divine fire surrounding body, deep orange and black color palette, Indian epic mythological art style, dramatic low-angle view, 9:16 portrait, no text",
        "Lord Hanuman soaring through crimson twilight sky, Sanjeevani mountain in one hand, glowing city of Lanka below, traditional Indian miniature art meets fantasy painting, gold and deep red palette, cinematic, 9:16 portrait, no text",
        "Lord Hanuman kneeling in devotion, hands folded anjali mudra, tear of love on cheek, soft golden temple light, lotus flowers surrounding, incense smoke, warm amber saffron tones, Ravi Varma devotional painting style, 9:16 portrait, no text",
        "Five-faced Panchamukhi Hanuman, each face glowing with divine radiance, towering against midnight cosmic sky with stars, ten arms holding divine weapons, South Indian temple art style, gold and deep blue palette, dramatic, 9:16 portrait, no text",
        "Lord Hanuman silhouette against blazing orange sunrise, Sanjeevani mountain held aloft, golden divine light pouring from above, saffron and crimson palette, epic scale, traditional Indian art style, 9:16 portrait, no text",
        "Close-up of Hanuman face in Raudra fierce roop, eyes blazing red-gold, mace raised, dark thundercloud background with lightning, divine tilak glowing, traditional Indian miniature painting hyper-real detail, bold high contrast, 9:16 portrait, no text",
        "Lord Hanuman seated before Lord Rama, gentle bhakti expression, soft golden temple light, intricate Ravi Varma style drapery jewelry detail, lotus flowers, incense smoke, warm saffron gold palette, 9:16 portrait, no text",
    ],
    "mahadev": [
        "Close-up portrait of Lord Shiva Neelkanth, third eye slowly opening with blinding white cosmic light, crescent moon in matted jata hair, blue throat, sacred ash on forehead, dark starry universe behind, traditional Indian devotional painting style, dramatic rim lighting, 9:16 portrait, no text",
        "Lord Shiva seated on Mount Kailash, snow-capped Himalayan peaks behind, Ganga flowing from hair, Trishul trident beside him, Nandi bull at feet, golden hour warm light, Ravi Varma Indian painting style epic fantasy, regal powerful, 9:16 portrait, no text",
        "Lord Shiva performing Tandava cosmic dance, ring of fire surrounding him, dark swirling cosmos with sparks of creation, fierce expression, matted hair flying, Indian bronze Nataraja sculpture aesthetic cinematic digital art, 9:16 portrait, no text",
        "Lord Shiva as Ardhanarishvara, left half fierce silver-white Shiva, right half graceful golden Parvati, split down center, divine jewelry on each side, temple arch background, soft devotional lighting, traditional Indian miniature painting style, 9:16 portrait, no text",
        "Lord Shiva in deep samadhi meditation, eyes half-closed, glowing crescent moon above, ethereal white aura, Rudraksha beads, snow falling gently, sacred Kailash mist, lotus beneath him, peaceful devotional mood, traditional Indian painting soft cinematic glow, 9:16 portrait, no text",
        "Mahadev Shiva close-up, third eye open shooting cosmic fire, universe expanding behind him, blue skin, ash-white matted hair, serpent around neck, dramatic cinematic lighting, traditional Indian devotional art style, 9:16 portrait, no text",
        "Lord Shiva and Parvati on Mount Kailash, regal seated pose, divine Himalayan snowscape golden hour, Nandi bull at feet, Ravi Varma painting style photorealistic background, warm golden sunset palette, devotional mood, 9:16 portrait, no text",
        "Shiva Lingam glowing with divine blue energy, abhishek water streaming over it, marigold flowers surrounding, temple lamp flames, smoke of incense, dark background with cosmic glow, ultra-detailed traditional Indian devotional art, 9:16 portrait, no text",
    ],
    "ganesha": [
        "Close-up portrait of Lord Ganesha, large kind eyes filled with wisdom and warmth, golden crown and jewels, modak sweet in hand, glowing saffron aura, dark background with lotus petals, traditional Indian devotional painting style, cinematic lighting, 9:16 portrait, no text",
        "Lord Ganesha in triumphant pose, trunk raised for good luck, riding his mouse vahana, marigold garlands, golden divine light from above, vibrant orange and gold palette, Ravi Varma inspired Indian art style, 9:16 portrait, no text",
        "Lord Ganesha writing Mahabharata with broken tusk as pen, sage Vyasa beside him, soft candlelight, ancient manuscript setting, traditional Indian miniature painting style, warm golden tones, ultra-detailed, 9:16 portrait, no text",
        "Bal Ganesha as a child deity, chubby playful form, holding modak, lotus flower background, soft divine golden light, ultra-cute traditional Indian art style, warm saffron palette, devotional mood, 9:16 portrait, no text",
    ],
    "shree krishna": [
        "Close-up portrait of young Lord Krishna, peacock feather crown, flute at lips, eyes like lotus petals with divine mischief, soft twilight background with river Yamuna, traditional Indian Ravi Varma painting style, warm blue and gold palette, 9:16 portrait, no text",
        "Lord Krishna performing Raas Leela cosmic dance, divine blue form, yellow dhoti, peacock crown, glowing full moon, Vrindavan forest background, traditional Indian miniature art, gold and deep blue palette, 9:16 portrait, no text",
        "Lord Krishna as Arjuna's charioteer on Kurukshetra battlefield, Bhagavad Gita moment, divine golden light from above, epic war panorama behind, traditional Indian painting style meets cinematic, 9:16 portrait, no text",
        "Baby Krishna crawling with stolen butter, mischievous smile, soft warm home lighting, traditional clay pot, marigolds, gentle devotional painting style, warm amber palette, ultra-cute, 9:16 portrait, no text",
    ],
    "rama": [
        "Close-up portrait of Lord Rama, noble and serene expression, golden crown, sacred thread, divine bow in hand, soft forest background with lotus flowers, traditional Ravi Varma Indian painting style, warm golden palette, 9:16 portrait, no text",
        "Lord Rama standing victorious over Ravana, divine light from above, Lanka in background, bow raised, Hanuman beside him, traditional Indian epic art style, rich crimson and gold palette, 9:16 portrait, no text",
        "Ram Darbar — Lord Rama, Sita, Lakshmana, and Hanuman seated together, soft temple light, intricate traditional Indian painting detail, warm golden devotional palette, 9:16 portrait, no text",
    ],
}

def generate_image(prompt, out_path, seed=None):
    """Download one image from Pollinations.ai. Returns True on success."""
    seed = seed or int(time.time() * 1000) % 999999
    encoded = urllib.parse.quote(prompt)
    url = (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?width=1080&height=1920&model=flux&nologo=true&seed={seed}"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = resp.read()
        if len(data) < 5000:
            print(f"    ⚠️  Response too small ({len(data)} bytes) — likely an error page")
            return False
        with open(out_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:
        print(f"    ❌ Request failed: {e}")
        return False


def run(deity, count, custom_prompt=None):
    out_dir = BASE / deity
    out_dir.mkdir(parents=True, exist_ok=True)

    prompts = ([custom_prompt] * count) if custom_prompt else DEITY_PROMPTS.get(deity, [])
    if not prompts:
        print(f"No prompts defined for deity '{deity}'")
        return

    print(f"\n🙏 Generating {count} image(s) for '{deity}' → {out_dir}")
    success = 0
    for i in range(count):
        prompt = prompts[i % len(prompts)]
        # unique seed per image so we get variety even on same prompt
        seed = int(time.time() * 1000 + i * 7919) % 999999
        ts = int(time.time())
        fname = out_dir / f"{deity.replace(' ','_')}_{ts}_{i+1}.jpg"
        print(f"  [{i+1}/{count}] seed={seed} → {fname.name} ...", end=" ", flush=True)
        ok = generate_image(prompt, fname, seed=seed)
        if ok:
            kb = fname.stat().st_size // 1024
            print(f"✅ {kb}KB")
            success += 1
        else:
            print("❌ failed")
        # small delay to be polite
        if i < count - 1:
            time.sleep(2)

    print(f"\nDone: {success}/{count} saved to {out_dir}")


def main():
    parser = argparse.ArgumentParser(description="Free devotional image generator (Pollinations.ai / FLUX)")
    parser.add_argument("--deity", default="hanuman",
                        help=f"Deity: {', '.join(DEITY_PROMPTS.keys())}")
    parser.add_argument("--all", action="store_true", help="Generate for all deities")
    parser.add_argument("--count", type=int, default=4, help="Number of images per deity (default 4)")
    parser.add_argument("--prompt", default=None, help="Custom prompt (overrides built-in)")
    args = parser.parse_args()

    if args.all:
        for deity in DEITY_PROMPTS:
            run(deity, args.count, args.prompt)
    else:
        run(args.deity, args.count, args.prompt)

if __name__ == "__main__":
    main()
