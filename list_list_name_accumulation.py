import argparse
import csv
import json
from collections import OrderedDict, defaultdict
from pathlib import Path

from api_config import get_openai_client


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_CSV = BASE_DIR / "final_output_TECH.csv"
DEFAULT_FOLDER_ITEMS_CSV = BASE_DIR / "list_titles_with_items.csv"
DEFAULT_MAPPING_CSV = BASE_DIR / "list_title_accumulation.csv"
DEFAULT_ENRICHED_CSV = BASE_DIR / "final_output_TECH_accumulated.csv"
DEFAULT_MODEL = "gpt-4.1-mini"
DEFAULT_GRANULARITY = 0.25


def normalize(value):
    return " ".join((value or "").strip().split()).lower()


def load_rows(input_csv):
    with open(input_csv, newline="", encoding="utf-8") as infile:
        return list(csv.DictReader(infile))


def collect_folder_items(rows):
    folders = OrderedDict()

    for row in rows:
        folder = " ".join((row.get("Folder") or "").strip().split())
        if not folder or folder.upper() in {"ERROR", "FAILED"}:
            continue

        key = normalize(folder)
        if key not in folders:
            folders[key] = {
                "folder": folder,
                "items": [],
            }

        item_name = " ".join((row.get("Item Name") or "").strip().split())
        summary = " ".join((row.get("Summary") or "").strip().split())

        if item_name:
            folders[key]["items"].append(
                {
                    "name": item_name,
                    "summary": summary,
                }
            )

    return folders


def build_prompt(folder_names, granularity):
    folder_list = "\n".join(f"- {name}" for name in folder_names)
    specificity_guide = (
        "Very broad and umbrella-like. Prefer a small number of wide buckets."
        if granularity <= 0.2 else
        "Broad but still meaningful. Combine clearly related folder titles into fewer simple umbrella names."
        if granularity <= 0.4 else
        "Balanced specificity. Merge noisy folder variations, but keep clearly different themes separate."
        if granularity <= 0.6 else
        "Fairly specific. Reduce noise, but do not merge themes unless they are obviously related."
        if granularity <= 0.8 else
        "Very specific. Only merge near-duplicates or very closely related folder titles."
    )

    return f"""
You are reducing noise in a set of saved-folder titles.

Your task:
- Read the folder titles below.
- Merge related folder titles into broader umbrella folders.
- The goal is to reduce unnecessary fragmentation in folder names.
- Different subtypes that naturally belong in one broader group should share one umbrella folder.
- Reuse the same umbrella label whenever folders are clearly part of the same bigger theme.

Naming rules:
- Use short, human-readable umbrella names.
- Use wording that feels natural to a normal person organizing saved content.
- Avoid stiff, academic, or overly technical category names unless the folders clearly require that language.
- Prefer a broad folder that a person would realistically browse later.
- Do not simply repeat the original folder title unless it really should stay separate.

Granularity setting: {granularity:.2f}
Granularity meaning: {specificity_guide}

Important:
- Lower granularity means fewer, broader umbrella folders.
- Higher granularity means more specific umbrella folders.
- The main goal is to eliminate folder-name noise while preserving useful structure.

Folder titles:
{folder_list}

Return ONLY valid minified JSON in this exact format:
{{
  "mappings": [
    {{
      "folder": "original folder title",
      "umbrella_folder": "broader umbrella folder"
    }}
  ]
}}
""".strip()


def request_mapping(folder_names, model, granularity):
    client = get_openai_client()
    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": build_prompt(folder_names, granularity)}],
    )

    content = response.choices[0].message.content
    data = json.loads(content)

    if "mappings" not in data or not isinstance(data["mappings"], list):
        raise ValueError("Model response did not include a valid mappings list.")

    return data["mappings"]


def build_lookup(mappings):
    lookup = {}

    for item in mappings:
        folder = " ".join((item.get("folder") or "").strip().split())
        umbrella = " ".join((item.get("umbrella_folder") or "").strip().split())

        if folder and umbrella:
            lookup[normalize(folder)] = umbrella

    return lookup


def fallback_umbrella_name(folder, granularity):
    words = [word for word in folder.split() if word]
    if not words:
        return "Miscellaneous"
    if granularity <= 0.4 and len(words) > 2:
        return " ".join(words[:2])
    return folder


def write_folder_items_csv(output_csv, folder_data):
    with open(output_csv, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["Folder", "Item Count", "Items"])

        for data in folder_data.values():
            item_names = [item["name"] for item in data["items"]]
            writer.writerow([data["folder"], len(item_names), " | ".join(item_names)])


def write_mapping_csv(output_csv, folder_data, lookup):
    with open(output_csv, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(["Folder", "Umbrella Folder"])

        for key, data in folder_data.items():
            writer.writerow([data["folder"], lookup.get(key, "")])


def write_enriched_csv(output_csv, rows, lookup):
    if rows:
        existing = list(rows[0].keys())
        preferred = ["Primary Category", "Secondary Category", "Umbrella Folder"]
        fieldnames = preferred + [key for key in existing if key not in preferred]
    else:
        fieldnames = ["Primary Category", "Secondary Category", "Umbrella Folder"]

    with open(output_csv, "w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            folder = " ".join((row.get("Folder") or "").strip().split())
            umbrella = lookup.get(normalize(folder), "")
            primary = umbrella or " ".join((row.get("Primary Category") or "").strip().split())
            secondary = " ".join((row.get("Secondary Category") or "").strip().split()) or folder
            enriched_row = {
                "Primary Category": primary,
                "Secondary Category": secondary,
                "Umbrella Folder": umbrella,
            }
            enriched_row.update(row)
            enriched_row["Primary Category"] = primary
            enriched_row["Secondary Category"] = secondary
            enriched_row["Umbrella Folder"] = umbrella
            writer.writerow(enriched_row)


def summarize_reduction(folder_data, lookup):
    original_count = len(folder_data)
    umbrella_count = len({value for value in lookup.values() if value})
    eliminated = original_count - umbrella_count
    return original_count, umbrella_count, eliminated


def main():
    parser = argparse.ArgumentParser(description="Accumulate list titles into broader umbrella folders.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT_CSV), help="CSV containing Folder, Item Name, and Summary columns.")
    parser.add_argument("--folder-items-output", default=str(DEFAULT_FOLDER_ITEMS_CSV), help="CSV showing each folder and its items.")
    parser.add_argument("--mapping-output", default=str(DEFAULT_MAPPING_CSV), help="CSV mapping each folder title to its umbrella folder.")
    parser.add_argument("--enriched-output", default=str(DEFAULT_ENRICHED_CSV), help="CSV with umbrella folder added to each original row.")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="OpenAI model to use.")
    parser.add_argument(
        "--granularity",
        type=float,
        default=DEFAULT_GRANULARITY,
        help="0 = broad umbrella folders, 1 = very specific umbrella folders.",
    )
    args = parser.parse_args()

    if not 0 <= args.granularity <= 1:
        raise ValueError("--granularity must be between 0 and 1.")

    rows = load_rows(args.input)
    folder_data = collect_folder_items(rows)

    if not folder_data:
        raise ValueError("No valid folder titles found in the input CSV.")

    write_folder_items_csv(args.folder_items_output, folder_data)

    mappings = request_mapping(
        [data["folder"] for data in folder_data.values()],
        args.model,
        args.granularity,
    )
    lookup = build_lookup(mappings)

    missing = [data["folder"] for key, data in folder_data.items() if key not in lookup]
    if missing:
        print(f"Warning: missing umbrella folders for {len(missing)} titles. Using fallback labels.")
        for key, data in folder_data.items():
            if key not in lookup:
                lookup[key] = fallback_umbrella_name(data["folder"], args.granularity)

    write_mapping_csv(args.mapping_output, folder_data, lookup)
    write_enriched_csv(args.enriched_output, rows, lookup)

    original_count, umbrella_count, eliminated = summarize_reduction(folder_data, lookup)

    print(f"Saved folder-items CSV: {args.folder_items_output}")
    print(f"Saved mapping CSV: {args.mapping_output}")
    print(f"Saved enriched CSV: {args.enriched_output}")
    print(f"Original folder count: {original_count}")
    print(f"Umbrella folder count: {umbrella_count}")
    print(f"Folders eliminated: {eliminated}")
    print(f"Granularity used: {args.granularity:.2f}")


if __name__ == "__main__":
    main()
