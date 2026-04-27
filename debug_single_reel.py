import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlparse


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CACHE = BASE_DIR / "cache.json"
DEFAULT_RAW = BASE_DIR / "saved_reels_output_v2.csv"
DEFAULT_CLEANED = BASE_DIR / "saved_reels_cleaned.csv"
DEFAULT_ACCUMULATED = BASE_DIR / "saved_reels_accumulated.csv"
DEFAULT_GRAPH = BASE_DIR / "saved_reels_topic_graph.json"
DEFAULT_PERSONALIZED = BASE_DIR / "saved_reels_personalized_view.json"
DEFAULT_REEL_STORE = BASE_DIR / "reel_store" / "reels"


def normalize(value):
    return " ".join((value or "").strip().split())


def shortcode_from_url(url):
    parsed = urlparse(normalize(url))
    parts = [part for part in parsed.path.split("/") if part]
    return parts[-1] if parts else normalize(url).rstrip("/")


def load_csv(path):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as infile:
        return list(csv.DictReader(infile))


def load_json(path, default):
    if not Path(path).exists():
        return default
    return json.loads(Path(path).read_text(encoding="utf-8"))


def find_rows(rows, url):
    target_shortcode = shortcode_from_url(url)
    target_url = normalize(url).rstrip("/")
    matches = []

    for row in rows:
        row_url = normalize(row.get("URL")).rstrip("/")
        if not row_url:
            continue
        if row_url == target_url or shortcode_from_url(row_url) == target_shortcode:
            matches.append(row)

    return matches


def summarize_stage(rows):
    if not rows:
        return {
            "found": False,
            "row_count": 0,
            "primary_category": "",
            "secondary_category": "",
            "umbrella_folder": "",
            "folder": "",
            "items": [],
        }

    first = rows[0]
    seen = set()
    items = []
    for row in rows:
        name = normalize(row.get("Item Name"))
        summary = normalize(row.get("Summary"))
        key = (name, summary)
        if key in seen:
            continue
        seen.add(key)
        items.append({"name": name, "summary": summary})

    return {
        "found": True,
        "row_count": len(rows),
        "primary_category": normalize(first.get("Primary Category")),
        "secondary_category": normalize(first.get("Secondary Category")),
        "umbrella_folder": normalize(first.get("Umbrella Folder")),
        "folder": normalize(first.get("Folder")),
        "items": items,
    }


def graph_lookup(graph, url):
    target_shortcode = shortcode_from_url(url)
    topic_by_id = {topic["id"]: topic for topic in graph.get("topics", [])}
    reel = None

    for candidate in graph.get("reels", []):
        if candidate.get("shortcode") == target_shortcode:
            reel = candidate
            break

    if not reel:
        return {"found": False}

    topics = []
    umbrellas = []
    for topic_id in reel.get("topic_ids", []):
        topic = topic_by_id.get(topic_id)
        if topic:
            topics.append(topic)
            parent = topic_by_id.get(topic.get("parent_id"))
            if parent:
                umbrellas.append(parent)

    return {
        "found": True,
        "reel": reel,
        "topics": topics,
        "umbrellas": umbrellas,
    }


def personalized_lookup(personalized, graph_result):
    if not graph_result.get("found"):
        return []

    topic_ids = {topic["id"] for topic in graph_result.get("topics", [])}
    placements = []

    for section in personalized.get("sections", []):
        for group in section.get("display_groups", []):
            group_topic_ids = {topic.get("id") for topic in group.get("topics", [])}
            if topic_ids & group_topic_ids:
                placements.append(
                    {
                        "personalized_primary": normalize(section.get("umbrella_name")),
                        "personalized_group": normalize(group.get("name")),
                        "mode": normalize(section.get("personalization_mode")),
                        "promoted_from": normalize(section.get("promoted_from")),
                    }
                )

    return placements


def build_debug_report(url):
    shortcode = shortcode_from_url(url)
    cache = load_json(DEFAULT_CACHE, {})
    raw_rows = load_csv(DEFAULT_RAW)
    cleaned_rows = load_csv(DEFAULT_CLEANED)
    accumulated_rows = load_csv(DEFAULT_ACCUMULATED)
    graph = load_json(DEFAULT_GRAPH, {"topics": [], "reels": []})
    personalized = load_json(DEFAULT_PERSONALIZED, {"sections": []})

    raw_summary = summarize_stage(find_rows(raw_rows, url))
    cleaned_summary = summarize_stage(find_rows(cleaned_rows, url))
    accumulated_summary = summarize_stage(find_rows(accumulated_rows, url))
    graph_result = graph_lookup(graph, url)
    personalized_placements = personalized_lookup(personalized, graph_result)

    store_path = DEFAULT_REEL_STORE / f"{shortcode}.json"
    store_record = load_json(store_path, {}) if store_path.exists() else {}

    return {
        "url": url,
        "shortcode": shortcode,
        "cache": {
            "found": shortcode in cache,
            "text": cache.get(shortcode, {}),
        },
        "raw_model_output": raw_summary,
        "after_topic_cleanup": cleaned_summary,
        "after_umbrella_accumulation": accumulated_summary,
        "topic_graph": {
            "found": graph_result.get("found", False),
            "topics": [
                {
                    "id": topic.get("id"),
                    "name": topic.get("name"),
                    "stats": topic.get("stats", {}),
                }
                for topic in graph_result.get("topics", [])
            ],
            "umbrellas": [
                {
                    "id": umbrella.get("id"),
                    "name": umbrella.get("name"),
                    "stats": umbrella.get("stats", {}),
                }
                for umbrella in graph_result.get("umbrellas", [])
            ],
        },
        "personalized_view": personalized_placements,
        "local_reel_store": {
            "found": bool(store_record),
            "path": str(store_path),
            "record": store_record,
        },
    }


def print_stage(name, stage):
    print(f"\n{name}")
    print("-" * 72)
    print(f"Found: {stage.get('found')}")
    print(f"Rows: {stage.get('row_count', 0)}")
    print(f"Primary: {stage.get('primary_category', '')}")
    print(f"Umbrella: {stage.get('umbrella_folder', '')}")
    print(f"Secondary: {stage.get('secondary_category', '')}")
    print(f"Folder: {stage.get('folder', '')}")
    print("Items:")
    for item in stage.get("items", []):
        detail = f" - {item['summary']}" if item.get("summary") else ""
        print(f"- {item.get('name', '')}{detail}")


def pretty_print_report(report):
    print("\nSingle Reel Debug Report")
    print("=" * 72)
    print(f"URL: {report['url']}")
    print(f"Shortcode: {report['shortcode']}")

    cache = report["cache"]
    print("\nText / Transcript Cache")
    print("-" * 72)
    print(f"Found: {cache['found']}")
    text = cache.get("text", {})
    print(f"Creator: {text.get('creator', '')}")
    print(f"Location: {text.get('location', '')}")
    print(f"Hashtags: {text.get('hashtags', '')}")
    print(f"Caption: {text.get('caption', '')}")
    print(f"Transcript: {text.get('transcript', '')}")

    print_stage("Raw Model Output", report["raw_model_output"])
    print_stage("After Topic Cleanup", report["after_topic_cleanup"])
    print_stage("After Umbrella Accumulation", report["after_umbrella_accumulation"])

    print("\nTopic Graph Placement")
    print("-" * 72)
    graph = report["topic_graph"]
    print(f"Found: {graph['found']}")
    print("Umbrellas:")
    for umbrella in graph["umbrellas"]:
        print(f"- {umbrella['name']} | {umbrella['stats']}")
    print("Topics:")
    for topic in graph["topics"]:
        print(f"- {topic['name']} | {topic['stats']}")

    print("\nPersonalized View Placement")
    print("-" * 72)
    if not report["personalized_view"]:
        print("No personalized placement found.")
    for placement in report["personalized_view"]:
        print(
            f"- Primary: {placement['personalized_primary']} | "
            f"Group: {placement['personalized_group']} | "
            f"Mode: {placement['mode']} | "
            f"Promoted from: {placement['promoted_from']}"
        )

    store = report["local_reel_store"]
    print("\nLocal Reel Store")
    print("-" * 72)
    print(f"Found: {store['found']}")
    print(f"Path: {store['path']}")


def main():
    parser = argparse.ArgumentParser(
        description="Show all locally saved debug information for one reel URL without calling any AI APIs."
    )
    parser.add_argument("url", help="Instagram reel/post URL to debug.")
    parser.add_argument("--json", action="store_true", help="Print full JSON report.")
    parser.add_argument("--output", help="Optional path to save the full JSON report.")
    args = parser.parse_args()

    report = build_debug_report(args.url)

    if args.output:
        Path(args.output).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Saved debug report: {args.output}")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        pretty_print_report(report)


if __name__ == "__main__":
    main()
