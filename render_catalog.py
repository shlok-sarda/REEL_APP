import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = BASE_DIR / "final_output_TECH_accumulated.csv"
DEFAULT_OUTPUT = BASE_DIR / "accumulated_catalog_view.html"


def load_rows(input_path):
    with open(input_path, newline="", encoding="utf-8") as infile:
        return list(csv.DictReader(infile))


def normalize(value):
    return " ".join((value or "").strip().split())


def get_primary_value(row):
    primary = normalize(row.get("Primary Category"))
    if primary:
        return primary
    for key in ("Umbrella Folder", "Umbrella Category"):
        value = normalize(row.get(key))
        if value:
            return value
    return "All Categories"


def get_secondary_value(row):
    for key in ("Secondary Category", "Folder"):
        value = normalize(row.get(key))
        if value:
            return value
    return "General"


def build_catalog(rows):
    grouped = defaultdict(lambda: {"items": [], "secondary_counts": defaultdict(int), "urls": set()})

    for row in rows:
        primary = get_primary_value(row)
        secondary = get_secondary_value(row)
        item_name = normalize(row.get("Item Name")) or "Untitled Item"
        summary = normalize(row.get("Summary")) or "No summary available."
        url = normalize(row.get("URL"))

        if not primary or primary.upper() in {"ERROR", "FAILED"}:
            continue

        grouped[primary]["secondary_counts"][secondary] += 1
        if url:
            grouped[primary]["urls"].add(url)

        grouped[primary]["items"].append(
            {
                "name": item_name,
                "summary": summary,
                "url": url,
                "secondary": secondary,
            }
        )

    catalog = []
    for primary in sorted(grouped):
        block = grouped[primary]
        items = sorted(
            block["items"],
            key=lambda item: (item["name"].lower(), item["summary"].lower(), item["url"]),
        )
        top_secondary = sorted(
            block["secondary_counts"].items(),
            key=lambda row: (-row[1], row[0].lower()),
        )[:3]
        catalog.append(
            {
                "primary": primary,
                "item_count": len(items),
                "reel_count": len(block["urls"]),
                "secondary_count": len(block["secondary_counts"]),
                "top_secondary": [name for name, _ in top_secondary],
                "items": items,
            }
        )
    return catalog


def render_html(catalog, source_name):
    total_items = sum(section["item_count"] for section in catalog)
    total_reels = sum(section["reel_count"] for section in catalog)
    catalog_json = json.dumps(catalog)
    source_name = json.dumps(Path(source_name).name)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reel Catalog</title>
  <style>
    :root {{
      --bg: #f4eadf;
      --panel: rgba(255, 251, 246, 0.9);
      --card: #fffdfa;
      --line: rgba(24, 33, 38, 0.10);
      --ink: #182126;
      --muted: #627079;
      --accent: #b55d36;
      --accent-soft: rgba(181, 93, 54, 0.10);
      --teal: #2f7672;
      --teal-soft: rgba(47, 118, 114, 0.10);
      --shadow: 0 24px 56px rgba(43, 32, 24, 0.12);
      --shadow-sm: 0 14px 30px rgba(43, 32, 24, 0.08);
      --radius-xl: 30px;
      --radius-lg: 22px;
      --radius-md: 16px;
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, rgba(181,93,54,0.16), transparent 23%),
        radial-gradient(circle at top right, rgba(47,118,114,0.12), transparent 20%),
        linear-gradient(180deg, #f8f1e9 0%, var(--bg) 100%);
    }}

    .page {{
      width: min(1180px, calc(100vw - 24px));
      margin: 14px auto 40px;
    }}

    .hero {{
      padding: 30px;
      border: 1px solid var(--line);
      border-radius: 34px;
      background: var(--panel);
      box-shadow: var(--shadow);
      backdrop-filter: blur(14px);
    }}

    .kicker {{
      display: inline-block;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font: 700 11px/1 Arial, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    h1 {{
      margin: 16px 0 10px;
      font-size: clamp(2.2rem, 4.5vw, 4.4rem);
      line-height: 0.94;
      letter-spacing: -0.05em;
    }}

    .hero-copy {{
      margin: 0;
      max-width: 820px;
      color: var(--muted);
      font: 500 0.98rem/1.65 Arial, sans-serif;
    }}

    .stats {{
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 12px;
      margin-top: 20px;
    }}

    .stat {{
      padding: 16px 18px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.92);
    }}

    .stat-label {{
      color: var(--muted);
      font: 700 11px/1 Arial, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .stat-value {{
      margin-top: 9px;
      font-size: 1.6rem;
      line-height: 1;
    }}

    .toolbar {{
      position: sticky;
      top: 12px;
      z-index: 15;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      align-items: center;
      margin: 18px 0;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(255,251,246,0.88);
      box-shadow: var(--shadow-sm);
      backdrop-filter: blur(14px);
    }}

    .input, .button {{
      width: 100%;
      padding: 13px 14px;
      border: 1px solid rgba(24,33,38,0.10);
      border-radius: 14px;
      background: rgba(255,255,255,0.95);
      color: var(--ink);
      font: 600 0.92rem/1.2 Arial, sans-serif;
      outline: none;
    }}

    .button {{
      width: auto;
      cursor: pointer;
    }}

    .layout {{
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }}

    .browser, .detail {{
      border: 1px solid var(--line);
      border-radius: 28px;
      background: rgba(255,252,247,0.78);
      box-shadow: var(--shadow);
      backdrop-filter: blur(12px);
    }}

    .browser {{
      padding: 18px;
      position: sticky;
      top: 92px;
    }}

    .panel-title {{
      margin: 0 0 6px;
      font-size: 1.18rem;
    }}

    .panel-copy {{
      margin: 0 0 14px;
      color: var(--muted);
      font: 500 0.88rem/1.55 Arial, sans-serif;
    }}

    .category-list {{
      display: grid;
      gap: 12px;
    }}

    .category-button {{
      width: 100%;
      position: relative;
      overflow: hidden;
      padding: 16px 16px 15px;
      border: 1px solid rgba(24,33,38,0.07);
      border-radius: 22px;
      background:
        radial-gradient(circle at top right, rgba(181,93,54,0.10), transparent 34%),
        linear-gradient(180deg, rgba(255,255,255,0.99), rgba(255,247,241,0.97));
      box-shadow: 0 16px 28px rgba(43, 32, 24, 0.08);
      text-align: left;
      cursor: pointer;
      transition: transform 160ms ease, border-color 160ms ease, box-shadow 160ms ease;
    }}

    .category-button::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(255,255,255,0.34), transparent 55%);
      pointer-events: none;
    }}

    .category-button:hover {{
      transform: translateY(-2px);
      border-color: rgba(181,93,54,0.18);
      box-shadow: 0 22px 34px rgba(43, 32, 24, 0.11);
    }}

    .category-button.active {{
      border-color: rgba(181,93,54,0.32);
      background:
        radial-gradient(circle at top right, rgba(181,93,54,0.16), transparent 38%),
        linear-gradient(135deg, rgba(181,93,54,0.17), rgba(47,118,114,0.12));
      box-shadow: 0 24px 40px rgba(43, 32, 24, 0.14);
    }}

    .category-button.active .category-name {{
      color: #7c3d20;
    }}

    .category-button.active .category-meta {{
      color: rgba(24,33,38,0.74);
    }}

    .category-button.active .category-tags {{
      color: #245f5b;
    }}

    .category-name {{
      margin: 0;
      font-size: 1.06rem;
      line-height: 1.1;
      letter-spacing: -0.02em;
    }}

    .category-meta {{
      margin-top: 9px;
      color: var(--muted);
      font: 700 0.7rem/1.45 Arial, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .category-tags {{
      margin-top: 10px;
      color: var(--teal);
      font: 700 0.75rem/1.45 Arial, sans-serif;
      letter-spacing: 0.01em;
    }}

    .detail {{
      overflow: hidden;
    }}

    .detail-head {{
      padding: 24px 24px 18px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(135deg, rgba(181,93,54,0.12), rgba(47,118,114,0.10));
    }}

    .detail-kicker {{
      color: var(--accent);
      font: 700 11px/1 Arial, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .detail-head h2 {{
      margin: 10px 0 0;
      font-size: clamp(1.6rem, 2.2vw, 2.4rem);
      line-height: 0.98;
    }}

    .detail-meta {{
      margin-top: 12px;
      color: var(--muted);
      font: 600 0.82rem/1.55 Arial, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .items {{
      display: grid;
      gap: 12px;
      padding: 18px;
    }}

    .item {{
      padding: 15px 16px;
      border: 1px solid rgba(24,33,38,0.08);
      border-radius: 18px;
      background: var(--card);
      box-shadow: var(--shadow-sm);
    }}

    .item-name {{
      margin: 0;
      font-size: 1.02rem;
      line-height: 1.28;
    }}

    .item-summary {{
      margin: 7px 0 0;
      color: var(--muted);
      font: 500 0.91rem/1.55 Arial, sans-serif;
    }}

    .item-meta {{
      margin-top: 10px;
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
    }}

    .item-pill {{
      display: inline-flex;
      align-items: center;
      padding: 7px 10px;
      border-radius: 999px;
      background: var(--teal-soft);
      color: var(--teal);
      font: 700 0.7rem/1 Arial, sans-serif;
      letter-spacing: 0.05em;
      text-transform: uppercase;
    }}

    .item-link {{
      display: inline-flex;
      align-items: center;
      padding: 8px 11px;
      border-radius: 999px;
      border: 1px solid rgba(181,93,54,0.18);
      color: var(--accent);
      text-decoration: none;
      font: 700 0.72rem/1 Arial, sans-serif;
      letter-spacing: 0.06em;
      text-transform: uppercase;
    }}

    .item-url {{
      margin-top: 10px;
      color: var(--muted);
      font: 500 0.78rem/1.45 Arial, sans-serif;
      word-break: break-all;
    }}

    .empty {{
      padding: 32px 24px;
      color: var(--muted);
      font: 600 0.98rem/1.6 Arial, sans-serif;
      text-align: center;
    }}

    @media (max-width: 980px) {{
      .layout {{
        grid-template-columns: 1fr;
      }}

      .browser {{
        position: static;
      }}

      .stats {{
        grid-template-columns: 1fr;
      }}

      .toolbar {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <section class="hero">
      <div class="kicker">Standard View</div>
      <h1>Browse Your Reels By Main Category</h1>
      <p class="hero-copy">This page only shows your primary categories first. Click one category to open it, then browse the real saved items and open the reel URL directly from there.</p>
      <div class="stats">
        <div class="stat">
          <div class="stat-label">Source File</div>
          <div class="stat-value" id="source-name"></div>
        </div>
        <div class="stat">
          <div class="stat-label">Primary Categories</div>
          <div class="stat-value">{len(catalog)}</div>
        </div>
        <div class="stat">
          <div class="stat-label">Saved Items</div>
          <div class="stat-value">{total_items}</div>
        </div>
      </div>
    </section>

    <section class="toolbar">
      <input id="search" class="input" type="search" placeholder="Search categories, item names, summaries, or URLs">
      <button id="clear-search" class="button" type="button">Clear Search</button>
    </section>

    <section class="layout">
      <aside class="browser">
        <h2 class="panel-title">Primary Categories</h2>
        <p class="panel-copy">Pick one category and we will only show that section, so you can browse without the whole page dumping everything at once.</p>
        <div id="category-list" class="category-list"></div>
      </aside>

      <main id="detail-panel" class="detail"></main>
    </section>
  </div>

  <script>
    const sourceName = {source_name};
    const catalog = {catalog_json};
    const sourceNameNode = document.getElementById("source-name");
    const searchInput = document.getElementById("search");
    const clearButton = document.getElementById("clear-search");
    const categoryList = document.getElementById("category-list");
    const detailPanel = document.getElementById("detail-panel");

    sourceNameNode.textContent = sourceName;

    function escapeHtml(value) {{
      return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#39;");
    }}

    function titleCase(value) {{
      return value.replace(/\\w\\S*/g, (word) => word.charAt(0).toUpperCase() + word.slice(1));
    }}

    function matchesSection(section, query) {{
      if (!query) return true;
      const haystack = [
        section.primary,
        ...section.top_secondary,
        ...section.items.map((item) => item.name),
        ...section.items.map((item) => item.summary),
        ...section.items.map((item) => item.url),
      ].join(" ").toLowerCase();
      return haystack.includes(query);
    }}

    function visibleItems(section, query) {{
      if (!query) return section.items;
      return section.items.filter((item) => {{
        const haystack = [item.name, item.summary, item.url].join(" ").toLowerCase();
        return haystack.includes(query);
      }});
    }}

    function renderCategoryList(sections, activePrimary) {{
      categoryList.innerHTML = sections.map((section) => `
        <button class="category-button ${{section.primary === activePrimary ? "active" : ""}}" type="button" data-primary="${{escapeHtml(section.primary)}}">
          <h3 class="category-name">${{escapeHtml(titleCase(section.primary))}}</h3>
          <div class="category-meta">${{section.reel_count}} reels · ${{section.item_count}} items</div>
          <div class="category-tags">${{section.top_secondary.length ? section.top_secondary.map((tag) => titleCase(tag)).join(" · ") : "No subclusters yet"}}</div>
        </button>
      `).join("");

      document.querySelectorAll("[data-primary]").forEach((button) => {{
        button.addEventListener("click", () => {{
          renderApp(button.getAttribute("data-primary"));
        }});
      }});
    }}

    function renderDetail(section, query) {{
      if (!section) {{
        detailPanel.innerHTML = '<div class="empty">No category matched that search. Try a broader term.</div>';
        return;
      }}

      const items = visibleItems(section, query);
      detailPanel.innerHTML = `
        <div class="detail-head">
          <div class="detail-kicker">Primary Category</div>
          <h2>${{escapeHtml(titleCase(section.primary))}}</h2>
          <div class="detail-meta">${{section.reel_count}} reels · ${{section.item_count}} items total · ${{section.secondary_count}} backend subcategories</div>
        </div>
        <div class="items">
          ${{
            items.length
              ? items.map((item) => `
                  <article class="item">
                    <h3 class="item-name">${{escapeHtml(item.name)}}</h3>
                    <p class="item-summary">${{escapeHtml(item.summary)}}</p>
                    <div class="item-meta">
                      <span class="item-pill">Saved Item</span>
                      ${{
                        item.url
                          ? `<a class="item-link" href="${{escapeHtml(item.url)}}" target="_blank" rel="noreferrer">Open Reel</a>`
                          : ""
                      }}
                    </div>
                    ${{
                      item.url
                        ? `<div class="item-url">${{escapeHtml(item.url)}}</div>`
                        : ""
                    }}
                  </article>
                `).join("")
              : '<div class="empty">No items matched this search inside the selected category.</div>'
          }}
        </div>
      `;
    }}

    function renderApp(requestedPrimary = "") {{
      const query = searchInput.value.trim().toLowerCase();
      const filtered = catalog.filter((section) => matchesSection(section, query));
      const activePrimary = filtered.some((section) => section.primary === requestedPrimary)
        ? requestedPrimary
        : (filtered[0]?.primary || "");

      renderCategoryList(filtered, activePrimary);
      renderDetail(filtered.find((section) => section.primary === activePrimary), query);
    }}

    searchInput.addEventListener("input", () => renderApp());
    clearButton.addEventListener("click", () => {{
      searchInput.value = "";
      renderApp();
    }});

    renderApp(catalog[0]?.primary || "");
  </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Render an interactive HTML viewer for reel catalog CSV data.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT), help="Input CSV path.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Output HTML path.")
    args = parser.parse_args()

    rows = load_rows(args.input)
    catalog = build_catalog(rows)
    html = render_html(catalog, args.input)
    Path(args.output).write_text(html, encoding="utf-8")
    print(f"Saved HTML viewer: {args.output}")


if __name__ == "__main__":
    main()
