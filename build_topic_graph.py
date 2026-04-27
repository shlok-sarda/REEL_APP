import argparse
from pathlib import Path

from topic_graph import (
    TopicGraphConfig,
    build_topic_graph,
    load_rows,
    summarize_graph,
    write_topic_graph,
)


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "final_output_TECH_accumulated.csv"
DEFAULT_OUTPUT = BASE_DIR / "topic_graph.json"


def main():
    parser = argparse.ArgumentParser(
        description="Build a canonical topic graph from the accumulated reel catalog."
    )
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Accumulated CSV input.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Topic graph JSON output.")
    parser.add_argument("--user-id", default="shloke", help="User id for interest-profile hints.")
    args = parser.parse_args()

    rows = load_rows(args.input)
    graph = build_topic_graph(
        rows,
        TopicGraphConfig(
            user_id=args.user_id,
            source_name=Path(args.input).name,
        ),
    )
    write_topic_graph(args.output, graph)
    summary = summarize_graph(graph)

    print(f"Saved topic graph: {args.output}")
    print(f"Umbrella nodes: {summary['umbrella_count']}")
    print(f"Topic nodes: {summary['topic_count']}")
    print(f"Reel nodes: {summary['reel_count']}")


if __name__ == "__main__":
    main()
