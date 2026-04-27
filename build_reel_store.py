import argparse
import csv
import json
from collections import defaultdict
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_RAW_CSV = BASE_DIR / "final_output_TECH.csv"
DEFAULT_ACCUMULATED_CSV = BASE_DIR / "final_output_TECH_accumulated.csv"
DEFAULT_CACHE_JSON = BASE_DIR / "cache.json"
DEFAULT_URLS_CSV = BASE_DIR / "all_current_urls.csv"
DEFAULT_STORE_DIR = BASE_DIR / "reel_store"


def normalize(value):
    return " ".join((value or "").strip().split())


def shortcode_from_url(url):
    parts = [part for part in urlparse(url).path.split("/") if part]
    return parts[-1] if parts else normalize(url).replace("/", "_")


def load_csv_rows(path):
    with open(path, newline="", encoding="utf-8") as infile:
        return list(csv.DictReader(infile))


def load_urls(path):
    urls = []
    seen = set()
    with open(path, newline="", encoding="utf-8") as infile:
        for row in csv.reader(infile):
            if not row:
                continue
            url = normalize(row[0])
            if url and url not in seen:
                seen.add(url)
                urls.append(url)
    return urls


def load_cache(path):
    if not Path(path).exists():
        return {}
    with open(path, encoding="utf-8") as infile:
        data = json.load(infile)
    return data if isinstance(data, dict) else {}


def collect_raw_records(rows):
    grouped = defaultdict(list)
    for row in rows:
        url = normalize(row.get("URL"))
        if not url:
            continue
        grouped[url].append(
            {
                "item_name": normalize(row.get("Item Name")),
                "summary": normalize(row.get("Summary")),
                "folder": normalize(row.get("Folder")),
                "primary_category": normalize(row.get("Primary Category")),
                "secondary_category": normalize(row.get("Secondary Category")),
            }
        )
    return grouped


def collect_umbrella_lookup(rows):
    lookup = {}
    for row in rows:
        url = normalize(row.get("URL"))
        if not url:
            continue
        lookup[url] = {
            "umbrella_folder": normalize(row.get("Umbrella Folder") or row.get("Umbrella Category")),
            "primary_category": normalize(row.get("Primary Category")),
            "secondary_category": normalize(row.get("Secondary Category")),
        }
    return lookup


def build_record(url, raw_records, umbrella_lookup, cache_lookup):
    shortcode = shortcode_from_url(url)
    cache_entry = cache_lookup.get(shortcode, {}) if isinstance(cache_lookup.get(shortcode), dict) else {}
    rows = raw_records.get(url, [])
    umbrella_meta = umbrella_lookup.get(url, {})

    items = []
    seen_items = set()
    for row in rows:
        item_key = (row.get("item_name"), row.get("summary"))
        if item_key in seen_items:
            continue
        seen_items.add(item_key)
        if row.get("item_name") or row.get("summary"):
            items.append(
                {
                    "name": row.get("item_name", ""),
                    "summary": row.get("summary", ""),
                }
            )

    secondary = ""
    for row in rows:
        secondary = row.get("secondary_category") or row.get("folder") or secondary
        if secondary:
            break
    primary = ""
    for row in rows:
        primary = row.get("primary_category") or primary
        if primary:
            break

    if not primary:
        primary = umbrella_meta.get("primary_category") or umbrella_meta.get("umbrella_folder") or ""
    if not secondary:
        secondary = umbrella_meta.get("secondary_category") or ""

    record = {
        "url": url,
        "shortcode": shortcode,
        "saved_on": str(date.today()),
        "text": {
            "caption": cache_entry.get("caption", ""),
            "transcript": cache_entry.get("transcript", ""),
            "hashtags": cache_entry.get("hashtags", ""),
            "creator": cache_entry.get("creator", ""),
            "location": cache_entry.get("location", ""),
        },
        "visual": {
            "status": "missing",
            "data": {},
        },
        "classification": {
            "status": "partial" if rows else "missing",
            "primary_category": primary,
            "secondary_category": secondary,
            "legacy_folder": secondary or (rows[0].get("folder", "") if rows else ""),
            "items": items,
        },
    }
    return record


def write_store(urls, raw_records, umbrella_lookup, cache_lookup, store_dir):
    store_dir.mkdir(parents=True, exist_ok=True)
    reels_dir = store_dir / "reels"
    reels_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "generated_on": str(date.today()),
        "reel_count": 0,
        "source_files": {
            "urls": str(DEFAULT_URLS_CSV.name),
            "raw_csv": str(DEFAULT_RAW_CSV.name),
            "accumulated_csv": str(DEFAULT_ACCUMULATED_CSV.name),
            "cache_json": str(DEFAULT_CACHE_JSON.name),
        },
        "reels": [],
    }

    for url in urls:
        record = build_record(url, raw_records, umbrella_lookup, cache_lookup)
        target = reels_dir / f"{record['shortcode']}.json"
        target.write_text(json.dumps(record, indent=2), encoding="utf-8")
        manifest["reels"].append(
            {
                "shortcode": record["shortcode"],
                "url": url,
                "path": str(target.relative_to(store_dir)),
                "primary_category": record["classification"]["primary_category"],
                "secondary_category": record["classification"]["secondary_category"],
                "has_transcript": bool(record["text"]["transcript"]),
                "has_visual_data": record["visual"]["status"] == "ready",
            }
        )

    manifest["reel_count"] = len(manifest["reels"])
    (store_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Build a reusable per-reel local data store.")
    parser.add_argument("--urls", default=str(DEFAULT_URLS_CSV), help="CSV with one reel URL per row.")
    parser.add_argument("--raw-csv", default=str(DEFAULT_RAW_CSV), help="Raw classification CSV.")
    parser.add_argument("--accumulated-csv", default=str(DEFAULT_ACCUMULATED_CSV), help="Accumulated CSV.")
    parser.add_argument("--cache-json", default=str(DEFAULT_CACHE_JSON), help="Text extraction cache.")
    parser.add_argument("--store-dir", default=str(DEFAULT_STORE_DIR), help="Output folder for per-reel JSON files.")
    args = parser.parse_args()

    urls = load_urls(args.urls)
    raw_rows = load_csv_rows(args.raw_csv)
    accumulated_rows = load_csv_rows(args.accumulated_csv) if Path(args.accumulated_csv).exists() else []
    cache_lookup = load_cache(args.cache_json)

    raw_records = collect_raw_records(raw_rows)
    umbrella_lookup = collect_umbrella_lookup(accumulated_rows)
    write_store(urls, raw_records, umbrella_lookup, cache_lookup, Path(args.store_dir))

    print(f"Saved reel store: {args.store_dir}")
    print(f"Reels written: {len(urls)}")


if __name__ == "__main__":
    main()
