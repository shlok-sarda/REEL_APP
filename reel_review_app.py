import csv
import json
import sys
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from render_mobile_knowledge_app import load_collections


CATALOG_CSV = BASE_DIR / "saved_reels_accumulated.csv"
RAW_CSV = BASE_DIR / "saved_reels_output_v2.csv"
CLEANED_CSV = BASE_DIR / "saved_reels_cleaned.csv"
DELETED_CSV = BASE_DIR / "deleted_reels.csv"
CACHE_JSON = BASE_DIR / "cache.json"
REEL_STORE_DIR = BASE_DIR / "reel_store" / "reels"
HOST = "127.0.0.1"
PORT = 8765


def normalize(value):
    return " ".join((value or "").strip().split())


def shortcode_from_url(url):
    parsed = urlparse(normalize(url))
    parts = [part for part in parsed.path.split("/") if part]
    return parts[-1] if parts else normalize(url).rstrip("/")


def same_reel(url_a, url_b):
    return (
        normalize(url_a).rstrip("/") == normalize(url_b).rstrip("/")
        or shortcode_from_url(url_a) == shortcode_from_url(url_b)
    )


def read_csv(path):
    if not path.exists():
        return [], []
    with path.open(newline="", encoding="utf-8") as infile:
        reader = csv.DictReader(infile)
        return list(reader), reader.fieldnames or []


def write_csv(path, rows, fieldnames):
    with path.open("w", newline="", encoding="utf-8") as outfile:
        writer = csv.DictWriter(outfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_deleted_rows(url, removed_by_file):
    existing_rows, existing_fields = read_csv(DELETED_CSV)
    fields = existing_fields or [
        "Deleted At",
        "Source File",
        "URL",
        "Primary Category",
        "Secondary Category",
        "Umbrella Folder",
        "Folder",
        "Item Name",
        "Summary",
    ]

    deleted_at = datetime.now().isoformat(timespec="seconds")
    new_rows = []
    for source_file, rows in removed_by_file.items():
        for row in rows:
            new_rows.append(
                {
                    "Deleted At": deleted_at,
                    "Source File": source_file,
                    "URL": row.get("URL", url),
                    "Primary Category": row.get("Primary Category", ""),
                    "Secondary Category": row.get("Secondary Category", ""),
                    "Umbrella Folder": row.get("Umbrella Folder", ""),
                    "Folder": row.get("Folder", ""),
                    "Item Name": row.get("Item Name", ""),
                    "Summary": row.get("Summary", ""),
                }
            )

    write_csv(DELETED_CSV, existing_rows + new_rows, fields)


def remove_reel_from_csv(path, url):
    rows, fields = read_csv(path)
    if not rows:
        return []

    kept = []
    removed = []
    for row in rows:
        if same_reel(row.get("URL", ""), url):
            removed.append(row)
        else:
            kept.append(row)

    if removed:
        write_csv(path, kept, fields)

    return removed


def remove_from_cache_and_store(url):
    shortcode = shortcode_from_url(url)
    cache_removed = False
    store_removed = False

    if CACHE_JSON.exists():
        data = json.loads(CACHE_JSON.read_text(encoding="utf-8"))
        if shortcode in data:
            del data[shortcode]
            CACHE_JSON.write_text(json.dumps(data, indent=2), encoding="utf-8")
            cache_removed = True

    store_path = REEL_STORE_DIR / f"{shortcode}.json"
    if store_path.exists():
        store_path.unlink()
        store_removed = True

    return {
        "cache_removed": cache_removed,
        "store_removed": store_removed,
    }


def delete_reel(url):
    removed_by_file = {}
    for path in (CATALOG_CSV, RAW_CSV, CLEANED_CSV):
        removed = remove_reel_from_csv(path, url)
        if removed:
            removed_by_file[path.name] = removed

    if removed_by_file:
        append_deleted_rows(url, removed_by_file)

    cleanup = remove_from_cache_and_store(url)
    return {
        "deleted": bool(removed_by_file or cleanup["cache_removed"] or cleanup["store_removed"]),
        "url": url,
        "shortcode": shortcode_from_url(url),
        "removed_rows": {name: len(rows) for name, rows in removed_by_file.items()},
        **cleanup,
    }


def build_collections():
    return load_collections(CATALOG_CSV)


HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>Reel Review</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #08090b;
      --line: rgba(255, 255, 255, 0.11);
      --line-strong: rgba(255, 255, 255, 0.18);
      --text: #f4f6f8;
      --muted: #a7adb7;
      --soft: #737b89;
      --accent: #e8d7b7;
      --accent-2: #a7d8c9;
      --danger: #ff9b8e;
      --shadow: 0 24px 70px rgba(0, 0, 0, 0.38);
      --safe-top: env(safe-area-inset-top, 0px);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
    }

    * { box-sizing: border-box; }
    html { min-height: 100%; background: var(--bg); scroll-behavior: smooth; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--text);
      font-family: ui-rounded, "SF Pro Rounded", "Avenir Next", "Nunito Sans", system-ui, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(232, 215, 183, 0.16), transparent 28rem),
        radial-gradient(circle at top right, rgba(167, 216, 201, 0.12), transparent 22rem),
        linear-gradient(180deg, #11151b 0%, #08090b 46%, #07080a 100%);
      overflow-x: hidden;
    }

    button, input, a, iframe { -webkit-tap-highlight-color: transparent; }

    .shell {
      width: min(760px, 100%);
      min-height: 100vh;
      margin: 0 auto;
      padding: calc(18px + var(--safe-top)) 16px calc(34px + var(--safe-bottom));
    }

    header {
      position: sticky;
      top: 0;
      z-index: 20;
      margin: calc(-18px - var(--safe-top)) -16px 14px;
      padding: calc(16px + var(--safe-top)) 16px 14px;
      background: linear-gradient(180deg, rgba(8, 9, 11, 0.96), rgba(8, 9, 11, 0.78) 74%, transparent);
      backdrop-filter: blur(18px);
    }

    .top { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
    .back {
      display: none;
      align-items: center;
      justify-content: center;
      flex: 0 0 auto;
      width: 42px;
      height: 42px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.075);
      color: var(--text);
      cursor: pointer;
      font-size: 1.15rem;
      transition: transform 180ms ease;
    }
    .back.visible { display: inline-flex; }
    .back:active { transform: scale(0.94); }
    .kicker {
      margin: 0 0 6px;
      color: var(--accent-2);
      font-size: 0.72rem;
      font-weight: 850;
      letter-spacing: 0.12em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      font-size: clamp(1.8rem, 8vw, 3rem);
      line-height: 0.95;
      letter-spacing: -0.055em;
    }
    .subtitle { margin: 8px 0 0; color: var(--muted); font-size: 0.93rem; line-height: 1.45; }

    .search-wrap { position: relative; }
    .search-icon {
      position: absolute;
      left: 15px;
      top: 50%;
      transform: translateY(-50%);
      color: var(--soft);
      pointer-events: none;
    }
    .search {
      width: 100%;
      height: 48px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.075);
      color: var(--text);
      padding: 0 44px;
      font: 750 0.96rem/1 ui-rounded, "SF Pro Rounded", system-ui, sans-serif;
      outline: none;
      transition: border-color 180ms ease, background 180ms ease, box-shadow 180ms ease;
    }
    .search::placeholder { color: #777f8d; }
    .search:focus {
      border-color: rgba(232,215,183,0.34);
      background: rgba(255,255,255,0.095);
      box-shadow: 0 0 0 4px rgba(232,215,183,0.07);
    }
    .clear-search {
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
    }
    .clear-search.visible { display: block; }

    .chips {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding: 2px 0 4px;
      margin: 2px 0 14px;
      scrollbar-width: none;
    }
    .chips::-webkit-scrollbar { display: none; }
    .chip {
      flex: 0 0 auto;
      padding: 8px 11px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,0.055);
      color: var(--muted);
      font-size: 0.74rem;
      font-weight: 850;
    }

    .stack { display: grid; gap: 12px; animation: riseIn 420ms ease both; }
    @keyframes riseIn {
      from { opacity: 0; transform: translateY(10px); }
      to { opacity: 1; transform: translateY(0); }
    }

    .collection {
      position: relative;
      width: 100%;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 28px;
      background:
        radial-gradient(circle at top right, rgba(232,215,183,0.11), transparent 36%),
        linear-gradient(180deg, rgba(255,255,255,0.092), rgba(255,255,255,0.048));
      box-shadow: var(--shadow);
      color: inherit;
      padding: 18px;
      text-align: left;
      cursor: pointer;
      transition: transform 180ms ease, border-color 180ms ease, background 180ms ease;
    }
    .collection::before {
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(255,255,255,0.12), transparent 52%);
      pointer-events: none;
    }
    .collection:active { transform: scale(0.985); }
    @media (hover: hover) {
      .collection:hover {
        transform: translateY(-2px);
        border-color: rgba(232,215,183,0.24);
      }
    }
    .collection-top {
      position: relative;
      display: flex;
      justify-content: space-between;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 12px;
    }
    .collection-kicker {
      margin: 0 0 8px;
      color: var(--accent-2);
      font-size: 0.7rem;
      font-weight: 900;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }
    .collection-title {
      margin: 0;
      font-size: 1.12rem;
      line-height: 1.14;
      letter-spacing: -0.022em;
    }
    .count {
      flex: 0 0 auto;
      padding: 7px 9px;
      border-radius: 999px;
      background: rgba(167,216,201,0.12);
      color: var(--accent-2);
      font-size: 0.7rem;
      font-weight: 900;
      text-transform: uppercase;
    }
    .preview {
      display: grid;
      gap: 8px;
      margin: 0;
      padding: 0;
      list-style: none;
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.42;
    }

    .list-layout {
      display: grid;
      gap: 14px;
      align-items: start;
    }
    .list-column {
      min-width: 0;
      display: grid;
      gap: 12px;
    }
    .list-head {
      position: sticky;
      top: 112px;
      z-index: 10;
      margin: 0 -2px 12px;
      padding: 14px 2px 10px;
      background: linear-gradient(180deg, rgba(8,9,11,0.92), rgba(8,9,11,0.74), transparent);
      backdrop-filter: blur(10px);
    }
    .list-head h2 {
      margin: 0;
      font-size: 1.55rem;
      letter-spacing: -0.04em;
    }
    .list-meta { margin: 8px 0 0; color: var(--muted); font-size: 0.86rem; font-weight: 750; }

    .item {
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(255,255,255,0.064);
      overflow: hidden;
      box-shadow: 0 16px 34px rgba(0,0,0,0.18);
      transition: border-color 180ms ease, transform 180ms ease, background 180ms ease;
    }
    .item.active {
      border-color: rgba(232,215,183,0.34);
      background:
        radial-gradient(circle at top right, rgba(232,215,183,0.09), transparent 50%),
        rgba(255,255,255,0.078);
      transform: translateY(-1px);
    }
    .item-main {
      width: 100%;
      border: 0;
      background: transparent;
      color: inherit;
      text-align: left;
      padding: 16px;
      cursor: pointer;
    }
    .item-name { margin: 0; font-size: 1rem; line-height: 1.25; font-weight: 900; }
    .item-summary {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.45;
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }
    .item.expanded .item-summary { -webkit-line-clamp: unset; overflow: visible; }
    .extra {
      max-height: 0;
      overflow: hidden;
      opacity: 0;
      border-top: 1px solid transparent;
      transition: max-height 240ms ease, opacity 220ms ease, border-color 220ms ease;
    }
    .item.expanded .extra { max-height: 180px; opacity: 1; border-color: var(--line); }
    .extra-inner { padding: 0 16px 16px; color: var(--soft); font-size: 0.82rem; line-height: 1.5; }
    .item-hint {
      display: inline-flex;
      margin-top: 11px;
      color: var(--accent);
      font-size: 0.76rem;
      font-weight: 950;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }

    .preview-panel {
      position: sticky;
      top: 122px;
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 28px;
      background:
        radial-gradient(circle at top left, rgba(167,216,201,0.10), transparent 44%),
        linear-gradient(180deg, rgba(255,255,255,0.085), rgba(255,255,255,0.038));
      box-shadow: var(--shadow);
    }
    .preview-frame-wrap {
      position: relative;
      width: 100%;
      aspect-ratio: 0.66;
      background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0.02));
      border-bottom: 1px solid var(--line);
    }
    .preview-iframe {
      width: 100%;
      height: 100%;
      border: 0;
      background: #050607;
    }
    .preview-placeholder {
      position: absolute;
      inset: 0;
      display: grid;
      place-items: center;
      padding: 24px;
      text-align: center;
      color: var(--muted);
      font-size: 0.95rem;
      line-height: 1.5;
    }
    .preview-body {
      display: grid;
      gap: 12px;
      padding: 16px;
    }
    .preview-kicker {
      margin: 0;
      color: var(--accent-2);
      font-size: 0.72rem;
      font-weight: 900;
      letter-spacing: 0.11em;
      text-transform: uppercase;
    }
    .preview-title {
      margin: 0;
      font-size: 1.15rem;
      line-height: 1.08;
      letter-spacing: -0.035em;
    }
    .preview-summary {
      margin: 0;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.55;
    }
    .preview-url {
      word-break: break-all;
      color: var(--soft);
      font-size: 0.78rem;
      line-height: 1.45;
    }
    .actions {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
    }
    .delete {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 36px;
      border-radius: 999px;
      padding: 0 12px;
      font-size: 0.74rem;
      font-weight: 950;
      letter-spacing: 0.07em;
      text-transform: uppercase;
      text-decoration: none;
      cursor: pointer;
      border: 1px solid rgba(255,155,142,0.22);
      color: var(--danger);
      background: rgba(255,155,142,0.07);
    }
    .preview-note {
      margin: 0;
      color: var(--soft);
      font-size: 0.76rem;
      line-height: 1.45;
    }

    .empty {
      min-height: 42vh;
      display: grid;
      place-items: center;
      padding: 34px 18px;
      border: 1px dashed var(--line-strong);
      border-radius: 28px;
      background: rgba(255,255,255,0.045);
      text-align: center;
      color: var(--muted);
    }
    .toast {
      position: fixed;
      left: 50%;
      bottom: 18px;
      transform: translateX(-50%) translateY(12px);
      opacity: 0;
      z-index: 50;
      width: min(420px, calc(100vw - 28px));
      padding: 13px 14px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(20,22,27,0.94);
      box-shadow: var(--shadow);
      color: var(--text);
      font-size: 0.9rem;
      transition: opacity 0.18s ease, transform 0.18s ease;
    }
    .toast.visible {
      opacity: 1;
      transform: translateX(-50%) translateY(0);
    }

    @media (min-width: 760px) {
      .stack.collections { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .collection { min-height: 170px; }
      .list-layout {
        grid-template-columns: minmax(0, 1.08fr) minmax(300px, 0.92fr);
        gap: 18px;
      }
    }
    @media (max-width: 759px) {
      .preview-panel {
        position: relative;
        top: 0;
        order: -1;
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div class="top">
        <button id="backButton" class="back" type="button">‹</button>
        <div>
          <p class="kicker">Local Review App</p>
          <h1 id="title">Clean Your Reels</h1>
          <p id="subtitle" class="subtitle">Open a collection, preview reels beside the list, and delete noise from local files.</p>
        </div>
      </div>
      <div class="search-wrap">
        <span class="search-icon">⌕</span>
        <input id="search" class="search" type="search" placeholder="Search lists, items, summaries" />
        <button id="clearSearch" class="clear-search" type="button">×</button>
      </div>
    </header>
    <section id="chips" class="chips"></section>
    <section id="content" class="stack collections"></section>
  </main>
  <div id="toast" class="toast"></div>
  <script>
    let DATA = [];
    const state = { currentList: null, query: "", activeItemIndex: 0 };
    const content = document.getElementById("content");
    const chips = document.getElementById("chips");
    const search = document.getElementById("search");
    const clearSearch = document.getElementById("clearSearch");
    const backButton = document.getElementById("backButton");
    const title = document.getElementById("title");
    const subtitle = document.getElementById("subtitle");
    const toast = document.getElementById("toast");

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }

    function showToast(message) {
      toast.textContent = message;
      toast.classList.add("visible");
      setTimeout(() => toast.classList.remove("visible"), 2600);
    }

    function totalItems() {
      return DATA.reduce((sum, list) => sum + list.items.length, 0);
    }

    function matchesItem(item, query) {
      if (!query) return true;
      return `${item.name} ${item.summary} ${item.url || ""}`.toLowerCase().includes(query);
    }

    function matchesList(list, query) {
      if (!query) return true;
      return `${list.parent_title || ""} ${list.list_title}`.toLowerCase().includes(query) || list.items.some((item) => matchesItem(item, query));
    }

    async function loadData() {
      const response = await fetch("/api/data");
      DATA = await response.json();
      render();
    }

    function renderChips() {
      const visible = DATA.filter((list) => matchesList(list, state.query));
      chips.innerHTML = `
        <span class="chip">${DATA.length} Lists</span>
        <span class="chip">${totalItems()} Items</span>
        <span class="chip">${visible.length} Visible</span>
      `;
    }

    function extractShortcode(url) {
      if (!url) return "";
      const match = String(url).match(/instagram\.com\/(?:reel|p)\/([^/?#]+)/i);
      return match ? match[1] : "";
    }

    function buildEmbedUrl(url) {
      const shortcode = extractShortcode(url);
      return shortcode ? `https://www.instagram.com/reel/${shortcode}/embed/captioned/` : "";
    }

    function renderHome() {
      content.className = "stack collections";
      backButton.classList.remove("visible");
      title.textContent = state.query ? "Search Results" : "Clean Your Reels";
      subtitle.textContent = state.query ? "Collections matching your search." : "Open a collection, preview reels beside the list, and delete noise from local files.";
      const lists = DATA.filter((list) => matchesList(list, state.query));
      if (!lists.length) {
        content.innerHTML = '<div class="empty">No matches found.</div>';
        return;
      }
      content.innerHTML = lists.map((list) => {
        const preview = list.items.filter((item) => matchesItem(item, state.query)).slice(0, 2);
        return `
          <button class="collection" type="button" data-index="${DATA.indexOf(list)}">
            <div class="collection-top">
              <div>
                ${list.parent_title ? `<p class="collection-kicker">${escapeHtml(list.parent_title)}</p>` : ""}
                <h2 class="collection-title">${escapeHtml(list.list_title)}</h2>
              </div>
              <span class="count">${list.items.length} items</span>
            </div>
            <ul class="preview">
              ${preview.map((item) => `<li>${escapeHtml(item.summary || item.name)}</li>`).join("")}
            </ul>
          </button>
        `;
      }).join("");
      content.querySelectorAll("[data-index]").forEach((button) => {
        button.addEventListener("click", () => {
          state.currentList = Number(button.dataset.index);
          state.activeItemIndex = 0;
          window.scrollTo({ top: 0, behavior: "smooth" });
          render();
        });
      });
    }

    function renderPreview(list, item) {
      const embedUrl = buildEmbedUrl(item?.url || "");
      if (!item) {
        return `
          <aside class="preview-panel">
            <div class="preview-frame-wrap">
              <div class="preview-placeholder">Hover or tap an item to preview its reel here.</div>
            </div>
            <div class="preview-body">
              <p class="preview-kicker">${escapeHtml(list.parent_title || list.list_title)}</p>
              <h3 class="preview-title">Nothing selected yet</h3>
            </div>
          </aside>
        `;
      }
      return `
        <aside class="preview-panel">
          <div class="preview-frame-wrap">
            ${
              embedUrl
                ? `<iframe class="preview-iframe" src="${escapeHtml(embedUrl)}" loading="lazy" allowfullscreen></iframe>`
                : `<div class="preview-placeholder">Preview unavailable for this reel.</div>`
            }
          </div>
          <div class="preview-body">
            <p class="preview-kicker">${escapeHtml(list.parent_title || list.list_title)}</p>
            <h3 class="preview-title">${escapeHtml(item.name)}</h3>
            <p class="preview-summary">${escapeHtml(item.summary || "No summary available.")}</p>
            <div class="preview-url">${escapeHtml(item.url || "No reel URL available.")}</div>
            <div class="actions">
              ${item.url ? `<button class="delete" type="button" data-url="${escapeHtml(item.url)}">Delete Reel</button>` : ""}
            </div>
            <p class="preview-note">Delete removes this reel from local CSV files, cache, and reel store.</p>
          </div>
        </aside>
      `;
    }

    function renderList() {
      const list = DATA[state.currentList];
      const items = list.items.filter((item) => matchesItem(item, state.query));
      if (!items.length) state.activeItemIndex = 0;
      else if (state.activeItemIndex >= items.length) state.activeItemIndex = 0;
      const activeItem = items[state.activeItemIndex] || items[0] || null;
      content.className = "stack";
      backButton.classList.add("visible");
      title.textContent = list.list_title;
      subtitle.textContent = `${list.parent_title ? `${list.parent_title} · ` : ""}${items.length} of ${list.items.length} items shown`;
      if (!items.length) {
        content.innerHTML = `
          <div class="list-head">
            ${list.parent_title ? `<p class="collection-kicker">${escapeHtml(list.parent_title)}</p>` : ""}
            <h2>${escapeHtml(list.list_title)}</h2>
            <p class="list-meta">No matching items.</p>
          </div>
          <div class="empty">No items found for this search.</div>
        `;
        return;
      }
      content.innerHTML = `
        <div class="list-layout">
          <div class="list-column">
            <div class="list-head">
              ${list.parent_title ? `<p class="collection-kicker">${escapeHtml(list.parent_title)}</p>` : ""}
              <h2>${escapeHtml(list.list_title)}</h2>
              <p class="list-meta">${items.length} items · hover on desktop, tap on phone</p>
            </div>
            ${items.map((item, index) => `
              <article class="item ${index === state.activeItemIndex ? "active expanded" : ""}" data-item-index="${index}">
                <button class="item-main" type="button" aria-expanded="${index === state.activeItemIndex ? "true" : "false"}">
                  <h3 class="item-name">${escapeHtml(item.name)}</h3>
                  <p class="item-summary">${escapeHtml(item.summary || "No summary available.")}</p>
                </button>
                <div class="extra">
                  <div class="extra-inner">
                    <div>${escapeHtml(item.summary || "No additional text available.")}</div>
                    <span class="item-hint">Preview opens beside this list</span>
                  </div>
                </div>
              </article>
            `).join("")}
          </div>
          ${renderPreview(list, activeItem)}
        </div>
      `;

      content.querySelectorAll(".item").forEach((card) => {
        const setActive = () => {
          state.activeItemIndex = Number(card.dataset.itemIndex);
          renderList();
        };
        card.addEventListener("mouseenter", setActive);
        card.addEventListener("focusin", setActive);
        card.querySelector(".item-main").addEventListener("click", setActive);
      });

      content.querySelectorAll("[data-url]").forEach((button) => {
        button.addEventListener("click", async (event) => {
          event.stopPropagation();
          const url = button.dataset.url;
          if (!confirm("Delete this reel from local CSV/cache files?")) return;
          button.disabled = true;
          const response = await fetch("/api/delete", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ url })
          });
          const result = await response.json();
          if (!result.deleted) {
            showToast("Nothing was deleted. Reel may already be gone.");
            button.disabled = false;
            return;
          }
          showToast("Deleted reel from local files.");
          await loadData();
          if (state.currentList !== null && !DATA[state.currentList]) {
            state.currentList = null;
            state.activeItemIndex = 0;
          }
        });
      });
    }

    function render() {
      renderChips();
      clearSearch.classList.toggle("visible", Boolean(state.query));
      if (state.currentList === null) renderHome();
      else renderList();
    }

    search.addEventListener("input", () => {
      state.query = search.value.trim().toLowerCase();
      render();
    });

    clearSearch.addEventListener("click", () => {
      search.value = "";
      state.query = "";
      render();
    });

    backButton.addEventListener("click", () => {
      state.currentList = null;
      state.activeItemIndex = 0;
      window.scrollTo({ top: 0, behavior: "smooth" });
      render();
    });

    loadData();
  </script>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            body = HTML.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/api/data":
            self.send_json(build_collections())
            return
        self.send_error(404)

    def do_POST(self):
        if self.path != "/api/delete":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8")
        try:
            payload = json.loads(body)
            url = normalize(payload.get("url"))
            if not url:
                self.send_json({"deleted": False, "error": "Missing URL"}, 400)
                return
            self.send_json(delete_reel(url))
        except Exception as exc:
            self.send_json({"deleted": False, "error": str(exc)}, 500)

    def log_message(self, format, *args):
        return


def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Review app running: http://{HOST}:{PORT}")
    print("Press Control+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
