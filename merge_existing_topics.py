import argparse
import csv
import json
import re
from collections import OrderedDict, defaultdict
from pathlib import Path

from api_config import get_openai_client


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "final_output_TECH_accumulated.csv"
DEFAULT_RAW_OUTPUT = BASE_DIR / "final_output_TECH.csv"
DEFAULT_MAPPING_OUTPUT = BASE_DIR / "topic_merge_mapping.csv"
DEFAULT_MODEL = "gpt-4.1-mini"

SEMANTIC_OVERRIDE_GROUPS = {
    "tech & gadgets": {
        "car gadgets": "Car Gadgets",
        "car gadget": "Car Gadgets",
        "car tech devices": "Car Gadgets",
        "car tech device": "Car Gadgets",
        "tech gadgets": "Tech Gadgets",
        "charging gadgets": "Charging Gadgets",
        "multiport charging gadgets": "Charging Gadgets",
    },
    "sports & fitness": {
        "swimming technique": "Swimming Technique",
        "swimming techniques": "Swimming Technique",
    },
}


def normalize(value):
    return " ".join((value or "").strip().split())


def normalize_key(value):
    return normalize(value).lower()


def singularize_word(word):
    lower = word.lower()
    if len(word) <= 3:
        return lower
    if lower.endswith("ies") and len(word) > 4:
        return lower[:-3] + "y"
    if lower.endswith("ses"):
        return lower[:-2]
    if lower.endswith("s") and not lower.endswith("ss"):
        return lower[:-1]
    return lower


def topic_signature(title):
    tokens = re.findall(r"[a-zA-Z0-9]+", normalize_key(title))
    return " ".join(singularize_word(token) for token in tokens)


def best_display_title(titles):
    def score(title):
        normalized = normalize(title)
        title_case_words = sum(1 for word in normalized.split() if word[:1].isupper())
        return (
            title_case_words,
            -sum(1 for char in normalized if char.islower()),
            len(normalized),
        )

    return max(titles, key=score)


def load_rows(input_csv):
    with open(input_csv, newline="", encoding="utf-8") as infile:
        return list(csv.DictReader(infile))


def collect_topics(rows):
    grouped = defaultdict(OrderedDict)

    for row in rows:
        umbrella = normalize(row.get("Umbrella Folder") or row.get("Umbrella Category") or "All Folders")
        folder = normalize(row.get("Folder"))
        item_name = normalize(row.get("Item Name"))
        summary = normalize(row.get("Summary"))

        if not folder or folder.upper() in {"ERROR", "FAILED"}:
            continue

        if folder not in grouped[umbrella]:
            grouped[umbrella][folder] = {
                "folder": folder,
                "items": [],
            }

        if item_name:
            grouped[umbrella][folder]["items"].append({"name": item_name, "summary": summary})

    return grouped


def auto_merge_topics(topics):
    merged = OrderedDict()
    alias_to_seed = {}

    for folder_name, payload in topics.items():
        signature = topic_signature(folder_name)
        if signature not in merged:
            merged[signature] = {
                "seed_title": folder_name,
                "aliases": [],
                "items": [],
            }

        merged[signature]["aliases"].append(folder_name)
        merged[signature]["items"].extend(payload["items"])
        alias_to_seed[folder_name] = signature

    for signature, payload in merged.items():
        payload["seed_title"] = best_display_title(payload["aliases"])

    return merged, alias_to_seed


def apply_semantic_overrides(umbrella_name, alias_to_seed, merged_topics):
    overrides = SEMANTIC_OVERRIDE_GROUPS.get(normalize_key(umbrella_name), {})
    if not overrides:
        return {}, []

    seed_to_canonical = {}
    forced_seeds = []

    for alias, seed_signature in alias_to_seed.items():
        alias_key = normalize_key(alias)
        if alias_key not in overrides:
            continue

        seed_title = merged_topics[seed_signature]["seed_title"]
        seed_to_canonical[seed_title] = overrides[alias_key]
        forced_seeds.append(seed_title)

    return seed_to_canonical, forced_seeds


def build_prompt(umbrella_name, merged_topics):
    blocks = []
    for payload in merged_topics.values():
        sample_items = payload["items"][:5]
        item_preview = "; ".join(
            f"{item['name']} ({item['summary']})" if item["summary"] else item["name"]
            for item in sample_items
        ) or "No items"
        blocks.append(
            f"- topic: {payload['seed_title']}\n"
            f"  aliases: {', '.join(payload['aliases'])}\n"
            f"  sample_items: {item_preview}"
        )

    topic_block = "\n".join(blocks)
    return f"""
You are cleaning up existing topic titles inside one umbrella folder.

Umbrella folder:
{umbrella_name}

Goal:
- Merge titles that clearly belong to the same browsing intent.
- Remove obvious noise such as casing differences, singular/plural drift, and near-duplicate wording.
- Also merge titles when the sample items clearly show they are really one subcategory.
- Also merge titles when they are different phrasings of the same core thing a user would browse together later.
- Keep distinct subcategories separate even if they belong to the same umbrella.
- Prefer fewer, cleaner topic titles when the difference is weak or unnecessary.

Important:
- Reduce unnecessary fragmentation.
- Do NOT keep separate micro-folders when one broader title would work better for browsing.
- If a user would realistically browse them as one list title, merge them.
- If two topics are basically the same shopping/discovery bucket with slightly different wording, merge them.
- If the sample items overlap heavily or point to the same core object, merge them.
- If one topic is just a narrower phrasing of another topic with the same user intent, merge them.
- If a user would expect separate folders, keep them separate.
- Canonical topic titles must be short, human-readable, and natural.

Topics:
{topic_block}

Return ONLY valid minified JSON in this format:
{{
  "mappings": [
    {{
      "topic": "seed topic title",
      "canonical_topic": "final merged topic title"
    }}
  ]
}}
""".strip()


def request_merge_mapping(umbrella_name, merged_topics, model):
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": build_prompt(umbrella_name, merged_topics)}],
    )
    data = json.loads(response.choices[0].message.content)
    mappings = data.get("mappings")
    if not isinstance(mappings, list):
        raise ValueError(f"Invalid merge response for umbrella {umbrella_name}")
    return mappings


def build_final_lookup(grouped_topics, model):
    final_lookup = {}
    records = []

    for umbrella_name, topics in grouped_topics.items():
        merged_topics, alias_to_seed = auto_merge_topics(topics)
        override_seed_map, forced_seeds = apply_semantic_overrides(
            umbrella_name,
            alias_to_seed,
            merged_topics,
        )

        if len(merged_topics) == 1:
            only_payload = next(iter(merged_topics.values()))
            for alias in only_payload["aliases"]:
                final_lookup[(umbrella_name, alias)] = only_payload["seed_title"]
                records.append((umbrella_name, alias, only_payload["seed_title"]))
            continue

        ai_mappings = request_merge_mapping(umbrella_name, merged_topics, model)
        seed_to_canonical = dict(override_seed_map)
        for row in ai_mappings:
            topic = normalize(row.get("topic"))
            canonical = normalize(row.get("canonical_topic"))
            if topic and canonical:
                if topic in seed_to_canonical:
                    continue
                seed_to_canonical[topic] = canonical

        missing = [
            payload["seed_title"]
            for payload in merged_topics.values()
            if payload["seed_title"] not in seed_to_canonical
        ]
        if missing:
            raise ValueError(f"Missing canonical topic for umbrella {umbrella_name}: {missing}")

        for alias, seed_signature in alias_to_seed.items():
            seed_title = merged_topics[seed_signature]["seed_title"]
            canonical = seed_to_canonical[seed_title]
            final_lookup[(umbrella_name, alias)] = canonical
            records.append((umbrella_name, alias, canonical))

    return final_lookup, records


def write_mapping_csv(output_path, records):
    with open(output_path, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["Umbrella Folder", "Old Topic", "Canonical Topic"])
        for umbrella_name, old_topic, canonical_topic in sorted(records):
            writer.writerow([umbrella_name, old_topic, canonical_topic])


def write_cleaned_raw_csv(output_path, rows, final_lookup):
    fieldnames = list(rows[0].keys()) if rows else ["URL", "Primary Category", "Secondary Category", "Folder", "Item Name", "Summary"]
    cleaned_rows = []

    for row in rows:
        umbrella = normalize(row.get("Umbrella Folder") or row.get("Umbrella Category") or "All Folders")
        folder = normalize(row.get("Folder"))
        canonical = final_lookup.get((umbrella, folder), folder)
        primary = normalize(row.get("Primary Category")) or umbrella
        cleaned_row = dict(row)
        cleaned_row["URL"] = row.get("URL", "")
        cleaned_row["Primary Category"] = primary
        cleaned_row["Secondary Category"] = canonical
        cleaned_row["Folder"] = canonical
        cleaned_rows.append(cleaned_row)

    with open(output_path, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    return cleaned_rows


def summarize_changes(records):
    old_topics = {(umbrella, old) for umbrella, old, _ in records}
    new_topics = {(umbrella, canonical) for umbrella, _, canonical in records}
    return len(old_topics), len(new_topics), len(old_topics) - len(new_topics)


def main():
    parser = argparse.ArgumentParser(
        description="Merge duplicate or near-duplicate existing topic titles."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Accumulated CSV input.")
    parser.add_argument("--raw-output", default=str(DEFAULT_RAW_OUTPUT), help="Cleaned raw CSV output.")
    parser.add_argument("--mapping-output", default=str(DEFAULT_MAPPING_OUTPUT), help="Mapping CSV output.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model to use.")
    args = parser.parse_args()

    rows = load_rows(args.input)
    grouped_topics = collect_topics(rows)
    final_lookup, records = build_final_lookup(grouped_topics, args.model)
    old_count, new_count, reduced_by = summarize_changes(records)
    write_mapping_csv(args.mapping_output, records)
    write_cleaned_raw_csv(args.raw_output, rows, final_lookup)

    print(f"Saved topic merge mapping: {args.mapping_output}")
    print(f"Saved cleaned raw CSV: {args.raw_output}")
    print(f"Topics before merge: {old_count}")
    print(f"Topics after merge: {new_count}")
    print(f"Topics reduced by: {reduced_by}")


if __name__ == "__main__":
    main()
