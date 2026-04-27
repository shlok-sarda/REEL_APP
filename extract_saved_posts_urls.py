import argparse
import csv
import json
from pathlib import Path


def normalize(value):
    return " ".join((value or "").strip().split())


def load_urls(saved_posts_json):
    data = json.loads(Path(saved_posts_json).read_text(encoding="utf-8"))
    items = data.get("saved_saved_media", [])
    urls = []
    seen = set()

    for item in items:
        url = normalize(item.get("string_map_data", {}).get("Saved on", {}).get("href"))
        if not url or url in seen:
            continue
        seen.add(url)
        urls.append(url)

    return urls


def write_urls(urls, output_csv):
    Path(output_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        for url in urls:
            writer.writerow([url])


def main():
    parser = argparse.ArgumentParser(description="Extract saved Instagram post/reel URLs from Meta export JSON.")
    parser.add_argument("--input", required=True, help="Path to saved_posts.json")
    parser.add_argument("--output", required=True, help="CSV output path")
    args = parser.parse_args()

    urls = load_urls(args.input)
    write_urls(urls, args.output)
    print(f"Saved URLs: {len(urls)}")
    print(f"Output CSV: {args.output}")


if __name__ == "__main__":
    main()
