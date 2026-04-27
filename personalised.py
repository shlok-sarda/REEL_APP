import argparse
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

from api_config import get_openai_client


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_GRAPH = BASE_DIR / "topic_graph.json"
DEFAULT_OUTPUT = BASE_DIR / "personalized_view.json"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_MIN_TOPIC_REELS = 3

STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "for", "from", "how", "in",
    "into", "is", "it", "its", "of", "on", "or", "the", "this", "to", "with",
    "your", "you", "than", "then", "all", "more", "only", "very", "use", "using",
    "tips", "idea", "ideas", "tools", "tool", "gadget", "gadgets", "tech",
    "recipe", "recipes", "product", "products", "device", "devices", "video", "videos",
}


def normalize(value):
    return " ".join((value or "").strip().split())


def normalize_key(value):
    return normalize(value).lower()


def tokenize(text):
    return [
        token.lower()
        for token in re.findall(r"[a-zA-Z0-9]+", normalize(text))
        if token and token.lower() not in STOPWORDS and len(token) > 2
    ]


def build_lookup(graph):
    topic_by_id = {}
    umbrellas = []
    topics_by_parent = defaultdict(list)

    for node in graph["topics"]:
        topic_by_id[node["id"]] = node
        if node["kind"] == "umbrella":
            umbrellas.append(node)
        elif node["kind"] == "topic":
            topics_by_parent[node["parent_id"]].append(node)

    return umbrellas, topics_by_parent


def topic_keywords(topic):
    counts = Counter(tokenize(topic["name"]))
    for item in topic.get("sample_items", []):
        counts.update(tokenize(item.get("name", "")))
        counts.update(tokenize(item.get("summary", "")))
    return counts


def topic_similarity(topic_a, topic_b):
    tokens_a = set(topic_keywords(topic_a))
    tokens_b = set(topic_keywords(topic_b))
    if not tokens_a or not tokens_b:
        return 0.0
    jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)

    words_a = set(tokenize(topic_a["name"]))
    words_b = set(tokenize(topic_b["name"]))
    word_overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
    return round(jaccard * 0.7 + word_overlap * 0.3, 4)


def group_topics_heuristically(umbrella, topics):
    if len(topics) <= 3:
        return [{"name": umbrella["name"], "topic_ids": [topic["id"] for topic in topics], "reason": "small umbrella"}]

    ordered = sorted(
        topics,
        key=lambda topic: (
            -topic["stats"]["unique_reel_count"],
            -topic["stats"]["item_count"],
            topic["name"].lower(),
        ),
    )

    groups = []
    assigned = set()

    for topic in ordered:
        if topic["id"] in assigned:
            continue

        current_group = [topic]
        assigned.add(topic["id"])

        for other in ordered:
            if other["id"] in assigned:
                continue
            similarity = topic_similarity(topic, other)
            if similarity >= 0.38:
                current_group.append(other)
                assigned.add(other["id"])

        group_name = best_group_name(current_group, umbrella["name"])
        groups.append(
            {
                "name": group_name,
                "topic_ids": [member["id"] for member in current_group],
                "reason": "heuristic_keyword_overlap",
            }
        )

    return groups


def topic_should_stand_alone(topic, min_topic_reels):
    return topic["stats"]["unique_reel_count"] >= min_topic_reels


def combine_topics_into_group(name, topics, reason):
    return {
        "name": name,
        "topic_ids": [topic["id"] for topic in topics],
        "reason": reason,
    }


def build_interest_driven_groups(
    umbrella,
    topics,
    use_ai=False,
    model=DEFAULT_MODEL,
    min_topic_reels=DEFAULT_MIN_TOPIC_REELS,
):
    if not topics:
        return []

    umbrella_reels = umbrella["stats"]["unique_reel_count"]
    umbrella_topics = umbrella["stats"]["topic_count"]

    if umbrella_reels < 8 and umbrella_topics < 4:
        return [combine_topics_into_group(umbrella["name"], topics, "low_interest_collapsed")]

    standalone_topics = []
    small_topics = []
    for topic in topics:
        if topic_should_stand_alone(topic, min_topic_reels):
            standalone_topics.append(topic)
        else:
            small_topics.append(topic)

    groups = []
    for topic in standalone_topics:
        groups.append(combine_topics_into_group(topic["name"], [topic], "standalone_topic"))

    if small_topics:
        if standalone_topics:
            if use_ai and len(small_topics) >= 5:
                grouped_small = group_topics_with_ai(umbrella, small_topics, model)
                used_ids = set()
                leftovers = []
                for group in grouped_small:
                    group_topics = [topic for topic in small_topics if topic["id"] in group["topic_ids"]]
                    if not group_topics:
                        continue
                    total_reels = sum(topic["stats"]["unique_reel_count"] for topic in group_topics)
                    if len(group_topics) == 1 and total_reels < min_topic_reels:
                        leftovers.extend(group_topics)
                        continue
                    used_ids.update(topic["id"] for topic in group_topics)
                    groups.append(
                        combine_topics_into_group(
                            group.get("name") or f"More in {umbrella['name']}",
                            group_topics,
                            group.get("reason", "clustered_small_topics"),
                        )
                    )
                leftovers.extend(topic for topic in small_topics if topic["id"] not in used_ids)
                if leftovers:
                    groups.append(combine_topics_into_group(f"More in {umbrella['name']}", leftovers, "leftover_topics"))
            else:
                groups.append(combine_topics_into_group(f"More in {umbrella['name']}", small_topics, "leftover_topics"))
        else:
            # Dense umbrella, but no single repeated sub-interest yet.
            if use_ai and len(small_topics) >= 6:
                grouped_small = group_topics_with_ai(umbrella, small_topics, model)
                used_ids = set()
                leftovers = []
                for group in grouped_small:
                    group_topics = [topic for topic in small_topics if topic["id"] in group["topic_ids"]]
                    if not group_topics:
                        continue
                    total_reels = sum(topic["stats"]["unique_reel_count"] for topic in group_topics)
                    if len(group_topics) == 1 and total_reels < min_topic_reels:
                        leftovers.extend(group_topics)
                        continue
                    used_ids.update(topic["id"] for topic in group_topics)
                    groups.append(
                        combine_topics_into_group(
                            group.get("name") or umbrella["name"],
                            group_topics,
                            group.get("reason", "clustered_topics"),
                        )
                    )
                leftovers.extend(topic for topic in small_topics if topic["id"] not in used_ids)
                if leftovers:
                    groups.append(combine_topics_into_group(f"More in {umbrella['name']}", leftovers, "merged_low_signal_topics"))
            else:
                groups.append(combine_topics_into_group(umbrella["name"], small_topics, "dense_but_not_yet_personalized"))

    if not groups:
        groups = [combine_topics_into_group(umbrella["name"], topics, "fallback_group")]

    # Keep display stable: strongest repeated interests first.
    groups.sort(
        key=lambda group: (
            -sum(topic["stats"]["unique_reel_count"] for topic in topics if topic["id"] in group["topic_ids"]),
            -sum(topic["stats"]["item_count"] for topic in topics if topic["id"] in group["topic_ids"]),
            group["name"].lower(),
        )
    )
    return groups


def best_group_name(topics, umbrella_name):
    if len(topics) == 1:
        return topics[0]["name"]

    counts = Counter()
    for topic in topics:
        counts.update(tokenize(topic["name"]))
        for item in topic.get("sample_items", []):
            counts.update(tokenize(item.get("name", "")))

    common = [token for token, _count in counts.most_common(2)]
    if common:
        return " ".join(word.capitalize() for word in common)
    return umbrella_name


def build_ai_prompt(umbrella, topics):
    topic_block = []
    for topic in topics:
        item_preview = "; ".join(
            f"{item['name']} ({item['summary']})" if item.get("summary") else item["name"]
            for item in topic.get("sample_items", [])[:4]
        ) or "No sample items"
        topic_block.append(
            f"- topic_id: {topic['id']}\n"
            f"  topic_name: {topic['name']}\n"
            f"  reel_count: {topic['stats']['unique_reel_count']}\n"
            f"  item_count: {topic['stats']['item_count']}\n"
            f"  sample_items: {item_preview}"
        )

    return f"""
You are creating a personalized browsing structure inside one saved-reels umbrella folder.

Umbrella:
- name: {umbrella['name']}
- reel_count: {umbrella['stats']['unique_reel_count']}
- topic_count: {umbrella['stats']['topic_count']}

Goal:
- Group the topics below into a cleaner personalized browsing structure.
- This is NOT a broad umbrella merge.
- This is a display-layer grouping for a user who saves many reels in this area.
- Create new visible lists only when there is a real recurring sub-interest.
- Do NOT create lots of tiny one-topic groups just because the wording is different.
- Prefer a few strong browseable groups over many weak micro-groups.
- If a topic appears only once and does not pair naturally with a recurring theme, leave it inside a broad "more" style group.
- Keep groups human-readable and practical to browse.
- Use fewer groups than raw topics when helpful.
- If a topic is already distinct enough and recurring, it can remain its own group.

Topics:
{chr(10).join(topic_block)}

Return ONLY valid minified JSON:
{{
  "display_groups": [
    {{
      "name": "group name",
      "topic_ids": ["topic_id_1", "topic_id_2"]
    }}
  ]
}}
""".strip()


def group_topics_with_ai(umbrella, topics, model):
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": build_ai_prompt(umbrella, topics)}],
    )
    data = json.loads(response.choices[0].message.content)
    display_groups = data.get("display_groups")
    if not isinstance(display_groups, list):
        raise ValueError(f"Invalid AI personalization response for umbrella {umbrella['name']}")
    return display_groups


def compute_personalization_mode(umbrella):
    reels = umbrella["stats"]["unique_reel_count"]
    topics = umbrella["stats"]["topic_count"]
    score = reels * 1.6 + topics * 1.1

    if reels >= 14 or topics >= 8 or score >= 30:
        return "expanded"
    if reels >= 6 or topics >= 4 or score >= 14:
        return "show_topics"
    return "collapsed"


def build_personalized_view(
    graph,
    use_ai=False,
    model=DEFAULT_MODEL,
    min_topic_reels=DEFAULT_MIN_TOPIC_REELS,
):
    umbrellas, topics_by_parent = build_lookup(graph)
    interest_profile = graph.get("user_profile", {})
    result = {
        "version": 1,
        "generated_from": graph.get("source", {}),
        "user_id": interest_profile.get("user_id", "default_user"),
        "sections": [],
    }

    for umbrella in sorted(umbrellas, key=lambda node: node["name"].lower()):
        topics = sorted(
            topics_by_parent.get(umbrella["id"], []),
            key=lambda topic: (
                -topic["stats"]["unique_reel_count"],
                -topic["stats"]["item_count"],
                topic["name"].lower(),
            ),
        )
        mode = compute_personalization_mode(umbrella)

        display_groups = build_interest_driven_groups(
            umbrella,
            topics,
            use_ai=use_ai and mode == "expanded",
            model=model,
            min_topic_reels=min_topic_reels,
        )

        topic_lookup = {topic["id"]: topic for topic in topics}
        hydrated_groups = []
        for group in display_groups:
            topic_ids = [topic_id for topic_id in group["topic_ids"] if topic_id in topic_lookup]
            group_topics = [topic_lookup[topic_id] for topic_id in topic_ids]
            if not group_topics:
                continue

            reels = sum(topic["stats"]["unique_reel_count"] for topic in group_topics)
            items = sum(topic["stats"]["item_count"] for topic in group_topics)
            hydrated_groups.append(
                {
                    "name": group["name"],
                    "reason": group.get("reason", "ai_grouping" if use_ai else "heuristic_grouping"),
                    "stats": {
                        "unique_reel_count": reels,
                        "item_count": items,
                        "topic_count": len(group_topics),
                    },
                    "topics": [
                        {
                            "id": topic["id"],
                            "name": topic["name"],
                            "stats": topic["stats"],
                            "sample_items": topic.get("sample_items", [])[:5],
                        }
                        for topic in group_topics
                    ],
                }
            )

        if hydrated_groups:
            section = {
                "umbrella_id": umbrella["id"],
                "umbrella_name": umbrella["name"],
                "personalization_mode": mode,
                "recommended_depth": interest_profile.get("recommended_depth_by_umbrella", {}).get(umbrella["id"], "umbrella_only"),
                "stats": {
                    "unique_reel_count": sum(group["stats"]["unique_reel_count"] for group in hydrated_groups),
                    "item_count": sum(group["stats"]["item_count"] for group in hydrated_groups),
                    "topic_count": sum(group["stats"]["topic_count"] for group in hydrated_groups),
                },
                "display_groups": hydrated_groups,
            }
            result["sections"].append(section)

    result["sections"] = sorted(result["sections"], key=lambda section: section["umbrella_name"].lower())
    return result


def summarize(view):
    section_count = len(view["sections"])
    group_count = sum(len(section["display_groups"]) for section in view["sections"])
    return {
        "section_count": section_count,
        "group_count": group_count,
        "expanded_sections": sum(1 for section in view["sections"] if section["personalization_mode"] == "expanded"),
    }


def main():
    parser = argparse.ArgumentParser(description="Create a personalized display structure from the topic graph.")
    parser.add_argument("--graph", default=str(DEFAULT_GRAPH), help="Topic graph JSON input.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output personalized JSON file.")
    parser.add_argument("--use-ai", action="store_true", help="Use AI to create display groups for dense umbrellas.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model to use with --use-ai.")
    parser.add_argument(
        "--min-topic-reels",
        type=int,
        default=DEFAULT_MIN_TOPIC_REELS,
        help="Minimum reel count before a repeated subtopic deserves its own personalized list.",
    )
    args = parser.parse_args()

    graph = json.loads(Path(args.graph).read_text())
    view = build_personalized_view(
        graph,
        use_ai=args.use_ai,
        model=args.model,
        min_topic_reels=args.min_topic_reels,
    )
    Path(args.output).write_text(json.dumps(view, indent=2), encoding="utf-8")

    summary = summarize(view)
    print(f"Saved personalized view: {args.output}")
    print(f"Sections: {summary['section_count']}")
    print(f"Display groups: {summary['group_count']}")
    print(f"Expanded sections: {summary['expanded_sections']}")


if __name__ == "__main__":
    main()
