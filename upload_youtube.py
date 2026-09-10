#!/usr/bin/env python3
"""Upload a rendered short to YouTube using stored OAuth refresh token.
Improvements: token-refresh failure handling, resumable chunked upload with retry,
durable upload log (dedup + analytics), and graceful failure that keeps the video file.
Category 22 = People & Blogs (suitable for spiritual/shorts)."""
import json
import mimetypes
import os
import re
import sys
import time
import urllib.parse
import urllib.request

BASE = os.path.expanduser("~/devotional-shorts")
CONFIG_PATH = os.path.join(BASE, "yt_config.json")
LOG_PATH = os.path.join(BASE, "uploads.jsonl")
TOKEN_URL = "https://oauth2.googleapis.com/token"
UPLOAD_URL = "https://www.googleapis.com/upload/youtube/v3/videos?uploadType=resumable&part=snippet,status"

# Stable channel metadata. The model may suggest useful story-specific tags, but
# the channel identity should not change from upload to upload.
CATEGORY_META = {
    "ganesha": {"name": "गणेश", "tag": "Ganesha"},
    "shiva": {"name": "शिव", "tag": "Shiva"},
    "hanuman": {"name": "हनुमान", "tag": "Hanuman"},
    "krishna": {"name": "कृष्ण", "tag": "Krishna"},
    "rama": {"name": "राम", "tag": "Ram"},
    "vishnu": {"name": "विष्णु", "tag": "Vishnu"},
    "durga": {"name": "दुर्गा", "tag": "Durga"},
    "lakshmi": {"name": "लक्ष्मी", "tag": "Lakshmi"},
    "saraswati": {"name": "सरस्वती", "tag": "Saraswati"},
}


def build_title(raw_title, topic):
    """Keep a human-readable Hindi title with exactly one Shorts marker."""
    title = " ".join((raw_title or topic or "हिंदी भक्ति कथा").split())
    # The generator is asked for #Shorts, but some models emit it twice or add
    # unrelated hashtags to the title. Keep hashtags in the description instead.
    title = re.sub(r"#shorts\b", "", title, flags=re.IGNORECASE)
    title = re.sub(r"#[A-Za-z0-9_]+", "", title)
    title = " ".join(title.split()).strip(" -|")
    suffix = " #Shorts"
    return (title[:100 - len(suffix)].rstrip() + suffix)[:100]


def build_hashtags(raw_hashtags, category):
    """Return a compact, relevant hashtag string for the description."""
    meta = CATEGORY_META.get(category, {"tag": "Bhakti"})
    stable = ["#Shorts", "#Bhakti", "#HindiDevotional", f"#{meta['tag']}", "#HinduStories"]
    suggested = re.findall(r"#[A-Za-z0-9_]+", raw_hashtags or "")
    result = []
    for tag in stable + suggested:
        key = tag.lower()
        if key not in {x.lower() for x in result}:
            result.append(tag)
        if len(result) >= 8:
            break
    return " ".join(result)


def build_tags(raw_hashtags, category, topic):
    """Build useful API tags while staying well below YouTube's 500-char limit."""
    meta = CATEGORY_META.get(category, {"tag": "Bhakti"})
    candidates = [
        meta["tag"], "Bhakti", "Hindi devotional", "Hindu mythology",
        "Hindi stories", "Devotional Shorts", topic,
    ] + [x.lstrip("#") for x in re.findall(r"#[A-Za-z0-9_]+", raw_hashtags or "")]
    result, used, chars = [], set(), 0
    for tag in candidates:
        tag = " ".join((tag or "").split()).strip()
        key = tag.casefold()
        cost = len(tag) + (1 if result else 0)
        if not tag or key in used or chars + cost > 490:
            continue
        result.append(tag)
        used.add(key)
        chars += cost
    return result


def get_access_token(cfg, retries=3):
    last = None
    for i in range(retries):
        try:
            body = urllib.parse.urlencode({
                "client_id": cfg["client_id"],
                "client_secret": cfg["client_secret"],
                "refresh_token": cfg["refresh_token"],
                "grant_type": "refresh_token",
            }).encode()
            req = urllib.request.Request(TOKEN_URL, data=body, method="POST")
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read())["access_token"]
        except Exception as e:
            last = e
            time.sleep(2 ** i)
    raise RuntimeError(f"Token refresh failed after {retries} tries: {last}")


def _do_put(session_url, video_path, access_token):
    """Resumable PUT with retry on network errors; returns parsed JSON or raises."""
    total = os.path.getsize(video_path)
    ct = mimetypes.guess_type(video_path)[0] or "video/mp4"
    with open(video_path, "rb") as f:
        data = f.read()
    for attempt in range(5):
        try:
            req = urllib.request.Request(
                session_url, data=data, method="PUT",
                headers={"Content-Type": ct, "Authorization": f"Bearer {access_token}"},
            )
            with urllib.request.urlopen(req, timeout=300) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            if e.code in (401,):
                raise  # token bad, caller refreshes
            time.sleep(3 * (attempt + 1))
        except Exception:
            time.sleep(3 * (attempt + 1))
    raise RuntimeError("Upload PUT failed after retries")


def upload_video(video_path, title, description, tags, access_token, privacy="public", publish_at=None):
    metadata = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": "22",
            "defaultLanguage": "hi",
            "defaultAudioLanguage": "hi",
        },
        "status": {
            "privacyStatus": privacy,
            "license": "youtube",
            "embeddable": True,
            "publicStatsViewable": True,
            "selfDeclaredMadeForKids": False,
            # Disclose AI-assisted content (LLM script + TTS voiceover). Future-proofs
            # the channel if realistic AI visuals are ever added. Override via env.
            "containsSyntheticMedia": os.environ.get("SYNTHETIC_MEDIA", "true").lower() in ("1", "true", "yes"),
        },
    }
    if publish_at:
        # YouTube only allows publishAt with privacyStatus "private" (scheduled release).
        # A public video cannot carry a future publishAt.
        metadata["status"]["privacyStatus"] = "private"
        metadata["status"]["publishAt"] = publish_at
    meta_bytes = json.dumps(metadata).encode()
    init_req = urllib.request.Request(
        UPLOAD_URL, data=meta_bytes, method="POST",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; charset=UTF-8",
            "X-Upload-Content-Type": mimetypes.guess_type(video_path)[0] or "video/mp4",
            "X-Upload-Content-Length": str(os.path.getsize(video_path)),
        },
    )
    with urllib.request.urlopen(init_req, timeout=20) as resp:
        session_url = resp.headers.get("Location")
    return _do_put(session_url, video_path, access_token)


def log_upload(entry):
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def already_uploaded(topic, title):
    if not os.path.exists(LOG_PATH):
        return False
    for line in open(LOG_PATH):
        try:
            e = json.loads(line)
        except Exception:
            continue
        if e.get("topic") == topic or e.get("title") == title:
            return e.get("id")
    return False


if __name__ == "__main__":
    video_path = sys.argv[1]
    script_json_path = sys.argv[2]
    privacy = sys.argv[3] if len(sys.argv) > 3 else "public"
    publish_at = sys.argv[4] if len(sys.argv) > 4 else None

    with open(CONFIG_PATH) as f:
        cfg = json.load(f)
    with open(script_json_path) as f:
        script = json.load(f)

    topic = script.get("topic", "")
    category = script.get("category", "")
    title = build_title(script.get("title", ""), topic)

    # Dedup guard: don't re-upload same topic/title
    dup = already_uploaded(topic, title)
    if dup:
        print(json.dumps({"id": dup, "status": "skipped_duplicate", "topic": topic}))
        sys.exit(0)

    hashtags = build_hashtags(script.get("hashtags", ""), category)
    deity = CATEGORY_META.get(category, {}).get("name", "भक्ति")
    cta = script.get("cta") or "भक्ति में आपकी राय क्या है? कमेंट करें।"
    description = (
        f"{script['narration']}\n\n"
        f"{cta}\n\n"
        f"🙏 {deity} भक्ति, पौराणिक कथाएँ और आध्यात्मिक सीख — हर दिन हिंदी में।\n"
        f"इस Short में: {topic}\n\n"
        f"{hashtags}\n\n"
        "भक्ति और धर्म की ऐसी कथाओं के लिए चैनल को सब्सक्राइब करें।\n"
        "Subscribe for Hindi devotional stories and spiritual wisdom."
    )
    tags = build_tags(script.get("hashtags", ""), category, topic)

    try:
        token = get_access_token(cfg)
        result = upload_video(video_path, title, description, tags, token, privacy, publish_at)
        vid = result.get("id", "unknown")
        log_upload({
            "id": vid, "topic": topic, "title": title,
            "category": script.get("category", ""),
            "festival_event": script.get("festival_event", ""),
            "festival_date": script.get("festival_date", ""),
            "scheduled_category": script.get("scheduled_category", ""),
            "uploaded_at": time.time(), "privacy": privacy,
            "publish_at": publish_at, "status": "uploaded",
        })
        print(json.dumps(result, ensure_ascii=False))
    except Exception as e:
        # Keep the video file; record failure so n8n can alert and we can retry
        log_upload({"topic": topic, "title": title, "uploaded_at": time.time(),
                    "status": "failed", "error": str(e)})
        raise SystemExit(f"Upload failed (video kept at {video_path}): {e}")
