from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from api_config import get_openai_client
from data_preprocessing import download_reel, is_app_media, process_reel
from finale import (
    extract_product_data,
    extract_visual_data,
    format_hashtags,
    load_json_content,
    match_product_to_item,
    normalize_label,
    summarize_error,
)
from pipeline_b_prompts import BRANCH_PROMPTS, JUDGE_PROMPT, ROUTER_PROMPT


client = get_openai_client()
BASE_DIR = Path(__file__).resolve().parent
MODEL = "gpt-4.1"

DEEP_SEARCH_DIAGNOSTIC_COLUMNS = [
    ("Creator", "creator"),
    ("Caption", "caption"),
    ("Hashtags", "hashtags"),
    ("Transcript", "transcript"),
    ("Main Subject", "main_subject"),
    ("Main Subject Type", "main_subject_type"),
    ("Inferred Main Theme", "inferred_main_theme"),
    ("Relevant Visible Text", "relevant_visible_text"),
    ("Relevant Visual Entities", "relevant_visual_entities"),
    ("Visual Supporting Points", "visual_supporting_points"),
    ("Overall Visual Summary", "overall_visual_summary"),
]


def encode_csv_value(value) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def deep_search_diagnostic_values(output: dict) -> list[str]:
    diagnostics = output.get("diagnostics", {})
    return [encode_csv_value(diagnostics.get(key, "")) for _, key in DEEP_SEARCH_DIAGNOSTIC_COLUMNS]


def fill_template(template: str, result: dict, visual_data: dict) -> str:
    replacements = {
        "{caption}": result.get("caption", ""),
        "{transcript}": result.get("transcript", ""),
        "{hashtags}": format_hashtags(result.get("hashtags", "")),
        "{creator}": result.get("creator", ""),
        "{theme}": visual_data.get("inferred_main_theme", ""),
        "{visible_text}": ", ".join(visual_data.get("relevant_visible_text", [])),
        "{visual_entities}": ", ".join(visual_data.get("relevant_visual_entities", [])),
        "{visual_insights}": ", ".join(visual_data.get("visual_supporting_points", [])),
    }
    for needle, value in replacements.items():
        template = template.replace(needle, value)
    return template


def call_json_prompt(prompt: str) -> dict:
    response = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        temperature=0,
        messages=[{"role": "user", "content": prompt}],
    )
    payload = load_json_content(response)
    if "error" in payload:
        raise ValueError(payload.get("raw", "Model returned invalid JSON"))
    return payload


def router_call(result: dict, visual_data: dict) -> dict:
    payload = call_json_prompt(fill_template(ROUTER_PROMPT, result, visual_data))
    top_1_branch = normalize_label(payload.get("top_1_branch"))
    top_2_branch = normalize_label(payload.get("top_2_branch"))
    if top_1_branch not in BRANCH_PROMPTS:
        raise ValueError(f"Unknown top_1_branch: {top_1_branch}")
    if top_2_branch not in BRANCH_PROMPTS:
        raise ValueError(f"Unknown top_2_branch: {top_2_branch}")
    if top_1_branch == top_2_branch:
        raise ValueError("Router returned duplicate branches")
    return {
        "top_1_branch": top_1_branch,
        "top_2_branch": top_2_branch,
        "reason_top_1": normalize_label(payload.get("reason_top_1")),
        "reason_top_2": normalize_label(payload.get("reason_top_2")),
    }


def branch_call(branch: str, result: dict, visual_data: dict) -> dict:
    template = BRANCH_PROMPTS.get(branch)
    if not template:
        raise ValueError(f"Unknown branch: {branch}")
    payload = call_json_prompt(fill_template(template, result, visual_data))
    primary = normalize_label(payload.get("primary_category"))
    secondary = normalize_label(payload.get("secondary_category")) or primary or branch
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []
    normalized_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        name = normalize_label(item.get("name"))
        summary = normalize_label(item.get("summary"))
        if not name and not summary:
            continue
        normalized_items.append({"name": name, "summary": summary})
    return {
        "primary_category": primary or branch,
        "secondary_category": secondary,
        "items": normalized_items,
    }


def build_judge_prompt(result: dict, visual_data: dict, branch_a: str, candidate_a: dict, branch_b: str, candidate_b: dict) -> str:
    template = JUDGE_PROMPT
    replacements = {
        "{caption}": result.get("caption", ""),
        "{transcript}": result.get("transcript", ""),
        "{hashtags}": format_hashtags(result.get("hashtags", "")),
        "{creator}": result.get("creator", ""),
        "{theme}": visual_data.get("inferred_main_theme", ""),
        "{visible_text}": ", ".join(visual_data.get("relevant_visible_text", [])),
        "{visual_entities}": ", ".join(visual_data.get("relevant_visual_entities", [])),
        "{visual_insights}": ", ".join(visual_data.get("visual_supporting_points", [])),
        "{branch_a}": branch_a,
        "{branch_b}": branch_b,
        "{candidate_a_json}": json.dumps(candidate_a, ensure_ascii=False, indent=2),
        "{candidate_b_json}": json.dumps(candidate_b, ensure_ascii=False, indent=2),
    }
    for needle, value in replacements.items():
        template = template.replace(needle, value)
    return template


def judge_call(result: dict, visual_data: dict, branch_a: str, candidate_a: dict, branch_b: str, candidate_b: dict) -> dict:
    payload = call_json_prompt(build_judge_prompt(result, visual_data, branch_a, candidate_a, branch_b, candidate_b))
    winner = normalize_label(payload.get("winner")).upper()
    winning_branch = normalize_label(payload.get("winning_branch"))
    if winner not in {"A", "B"}:
        winner = "A"
    if winner == "A" and winning_branch != branch_a:
        winning_branch = branch_a
    if winner == "B" and winning_branch != branch_b:
        winning_branch = branch_b
    return {
        "winner": winner,
        "winning_branch": winning_branch,
        "reason": normalize_label(payload.get("reason")),
    }


def finalize_output(branch: str, payload: dict) -> dict:
    primary = normalize_label(payload.get("primary_category")) or branch
    secondary = normalize_label(payload.get("secondary_category")) or primary
    items = payload.get("items", [])
    if not isinstance(items, list):
        items = []
    return {
        "primary_category": primary,
        "secondary_category": secondary,
        "list_title": primary,
        "folder": secondary,
        "items": items,
    }


def run_pipeline(url: str) -> dict:
    print("🚀 Processing reel with Pipeline B...")
    result = process_reel(url)

    visual_data = {}
    visual_status = "not_attempted"
    visual_error = ""
    try:
        video_path = result.get("video_path_for_visual") or ""
        if video_path:
            video_download_status = result.get("video_download_status") or "reused_existing"
        else:
            video_path, video_download_status = download_reel(url)
    except Exception as exc:
        print(f"⚠️ Video download skipped: {summarize_error(exc)}")
        video_path = ""
        video_download_status = "download_failed"
        visual_error = summarize_error(exc)

    if video_path:
        try:
            visual_data = extract_visual_data(result, video_path)
            visual_status = "success" if visual_data else "empty"
        except Exception as exc:
            print(f"⚠️ Visual extraction skipped: {summarize_error(exc)}")
            visual_status = "failed"
            visual_error = summarize_error(exc)
            video_path_path = Path(video_path)
            if video_path_path.exists() and not is_app_media(video_path):
                try:
                    video_path_path.unlink()
                except Exception:
                    pass
    else:
        visual_status = "download_missing"

    # Nothing was fetchable: no video, no caption, no transcript. Running the
    # router/branch/judge calls anyway makes the model invent a category for
    # empty air — the reel "completes" as a junk card. Raising here routes it
    # through process_csv's failure row (Folder=failed), which the app shows
    # as a clean "needs attention" state, and skips five pointless LLM calls.
    if not video_path and not str(result.get("caption") or "").strip() and not str(result.get("transcript") or "").strip():
        raise ValueError(
            "Reel unavailable: no video, caption, or transcript could be fetched (deleted, private, or invalid link)"
        )

    router = router_call(result, visual_data)
    branch_a = router["top_1_branch"]
    branch_b = router["top_2_branch"]
    candidate_a = branch_call(branch_a, result, visual_data)
    candidate_b = branch_call(branch_b, result, visual_data)
    judge = judge_call(result, visual_data, branch_a, candidate_a, branch_b, candidate_b)

    final_branch = branch_a if judge["winner"] == "A" else branch_b
    final_candidate = candidate_a if judge["winner"] == "A" else candidate_b
    final_output = finalize_output(final_branch, final_candidate)
    final_output["router_top_1"] = branch_a
    final_output["router_top_2"] = branch_b
    final_output["judge_winner"] = judge["winner"]
    final_output["judge_reason"] = judge["reason"]

    try:
        product_data = extract_product_data(result, visual_data, final_output)
        final_output["contains_products"] = product_data["contains_products"]
        final_output["products"] = product_data["products"]
    except Exception as exc:
        print(f"⚠️ Product extraction skipped: {summarize_error(exc)}")
        final_output["contains_products"] = False
        final_output["products"] = []

    final_output["diagnostics"] = {
        "caption_present": bool(result.get("caption_present")),
        "hashtags_present": bool(result.get("hashtags_present")),
        "creator_present": bool(result.get("creator_present")),
        "transcript_present": bool(result.get("transcript_present")),
        "transcript_status": result.get("transcript_status", ""),
        "transcript_model": result.get("transcript_model", ""),
        "transcript_attempts": result.get("transcript_attempts", 0),
        "transcript_error": result.get("transcript_error", ""),
        "audio_download_status": result.get("audio_download_status", ""),
        "video_download_status": video_download_status or result.get("video_download_status", ""),
        "visual_present": bool(visual_data),
        "visual_status": visual_status,
        "visual_error": visual_error,
        "processing_version": "pipeline_b_v2_observable",
        "creator": result.get("creator", ""),
        "caption": result.get("caption", ""),
        "hashtags": result.get("hashtags", ""),
        "transcript": result.get("transcript", ""),
        "main_subject": visual_data.get("main_subject", ""),
        "main_subject_type": visual_data.get("main_subject_type", ""),
        "inferred_main_theme": visual_data.get("inferred_main_theme", ""),
        "relevant_visible_text": visual_data.get("relevant_visible_text", []),
        "relevant_visual_entities": visual_data.get("relevant_visual_entities", []),
        "visual_supporting_points": visual_data.get("visual_supporting_points", []),
        "overall_visual_summary": visual_data.get("overall_visual_summary", ""),
    }

    return final_output


def process_csv(input_csv: str | Path, output_csv: str | Path) -> None:
    input_csv = Path(input_csv)
    output_csv = Path(output_csv)
    results: list[list[str]] = []

    with input_csv.open("r", encoding="utf-8") as infile:
        reader = csv.reader(infile)
        for row in reader:
            url = row[0].strip()
            if not url:
                continue
            print(f"\n🔄 Processing: {url}")
            try:
                output = run_pipeline(url)
                primary = output.get("primary_category", "")
                secondary = output.get("secondary_category", "") or primary
                folder = output.get("folder", "") or secondary or primary
                products = output.get("products", [])

                for item in output.get("items", []):
                    name = item.get("name", "")
                    summary = item.get("summary", "")
                    product = match_product_to_item(name, products)
                    links = (product or {}).get("links", {})
                    results.append(
                        [
                            url,
                            primary,
                            secondary,
                            folder,
                            name,
                            summary,
                            "yes" if output.get("contains_products") else "no",
                            (product or {}).get("product_name", ""),
                            (product or {}).get("brand", ""),
                            (product or {}).get("model", ""),
                            (product or {}).get("product_type", ""),
                            (product or {}).get("search_query", ""),
                            links.get("best_buy_link", ""),
                            links.get("amazon", ""),
                            links.get("flipkart", ""),
                            links.get("nykaa", ""),
                            "yes" if output.get("diagnostics", {}).get("caption_present") else "no",
                            "yes" if output.get("diagnostics", {}).get("hashtags_present") else "no",
                            "yes" if output.get("diagnostics", {}).get("creator_present") else "no",
                            "yes" if output.get("diagnostics", {}).get("transcript_present") else "no",
                            output.get("diagnostics", {}).get("transcript_status", ""),
                            output.get("diagnostics", {}).get("transcript_model", ""),
                            output.get("diagnostics", {}).get("transcript_attempts", 0),
                            output.get("diagnostics", {}).get("transcript_error", ""),
                            output.get("diagnostics", {}).get("audio_download_status", ""),
                            output.get("diagnostics", {}).get("video_download_status", ""),
                            "yes" if output.get("diagnostics", {}).get("visual_present") else "no",
                            output.get("diagnostics", {}).get("visual_status", ""),
                            output.get("diagnostics", {}).get("visual_error", ""),
                            output.get("diagnostics", {}).get("processing_version", ""),
                        ]
                        + deep_search_diagnostic_values(output)
                    )

                if not output.get("items"):
                    product = products[0] if products else {}
                    links = product.get("links", {})
                    results.append(
                        [
                            url,
                            primary,
                            secondary,
                            folder,
                            "",
                            "",
                            "yes" if output.get("contains_products") else "no",
                            product.get("product_name", ""),
                            product.get("brand", ""),
                            product.get("model", ""),
                            product.get("product_type", ""),
                            product.get("search_query", ""),
                            links.get("best_buy_link", ""),
                            links.get("amazon", ""),
                            links.get("flipkart", ""),
                            links.get("nykaa", ""),
                            "yes" if output.get("diagnostics", {}).get("caption_present") else "no",
                            "yes" if output.get("diagnostics", {}).get("hashtags_present") else "no",
                            "yes" if output.get("diagnostics", {}).get("creator_present") else "no",
                            "yes" if output.get("diagnostics", {}).get("transcript_present") else "no",
                            output.get("diagnostics", {}).get("transcript_status", ""),
                            output.get("diagnostics", {}).get("transcript_model", ""),
                            output.get("diagnostics", {}).get("transcript_attempts", 0),
                            output.get("diagnostics", {}).get("transcript_error", ""),
                            output.get("diagnostics", {}).get("audio_download_status", ""),
                            output.get("diagnostics", {}).get("video_download_status", ""),
                            "yes" if output.get("diagnostics", {}).get("visual_present") else "no",
                            output.get("diagnostics", {}).get("visual_status", ""),
                            output.get("diagnostics", {}).get("visual_error", ""),
                            output.get("diagnostics", {}).get("processing_version", ""),
                        ]
                        + deep_search_diagnostic_values(output)
                    )
            except Exception as exc:
                print(f"❌ Failed: {url} | {exc}")
                results.append(
                    [
                        url,
                        "Failed Reels",
                        "Processing Failures",
                        "failed",
                        "Processing Failed",
                        f"Processing error: {summarize_error(exc)}",
                        "no",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "",
                        "no",
                        "no",
                        "no",
                        "no",
                        "failed",
                        "",
                        0,
                        summarize_error(exc),
                        "",
                        "",
                        "no",
                        "failed",
                        summarize_error(exc),
                        "pipeline_b_v2_observable",
                    ]
                    + [""] * len(DEEP_SEARCH_DIAGNOSTIC_COLUMNS)
                )

    with output_csv.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        writer.writerow(
            [
                "URL",
                "Primary Category",
                "Secondary Category",
                "Folder",
                "Item Name",
                "Summary",
                "Contains Product",
                "Product Name",
                "Product Brand",
                "Product Model",
                "Product Type",
                "Product Search Query",
                "Best Buy Link",
                "Amazon Link",
                "Flipkart Link",
                "Nykaa Link",
                "Caption Present",
                "Hashtags Present",
                "Creator Present",
                "Transcript Present",
                "Transcript Status",
                "Transcript Model",
                "Transcript Attempts",
                "Transcript Error",
                "Audio Download Status",
                "Video Download Status",
                "Visual Present",
                "Visual Status",
                "Visual Error",
                "Processing Version",
                *[column for column, _ in DEEP_SEARCH_DIAGNOSTIC_COLUMNS],
            ]
        )
        writer.writerows(results)

    print(f"\n✅ Done! Output saved to: {output_csv}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Instagram reel URLs using Pipeline B.")
    parser.add_argument(
        "--input",
        default=str(BASE_DIR / "tech - Sheet1.csv"),
        help="Input CSV containing reel URLs, one per row.",
    )
    parser.add_argument(
        "--output",
        default=str(BASE_DIR / "final_output_TECH.csv"),
        help="Output CSV path.",
    )
    args = parser.parse_args()
    process_csv(args.input, args.output)
