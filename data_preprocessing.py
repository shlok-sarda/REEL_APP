import yt_dlp
import re
import os
import json
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


def is_cache_entry_usable(entry):
    if not isinstance(entry, dict):
        return False

    return bool(
        (entry.get("caption") or "").strip()
        or (entry.get("transcript") or "").strip()
        or (entry.get("hashtags") or "").strip()
    )

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
def download_reel(url):
    shortcode = get_shortcode_from_url(url)
    filename = BASE_DIR / f"{shortcode}.mp4"

    if filename.exists():
        return str(filename)

    try:
        with yt_dlp.YoutubeDL({
            'outtmpl': filename,
            'format': 'mp4',
            'quiet': True,
            'no_warnings': True
        }) as ydl:
            ydl.download([url])

        return str(filename)

    except:
        return None


# ----------------------------
# TRANSCRIPT
# ----------------------------
def generate_transcript(video_path):
    try:
        with open(video_path, "rb") as f:
            transcript = client.audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=f
            )
        return transcript.text

    except:
        return ""


# ----------------------------
# PROCESS ONE REEL
# ----------------------------
def process_reel(url):
    shortcode = get_shortcode_from_url(url)

    # CACHE HIT
    if shortcode in cache and is_cache_entry_usable(cache[shortcode]):
        print(f"⚡ Cache: {shortcode}")
        return cache[shortcode]

    print(f"⬇️ Processing: {shortcode}")

    meta = extract_metadata(url)
    video_path = download_reel(url)

    transcript = ""

    if video_path and os.path.exists(video_path):
        transcript = generate_transcript(video_path)
        os.remove(video_path)   # 🔥 delete video immediately

    result = {
        "transcript": transcript if transcript else "",
        "caption": meta.get("caption", ""),
        "hashtags": meta.get("hashtags", ""),   # 🔥 ensure always present
        "creator": meta.get("creator", ""),
        "location": meta.get("location", "")
    }   

    # SAVE CACHE
    cache[shortcode] = result
    with open(CACHE_FILE, "w") as f:
        json.dump(cache, f)

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
