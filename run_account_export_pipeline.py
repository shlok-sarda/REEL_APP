import argparse
import subprocess
import sys
from pathlib import Path

from render_mobile_knowledge_app import render_html as render_standard_html, load_collections
from render_personalized_mobile_app import build_collections as build_personalized_collections


BASE_DIR = Path(__file__).resolve().parent


def run_step(cmd):
    print(f"\n>>> Running: {' '.join(str(part) for part in cmd)}", flush=True)
    subprocess.run([str(part) for part in cmd], cwd=str(BASE_DIR), check=True)


def build_standard_page(accumulated_csv, output_html, title, subtitle):
    collections = load_collections(accumulated_csv)
    html = render_standard_html(collections, title, subtitle)
    Path(output_html).write_text(html, encoding="utf-8")


def build_personalized_page(view_json, graph_json, output_html, title, subtitle):
    import json

    view = json.loads(Path(view_json).read_text(encoding="utf-8"))
    graph = json.loads(Path(graph_json).read_text(encoding="utf-8"))
    collections = build_personalized_collections(view, graph)
    html = render_standard_html(collections, title, subtitle)
    Path(output_html).write_text(html, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Run the full pipeline for a specific Instagram export account.")
    parser.add_argument("--saved-posts-json", required=True, help="Path to saved_posts.json from Meta export.")
    parser.add_argument("--output-dir", required=True, help="Output directory for this account.")
    parser.add_argument("--account-name", required=True, help="Display/account name for pages.")
    parser.add_argument("--granularity", type=float, default=0.35)
    parser.add_argument("--min-topic-reels", type=int, default=3)
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    urls_csv = output_dir / "saved_urls.csv"
    raw_output = output_dir / "account_output.csv"
    folder_items = output_dir / "list_titles_with_items.csv"
    mapping = output_dir / "list_title_accumulation.csv"
    accumulated = output_dir / "account_accumulated.csv"
    cleaned_raw = output_dir / "account_cleaned.csv"
    merge_mapping = output_dir / "topic_merge_mapping.csv"
    graph_json = output_dir / "topic_graph.json"
    personalized_json = output_dir / "personalized_view.json"
    standard_html = output_dir / "account_app.html"
    personalized_html = output_dir / "account_personalized_app.html"

    run_step(
        [
            sys.executable,
            BASE_DIR / "extract_saved_posts_urls.py",
            "--input",
            args.saved_posts_json,
            "--output",
            urls_csv,
        ]
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "finale.py",
            "--input",
            urls_csv,
            "--output",
            raw_output,
        ]
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "list_list_name_accumulation.py",
            "--input",
            raw_output,
            "--folder-items-output",
            folder_items,
            "--mapping-output",
            mapping,
            "--enriched-output",
            accumulated,
            "--granularity",
            str(args.granularity),
        ]
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "merge_existing_topics.py",
            "--input",
            accumulated,
            "--raw-output",
            cleaned_raw,
            "--mapping-output",
            merge_mapping,
        ]
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "list_list_name_accumulation.py",
            "--input",
            cleaned_raw,
            "--folder-items-output",
            folder_items,
            "--mapping-output",
            mapping,
            "--enriched-output",
            accumulated,
            "--granularity",
            str(args.granularity),
        ]
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "build_topic_graph.py",
            "--input",
            accumulated,
            "--output",
            graph_json,
            "--user-id",
            args.account_name,
        ]
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "personalised.py",
            "--graph",
            graph_json,
            "--output",
            personalized_json,
            "--min-topic-reels",
            str(args.min_topic_reels),
        ]
    )

    build_standard_page(
        accumulated,
        standard_html,
        f"{args.account_name} Reels",
        "Saved reels from the Instagram export, organized into browseable lists.",
    )
    build_personalized_page(
        personalized_json,
        graph_json,
        personalized_html,
        f"{args.account_name} Reels Personalized",
        "Repeated interests get their own lists while low-signal topics stay grouped.",
    )

    print("\nPipeline complete.", flush=True)
    print(f"Standard page: {standard_html}", flush=True)
    print(f"Personalized page: {personalized_html}", flush=True)


if __name__ == "__main__":
    main()
