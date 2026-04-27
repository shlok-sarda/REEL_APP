import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG = BASE_DIR / "saved_reels_accumulated.csv"
DEFAULT_PERSONALIZED = BASE_DIR / "saved_reels_personalized_view.json"


def normalize(value):
    return " ".join((value or "").strip().split())


def shortcode_from_url(url):
    parsed = urlparse(normalize(url))
    parts = [part for part in parsed.path.split("/") if part]
    return parts[-1] if parts else normalize(url).rstrip("/")


def load_rows(path):
    with open(path, newline="", encoding="utf-8") as infile:
        return list(csv.DictReader(infile))


def load_personalized_lookup(path):
    if not Path(path).exists():
        return {}

    data = json.loads(Path(path).read_text(encoding="utf-8"))
    lookup = {}

    for section in data.get("sections", []):
        primary = normalize(section.get("umbrella_name"))
        mode = normalize(section.get("personalization_mode"))
        promoted_from = normalize(section.get("promoted_from"))

        for group in section.get("display_groups", []):
            group_name = normalize(group.get("name"))
            for topic in group.get("topics", []):
                topic_id = normalize(topic.get("id"))
                if topic_id:
                    lookup[topic_id] = {
                        "personalized_primary": primary,
                        "personalized_group": group_name,
                        "personalization_mode": mode,
                        "promoted_from": promoted_from,
                    }

    return lookup


def find_rows(rows, url):
    target_shortcode = shortcode_from_url(url)
    target_normalized = normalize(url).rstrip("/")

    matches = []
    for row in rows:
        row_url = normalize(row.get("URL"))
        if not row_url:
            continue
        row_shortcode = shortcode_from_url(row_url)
        if row_url.rstrip("/") == target_normalized or row_shortcode == target_shortcode:
            matches.append(row)
    return matches


def summarize_rows(rows):
    primary = normalize(rows[0].get("Primary Category") or rows[0].get("Umbrella Folder"))
    umbrella = normalize(rows[0].get("Umbrella Folder"))
    secondary = normalize(rows[0].get("Secondary Category") or rows[0].get("Folder"))
    folder = normalize(rows[0].get("Folder"))
    url = normalize(rows[0].get("URL"))

    items = []
    seen = set()
    for row in rows:
        name = normalize(row.get("Item Name"))
        summary = normalize(row.get("Summary"))
        key = (name, summary)
        if key in seen:
            continue
        seen.add(key)
        if name or summary:
            items.append({"name": name, "summary": summary})

    return {
        "url": url,
        "shortcode": shortcode_from_url(url),
        "primary_category": primary,
        "umbrella_folder": umbrella,
        "secondary_category": secondary,
        "folder": folder,
        "items": items,
    }


def build_secondary_counts(rows):
    counts = defaultdict(int)
    for row in rows:
        secondary = normalize(row.get("Secondary Category") or row.get("Folder"))
        if secondary:
            counts[secondary] += 1
    return counts


def print_result(summary, secondary_counts):
    print("\nReel found")
    print("=" * 72)
    print(f"URL: {summary['url']}")
    print(f"Shortcode: {summary['shortcode']}")
    print(f"Primary / Umbrella: {summary['primary_category']}")
    print(f"Secondary / Folder: {summary['secondary_category']}")
    print(f"Rows in this folder: {secondary_counts.get(summary['secondary_category'], 0)}")

    print("\nItems in this reel:")
    if not summary["items"]:
        print("- No items found")
    else:
        for item in summary["items"]:
            label = item["name"] or "Untitled Item"
            detail = f" - {item['summary']}" if item["summary"] else ""
            print(f"- {label}{detail}")

    print("\nOpen Reel:")
    print(summary["url"])


def find_reel_location(url, catalog_path=DEFAULT_CATALOG):
    rows = load_rows(catalog_path)
    matches = find_rows(rows, url)

    if not matches:
        return {
            "found": False,
            "searched_url": url,
            "searched_shortcode": shortcode_from_url(url),
            "catalog": str(catalog_path),
        }

    summary = summarize_rows(matches)
    secondary_counts = build_secondary_counts(rows)
    return {
        "found": True,
        **summary,
        "rows_in_secondary_folder": secondary_counts.get(summary["secondary_category"], 0),
        "catalog": str(catalog_path),
    }


def pretty_print_location(result):
    if not result.get("found"):
        print("Reel not found in catalog.")
        print(f"Searched shortcode: {result.get('searched_shortcode', '')}")
        print(f"Catalog: {result.get('catalog', '')}")
        return

    print("\nReel found")
    print("=" * 72)
    print(f"URL: {result['url']}")
    print(f"Shortcode: {result['shortcode']}")
    print(f"Primary / Umbrella: {result['primary_category']}")
    print(f"Secondary / Folder: {result['secondary_category']}")
    print(f"Rows in this folder: {result['rows_in_secondary_folder']}")

    print("\nItems in this reel:")
    if not result["items"]:
        print("- No items found")
    else:
        for item in result["items"]:
            label = item["name"] or "Untitled Item"
            detail = f" - {item['summary']}" if item["summary"] else ""
            print(f"- {label}{detail}")

    print("\nOpen Reel:")
    print(result["url"])


def main():
    parser = argparse.ArgumentParser(
        description="Find where a saved reel URL landed in the generated catalog."
    )
    parser.add_argument("url", help="Instagram reel/post URL to search for.")
    parser.add_argument(
        "--catalog",
        default=str(DEFAULT_CATALOG),
        help="Catalog CSV to search. Defaults to saved_reels_accumulated.csv.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of text.",
    )
    args = parser.parse_args()

    result = find_reel_location(args.url, args.catalog)

    if args.json:
        print(json.dumps(result, indent=2))
        return

    pretty_print_location(result)


if __name__ == "__main__":
    main()
