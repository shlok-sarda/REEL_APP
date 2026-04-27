import argparse
import json
from collections import defaultdict
from pathlib import Path

from render_mobile_knowledge_app import render_html


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_VIEW = BASE_DIR / "saved_reels_personalized_view.json"
DEFAULT_GRAPH = BASE_DIR / "saved_reels_topic_graph.json"
DEFAULT_OUTPUT = BASE_DIR / "saved_reels_personalized_app.html"


def normalize(value):
    return " ".join((value or "").strip().split())


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_collections(view, graph):
    reels_by_topic = defaultdict(list)
    for reel in graph.get("reels", []):
        for topic_id in reel.get("topic_ids", []):
            reels_by_topic[topic_id].append(reel)

    collections = []
    for section in view.get("sections", []):
        parent_title = normalize(section.get("umbrella_name"))
        for group in section.get("display_groups", []):
            seen = set()
            items = []
            reel_urls = set()

            for topic in group.get("topics", []):
                for reel in reels_by_topic.get(topic.get("id"), []):
                    url = normalize(reel.get("url"))
                    if url:
                        reel_urls.add(url)
                    for item in reel.get("items", []):
                        name = normalize(item.get("name"))
                        summary = normalize(item.get("summary")) or "No summary available."
                        if not name:
                            continue
                        key = (url, name.lower(), summary.lower())
                        if key in seen:
                            continue
                        seen.add(key)
                        items.append(
                            {
                                "name": name,
                                "summary": summary,
                                "url": url,
                                "contains_product": normalize(item.get("contains_product")),
                                "product_name": normalize(item.get("product_name")),
                                "product_brand": normalize(item.get("product_brand")),
                                "product_model": normalize(item.get("product_model")),
                                "product_type": normalize(item.get("product_type")),
                                "product_search_query": normalize(item.get("product_search_query")),
                                "best_buy_link": normalize(item.get("best_buy_link")),
                                "amazon_link": normalize(item.get("amazon_link")),
                                "flipkart_link": normalize(item.get("flipkart_link")),
                                "nykaa_link": normalize(item.get("nykaa_link")),
                                "media_status": normalize(item.get("media_status")),
                                "local_video_path": normalize(item.get("local_video_path")),
                                "local_video_url": normalize(item.get("local_video_url")),
                                "thumbnail_path": normalize(item.get("thumbnail_path")),
                                "thumbnail_url": normalize(item.get("thumbnail_url")),
                            }
                        )

            if not items:
                continue

            collections.append(
                {
                    "parent_title": parent_title,
                    "list_title": normalize(group.get("name")) or parent_title or "Untitled",
                    "items": sorted(items, key=lambda row: (row["name"].lower(), row["summary"].lower(), row["url"])),
                }
            )

    return collections


def main():
    parser = argparse.ArgumentParser(description="Render the personalized view in the new mobile split-view UI.")
    parser.add_argument("--view", default=str(DEFAULT_VIEW), help="Personalized view JSON.")
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH), help="Topic graph JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output HTML file.")
    parser.add_argument("--title", default="Saved Reels Personalized", help="Page title.")
    parser.add_argument(
        "--subtitle",
        default="Your repeated interests get their own lists; low-signal topics stay tucked away.",
        help="Page subtitle.",
    )
    args = parser.parse_args()

    view = load_json(args.view)
    graph = load_json(args.graph)
    collections = build_collections(view, graph)
    html = render_html(collections, args.title, args.subtitle)
    Path(args.output).write_text(html, encoding="utf-8")

    print(f"Saved personalized mobile app: {args.output}")
    print(f"Collections: {len(collections)}")
    print(f"Items: {sum(len(collection['items']) for collection in collections)}")


if __name__ == "__main__":
    main()
