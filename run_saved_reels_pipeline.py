import argparse
import subprocess
import sys
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "instagram_saved_reel_urls.txt"
DEFAULT_RAW_OUTPUT = BASE_DIR / "saved_reels_output_v2.csv"
DEFAULT_FOLDER_ITEMS = BASE_DIR / "saved_reels_list_titles_with_items.csv"
DEFAULT_MAPPING = BASE_DIR / "saved_reels_list_title_accumulation.csv"
DEFAULT_ACCUMULATED = BASE_DIR / "saved_reels_accumulated.csv"
DEFAULT_CLEANED_RAW = BASE_DIR / "saved_reels_cleaned.csv"
DEFAULT_MERGE_MAPPING = BASE_DIR / "saved_reels_topic_merge_mapping.csv"
DEFAULT_GRAPH = BASE_DIR / "saved_reels_topic_graph.json"
DEFAULT_PERSONALIZED = BASE_DIR / "saved_reels_personalized_view.json"
DEFAULT_STANDARD_HTML = BASE_DIR / "saved_reels_standard.html"
DEFAULT_PERSONALIZED_HTML = BASE_DIR / "saved_reels_personalized.html"


def run_step(cmd, cwd):
    print(f"\n>>> Running: {' '.join(str(part) for part in cmd)}", flush=True)
    subprocess.run([str(part) for part in cmd], cwd=str(cwd), check=True)


def main():
    parser = argparse.ArgumentParser(description="Run the full saved-reels pipeline end to end.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input file with one reel URL per line.")
    parser.add_argument("--granularity", type=float, default=0.35, help="Umbrella granularity for accumulation.")
    parser.add_argument(
        "--promotion-reel-threshold",
        type=int,
        default=8,
        help="Promote personalized groups with at least this many reels into top-level categories.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    run_step(
        [
            sys.executable,
            BASE_DIR / "finale.py",
            "--input",
            input_path,
            "--output",
            DEFAULT_RAW_OUTPUT,
        ],
        BASE_DIR,
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "list_list_name_accumulation.py",
            "--input",
            DEFAULT_RAW_OUTPUT,
            "--folder-items-output",
            DEFAULT_FOLDER_ITEMS,
            "--mapping-output",
            DEFAULT_MAPPING,
            "--enriched-output",
            DEFAULT_ACCUMULATED,
            "--granularity",
            str(args.granularity),
        ],
        BASE_DIR,
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "merge_existing_topics.py",
            "--input",
            DEFAULT_ACCUMULATED,
            "--raw-output",
            DEFAULT_CLEANED_RAW,
            "--mapping-output",
            DEFAULT_MERGE_MAPPING,
        ],
        BASE_DIR,
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "list_list_name_accumulation.py",
            "--input",
            DEFAULT_CLEANED_RAW,
            "--folder-items-output",
            DEFAULT_FOLDER_ITEMS,
            "--mapping-output",
            DEFAULT_MAPPING,
            "--enriched-output",
            DEFAULT_ACCUMULATED,
            "--granularity",
            str(args.granularity),
        ],
        BASE_DIR,
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "build_topic_graph.py",
            "--input",
            DEFAULT_ACCUMULATED,
            "--output",
            DEFAULT_GRAPH,
            "--user-id",
            "shloke",
        ],
        BASE_DIR,
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "render_catalog.py",
            "--input",
            DEFAULT_ACCUMULATED,
            "--output",
            DEFAULT_STANDARD_HTML,
        ],
        BASE_DIR,
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "personalised.py",
            "--graph",
            DEFAULT_GRAPH,
            "--output",
            DEFAULT_PERSONALIZED,
            "--use-ai",
            "--promotion-reel-threshold",
            str(args.promotion_reel_threshold),
        ],
        BASE_DIR,
    )

    run_step(
        [
            sys.executable,
            BASE_DIR / "render_personalized_view.py",
            "--input",
            DEFAULT_PERSONALIZED,
            "--graph",
            DEFAULT_GRAPH,
            "--output",
            DEFAULT_PERSONALIZED_HTML,
        ],
        BASE_DIR,
    )

    print("\nPipeline complete.", flush=True)
    print(f"Standard page: {DEFAULT_STANDARD_HTML}", flush=True)
    print(f"Personalized page: {DEFAULT_PERSONALIZED_HTML}", flush=True)


if __name__ == "__main__":
    main()
