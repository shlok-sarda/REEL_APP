import csv
import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import urlparse


def normalize(value):
    return " ".join((value or "").strip().split())


def normalize_key(value):
    return normalize(value).lower()


def best_display_name(current_name, incoming_name):
    current_name = normalize(current_name)
    incoming_name = normalize(incoming_name)

    current_caps = sum(1 for word in current_name.split() if word[:1].isupper())
    incoming_caps = sum(1 for word in incoming_name.split() if word[:1].isupper())

    if incoming_caps > current_caps:
        return incoming_name
    if incoming_caps == current_caps and len(incoming_name) > len(current_name):
        return incoming_name
    return current_name


def slugify(value):
    chars = []
    last_dash = False
    for char in normalize_key(value):
        if char.isalnum():
            chars.append(char)
            last_dash = False
        elif not last_dash:
            chars.append("-")
            last_dash = True

    slug = "".join(chars).strip("-")
    return slug or "untitled"


def short_hash(value, length=8):
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def extract_shortcode(url):
    path_parts = [part for part in urlparse(url).path.split("/") if part]
    return path_parts[-1] if path_parts else short_hash(url, 10)


def topic_id(kind, name, parent_id=None):
    base = f"{kind}:{normalize_key(name)}:{parent_id or ''}"
    return f"{kind}_{slugify(name)}_{short_hash(base)}"


def load_rows(input_csv):
    with open(input_csv, newline="", encoding="utf-8") as infile:
        return list(csv.DictReader(infile))


@dataclass
class TopicGraphConfig:
    user_id: str = "default_user"
    source_name: str = ""


def build_interest_score(unique_reels, topic_count, unique_items):
    return round(unique_reels * 1.8 + topic_count * 1.2 + unique_items * 0.35, 2)


def recommend_depth(unique_reels, topic_count):
    if unique_reels >= 12 or topic_count >= 6:
        return "expanded_subtopics"
    if unique_reels >= 5 or topic_count >= 3:
        return "show_subtopics"
    return "umbrella_only"


def build_topic_graph(rows, config):
    umbrella_nodes = {}
    topic_nodes = {}
    reel_nodes = {}
    umbrella_to_topics = defaultdict(set)
    topic_to_reels = defaultdict(set)
    topic_to_items = defaultdict(list)
    topic_item_keys = defaultdict(set)

    for row in rows:
        umbrella_name = normalize(
            row.get("Primary Category")
            or row.get("Umbrella Folder")
            or row.get("Umbrella Category")
            or "All Folders"
        )
        topic_name = normalize(row.get("Secondary Category") or row.get("Folder") or umbrella_name)
        item_name = normalize(row.get("Item Name"))
        summary = normalize(row.get("Summary"))
        url = normalize(row.get("URL"))

        if not topic_name or topic_name.upper() in {"ERROR", "FAILED"}:
            continue

        umbrella_id = umbrella_nodes.get(umbrella_name, {}).get("id")
        if not umbrella_id:
            umbrella_id = topic_id("umbrella", umbrella_name)
            umbrella_nodes[umbrella_name] = {
                "id": umbrella_id,
                "name": umbrella_name,
                "kind": "umbrella",
                "parent_id": None,
                "aliases": [],
                "stats": {
                    "unique_reel_count": 0,
                    "topic_count": 0,
                    "item_count": 0,
                },
            }

        topic_key = (umbrella_name, normalize_key(topic_name))
        if topic_key not in topic_nodes:
            node_id = topic_id("topic", topic_name, umbrella_id)
            topic_nodes[topic_key] = {
                "id": node_id,
                "name": topic_name,
                "kind": "topic",
                "parent_id": umbrella_id,
                "aliases": [topic_name],
                "stats": {
                    "unique_reel_count": 0,
                    "item_count": 0,
                },
                "sample_items": [],
                "sample_reels": [],
            }
        elif topic_name not in topic_nodes[topic_key]["aliases"]:
            topic_nodes[topic_key]["aliases"].append(topic_name)
            topic_nodes[topic_key]["name"] = best_display_name(
                topic_nodes[topic_key]["name"],
                topic_name,
            )

        current_topic = topic_nodes[topic_key]
        umbrella_to_topics[umbrella_name].add(current_topic["id"])

        if url:
            reel_id = f"reel_{extract_shortcode(url)}"
            if reel_id not in reel_nodes:
                reel_nodes[reel_id] = {
                    "id": reel_id,
                    "url": url,
                    "shortcode": extract_shortcode(url),
                    "topic_ids": [],
                    "umbrella_ids": [],
                    "items": [],
                }

            if current_topic["id"] not in reel_nodes[reel_id]["topic_ids"]:
                reel_nodes[reel_id]["topic_ids"].append(current_topic["id"])
            if umbrella_id not in reel_nodes[reel_id]["umbrella_ids"]:
                reel_nodes[reel_id]["umbrella_ids"].append(umbrella_id)

            topic_to_reels[current_topic["id"]].add(reel_id)

        item_key = (item_name.lower(), summary.lower())
        if item_name and item_key not in topic_item_keys[current_topic["id"]]:
            topic_item_keys[current_topic["id"]].add(item_key)
            item_payload = {
                "name": item_name,
                "summary": summary,
                "url": url,
                "contains_product": normalize(row.get("Contains Product")),
                "product_name": normalize(row.get("Product Name")),
                "product_brand": normalize(row.get("Product Brand")),
                "product_model": normalize(row.get("Product Model")),
                "product_type": normalize(row.get("Product Type")),
                "product_search_query": normalize(row.get("Product Search Query")),
                "best_buy_link": normalize(row.get("Best Buy Link")),
                "amazon_link": normalize(row.get("Amazon Link")),
                "flipkart_link": normalize(row.get("Flipkart Link")),
                "nykaa_link": normalize(row.get("Nykaa Link")),
                "media_status": normalize(row.get("Media Status")),
                "local_video_path": normalize(row.get("Local Video Path")),
                "local_video_url": normalize(row.get("Local Video URL")),
                "thumbnail_path": normalize(row.get("Thumbnail Path")),
                "thumbnail_url": normalize(row.get("Thumbnail URL")),
            }
            topic_to_items[current_topic["id"]].append(item_payload)
            current_topic["sample_items"].append(item_payload)
            if url:
                reel_nodes[reel_id]["items"].append(item_payload)

    for (umbrella_name, _topic_name), node in topic_nodes.items():
        reel_ids = sorted(topic_to_reels[node["id"]])
        items = topic_to_items[node["id"]]
        node["stats"]["unique_reel_count"] = len(reel_ids)
        node["stats"]["item_count"] = len(items)
        node["sample_items"] = node["sample_items"][:8]
        node["sample_reels"] = reel_ids[:8]

    interest_profile = {
        "user_id": config.user_id,
        "recommended_depth_by_umbrella": {},
        "interest_scores": {
            "umbrella": {},
            "topic": {},
        },
    }

    for umbrella_name, umbrella in umbrella_nodes.items():
        child_topic_ids = sorted(umbrella_to_topics[umbrella_name])
        unique_reels = set()
        unique_items = 0

        for node in topic_nodes.values():
            if node["parent_id"] != umbrella["id"]:
                continue
            unique_reels.update(topic_to_reels[node["id"]])
            unique_items += node["stats"]["item_count"]
            interest_profile["interest_scores"]["topic"][node["id"]] = {
                "name": node["name"],
                "score": build_interest_score(
                    node["stats"]["unique_reel_count"],
                    1,
                    node["stats"]["item_count"],
                ),
                "unique_reel_count": node["stats"]["unique_reel_count"],
                "item_count": node["stats"]["item_count"],
            }

        umbrella["stats"]["unique_reel_count"] = len(unique_reels)
        umbrella["stats"]["topic_count"] = len(child_topic_ids)
        umbrella["stats"]["item_count"] = unique_items

        interest_profile["interest_scores"]["umbrella"][umbrella["id"]] = {
            "name": umbrella_name,
            "score": build_interest_score(len(unique_reels), len(child_topic_ids), unique_items),
            "unique_reel_count": len(unique_reels),
            "topic_count": len(child_topic_ids),
            "item_count": unique_items,
        }
        interest_profile["recommended_depth_by_umbrella"][umbrella["id"]] = recommend_depth(
            len(unique_reels),
            len(child_topic_ids),
        )

    graph = {
        "version": 1,
        "generated_on": str(date.today()),
        "source": {
            "name": config.source_name,
            "row_count": len(rows),
        },
        "user_profile": interest_profile,
        "topics": sorted(
            list(umbrella_nodes.values()) + list(topic_nodes.values()),
            key=lambda node: (node["kind"], node["name"].lower()),
        ),
        "reels": sorted(reel_nodes.values(), key=lambda reel: reel["shortcode"]),
    }

    return graph


def write_topic_graph(output_path, graph):
    Path(output_path).write_text(json.dumps(graph, indent=2), encoding="utf-8")


def summarize_graph(graph):
    topics = graph["topics"]
    umbrella_count = sum(1 for node in topics if node["kind"] == "umbrella")
    topic_count = sum(1 for node in topics if node["kind"] == "topic")
    return {
        "umbrella_count": umbrella_count,
        "topic_count": topic_count,
        "reel_count": len(graph["reels"]),
    }
