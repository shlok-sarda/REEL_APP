import csv
import json
import os
import subprocess
import sys
from pathlib import Path
import argparse
from types import SimpleNamespace

from render_mobile_knowledge_app import render_html as render_standard_html, load_collections
from render_personalized_mobile_app import build_collections as build_personalized_collections
from app.services.media import ensure_reel_media
from app.services.reel_ingest import get_reel_by_url, load_reels, sync_csv_from_db, sync_reel_items_from_accumulated, update_reel_status
from app.storage import user_storage_dir


BASE_DIR = Path(__file__).resolve().parent


def extraction_script() -> Path:
    mode = os.getenv("PROCESSOR_MODE", "legacy").strip().lower()
    if mode == "pipeline_b":
        return BASE_DIR / "pipeline_b_processor.py"
    return BASE_DIR / "finale.py"


def normalize(value):
    return " ".join((value or "").strip().split())


def build_paths(storage_dir: Path):
    return SimpleNamespace(
        storage_dir=storage_dir,
        urls_csv=storage_dir / "reel_urls.csv",
        raw_output=storage_dir / "shlok_reels_output.csv",
        folder_items=storage_dir / "shlok_reels_list_titles_with_items.csv",
        mapping=storage_dir / "shlok_reels_list_title_accumulation.csv",
        accumulated=storage_dir / "shlok_reels_accumulated.csv",
        cleaned_raw=storage_dir / "shlok_reels_cleaned.csv",
        merge_mapping=storage_dir / "shlok_reels_topic_merge_mapping.csv",
        graph_json=storage_dir / "shlok_reels_topic_graph.json",
        personalized_json=storage_dir / "shlok_reels_personalized_view.json",
        standard_html=storage_dir / "shlok_reels_app.html",
        personalized_html=storage_dir / "shlok_reels_personalized_app.html",
        status_json=storage_dir / "pipeline_status.json",
    )


def sync_user_url_csv(user_id: str, paths):
    rows = load_reels(user_id=user_id)
    paths.storage_dir.mkdir(parents=True, exist_ok=True)
    with paths.urls_csv.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(
            outfile,
            fieldnames=["id", "user_id", "url", "shortcode", "received_at", "status", "media_status", "local_video_path", "thumbnail_path"],
        )
        writer.writeheader()
        writer.writerows(rows)


def load_url_rows(paths):
    if not paths.urls_csv.exists():
        return []
    with paths.urls_csv.open(newline="", encoding="utf-8") as infile:
        return [row for row in csv.DictReader(infile) if normalize(row.get("url"))]


def load_raw_rows(paths):
    if not paths.raw_output.exists():
        return []
    with paths.raw_output.open(newline="", encoding="utf-8") as infile:
        return list(csv.DictReader(infile))


def processed_urls(rows):
    done = set()
    for row in rows:
        url = normalize(row.get("URL"))
        folder = normalize(row.get("Folder"))
        if not url:
            continue
        if folder in {"failed", "error"}:
            continue
        done.add(url)
    return done


def write_raw_rows(rows, paths):
    fieldnames = list(rows[0].keys()) if rows else ["URL", "Primary Category", "Secondary Category", "Folder", "Item Name", "Summary"]
    with paths.raw_output.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def filter_csv_by_active_urls(input_path, output_path, active_urls):
    source = Path(input_path)
    if not source.exists():
        return False
    with source.open(newline="", encoding="utf-8") as infile:
        rows = [row for row in csv.DictReader(infile) if normalize(row.get("URL")) in active_urls]
        fieldnames = list(rows[0].keys()) if rows else []
    if not fieldnames:
        return False
    with Path(output_path).open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return True


def write_csv_rows(rows, output_path, preferred_fieldnames=None):
    output = Path(output_path)
    fieldnames = preferred_fieldnames or (list(rows[0].keys()) if rows else [])
    if not fieldnames:
        return
    with output.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def normalize_failed_rows(rows):
    normalized = []
    for row in rows:
        updated = dict(row)
        folder = normalize(updated.get("Folder")).lower()
        if folder in {"failed", "error"}:
            updated["Primary Category"] = normalize(updated.get("Primary Category")) or "Failed Reels"
            updated["Secondary Category"] = normalize(updated.get("Secondary Category")) or "Processing Failures"
            updated["Folder"] = normalize(updated.get("Folder")) or "failed"
            updated["Item Name"] = normalize(updated.get("Item Name")) or "Processing Failed"
            updated["Summary"] = normalize(updated.get("Summary")) or "This reel could not be processed in the current run."
            updated["Contains Product"] = normalize(updated.get("Contains Product")) or "no"
        normalized.append(updated)
    return normalized


def write_input_urls(urls, output_path):
    with output_path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.writer(outfile)
        for url in urls:
            writer.writerow([url])


def run_step(cmd):
    subprocess.run([str(part) for part in cmd], cwd=str(BASE_DIR), check=True)


def build_file_uri(path_value):
    if not normalize(path_value):
        return ""
    path = Path(path_value)
    if not path.exists():
        return ""
    return path.resolve().as_uri()


def enrich_rows_with_media(rows):
    enriched = []
    for row in rows:
        updated = dict(row)
        url = normalize(row.get("URL"))
        reel = get_reel_by_url(url) if url else None
        local_video_path = (reel or {}).get("local_video_path", "")
        thumbnail_path = (reel or {}).get("thumbnail_path", "")
        media_status = (reel or {}).get("media_status", "")
        updated["Media Status"] = media_status
        updated["Local Video Path"] = local_video_path
        updated["Local Video URL"] = build_file_uri(local_video_path)
        updated["Thumbnail Path"] = thumbnail_path
        updated["Thumbnail URL"] = build_file_uri(thumbnail_path)
        enriched.append(updated)
    return enriched


def summarize_status_by_url(rows):
    summary = {}
    for row in rows:
        url = normalize(row.get("URL"))
        folder = normalize(row.get("Folder"))
        if not url:
            continue
        current = summary.get(url)
        if folder in {"failed", "error"}:
            summary[url] = "failed"
        elif current != "failed":
            summary[url] = "completed"
    return summary


def sync_existing_status_and_media(rows):
    status_by_url = summarize_status_by_url(rows)
    for url, status in status_by_url.items():
        update_reel_status(url, status)
        if status == "completed":
            reel = get_reel_by_url(url)
            local_video_path = (reel or {}).get("local_video_path", "")
            media_status = normalize((reel or {}).get("media_status", ""))
            if media_status != "ready" or not local_video_path or not Path(local_video_path).exists():
                ensure_reel_media(url)


def build_standard_page(paths, app_title="Shlok Reels"):
    collections = load_collections(paths.accumulated)
    html = render_standard_html(
        collections,
        app_title,
        "Telegram reels update this page automatically as they get processed.",
    )
    paths.standard_html.write_text(html, encoding="utf-8")


def build_personalized_page(paths, app_title="Shlok Reels Personalized"):
    view = json.loads(paths.personalized_json.read_text(encoding="utf-8"))
    graph = json.loads(paths.graph_json.read_text(encoding="utf-8"))
    collections = build_personalized_collections(view, graph)
    html = render_standard_html(
        collections,
        app_title,
        "Repeated interests get their own lists while low-signal topics stay grouped.",
    )
    paths.personalized_html.write_text(html, encoding="utf-8")


def write_status(payload, paths):
    paths.status_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(user_id="default", only_urls=None):
    sync_csv_from_db()
    paths = build_paths(user_storage_dir(user_id))
    sync_user_url_csv(user_id, paths)
    paths.storage_dir.mkdir(parents=True, exist_ok=True)
    url_rows = load_url_rows(paths)
    urls = [normalize(row.get("url")) for row in url_rows if normalize(row.get("url"))]
    raw_rows = load_raw_rows(paths)
    active_url_set = set(urls)
    if raw_rows:
        raw_rows = [row for row in raw_rows if normalize(row.get("URL")) in active_url_set]
    done_urls = processed_urls(raw_rows)
    lightweight_rebuild = False
    if only_urls:
        requested = [normalize(url) for url in only_urls if normalize(url)]
        pending_urls = [url for url in requested if url and url in urls]
    else:
        pending_urls = [url for url in urls if url not in done_urls]

    if pending_urls:
        for url in pending_urls:
            update_reel_status(url, "processing")

        pending_input = paths.storage_dir / "pending_urls.csv"
        pending_output = paths.storage_dir / "pending_output.csv"
        write_input_urls(pending_urls, pending_input)

        finale_failed = False
        try:
            run_step([sys.executable, extraction_script(), "--input", pending_input, "--output", pending_output])
        except subprocess.CalledProcessError:
            finale_failed = True
        pending_input.unlink(missing_ok=True)
        pending_rows = []
        if pending_output.exists():
            with pending_output.open(newline="", encoding="utf-8") as infile:
                pending_rows = list(csv.DictReader(infile))
            pending_output.unlink(missing_ok=True)
        if finale_failed and not pending_rows:
            pending_rows = [
                {
                    "URL": url,
                    "Primary Category": "Uncategorized",
                    "Secondary Category": "Failed Processing",
                    "Folder": "failed",
                    "Item Name": "Processing Failed",
                    "Summary": "This reel could not be processed in the current run.",
                    "Contains Product": "no",
                    "Product Name": "",
                    "Product Brand": "",
                    "Product Model": "",
                    "Product Type": "",
                    "Product Search Query": "",
                    "Best Buy Link": "",
                    "Amazon Link": "",
                    "Flipkart Link": "",
                    "Nykaa Link": "",
                    "Media Status": "",
                    "Local Video Path": "",
                    "Local Video URL": "",
                    "Thumbnail Path": "",
                    "Thumbnail URL": "",
                }
                for url in pending_urls
            ]
        pending_rows = normalize_failed_rows(pending_rows)

        status_by_url = summarize_status_by_url(pending_rows)
        for url in pending_urls:
            update_reel_status(url, status_by_url.get(url, "failed"))
            if status_by_url.get(url) == "completed":
                ensure_reel_media(url)

        pending_set = {normalize(url) for url in pending_urls}
        kept_rows = [
            row for row in raw_rows
            if normalize(row.get("URL")) in active_url_set and normalize(row.get("URL")) not in pending_set
        ]
        combined_rows = enrich_rows_with_media(kept_rows + pending_rows)
        write_raw_rows(combined_rows, paths)
    elif raw_rows:
        sync_existing_status_and_media(raw_rows)
        write_raw_rows(enrich_rows_with_media(raw_rows), paths)
        lightweight_rebuild = True

    if paths.raw_output.exists():
        current_rows = load_raw_rows(paths)
        current_rows = normalize_failed_rows(current_rows)
        successful_rows = [
            row for row in current_rows
            if normalize(row.get("Folder")).lower() not in {"failed", "error"}
        ]
        if not successful_rows and current_rows:
            preferred = list(current_rows[0].keys())
            write_csv_rows(current_rows, paths.accumulated, preferred)
            write_csv_rows(current_rows, paths.cleaned_raw, preferred)
            write_csv_rows(current_rows, paths.folder_items, preferred)
            paths.mapping.write_text("folder,umbrella_folder\n", encoding="utf-8")
            paths.merge_mapping.write_text("topic,canonical_topic\n", encoding="utf-8")
            minimal_graph = {
                "user_id": user_id,
                "source_name": Path(paths.accumulated).name,
                "topics": [],
                "reels": [],
            }
            paths.graph_json.write_text(json.dumps(minimal_graph, indent=2), encoding="utf-8")
            empty_personalized = {"sections": []}
            paths.personalized_json.write_text(json.dumps(empty_personalized, indent=2), encoding="utf-8")
            title_root = "Shlok Reels" if user_id == "default" else f"Reels · {user_id}"
            build_standard_page(paths, app_title=title_root)
            from render_mobile_knowledge_app import render_html as _render_html
            paths.personalized_html.write_text(
                _render_html([], f"{title_root} Personalized", "No repeated interests yet."),
                encoding="utf-8",
            )
            sync_reel_items_from_accumulated(user_id, paths.accumulated)
        elif lightweight_rebuild and paths.accumulated.exists():
            filter_csv_by_active_urls(paths.accumulated, paths.accumulated, active_url_set)
            if paths.cleaned_raw.exists():
                filter_csv_by_active_urls(paths.cleaned_raw, paths.cleaned_raw, active_url_set)
            if paths.folder_items.exists():
                filter_csv_by_active_urls(paths.folder_items, paths.folder_items, active_url_set)
        else:
            run_step(
                [
                    sys.executable,
                    BASE_DIR / "list_list_name_accumulation.py",
                    "--input",
                    paths.raw_output,
                    "--folder-items-output",
                    paths.folder_items,
                    "--mapping-output",
                    paths.mapping,
                    "--enriched-output",
                    paths.accumulated,
                    "--granularity",
                    "0.35",
                ]
            )

            run_step(
                [
                    sys.executable,
                    BASE_DIR / "merge_existing_topics.py",
                    "--input",
                    paths.accumulated,
                    "--raw-output",
                    paths.cleaned_raw,
                    "--mapping-output",
                    paths.merge_mapping,
                ]
            )

            run_step(
                [
                    sys.executable,
                    BASE_DIR / "list_list_name_accumulation.py",
                    "--input",
                    paths.cleaned_raw,
                    "--folder-items-output",
                    paths.folder_items,
                    "--mapping-output",
                    paths.mapping,
                    "--enriched-output",
                    paths.accumulated,
                    "--granularity",
                    "0.35",
                ]
            )

        run_step(
            [
                sys.executable,
                BASE_DIR / "build_topic_graph.py",
                "--input",
                paths.accumulated,
                "--output",
                paths.graph_json,
                "--user-id",
                user_id,
            ]
        )

        run_step(
            [
                sys.executable,
                BASE_DIR / "personalised.py",
                "--graph",
                paths.graph_json,
                "--output",
                paths.personalized_json,
                "--min-topic-reels",
                "3",
            ]
        )

        title_root = "Shlok Reels" if user_id == "default" else f"Reels · {user_id}"
        build_standard_page(paths, app_title=title_root)
        build_personalized_page(paths, app_title=f"{title_root} Personalized")
        sync_reel_items_from_accumulated(user_id, paths.accumulated)

    refreshed_rows = load_raw_rows(paths)
    write_status(
        {
            "url_count": len(urls),
            "processed_url_count": len(processed_urls(refreshed_rows)),
            "pending_url_count": max(len(urls) - len(processed_urls(refreshed_rows)), 0),
            "item_count": len(refreshed_rows),
            "last_updated": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            "standard_page": str(paths.standard_html),
            "personalized_page": str(paths.personalized_html),
            "raw_output": str(paths.raw_output),
            "accumulated_output": str(paths.accumulated),
        }
    , paths)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Process Shlok reels and rebuild outputs.")
    parser.add_argument("--only-url", action="append", default=[], help="Only process the given reel URL. Can be passed multiple times.")
    parser.add_argument("--user-id", default="default", help="Only process reels for this user id.")
    args = parser.parse_args()
    main(user_id=args.user_id, only_urls=args.only_url)
