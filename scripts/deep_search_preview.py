from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.deep_search import index_user_documents, load_deep_search_documents, search_documents_locally


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview ClipNest deep-search docs/results without mutating SQLite.")
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--index-meili", action="store_true")
    parser.add_argument("--index", default="")
    args = parser.parse_args()

    if args.index_meili:
        print(json.dumps(index_user_documents(args.user_id, index_name=args.index or None), indent=2, ensure_ascii=False))
        return

    documents = load_deep_search_documents(args.user_id)
    payload = {
        "user_id": args.user_id,
        "document_count": len(documents),
        "query": args.query,
    }
    if args.query:
        payload["results"] = search_documents_locally(documents, args.query, limit=args.limit)
    else:
        payload["documents"] = documents[: args.limit]
    print(json.dumps(payload, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

