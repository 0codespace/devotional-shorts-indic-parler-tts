#!/usr/bin/env python3
"""Build a YouTube Shorts thumbnail: cover-crop the background image to 1080x1920 and
burn in the script's Hindi hook line. Uses Pillow+raqm for correct Devanagari shaping
(ffmpeg's drawtext text_shaping has a real bug that drops/corrupts conjunct glyphs).
Usage: make_thumbnail.py <bg_image_path> <script_json_path> <output_jpg_path>
"""
import json
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
FONT_PATH = "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Bold.ttf"
MAX_TEXT_WIDTH = 940  # leaves ~70px margin each side
MIN_FONT_SIZE = 44
MAX_LINES = 3


def cover_crop(img):
    src_ratio = img.width / img.height
    dst_ratio = W / H
    if src_ratio > dst_ratio:
        new_h = H
        new_w = int(H * src_ratio)
    else:
        new_w = W
        new_h = int(W / src_ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - W) // 2
    top = (new_h - H) // 2
    return img.crop((left, top, left + W, top + H))


def wrap_lines(draw, text, font):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        trial = (cur + " " + w).strip()
        if draw.textbbox((0, 0), trial, font=font)[2] > MAX_TEXT_WIDTH and cur:
            lines.append(cur)
            cur = w
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines


def fit_text(draw, text):
    size = 76
    while size >= MIN_FONT_SIZE:
        font = ImageFont.truetype(FONT_PATH, size)
        lines = wrap_lines(draw, text, font)
        if len(lines) <= MAX_LINES:
            return font, lines
        size -= 4
    # last resort: smallest size, hard-cap lines
    font = ImageFont.truetype(FONT_PATH, MIN_FONT_SIZE)
    return font, wrap_lines(draw, text, font)[:MAX_LINES]


def main():
    bg_path, script_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

    d = json.load(open(script_path))
    text = (d.get("key_line") or d.get("title", "")).replace("#Shorts", "").strip()

    img = cover_crop(Image.open(bg_path).convert("RGB"))
    draw = ImageDraw.Draw(img)

    if text:
        font, lines = fit_text(draw, text)
        line_height = int(font.size * 1.35)
        block_height = line_height * len(lines)
        box_top = H - block_height - 140
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        odraw.rectangle([0, box_top - 40, W, H], fill=(0, 0, 0, 140))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

        y = box_top
        for line in lines:
            w = draw.textbbox((0, 0), line, font=font)[2]
            x = (W - w) // 2
            draw.text((x, y), line, font=font, fill="white",
                       stroke_width=3, stroke_fill="black")
            y += line_height

    img.save(out_path, quality=92)


if __name__ == "__main__":
    main()
