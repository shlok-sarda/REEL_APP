import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "saved_reels_accumulated.csv"
DEFAULT_OUTPUT = BASE_DIR / "index.html"


def normalize(value):
    return " ".join((value or "").strip().split())


def chunk_items(items, chunk_size):
    return [items[index:index + chunk_size] for index in range(0, len(items), chunk_size)]


def pack_small_groups(groups, target_size, label_prefix):
    packed = []
    bucket = []
    bucket_size = 0

    for label, items in groups:
        if bucket and bucket_size + len(items) > target_size:
            packed.append((f"{label_prefix} {len(packed) + 1}", bucket))
            bucket = []
            bucket_size = 0
        bucket.append((label, items))
        bucket_size += len(items)

    if bucket:
        packed.append((f"{label_prefix} {len(packed) + 1}", bucket))

    return packed


def normalized_item_rows(rows):
    normalized = []
    for row in rows:
        normalized.append(
            {
                "reel_id": normalize(row.get("Reel ID") or row.get("reel_id")),
                "primary": normalize(row.get("Primary Category") or row.get("Umbrella Folder") or row.get("primary_category") or "Untitled"),
                "secondary": normalize(row.get("Secondary Category") or row.get("Folder") or row.get("secondary_category") or row.get("primary_category") or "General"),
                "name": normalize(row.get("Item Name") or row.get("item_name")),
                "summary": normalize(row.get("Summary") or row.get("summary")),
                "url": normalize(row.get("URL") or row.get("url")),
                "contains_product": normalize(row.get("Contains Product") or row.get("contains_product")),
                "product_name": normalize(row.get("Product Name") or row.get("product_name")),
                "product_brand": normalize(row.get("Product Brand") or row.get("product_brand")),
                "product_model": normalize(row.get("Product Model") or row.get("product_model")),
                "product_type": normalize(row.get("Product Type") or row.get("product_type")),
                "product_search_query": normalize(row.get("Product Search Query") or row.get("product_search_query")),
                "best_buy_link": normalize(row.get("Best Buy Link") or row.get("best_buy_link")),
                "amazon_link": normalize(row.get("Amazon Link") or row.get("amazon_link")),
                "flipkart_link": normalize(row.get("Flipkart Link") or row.get("flipkart_link")),
                "nykaa_link": normalize(row.get("Nykaa Link") or row.get("nykaa_link")),
                "media_status": normalize(row.get("Media Status") or row.get("media_status")),
                "local_video_path": normalize(row.get("Local Video Path") or row.get("local_video_path")),
                "local_video_url": normalize(row.get("Local Video URL") or row.get("local_video_url")),
                "thumbnail_path": normalize(row.get("Thumbnail Path") or row.get("thumbnail_path")),
                "thumbnail_url": normalize(row.get("Thumbnail URL") or row.get("thumbnail_url")),
                "received_at": normalize(row.get("Received At") or row.get("received_at")),
            }
        )
    return normalized


def build_collections_from_rows(rows):
    grouped = defaultdict(lambda: defaultdict(list))
    seen = defaultdict(set)

    for row in normalized_item_rows(rows):
        primary = row["primary"]
        secondary = row["secondary"]
        name = row["name"]
        summary = row["summary"]
        url = row["url"]
        if not primary or not name:
            continue

        key = (primary.lower(), secondary.lower(), name.lower(), summary.lower(), url)
        if key in seen[primary]:
            continue

        seen[primary].add(key)
        grouped[primary][secondary].append(
            {
                "reel_id": row["reel_id"],
                "name": name,
                "summary": summary,
                "url": url,
                "contains_product": row["contains_product"],
                "product_name": row["product_name"],
                "product_brand": row["product_brand"],
                "product_model": row["product_model"],
                "product_type": row["product_type"],
                "product_search_query": row["product_search_query"],
                "best_buy_link": row["best_buy_link"],
                "amazon_link": row["amazon_link"],
                "flipkart_link": row["flipkart_link"],
                "nykaa_link": row["nykaa_link"],
                "media_status": row["media_status"],
                "local_video_path": row["local_video_path"],
                "local_video_url": row["local_video_url"],
                "thumbnail_path": row["thumbnail_path"],
                "thumbnail_url": row["thumbnail_url"],
                "received_at": row["received_at"],
            }
        )

    collections = []
    soft_cap = 12
    hard_cap = 24
    split_trigger = 25
    standalone_secondary_threshold = 8

    for primary, secondary_map in sorted(grouped.items(), key=lambda row: row[0].lower()):
        secondary_items = {
            secondary: sorted(items, key=lambda item: item["name"].lower())
            for secondary, items in secondary_map.items()
            if items
        }
        total_items = sum(len(items) for items in secondary_items.values())

        if total_items <= hard_cap:
            merged = []
            for _, items in sorted(secondary_items.items(), key=lambda row: row[0].lower()):
                merged.extend(items)
            collections.append(
                {
                    "parent_title": "",
                    "list_title": primary,
                    "items": merged,
                }
            )
            continue

        big_secondaries = []
        small_secondaries = []
        for secondary, items in sorted(secondary_items.items(), key=lambda row: (-len(row[1]), row[0].lower())):
            if len(items) >= standalone_secondary_threshold:
                big_secondaries.append((secondary, items))
            else:
                small_secondaries.append((secondary, items))

        for secondary, items in big_secondaries:
            if len(items) <= hard_cap:
                collections.append(
                    {
                        "parent_title": primary,
                        "list_title": secondary,
                        "items": items,
                    }
                )
                continue

            chunks = chunk_items(items, soft_cap)
            for part, chunk in enumerate(chunks, start=1):
                collections.append(
                    {
                        "parent_title": primary,
                        "list_title": f"{secondary} · Part {part}",
                        "items": chunk,
                    }
                )

        if not big_secondaries and total_items <= split_trigger:
            merged = []
            for _, items in sorted(secondary_items.items(), key=lambda row: row[0].lower()):
                merged.extend(items)
            collections.append(
                {
                    "parent_title": "",
                    "list_title": primary,
                    "items": merged,
                }
            )
            continue

        if small_secondaries:
            packed_groups = pack_small_groups(small_secondaries, soft_cap, f"{primary} · More")
            for packed_label, bundle in packed_groups:
                merged_items = []
                labels = []
                for secondary, items in bundle:
                    merged_items.extend(items)
                    labels.append(secondary)
                label = packed_label
                if len(bundle) == 1:
                    label = labels[0]
                collections.append(
                    {
                        "parent_title": primary,
                        "list_title": label,
                        "items": merged_items,
                    }
                )
    return collections


def load_collections(input_csv):
    with open(input_csv, newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        return build_collections_from_rows(reader)


def render_html(collections, app_title, app_subtitle):
    data_json = json.dumps(collections, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>{app_title}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #08090b;
      --line: rgba(255, 255, 255, 0.11);
      --line-strong: rgba(255, 255, 255, 0.18);
      --text: #f4f6f8;
      --muted: #a7adb7;
      --soft: #737b89;
      --accent: #e8d7b7;
      --accent-2: #a7d8c9;
      --shadow: 0 24px 70px rgba(0, 0, 0, 0.38);
      --safe-top: env(safe-area-inset-top, 0px);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
    }}

    * {{ box-sizing: border-box; }}
    html {{ min-height: 100%; background: var(--bg); scroll-behavior: smooth; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-family: ui-rounded, "SF Pro Rounded", "Avenir Next", "Nunito Sans", system-ui, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(232, 215, 183, 0.16), transparent 28rem),
        radial-gradient(circle at top right, rgba(167, 216, 201, 0.12), transparent 22rem),
        linear-gradient(180deg, #11151b 0%, #08090b 46%, #07080a 100%);
      overflow-x: hidden;
    }}

    button, input, a {{ -webkit-tap-highlight-color: transparent; }}

    .app-shell {{
      width: min(760px, 100%);
      min-height: 100vh;
      margin: 0 auto;
      padding: calc(18px + var(--safe-top)) 16px calc(34px + var(--safe-bottom));
    }}

    .app-header {{
      position: sticky;
      top: 0;
      z-index: 20;
      margin: calc(-18px - var(--safe-top)) -16px 14px;
      padding: calc(16px + var(--safe-top)) 16px 14px;
      background: linear-gradient(180deg, rgba(8, 9, 11, 0.96), rgba(8, 9, 11, 0.78) 74%, transparent);
      backdrop-filter: blur(18px);
    }}

    .top-row {{ display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }}
    .brand-kicker {{
      margin: 0 0 6px;
      color: var(--accent-2);
      font-size: 0.72rem;
      font-weight: 850;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }}
    .screen-title {{
      margin: 0;
      font-size: clamp(1.8rem, 8vw, 3rem);
      line-height: 0.95;
      letter-spacing: -0.055em;
    }}
    .screen-subtitle {{ margin: 8px 0 0; color: var(--muted); font-size: 0.93rem; line-height: 1.45; }}

    .back-button {{
      display: none;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      width: 42px;
      height: 42px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255, 255, 255, 0.075);
      color: var(--text);
      cursor: pointer;
      font-size: 1.15rem;
      transition: transform 180ms ease;
    }}
    .back-button.visible {{ display: inline-flex; }}
    .back-button:active {{ transform: scale(0.94); }}

    .search-wrap {{ position: relative; }}
    .search-icon {{
      position: absolute;
      left: 15px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--soft);
      pointer-events: none;
    }}
    .search-input {{
      width: 100%;
      height: 48px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255, 255, 255, 0.075);
      color: var(--text);
      padding: 0 44px;
      font: 750 0.96rem/1 ui-rounded, "SF Pro Rounded", system-ui, sans-serif;
      outline: none;
      transition: border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
    }}
    .search-input::placeholder {{ color: #777f8d; }}
    .search-input:focus {{
      border-color: rgba(232, 215, 183, 0.34);
      background: rgba(255, 255, 255, 0.095);
      box-shadow: 0 0 0 4px rgba(232, 215, 183, 0.07);
    }}
    .clear-search {{
      position: absolute;
      right: 8px;
      top: 50%;
      transform: translateY(-50%);
      display: none;
      width: 32px;
      height: 32px;
      border: 0;
      border-radius: 999px;
      background: rgba(255,255,255,0.10);
      color: var(--muted);
      cursor: pointer;
      font-weight: 900;
    }}
    .clear-search.visible {{ display: block; }}

    .stats-bar {{
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 2px 0 4px;
      margin: 2px 0 14px;
      scrollbar-width: none;
    }}
    .stats-bar::-webkit-scrollbar {{ display: none; }}
    .chip {{
      flex: 0 0 auto;
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.055);
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 850;
    }}

    .content-stack {{ display: grid; gap: 12px; animation: riseIn 420ms ease both; }}
    @keyframes riseIn {{
      from {{ opacity: 0; transform: translateY(10px); }}
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    .collection-card {{
      position: relative;
      width: 100%;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 28px;
      background:
        radial-gradient(circle at top right, rgba(232, 215, 183, 0.11), transparent 36%),
        linear-gradient(180deg, rgba(255,255,255,0.092), rgba(255,255,255,0.048));
      box-shadow: var(--shadow);
      color: inherit;
      padding: 18px;
      text-align: left;
      cursor: pointer;
      transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
    }}
    .collection-card::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(255,255,255,0.12), transparent 52%);
      pointer-events: none;
    }}
    .collection-card:active {{ transform: scale(0.985); }}
    @media (hover: hover) {{
      .collection-card:hover {{
        transform: translateY(-2px);
        border-color: rgba(232, 215, 183, 0.24);
      }}
    }}

    .card-top {{
      position: relative;
      display: flex;
      justify-content: space-between;
      gap: 14px;
      align-items: flex-start;
      margin-bottom: 14px;
    }}
    .card-kicker {{
      margin: 0 0 8px;
      color: var(--accent-2);
      font-size: 0.7rem;
      font-weight: 900;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }}
    .collection-title {{ margin: 0; font-size: 1.13rem; line-height: 1.14; letter-spacing: -0.022em; }}
    .item-count {{
      flex: 0 0 auto;
      padding: 7px 9px;
      border-radius: 999px;
      background: rgba(167, 216, 201, 0.12);
      color: var(--accent-2);
      font-size: 0.72rem;
      font-weight: 950;
      text-transform: uppercase;
    }}
    .preview-list {{
      position: relative;
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}
    .preview-list li {{
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.42;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}

    .list-layout {{
      display: grid;
      gap: 14px;
      align-items: start;
    }}
    .list-column {{
      min-width: 0;
      display: grid;
      gap: 12px;
    }}
    .list-header {{
      position: sticky;
      top: 112px;
      z-index: 10;
      margin: 0 -2px 12px;
      padding: 14px 2px 10px;
      background: linear-gradient(180deg, rgba(8,9,11,0.92), rgba(8,9,11,0.72), transparent);
      backdrop-filter: blur(10px);
    }}
    .list-title {{ margin: 0; font-size: 1.55rem; line-height: 1; letter-spacing: -0.04em; }}
    .list-meta {{ margin: 8px 0 0; color: var(--muted); font-size: 0.86rem; font-weight: 750; }}

    .item-card {{
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(255,255,255,0.064);
      box-shadow: 0 16px 34px rgba(0,0,0,0.18);
      transition: border-color 180ms ease, transform 180ms ease, background 180ms ease;
    }}
    .item-card.active {{
      border-color: rgba(232, 215, 183, 0.34);
      background:
        radial-gradient(circle at top right, rgba(232, 215, 183, 0.09), transparent 50%),
        rgba(255,255,255,0.078);
      transform: translateY(-1px);
    }}
    .item-button {{
      width: 100%;
      border: 0;
      background: transparent;
      color: inherit;
      text-align: left;
      padding: 16px;
      cursor: pointer;
    }}
    .item-name {{ margin: 0; font-size: 1rem; line-height: 1.22; font-weight: 900; }}
    .item-summary {{
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.45;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}
    .item-card.expanded .item-summary {{ -webkit-line-clamp: unset; overflow: visible; }}
    .item-extra {{
      max-height: 0;
      overflow: hidden;
      opacity: 0;
      border-top: 1px solid transparent;
      transition: max-height 240ms ease, opacity 220ms ease, border-color 220ms ease;
    }}
    .item-card.expanded .item-extra {{ max-height: 180px; opacity: 1; border-color: var(--line); }}
    .item-extra-inner {{ padding: 0 16px 16px; color: var(--soft); font-size: 0.82rem; line-height: 1.5; }}
    .item-hint {{
      display: inline-flex;
      margin-top: 11px;
      color: var(--accent);
      font-size: 0.76rem;
      font-weight: 950;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}
    .preview-panel {{
      position: sticky;
      top: 122px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 28px;
      background:
        radial-gradient(circle at top left, rgba(167, 216, 201, 0.10), transparent 44%),
        linear-gradient(180deg, rgba(255,255,255,0.085), rgba(255,255,255,0.038));
      box-shadow: var(--shadow);
    }}
    .preview-frame-wrap {{
      position: relative;
      width: 100%;
      aspect-ratio: 0.66;
      background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
      border-bottom: 1px solid var(--line);
    }}
    .preview-iframe {{
      width: 100%;
      height: 100%;
      border: 0;
      background: #050607;
    }}
    .preview-video {{
      width: 100%;
      height: 100%;
      display: block;
      object-fit: cover;
      background: #050607;
    }}
    .preview-placeholder {{
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      padding: 24px;
      text-align: center;
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.5;
    }}
    .preview-body {{
      display: grid;
      gap: 12px;
      padding: 16px;
    }}
    .preview-kicker {{
      margin: 0;
      color: var(--accent-2);
      font-size: 0.72rem;
      font-weight: 900;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }}
    .preview-item-title {{
      margin: 0;
      font-size: 1.15rem;
      line-height: 1.08;
      letter-spacing: -0.035em;
    }}
    .preview-item-summary {{
      margin: 0;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.55;
    }}
    .preview-url {{
      word-break: break-all;
      color: var(--soft);
      font-size: 0.78rem;
      line-height: 1.45;
    }}
    .preview-note {{
      margin: 0;
      color: var(--soft);
      font-size: 0.76rem;
      line-height: 1.45;
    }}
    .buy-panel {{
      display: grid;
      gap: 10px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.05);
    }}
    .buy-kicker {{
      margin: 0;
      color: var(--accent);
      font-size: 0.7rem;
      font-weight: 900;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }}
    .buy-title {{
      margin: 0;
      font-size: 0.96rem;
      line-height: 1.35;
      color: var(--text);
      font-weight: 850;
    }}
    .buy-meta {{
      margin: 0;
      color: var(--muted);
      font-size: 0.8rem;
      line-height: 1.45;
    }}
    .buy-actions {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }}
    .buy-link {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 38px;
      padding: 0 13px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.065);
      color: var(--text);
      text-decoration: none;
      font-size: 0.78rem;
      font-weight: 900;
      letter-spacing: 0.02em;
      transition: transform 160ms ease, border-color 160ms ease, background 160ms ease;
    }}
    .buy-link.primary {{
      border-color: rgba(232, 215, 183, 0.34);
      background: rgba(232, 215, 183, 0.14);
      color: #fff2da;
    }}
    @media (hover: hover) {{
      .buy-link:hover {{
        transform: translateY(-1px);
        border-color: rgba(232, 215, 183, 0.34);
      }}
    }}
    .empty-state {{
      min-height: 42vh;
      display: grid;
      place-items: center;
      padding: 34px 18px;
      border: 1px dashed var(--line-strong);
      border-radius: 28px;
      background: rgba(255,255,255,0.045);
      text-align: center;
    }}
    .empty-state h2 {{ margin: 0 0 8px; font-size: 1.25rem; }}
    .empty-state p {{ margin: 0; color: var(--muted); line-height: 1.5; font-size: 0.92rem; }}

    @media (min-width: 760px) {{
      .app-shell {{ padding-inline: 22px; }}
      .content-stack.collections {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .collection-card {{ min-height: 180px; }}
      .list-layout {{
        grid-template-columns: minmax(0, 1.08fr) minmax(300px, 0.92fr);
        gap: 18px;
      }}
    }}
    @media (max-width: 759px) {{
      .preview-panel {{
        position: relative;
        top: 0;
        order: -1;
      }}
    }}
  </style>
</head>
<body>
  <main class="app-shell">
    <header class="app-header">
      <div class="top-row">
        <button id="backButton" class="back-button" aria-label="Back to collections">‹</button>
        <div style="min-width:0; flex:1;">
          <p class="brand-kicker">Technology Reels</p>
          <h1 id="screenTitle" class="screen-title">{app_title}</h1>
          <p id="screenSubtitle" class="screen-subtitle">{app_subtitle}</p>
        </div>
      </div>
      <div class="search-wrap">
        <span class="search-icon">⌕</span>
        <input id="searchInput" class="search-input" type="search" placeholder="Search tech lists and items" autocomplete="off" />
        <button id="clearSearch" class="clear-search" aria-label="Clear search">×</button>
      </div>
    </header>

    <section id="statsBar" class="stats-bar"></section>
    <section id="content" class="content-stack collections"></section>
  </main>

  <script>
    const DATA = {data_json};
    const state = {{ currentList: null, query: "", activeItemIndex: 0 }};
    const content = document.getElementById("content");
    const searchInput = document.getElementById("searchInput");
    const clearSearch = document.getElementById("clearSearch");
    const backButton = document.getElementById("backButton");
    const screenTitle = document.getElementById("screenTitle");
    const screenSubtitle = document.getElementById("screenSubtitle");
    const statsBar = document.getElementById("statsBar");
    const homeTitle = {json.dumps(app_title)};
    const homeSubtitle = {json.dumps(app_subtitle)};
    const totalItems = DATA.reduce((sum, list) => sum + list.items.length, 0);

    function escapeHtml(value) {{
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}
    function matchesItem(item, query) {{
      if (!query) return true;
      return `${{item.name}} ${{item.summary}} ${{item.url || ""}} ${{item.product_name || ""}} ${{item.product_brand || ""}} ${{item.product_model || ""}} ${{item.product_type || ""}}`.toLowerCase().includes(query);
    }}
    function matchesList(list, query) {{
      if (!query) return true;
      return `${{list.parent_title || ""}} ${{list.list_title}}`.toLowerCase().includes(query) || list.items.some((item) => matchesItem(item, query));
    }}
    function renderStats() {{
      const query = state.query;
      const visibleLists = DATA.filter((list) => matchesList(list, query));
      const visibleItems = visibleLists.reduce((sum, list) => sum + list.items.filter((item) => matchesItem(item, query)).length, 0);
      statsBar.innerHTML = `
        <span class="chip">${{DATA.length}} Lists</span>
        <span class="chip">${{totalItems}} Items</span>
        <span class="chip">${{query ? `${{visibleItems}} Matches` : "Mobile First"}}</span>
      `;
    }}
    function renderHome() {{
      content.className = "content-stack collections";
      backButton.classList.remove("visible");
      screenTitle.textContent = state.query ? "Search Results" : homeTitle;
      screenSubtitle.textContent = state.query ? "Tech collections containing matching items." : homeSubtitle;
      const lists = DATA.filter((list) => matchesList(list, state.query));
      if (!lists.length) {{
        renderEmpty("No matches", "Try a different search term or clear the search.");
        return;
      }}
      content.innerHTML = lists.map((list, index) => {{
        const matchingItems = list.items.filter((item) => matchesItem(item, state.query));
        const previewItems = (state.query ? matchingItems : list.items).slice(0, 2);
        return `
          <button class="collection-card" type="button" data-list-index="${{DATA.indexOf(list)}}" style="animation-delay:${{Math.min(index * 22, 180)}}ms">
            <div class="card-top">
              <div>
                ${{list.parent_title ? `<p class="card-kicker">${{escapeHtml(list.parent_title)}}</p>` : ""}}
                <h2 class="collection-title">${{escapeHtml(list.list_title)}}</h2>
              </div>
              <span class="item-count">${{list.items.length}} items</span>
            </div>
            <ul class="preview-list">
              ${{previewItems.map((item) => `<li>${{escapeHtml(item.summary || item.name)}}</li>`).join("")}}
            </ul>
          </button>
        `;
      }}).join("");
      content.querySelectorAll("[data-list-index]").forEach((card) => {{
        card.addEventListener("click", () => {{
          state.currentList = Number(card.dataset.listIndex);
          state.activeItemIndex = 0;
          window.scrollTo({{ top: 0, behavior: "smooth" }});
          render();
        }});
      }});
    }}
    function extractShortcode(url) {{
      if (!url) return "";
      const match = String(url).match(/instagram\\.com\\/(?:reel|p)\\/([^/?#]+)/i);
      return match ? match[1] : "";
    }}
    function buildEmbedUrl(url) {{
      const shortcode = extractShortcode(url);
      return shortcode ? `https://www.instagram.com/reel/${{shortcode}}/embed/captioned/` : "";
    }}
    function renderBuyPanel(item) {{
      const bestBuyLink = item?.best_buy_link || "";
      const productName = item?.product_name || item?.name || "";
      const metaParts = [item?.product_brand || "", item?.product_model || "", item?.product_type || ""].filter(Boolean);
      const extraLinks = [
        item?.amazon_link ? `<a class="buy-link" href="${{escapeHtml(item.amazon_link)}}" target="_blank" rel="noopener noreferrer">Amazon</a>` : "",
        item?.flipkart_link ? `<a class="buy-link" href="${{escapeHtml(item.flipkart_link)}}" target="_blank" rel="noopener noreferrer">Flipkart</a>` : "",
        item?.nykaa_link ? `<a class="buy-link" href="${{escapeHtml(item.nykaa_link)}}" target="_blank" rel="noopener noreferrer">Nykaa</a>` : "",
      ].filter(Boolean).join("");

      if (!bestBuyLink) return "";

      return `
        <section class="buy-panel">
          <p class="buy-kicker">Buy Link</p>
          <h4 class="buy-title">${{escapeHtml(productName || "Product match found")}}</h4>
          ${{metaParts.length ? `<p class="buy-meta">${{escapeHtml(metaParts.join(" · "))}}</p>` : ""}}
          <div class="buy-actions">
            <a class="buy-link primary" href="${{escapeHtml(bestBuyLink)}}" target="_blank" rel="noopener noreferrer">Best Buy Link</a>
            ${{extraLinks}}
          </div>
        </section>
      `;
    }}
    function renderPreview(item, listTitle) {{
      const embedUrl = buildEmbedUrl(item?.url || "");
      const localVideoUrl = item?.local_video_url || "";
      const thumbnailUrl = item?.thumbnail_url || "";
      if (!item) {{
        return `
          <aside class="preview-panel">
            <div class="preview-frame-wrap">
              <div class="preview-placeholder">Hover or tap an item to preview its reel here.</div>
            </div>
            <div class="preview-body">
              <p class="preview-kicker">${{escapeHtml(listTitle)}}</p>
              <h3 class="preview-item-title">Nothing selected yet</h3>
            </div>
          </aside>
        `;
      }}
      return `
        <aside class="preview-panel">
          <div class="preview-frame-wrap">
            ${{
              localVideoUrl
                ? `<video class="preview-video" src="${{escapeHtml(localVideoUrl)}}" ${{thumbnailUrl ? `poster="${{escapeHtml(thumbnailUrl)}}"` : ""}} controls playsinline preload="metadata"></video>`
                : embedUrl
                ? `<iframe class="preview-iframe" src="${{escapeHtml(embedUrl)}}" loading="lazy" allowfullscreen></iframe>`
                : `<div class="preview-placeholder">Preview unavailable for this reel.</div>`
            }}
          </div>
          <div class="preview-body">
            <p class="preview-kicker">${{escapeHtml(listTitle)}}</p>
            <h3 class="preview-item-title">${{escapeHtml(item.name)}}</h3>
            <p class="preview-item-summary">${{escapeHtml(item.summary || "No summary available.")}}</p>
            ${{renderBuyPanel(item)}}
            <div class="preview-url">${{escapeHtml(item.url || "No reel URL available.")}}</div>
            <p class="preview-note">Move across the item list to switch the reel preview without leaving the page.</p>
          </div>
        </aside>
      `;
    }}
    function renderList() {{
      const list = DATA[state.currentList];
      const items = list.items.filter((item) => matchesItem(item, state.query));
      if (!items.length) state.activeItemIndex = 0;
      else if (state.activeItemIndex >= items.length) state.activeItemIndex = 0;
      const activeItem = items[state.activeItemIndex] || items[0] || null;
      content.className = "content-stack";
      backButton.classList.add("visible");
      screenTitle.textContent = list.list_title;
      screenSubtitle.textContent = `${{list.parent_title ? `${{list.parent_title}} · ` : ""}}${{items.length}} of ${{list.items.length}} items shown`;
      if (!items.length) {{
        content.innerHTML = `<div class="list-header"><h2 class="list-title">${{escapeHtml(list.list_title)}}</h2><p class="list-meta">No matching items.</p></div>`;
        renderEmpty("No items here", "Clear search or try a different keyword.", true);
        return;
      }}
      content.innerHTML = `
        <div class="list-layout">
          <div class="list-column">
            <div class="list-header">
              ${{list.parent_title ? `<p class="card-kicker">${{escapeHtml(list.parent_title)}}</p>` : ""}}
              <h2 class="list-title">${{escapeHtml(list.list_title)}}</h2>
              <p class="list-meta">${{items.length}} items · hover on desktop, tap on phone</p>
            </div>
            ${{items.map((item, index) => `
              <article class="item-card ${{index === state.activeItemIndex ? "active expanded" : ""}}" data-item-index="${{index}}" style="animation-delay:${{Math.min(index * 18, 180)}}ms">
                <button class="item-button" type="button" aria-expanded="${{index === state.activeItemIndex ? "true" : "false"}}">
                  <h3 class="item-name">${{escapeHtml(item.name)}}</h3>
                  <p class="item-summary">${{escapeHtml(item.summary || "No summary available.")}}</p>
                </button>
                <div class="item-extra">
                  <div class="item-extra-inner">
                    <div>${{escapeHtml(item.summary || "No additional text available.")}}</div>
                    <span class="item-hint">Preview opens beside this list</span>
                  </div>
                </div>
              </article>
            `).join("")}}
          </div>
          ${{renderPreview(activeItem, list.list_title)}}
        </div>
      `;
      content.querySelectorAll(".item-card").forEach((card) => {{
        const setActive = () => {{
          state.activeItemIndex = Number(card.dataset.itemIndex);
          renderList();
        }};
        card.addEventListener("mouseenter", setActive);
        card.addEventListener("focusin", setActive);
        card.querySelector(".item-button").addEventListener("click", setActive);
      }});
    }}
    function renderEmpty(title, message, append = false) {{
      const html = `<div class="empty-state"><div><h2>${{escapeHtml(title)}}</h2><p>${{escapeHtml(message)}}</p></div></div>`;
      if (append) content.insertAdjacentHTML("beforeend", html);
      else content.innerHTML = html;
    }}
    function render() {{
      renderStats();
      clearSearch.classList.toggle("visible", Boolean(state.query));
      if (state.currentList === null) renderHome();
      else renderList();
    }}
    searchInput.addEventListener("input", (event) => {{
      state.query = event.target.value.trim().toLowerCase();
      render();
    }});
    clearSearch.addEventListener("click", () => {{
      searchInput.value = "";
      state.query = "";
      render();
    }});
    backButton.addEventListener("click", () => {{
      state.currentList = null;
      state.activeItemIndex = 0;
      window.scrollTo({{ top: 0, behavior: "smooth" }});
      render();
    }});
    render();
  </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Render a mobile-first List Title -> Items -> Summary HTML app.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input CSV.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output HTML file.")
    parser.add_argument("--title", default="Knowledge Library", help="App title.")
    parser.add_argument("--subtitle", default="Tap a collection to open its items.", help="App subtitle.")
    args = parser.parse_args()

    collections = load_collections(args.input)
    html = render_html(collections, args.title, args.subtitle)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"Saved mobile app: {args.output}")
    print(f"Collections: {len(collections)}")
    print(f"Items: {sum(len(collection['items']) for collection in collections)}")


if __name__ == "__main__":
    main()
