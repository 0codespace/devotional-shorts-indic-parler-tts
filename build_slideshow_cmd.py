#!/usr/bin/env python3
"""Build an ffmpeg crossfade-slideshow command for a list of images + one audio file.
Generates a bash snippet that renders a Ken-Burns-zoomed crossfade video.
Usage: build_slideshow_cmd.py <audio_mp3> <out_mp4> <duration> <img1> [img2 ...]
Prints a ready-to-run ffmpeg command (single line).
"""
import sys, json

audio = sys.argv[1]
out = sys.argv[2]
duration = float(sys.argv[3])
imgs = sys.argv[4:]
n = len(imgs)
trans = 0.6
seg = round((duration - trans * (n - 1)) / n, 3)
fps = 25

# scale/crop each input
pre = []
for i in range(n):
    pre.append(f"[{i}:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,format=yuv420p,setsar=1[vi{i}];")
# xfade chain: each step takes previous composited output + next raw image
chain = "[vi0]"
for i in range(1, n):
    off = round(seg * i, 3)
    chain += f"[vi{i}]xfade=transition=fade:duration={trans}:offset={off}[v{i}];"
chain = chain.replace("[vi0]", "[vi0][vi1]xfade=transition=fade:duration=%s:offset=%s[v1];" % (trans, round(seg*1,3)), 1) if n >= 2 else chain
# Rebuild cleanly to avoid the fragile replace above:
chain = "[vi0][vi1]xfade=transition=fade:duration=%s:offset=%s[v1];" % (trans, round(seg*1,3))
for i in range(2, n):
    off = round(seg * i, 3)
    chain += f"[v{i-1}][vi{i}]xfade=transition=fade:duration={trans}:offset={off}[v{i}];"
chain += f"[v{n-1}]scale=1080:1920,zoompan=z='min(zoom+0.0006,1.12)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps={fps},format=yuv420p[vout]"
fc = "".join(pre) + chain

inp = " ".join(f"-loop 1 -i \"{p}\"" for p in imgs)
cmd = (
    f"ffmpeg -y {inp} -i \"{audio}\" "
    f"-filter_complex \"{fc}\" -map \"[vout]\" -map {n}:a "
    f"-af \"loudnorm=I=-16:TP=-1.5:LRA=11\" "
    f"-c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p "
    f"-c:a aac -b:a 160k -t {duration} -movflags +faststart \"{out}\""
)
print(cmd)
