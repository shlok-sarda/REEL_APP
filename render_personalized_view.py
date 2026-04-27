import argparse
import json
from collections import defaultdict
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
INPUT_JSON = BASE_DIR / "personalized_view.json"
GRAPH_JSON = BASE_DIR / "topic_graph.json"
OUTPUT_HTML = BASE_DIR / "personalized_catalog_view.html"


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def normalize(value):
    return " ".join((value or "").strip().split())


def build_grouped_view(view, graph):
    reels_by_topic = defaultdict(list)
    for reel in graph.get("reels", []):
        for topic_id in reel.get("topic_ids", []):
            reels_by_topic[topic_id].append(reel)

    sections = []
    for section in view.get("sections", []):
        groups = []
        for group in section.get("display_groups", []):
            seen = set()
            items = []
            reel_urls = set()

            for topic in group.get("topics", []):
                topic_id = topic.get("id")
                for reel in reels_by_topic.get(topic_id, []):
                    reel_urls.add(reel.get("url", ""))
                    for item in reel.get("items", []):
                        key = (reel.get("url", ""), normalize(item.get("name")), normalize(item.get("summary")))
                        if key in seen:
                            continue
                        seen.add(key)
                        items.append(
                            {
                                "name": normalize(item.get("name")) or "Untitled Item",
                                "summary": normalize(item.get("summary")) or "No summary available.",
                                "url": normalize(reel.get("url")),
                                "topic_name": normalize(topic.get("name")),
                            }
                        )

            groups.append(
                {
                    "name": group.get("name", "Personalized Group"),
                    "topic_count": group.get("stats", {}).get("topic_count", len(group.get("topics", []))),
                    "reel_count": len([url for url in reel_urls if url]),
                    "items": sorted(items, key=lambda row: (row["name"].lower(), row["summary"].lower(), row["url"])),
                }
            )

        sections.append(
            {
                "primary": section.get("umbrella_name", "All Categories"),
                "mode": section.get("personalization_mode", "collapsed"),
                "group_count": len(groups),
                "reel_count": section.get("stats", {}).get("unique_reel_count", 0),
                "groups": groups,
            }
        )

    return sections


def render_html(sections, source_name):
    total_groups = sum(section["group_count"] for section in sections)
    total_items = sum(len(group["items"]) for section in sections for group in section["groups"])
    sections_json = json.dumps(sections)
    source_name = json.dumps(Path(source_name).name)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Personalized Reel View</title>
  <style>
    :root {{
      --bg: #f3ebdf;
      --panel: rgba(255,252,247,0.88);
      --card: #fffdfa;
      --line: rgba(24,33,38,0.10);
      --ink: #182126;
      --muted: #60707a;
      --accent: #b55d36;
      --accent-soft: rgba(181,93,54,0.12);
      --teal: #2f7672;
      --teal-soft: rgba(47,118,114,0.10);
      --shadow: 0 24px 56px rgba(42,32,24,0.12);
      --shadow-sm: 0 14px 30px rgba(42,32,24,0.08);
    }}

    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: Georgia, "Times New Roman", serif;
      background:
        radial-gradient(circle at top left, rgba(181,93,54,0.14), transparent 24%),
        radial-gradient(circle at top right, rgba(47,118,114,0.13), transparent 18%),
        linear-gradient(180deg, #f8f1e8 0%, var(--bg) 100%);
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
      backdrop-filter: blur(12px);
    }}

    .tag {{
      display: inline-block;
      padding: 8px 12px;
      border-radius: 999px;
      background: var(--accent-soft);
      color: var(--accent);
      font: 700 11px/1 Arial, sans-serif;
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    h1 {{
      margin: 16px 0 10px;
      font-size: clamp(2.2rem, 4.4vw, 4.3rem);
      line-height: 0.94;
      letter-spacing: -0.05em;
    }}

    .hero p {{
      margin: 0;
      max-width: 820px;
      color: var(--muted);
      font: 500 0.97rem/1.65 Arial, sans-serif;
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
      letter-spacing: 0.08em;
      text-transform: uppercase;
    }}

    .stat-value {{
      margin-top: 8px;
      font-size: 1.55rem;
      line-height: 1;
    }}

    .toolbar {{
      position: sticky;
      top: 12px;
      z-index: 10;
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
      background: rgba(255,252,247,0.80);
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

    .section-list {{
      display: grid;
      gap: 12px;
    }}

    .section-button {{
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

    .section-button::before {{
      content: "";
      position: absolute;
      inset: 0;
      background: linear-gradient(135deg, rgba(255,255,255,0.34), transparent 55%);
      pointer-events: none;
    }}

    .section-button:hover {{
      transform: translateY(-2px);
      border-color: rgba(181,93,54,0.18);
      box-shadow: 0 22px 34px rgba(43, 32, 24, 0.11);
    }}

    .section-button.active {{
      border-color: rgba(181,93,54,0.32);
      background:
        radial-gradient(circle at top right, rgba(181,93,54,0.16), transparent 38%),
        linear-gradient(135deg, rgba(181,93,54,0.17), rgba(47,118,114,0.12));
      box-shadow: 0 24px 40px rgba(43, 32, 24, 0.14);
    }}

    .section-button.active .section-name {{
      color: #7c3d20;
    }}

    .section-button.active .section-meta {{
      color: rgba(24,33,38,0.74);
    }}

    .section-name {{
      margin: 0;
      font-size: 1.06rem;
      line-height: 1.1;
      letter-spacing: -0.02em;
    }}

    .section-meta {{
      margin-top: 9px;
      color: var(--muted);
      font: 700 0.7rem/1.45 Arial, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.08em;
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

    .groups {{
      display: grid;
      gap: 14px;
      padding: 18px;
    }}

    .group {{
      border: 1px solid rgba(24,33,38,0.08);
      border-radius: 20px;
      background: var(--card);
      box-shadow: var(--shadow-sm);
      overflow: hidden;
    }}

    .group-head {{
      padding: 14px 16px;
      border-bottom: 1px solid rgba(24,33,38,0.06);
      background: linear-gradient(135deg, rgba(181,93,54,0.10), rgba(47,118,114,0.08));
    }}

    .group-kicker {{
      color: var(--teal);
      font: 700 10px/1 Arial, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}

    .group-head h3 {{
      margin: 8px 0 0;
      font-size: 1.05rem;
      line-height: 1.15;
    }}

    .group-meta {{
      margin-top: 8px;
      color: var(--muted);
      font: 600 0.75rem/1.45 Arial, sans-serif;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}

    .items {{
      display: grid;
      gap: 10px;
      padding: 14px;
    }}

    .item {{
      padding: 14px 15px;
      border: 1px solid rgba(24,33,38,0.08);
      border-radius: 16px;
      background: rgba(255,255,255,0.92);
    }}

    .item-name {{
      margin: 0;
      font-size: 1rem;
      line-height: 1.28;
    }}

    .item-summary {{
      margin: 7px 0 0;
      color: var(--muted);
      font: 500 0.9rem/1.55 Arial, sans-serif;
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
      <div class="tag">Personalized View</div>
      <h1>Browse The Same Reels With Personalized Groups</h1>
      <p>This page still starts from the primary categories, but inside each category the items are regrouped into personalized clusters when the density is high enough. You can still see the real item names and open the reel URLs directly.</p>
      <div class="stats">
        <div class="stat">
          <div class="stat-label">Source File</div>
          <div class="stat-value" id="source-name"></div>
        </div>
        <div class="stat">
          <div class="stat-label">Personalized Groups</div>
          <div class="stat-value">{total_groups}</div>
        </div>
        <div class="stat">
          <div class="stat-label">Visible Items</div>
          <div class="stat-value">{total_items}</div>
        </div>
      </div>
    </section>

    <section class="toolbar">
      <input id="search" class="input" type="search" placeholder="Search categories, personalized groups, items, or URLs">
      <button id="clear-search" class="button" type="button">Clear Search</button>
    </section>

    <section class="layout">
      <aside class="browser">
        <h2 class="panel-title">Primary Categories</h2>
        <p class="panel-copy">Choose one main category. The page will only show that category and its personalized grouping, instead of dumping every section at once.</p>
        <div id="section-list" class="section-list"></div>
      </aside>

      <main id="detail-panel" class="detail"></main>
    </section>
  </div>

  <script>
    const sourceName = {source_name};
    const sections = {sections_json};
    const sourceNameNode = document.getElementById("source-name");
    const searchInput = document.getElementById("search");
    const clearButton = document.getElementById("clear-search");
    const sectionList = document.getElementById("section-list");
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
        ...section.groups.map((group) => group.name),
        ...section.groups.flatMap((group) => group.items.map((item) => item.name)),
        ...section.groups.flatMap((group) => group.items.map((item) => item.summary)),
        ...section.groups.flatMap((group) => group.items.map((item) => item.url)),
      ].join(" ").toLowerCase();
      return haystack.includes(query);
    }}

    function filterGroups(groups, query) {{
      if (!query) return groups;
      return groups
        .map((group) => ({{
          ...group,
          items: group.items.filter((item) => [item.name, item.summary, item.url].join(" ").toLowerCase().includes(query)),
        }}))
        .filter((group) => group.name.toLowerCase().includes(query) || group.items.length > 0);
    }}

    function renderSectionList(filtered, activePrimary) {{
      sectionList.innerHTML = filtered.map((section) => `
        <button class="section-button ${{section.primary === activePrimary ? "active" : ""}}" type="button" data-primary="${{escapeHtml(section.primary)}}">
          <h3 class="section-name">${{escapeHtml(titleCase(section.primary))}}</h3>
          <div class="section-meta">${{section.reel_count}} reels · ${{section.group_count}} groups · ${{section.mode.replaceAll("_", " ")}}</div>
        </button>
      `).join("");

      document.querySelectorAll("[data-primary]").forEach((button) => {{
        button.addEventListener("click", () => renderApp(button.getAttribute("data-primary")));
      }});
    }}

    function renderDetail(section, query) {{
      if (!section) {{
        detailPanel.innerHTML = '<div class="empty">No personalized category matched that search. Try a broader term.</div>';
        return;
      }}

      const groups = filterGroups(section.groups, query);
      detailPanel.innerHTML = `
        <div class="detail-head">
          <div class="detail-kicker">Primary Category</div>
          <h2>${{escapeHtml(titleCase(section.primary))}}</h2>
          <div class="detail-meta">${{section.reel_count}} reels · ${{section.group_count}} personalized groups · mode: ${{section.mode.replaceAll("_", " ")}}</div>
        </div>
        <div class="groups">
          ${{
            groups.length
              ? groups.map((group) => `
                  <section class="group">
                    <div class="group-head">
                      <div class="group-kicker">Personalized Group</div>
                      <h3>${{escapeHtml(titleCase(group.name))}}</h3>
                      <div class="group-meta">${{group.reel_count}} reels · ${{group.topic_count}} backend topics · ${{group.items.length}} visible items</div>
                    </div>
                    <div class="items">
                      ${{
                        group.items.length
                          ? group.items.map((item) => `
                              <article class="item">
                                <h4 class="item-name">${{escapeHtml(item.name)}}</h4>
                                <p class="item-summary">${{escapeHtml(item.summary)}}</p>
                                <div class="item-meta">
                                  <span class="item-pill">${{escapeHtml(titleCase(item.topic_name))}}</span>
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
                          : '<div class="empty">No items matched this search inside the selected personalized group.</div>'
                      }}
                    </div>
                  </section>
                `).join("")
              : '<div class="empty">No personalized groups matched this search inside the selected category.</div>'
          }}
        </div>
      `;
    }}

    function renderApp(requestedPrimary = "") {{
      const query = searchInput.value.trim().toLowerCase();
      const filtered = sections.filter((section) => matchesSection(section, query));
      const activePrimary = filtered.some((section) => section.primary === requestedPrimary)
        ? requestedPrimary
        : (filtered[0]?.primary || "");

      renderSectionList(filtered, activePrimary);
      renderDetail(filtered.find((section) => section.primary === activePrimary), query);
    }}

    searchInput.addEventListener("input", () => renderApp());
    clearButton.addEventListener("click", () => {{
      searchInput.value = "";
      renderApp();
    }});

    renderApp(sections[0]?.primary || "");
  </script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description="Render an interactive personalized reel view.")
    parser.add_argument("--input", default=str(INPUT_JSON), help="Personalized view JSON input.")
    parser.add_argument("--graph", default=str(GRAPH_JSON), help="Topic graph JSON input.")
    parser.add_argument("--output", default=str(OUTPUT_HTML), help="Output HTML path.")
    args = parser.parse_args()

    view = load_json(args.input)
    graph = load_json(args.graph)
    sections = build_grouped_view(view, graph)
    Path(args.output).write_text(render_html(sections, args.input), encoding="utf-8")
    print(f"Saved HTML viewer: {args.output}")


if __name__ == "__main__":
    main()
