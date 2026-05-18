import yt_dlp
import re
import os
import json
import time
import pandas as pd
from pathlib import Path
from urllib.parse import urlparse
from api_config import get_openai_client

# ----------------------------
# CONFIG
# ----------------------------
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
INPUT_CSV = PROJECT_ROOT / "Untitled spreadsheet - Sheet1-3.csv"        # url, category
OUTPUT_CSV = BASE_DIR / "formated_data.csv"
CACHE_FILE = BASE_DIR / "cache.json"

client = get_openai_client()

# Load cache
if CACHE_FILE.exists():
    with open(CACHE_FILE, "r") as f:
        cache = json.load(f)
else:
    cache = {}


def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)


def save_cache_entry(shortcode, payload):
    if not shortcode:
        return
    existing = cache.get(shortcode, {}) if isinstance(cache.get(shortcode), dict) else {}
    merged = dict(existing)
    merged.update(payload or {})
    cache[shortcode] = merged
    save_cache()


def is_cache_entry_usable(entry):
    if not isinstance(entry, dict):
        return False

    return bool(
        (entry.get("caption") or "").strip()
        or (entry.get("transcript") or "").strip()
        or (entry.get("hashtags") or "").strip()
    )


def has_transcript(entry):
    if not isinstance(entry, dict):
        return False
    return bool((entry.get("transcript") or "").strip())

# ----------------------------
# HELPERS
# ----------------------------
def get_shortcode_from_url(url):
    parsed = urlparse((url or "").strip())
    path_parts = [part for part in parsed.path.split("/") if part]
    return path_parts[-1] if path_parts else (url or "").strip("/").split("/")[-1]


# ----------------------------
# METADATA (FAST yt_dlp)
# ----------------------------
def extract_metadata(url):
    try:
        with yt_dlp.YoutubeDL({'quiet': True, 'skip_download': True}) as ydl:
            info = ydl.extract_info(url, download=False)

        caption = info.get("description") or info.get("title") or ""
        uploader = info.get("uploader", "unknown")

        return {
            "creator": uploader,
            "caption": caption,
            "hashtags": " ".join(re.findall(r"#\w+", caption.lower())),
            "location": ""
        }

    except:
        return {
            "creator": "unknown",
            "caption": "",
            "hashtags": "",
            "location": ""
        }


# ----------------------------
# DOWNLOAD
# ----------------------------
def download_reel(url, media_kind="video"):
    shortcode = get_shortcode_from_url(url)
    suffix = "audio" if media_kind == "audio" else "video"
    pattern = f"{shortcode}_{suffix}.*"
    existing_files = sorted(BASE_DIR.glob(pattern))
    if existing_files:
        return str(existing_files[0]), "reused_existing"

    outtmpl = str(BASE_DIR / f"{shortcode}_{suffix}.%(ext)s")
    candidate_formats = ['bestaudio/best', 'best'] if media_kind == "audio" else [
        'best[ext=mp4]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best',
        'best',
    ]

    for index, fmt in enumerate(candidate_formats, start=1):
        ydl_opts = {
            'outtmpl': outtmpl,
            'quiet': True,
            'no_warnings': True,
            'format': fmt,
        }
        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            downloaded_files = sorted(BASE_DIR.glob(pattern))
            if downloaded_files:
                return str(downloaded_files[0]), f"downloaded_attempt_{index}"
        except Exception as exc:
            print(f"⚠️ Download failed for {shortcode} ({media_kind}, attempt {index}): {exc}")

    return None, "download_failed"


# ----------------------------
# TRANSCRIPT
# ----------------------------
def generate_transcript(video_path, retries=3, retry_delay=2):
    models = ["gpt-4o-mini-transcribe", "whisper-1"]
    last_error = ""

    for model_name in models:
        for attempt in range(1, retries + 1):
            try:
                with open(video_path, "rb") as f:
                    transcript = client.audio.transcriptions.create(
                        model=model_name,
                        file=f
                    )

                text = (getattr(transcript, "text", "") or "").strip()
                if text:
                    return text, {
                        "status": "success",
                        "model": model_name,
                        "attempts": attempt,
                        "error": "",
                    }

                last_error = f"{model_name} returned empty transcript"
                print(f"⚠️ Transcript empty for {Path(video_path).name} via {model_name} (attempt {attempt}/{retries})")

            except Exception as exc:
                last_error = str(exc)
                print(f"⚠️ Transcript failed for {Path(video_path).name} via {model_name} (attempt {attempt}/{retries}): {exc}")

            if attempt < retries:
                time.sleep(retry_delay)

    return "", {
        "status": "empty_or_failed",
        "model": "",
        "attempts": retries * len(models),
        "error": last_error,
    }


def cleanup_file(path):
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


# ----------------------------
# PROCESS ONE REEL
# ----------------------------
def process_reel(url, refresh_transcript=True):
    shortcode = get_shortcode_from_url(url)
    existing_entry = cache.get(shortcode, {}) if isinstance(cache.get(shortcode), dict) else {}

    # CACHE HIT: if transcript is already present, reuse it.
    if is_cache_entry_usable(existing_entry) and (has_transcript(existing_entry) or not refresh_transcript):
        print(f"⚡ Cache: {shortcode}")
        payload = dict(existing_entry)
        payload.setdefault("caption_present", bool((payload.get("caption") or "").strip()))
        payload.setdefault("hashtags_present", bool((payload.get("hashtags") or "").strip()))
        payload.setdefault("creator_present", bool((payload.get("creator") or "").strip() and payload.get("creator") != "unknown"))
        payload.setdefault("transcript_present", bool((payload.get("transcript") or "").strip()))
        payload.setdefault("audio_download_status", "cache_reused")
        payload.setdefault("video_download_status", "cache_reused")
        payload.setdefault("video_path_for_visual", "")
        return payload

    print(f"⬇️ Processing: {shortcode}")

    meta = extract_metadata(url)
    if existing_entry:
        meta = {
            "creator": existing_entry.get("creator") or meta.get("creator", ""),
            "caption": existing_entry.get("caption") or meta.get("caption", ""),
            "hashtags": existing_entry.get("hashtags") or meta.get("hashtags", ""),
            "location": existing_entry.get("location") or meta.get("location", ""),
        }

    audio_path, audio_download_status = download_reel(url, media_kind="audio")

    transcript = ""
    transcript_meta = {
        "status": "download_failed" if not audio_path else "empty_or_failed",
        "model": "",
        "attempts": 0,
        "error": "",
    }

    if audio_path and os.path.exists(audio_path):
        transcript, transcript_meta = generate_transcript(audio_path)

    # If the audio asset is broken, try the full video file before giving up.
    if not transcript and transcript_meta.get("status") == "empty_or_failed":
        video_path, video_download_status = download_reel(url, media_kind="video")
        if video_path and os.path.exists(video_path):
            transcript, video_transcript_meta = generate_transcript(video_path)
            if transcript:
                transcript_meta = video_transcript_meta
            elif not transcript_meta.get("error"):
                transcript_meta = video_transcript_meta
        else:
            video_download_status = video_download_status or "download_failed"
    else:
        video_path = ""
        video_download_status = "not_needed"

    cleanup_file(audio_path)

    result = {
        "transcript": transcript if transcript else "",
        "caption": meta.get("caption", ""),
        "hashtags": meta.get("hashtags", ""),   # 🔥 ensure always present
        "creator": meta.get("creator", ""),
        "location": meta.get("location", ""),
        "transcript_status": transcript_meta["status"] if transcript_meta["status"] else ("success" if transcript else ("download_failed" if not audio_path else "empty_or_failed")),
        "transcript_model": transcript_meta.get("model", ""),
        "transcript_attempts": transcript_meta.get("attempts", 0),
        "transcript_error": transcript_meta.get("error", ""),
        "caption_present": bool(meta.get("caption", "").strip()),
        "hashtags_present": bool(meta.get("hashtags", "").strip()),
        "creator_present": bool(meta.get("creator", "").strip() and meta.get("creator", "") != "unknown"),
        "transcript_present": bool(transcript.strip()),
        "audio_download_status": audio_download_status,
        "video_download_status": video_download_status,
        "video_path_for_visual": video_path if video_path and os.path.exists(video_path) else "",
    }   

    # SAVE CACHE
    save_cache_entry(shortcode, result)

    return result


# ----------------------------
# BUILD DATASET
# ----------------------------
def build_dataset():
    df = pd.read_csv(INPUT_CSV)   # url, category

    rows = []

    for i, row in df.iterrows():
        url = row["URLs"]
        label = row["Category"]

        print(f"\n[{i+1}/{len(df)}]")

        data = process_reel(url)

        # COMBINE TEXT (important for SBERT later)
        combined_text = " ".join([
            (data.get("transcript") or "") * 2,
            data.get("caption") or "",
            data.get("hashtags") or ""
        ])

        rows.append({
            "url": url,
            "text": combined_text,
            "transcript": data["transcript"],
            "caption": data["caption"],
            "hashtags": data.get("hashtags", ""),
            "label": label
        })

    final_df = pd.DataFrame(rows)
    final_df.to_csv(OUTPUT_CSV, index=False)

    print(f"\n✅ Saved dataset → {OUTPUT_CSV}")


# ----------------------------
# RUN
# ----------------------------
if __name__ == "__main__":
    build_dataset()
