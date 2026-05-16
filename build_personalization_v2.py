from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.db.database import get_connection
from app.db.init_db import initialize_database
from app.services.personalization_v2.engine import PersonalizationV2Engine
from app.storage import user_storage_dir


def render_debug_html(snapshot: dict) -> str:
    titles_by_cluster = {row["cluster_node_id"]: row for row in snapshot.get("titles", [])}
    features_by_id = {row["reel_item_id"]: row for row in snapshot.get("features", [])}
    memberships_by_cluster = {}
    for membership in snapshot.get("memberships", []):
        memberships_by_cluster.setdefault(membership["cluster_node_id"], []).append(membership)

    clusters = [
        row
        for row in snapshot.get("nodes", [])
        if row.get("node_type") == "cluster" and int(row.get("save_count", 0) or 0) > 0
    ]
    clusters.sort(key=lambda row: (-row.get("save_count", 0), row.get("canonical_key", "")))

    nav_items = []
    detail_sections = []
    for index, cluster in enumerate(clusters, start=1):
        cluster_id = f"cluster-{index}"
        title_row = titles_by_cluster.get(cluster["id"], {})
        title = title_row.get("title") or cluster.get("display_hint") or "Untitled List"
        metadata = cluster.get("metadata_json") or {}
        members = []
        for membership in memberships_by_cluster.get(cluster["id"], []):
            feature = features_by_id.get(membership["reel_item_id"])
            if feature:
                members.append(feature)

        search_parts = [
            title,
            cluster.get("canonical_key", ""),
            metadata.get("canonical_domain", ""),
            metadata.get("top_location", ""),
            " ".join(metadata.get("top_subdomains", []) or []),
            " ".join(metadata.get("top_entities", []) or []),
        ]
        for member in members:
            search_parts.extend([
                member.get("item_name", ""),
                member.get("specific_category", ""),
                member.get("summary", ""),
            ])
        search_blob = html.escape(" | ".join(part for part in search_parts if part))

        nav_items.append(
            f"""
            <a class="nav-link" href="#{cluster_id}" data-search="{search_blob}">
              <span class="nav-link-title">{html.escape(title)}</span>
              <span class="nav-count">{cluster.get('save_count', 0)} items</span>
            </a>
            """.strip()
        )

        why_bullets = []
        if metadata.get("top_location"):
            why_bullets.append(f"This list is mainly tied to {metadata['top_location']}.")
        if metadata.get("top_subdomains"):
            why_bullets.append("Main pattern: " + ", ".join(metadata["top_subdomains"]) + ".")
        if metadata.get("intent_mode"):
            why_bullets.append("Main saved intent: " + metadata["intent_mode"].replace("_", " ") + ".")
        if metadata.get("proposed_action"):
            why_bullets.append("Engine thinks this may need a future " + metadata["proposed_action"].replace("_", " ") + " step.")
        if not why_bullets:
            why_bullets.append("These reels currently look more coherent together than apart.")

        signals = [
            ("Canonical Key", cluster.get("canonical_key") or "—"),
            ("Domain", metadata.get("canonical_domain") or "—"),
            ("Top Location", metadata.get("top_location") or "—"),
            ("Top Subdomains", ", ".join(metadata.get("top_subdomains", [])) or "—"),
            ("Intent Mode", metadata.get("intent_mode") or "—"),
            ("Item Type", metadata.get("item_type_mode") or "—"),
        ]

        items_html = []
        for member in members:
            url = member.get("url") or ""
            items_html.append(
                f"""
                <article class="item">
                  <div class="item-name">{html.escape(member.get("item_name") or "Untitled Reel")}</div>
                  <div class="item-meta">{html.escape(member.get("specific_category") or "No specific category")}</div>
                  <div class="item-summary">{html.escape(member.get("summary") or "No summary available.")}</div>
                  <div class="item-url"><a href="{html.escape(url)}" target="_blank" rel="noreferrer">Open reel</a></div>
                </article>
                """.strip()
            )

        detail_sections.append(
            f"""
            <section class="detail-card" id="{cluster_id}" data-search="{search_blob}">
              <div class="detail-head">
                <div class="detail-title-row">
                  <div class="detail-title">
                    <span class="pill">Generated List</span>
                    {html.escape(title)}
                    {f'<span class="pill warm-pill">{html.escape(str(metadata.get("proposed_action", "")).replace("_", " "))}</span>' if metadata.get("proposed_action") else ""}
                  </div>
                  <div class="nav-count">{cluster.get("save_count", 0)} items</div>
                </div>
                <div class="detail-meta">
                  {cluster.get("save_count", 0)} reels inside this list · Confidence {float(cluster.get("confidence", 0.0)):.2f} · Title confidence {float(title_row.get("title_confidence", 0.0)):.2f}
                </div>
              </div>
              <div class="sections">
                <section class="section-card">
                  <h3>Items in this list</h3>
                  <div class="top-items">
                    {''.join(items_html) if items_html else '<div class="empty">No items assigned.</div>'}
                  </div>
                </section>
                <details class="debug">
                  <summary>Show why the engine made this list</summary>
                  <div class="sections" style="padding-top:14px">
                    <section class="section-card">
                      <h3>Why this list exists</h3>
                      <div class="bullets">
                        {''.join(f'<div class="bullet">{html.escape(bullet)}</div>' for bullet in why_bullets)}
                      </div>
                    </section>
                    <section class="section-card">
                      <h3>What the engine thinks this is</h3>
                      <div class="signals">
                        {''.join(f'<div class="signal"><div class="signal-label">{html.escape(label)}</div><div class="signal-value">{html.escape(value)}</div></div>' for label, value in signals)}
                      </div>
                    </section>
                    <pre>{html.escape(json.dumps({
                        "canonical_key": cluster.get("canonical_key"),
                        "metadata": metadata,
                        "title_reason": title_row.get("generation_reason_json", {}),
                        "member_ids": [member.get("reel_item_id") for member in members],
                    }, ensure_ascii=False, indent=2))}</pre>
                  </div>
                </details>
              </div>
            </section>
            """.strip()
        )

    page = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Personalization V2 Viewer</title>
  <style>
    :root {{
      --bg: #f6f1e7;
      --panel: rgba(255, 251, 245, 0.92);
      --panel-strong: #fffdf9;
      --card: #ffffff;
      --line: rgba(38, 32, 24, 0.10);
      --ink: #182126;
      --muted: #60707a;
      --accent: #0f766e;
      --accent-soft: rgba(15, 118, 110, 0.12);
      --warm: #a16207;
      --warm-soft: rgba(161, 98, 7, 0.12);
      --shadow: 0 22px 48px rgba(52, 36, 16, 0.10);
      --shadow-sm: 0 12px 24px rgba(52, 36, 16, 0.08);
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif;
      background:
        radial-gradient(circle at top left, rgba(15,118,110,0.10), transparent 20%),
        radial-gradient(circle at top right, rgba(161,98,7,0.08), transparent 18%),
        linear-gradient(180deg, #fbf7f0 0%, var(--bg) 100%);
    }}
    .page {{
      width: min(1380px, calc(100vw - 26px));
      margin: 14px auto 40px;
    }}
    .hero {{
      padding: 28px;
      border: 1px solid var(--line);
      border-radius: 28px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: clamp(2rem, 4vw, 3.4rem);
      line-height: 0.96;
      letter-spacing: -0.04em;
    }}
    p {{
      margin: 0;
      color: var(--muted);
      line-height: 1.55;
      max-width: 980px;
    }}
    .stats {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 12px;
      margin-top: 18px;
    }}
    .stat {{
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255,255,255,0.92);
      box-shadow: var(--shadow-sm);
    }}
    .label {{
      font-size: 0.76rem;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
    }}
    .value {{
      margin-top: 6px;
      font-size: 1.35rem;
      font-weight: 800;
    }}
    .toolbar {{
      position: sticky;
      top: 12px;
      z-index: 10;
      display: grid;
      grid-template-columns: 1fr auto;
      gap: 12px;
      margin: 18px 0;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255, 251, 245, 0.88);
      box-shadow: var(--shadow-sm);
      backdrop-filter: blur(12px);
    }}
    input {{
      width: 100%;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff;
      color: var(--ink);
      font-size: 0.95rem;
    }}
    .count-chip {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 72px;
      padding: 0 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: #fff;
      font-weight: 700;
      color: var(--muted);
    }}
    .count-chip.dim {{
      opacity: 0.7;
    }}
    .layout {{
      display: grid;
      grid-template-columns: 320px minmax(0, 1fr);
      gap: 18px;
      align-items: start;
    }}
    .sidebar {{
      position: sticky;
      top: 92px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: var(--shadow-sm);
    }}
    .sidebar h2 {{
      margin: 0 0 8px;
      font-size: 1.08rem;
    }}
    .sidebar-copy {{
      margin: 0 0 14px;
      color: var(--muted);
      font-size: 0.92rem;
      line-height: 1.45;
    }}
    .nav {{
      display: grid;
      gap: 8px;
    }}
    .nav-link {{
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: center;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255,255,255,0.92);
      color: var(--ink);
      text-decoration: none;
      font-weight: 700;
    }}
    .nav-link:hover {{
      border-color: rgba(15,118,110,0.28);
    }}
    .nav-link.is-hidden,
    .detail-card.is-hidden {{
      display: none;
    }}
    .nav-count,
    .pill {{
      display: inline-block;
      padding: 4px 9px;
      border-radius: 999px;
      font-size: 0.72rem;
      font-weight: 700;
    }}
    .nav-count {{
      color: var(--muted);
      background: rgba(96,112,122,0.08);
    }}
    .pill {{
      color: var(--accent);
      background: var(--accent-soft);
    }}
    .warm-pill {{
      color: var(--warm);
      background: var(--warm-soft);
    }}
    .main {{
      min-width: 0;
    }}
    .detail-card {{
      border: 1px solid var(--line);
      border-radius: 24px;
      background: var(--panel);
      box-shadow: var(--shadow);
      overflow: hidden;
    }}
    .detail-head {{
      padding: 20px;
      border-bottom: 1px solid var(--line);
      background: linear-gradient(180deg, rgba(255,255,255,0.55) 0%, rgba(255,255,255,0.20) 100%);
    }}
    .detail-title-row {{
      display: flex;
      justify-content: space-between;
      gap: 12px;
      align-items: center;
    }}
    .detail-title {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      font-size: 1.2rem;
      font-weight: 800;
    }}
    .detail-meta {{
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.93rem;
      line-height: 1.5;
    }}
    .sections {{
      display: grid;
      gap: 16px;
      padding: 18px 20px 20px;
    }}
    .section-card {{
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.84);
    }}
    .section-card h3 {{
      margin: 0 0 10px;
      font-size: 1rem;
    }}
    .bullets {{
      display: grid;
      gap: 8px;
    }}
    .bullet {{
      padding: 10px 12px;
      border: 1px solid var(--line);
      border-radius: 12px;
      background: rgba(250,246,240,0.65);
    }}
    .signals {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }}
    .top-items {{
      display: grid;
      gap: 12px;
    }}
    .signal {{
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255,255,255,0.84);
    }}
    .signal .signal-label {{
      color: var(--muted);
      font-size: 0.75rem;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
    }}
    .signal .signal-value {{
      font-weight: 700;
      line-height: 1.45;
    }}
    .items {{
      display: grid;
      gap: 12px;
    }}
    .item {{
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 16px;
      background: rgba(255,255,255,0.88);
    }}
    .item-name {{
      font-weight: 800;
    }}
    .item-meta {{
      margin-top: 4px;
      color: var(--warm);
      font-size: 0.84rem;
      font-weight: 700;
    }}
    .item-summary {{
      margin-top: 6px;
      color: var(--muted);
      line-height: 1.5;
      font-size: 0.93rem;
    }}
    .item-url {{
      margin-top: 8px;
      font-size: 0.88rem;
    }}
    .item-url a {{
      color: var(--accent);
      text-decoration: none;
      font-weight: 700;
    }}
    details.debug {{
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255,255,255,0.78);
      overflow: hidden;
    }}
    details.debug summary {{
      cursor: pointer;
      padding: 12px 14px;
      font-weight: 700;
      list-style: none;
    }}
    details.debug summary::-webkit-details-marker {{
      display: none;
    }}
    pre {{
      margin: 0;
      padding: 0 14px 14px;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: ui-monospace, monospace;
      color: var(--muted);
      font-size: 0.85rem;
    }}
    .empty {{
      padding: 22px;
      border: 1px dashed var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.78);
      color: var(--muted);
      text-align: center;
    }}
    .list-button {{
      width: 100%;
      text-align: left;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 14px;
      background: rgba(255,255,255,0.92);
      color: var(--ink);
      font: inherit;
      cursor: pointer;
      box-shadow: var(--shadow-sm);
    }}
    .list-button.active {{
      border-color: rgba(15,118,110,0.32);
      background: rgba(15,118,110,0.08);
    }}
    .list-button-title {{
      font-weight: 800;
      line-height: 1.3;
    }}
    .list-button-meta {{
      margin-top: 6px;
      color: var(--muted);
      font-size: 0.85rem;
    }}
    @media (max-width: 1100px) {{
      .stats {{
        grid-template-columns: repeat(3, minmax(0, 1fr));
      }}
      .layout {{
        grid-template-columns: 1fr;
      }}
      .sidebar {{
        position: static;
      }}
      .signals {{
        grid-template-columns: 1fr;
      }}
    }}
    @media (max-width: 720px) {{
      .stats {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
      .toolbar {{
        grid-template-columns: 1fr;
      }}
    }}
  </style>
</head>
<body>
  <div class="page">
    <div class="hero">
      <h1>Personalization V2 Viewer</h1>
      <p>This is the new parallel graph-backed engine preview built from your saved reel export. It does not affect the live app yet. Each card below is one generated cluster with its current title, signals, and assigned reels.</p>
      <div class="stats">
        <div class="stat"><div class="label">Features</div><div class="value">__FEATURE_COUNT__</div></div>
        <div class="stat"><div class="label">Nodes</div><div class="value">__NODE_COUNT__</div></div>
        <div class="stat"><div class="label">Edges</div><div class="value">__EDGE_COUNT__</div></div>
        <div class="stat"><div class="label">Memberships</div><div class="value">__MEMBERSHIP_COUNT__</div></div>
        <div class="stat"><div class="label">Titles</div><div class="value">__TITLE_COUNT__</div></div>
      </div>
    </div>
    <div class="toolbar">
      <input id="viewer-search" type="search" placeholder="Search for a reel, list, location, or category..." autocomplete="off" />
      <div id="search-count" class="count-chip">__TITLE_COUNT__ lists</div>
    </div>
    <div class="layout">
      <aside class="sidebar">
        <h2>Generated Lists</h2>
        <p class="sidebar-copy">Click any generated list here. The right side shows the actual reels inside that list first, and the engine reasoning stays hidden below.</p>
        <div id="sidebar-count" class="count-chip">__TITLE_COUNT__ lists</div>
        <nav class="nav">__NAV__</nav>
      </aside>
      <main class="main">__DETAILS__</main>
    </div>
  </div>
  <script>
    (() => {
      const input = document.getElementById('viewer-search');
      const navLinks = Array.from(document.querySelectorAll('.nav-link'));
      const searchCount = document.getElementById('search-count');
      const sidebarCount = document.getElementById('sidebar-count');

      function updateCount(value) {
        const label = `${value} list${value === 1 ? '' : 's'}`;
        searchCount.textContent = label;
        sidebarCount.textContent = label;
        searchCount.classList.toggle('dim', value === 0);
        sidebarCount.classList.toggle('dim', value === 0);
      }

      function applyFilter() {
        const term = (input.value || '').trim().toLowerCase();
        let visible = 0;
        navLinks.forEach((link) => {
          const matches = !term || (link.dataset.search || '').toLowerCase().includes(term);
          link.classList.toggle('is-hidden', !matches);
          const targetId = link.getAttribute('href');
          const card = targetId ? document.querySelector(targetId) : null;
          if (card) {
            card.classList.toggle('is-hidden', !matches);
          }
          if (matches) visible += 1;
        });
        updateCount(visible);
      }

      input.addEventListener('input', applyFilter);
      applyFilter();
    })();
  </script>
</body>
</html>"""
    rendered = (
        page
        .replace("__FEATURE_COUNT__", str(snapshot["feature_count"]))
        .replace("__NODE_COUNT__", str(snapshot["node_count"]))
        .replace("__EDGE_COUNT__", str(snapshot["edge_count"]))
        .replace("__MEMBERSHIP_COUNT__", str(snapshot["membership_count"]))
        .replace("__TITLE_COUNT__", str(snapshot["title_count"]))
        .replace("__NAV__", "\n".join(nav_items))
        .replace("__DETAILS__", "\n".join(detail_sections) if detail_sections else '<div class="empty">No generated lists available.</div>')
    )
    return rendered.replace("{{", "{").replace("}}", "}")


def bootstrap_export_user(export_json: Path, user_id: str) -> None:
    payload = json.loads(export_json.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])

    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO users (
                id, telegram_user_id, display_name, created_at, google_sub, email,
                picture_url, telegram_username, last_login_at, updated_at
            )
            VALUES (?, ?, ?, datetime('now'), NULL, '', '', '', '', datetime('now'))
            """,
            (user_id, user_id, f"Bootstrap {user_id}"),
        )
        reel_ids = [
            row["id"]
            for row in connection.execute("SELECT id FROM reels WHERE user_id = ?", (user_id,)).fetchall()
        ]
        if reel_ids:
            placeholders = ",".join("?" for _ in reel_ids)
            reel_item_ids = [
                row["id"]
                for row in connection.execute(
                    f"SELECT id FROM reel_items WHERE reel_id IN ({placeholders})",
                    reel_ids,
                ).fetchall()
            ]
            if reel_item_ids:
                item_placeholders = ",".join("?" for _ in reel_item_ids)
                connection.execute(f"DELETE FROM product_links WHERE reel_item_id IN ({item_placeholders})", reel_item_ids)
            connection.execute("DELETE FROM reel_items WHERE reel_id IN (" + placeholders + ")", reel_ids)
            connection.execute("DELETE FROM processing_jobs WHERE reel_id IN (" + placeholders + ")", reel_ids)
            connection.execute("DELETE FROM reels WHERE user_id = ?", (user_id,))

        grouped_rows: dict[str, list[dict]] = {}
        ordered_keys: list[str] = []
        for index, row in enumerate(rows, start=1):
            url = (row.get("URL") or "").strip()
            group_key = url or f"missing-url-{index:03d}"
            if group_key not in grouped_rows:
                grouped_rows[group_key] = []
                ordered_keys.append(group_key)
            grouped_rows[group_key].append(row)

        for index, group_key in enumerate(ordered_keys, start=1):
            group = grouped_rows[group_key]
            sample_row = group[0]
            url = (sample_row.get("URL") or "").strip()
            reel_id = f"{user_id}_bootstrap_{index:03d}"
            connection.execute(
                """
                INSERT INTO reels (
                    id, user_id, url, shortcode, received_at, status, media_status,
                    local_video_path, thumbnail_path, source, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, datetime('now'), 'completed', 'bootstrap', '', '', 'bootstrap', datetime('now'), datetime('now'))
                """,
                (reel_id, user_id, url, reel_id),
            )

            for row in group:
                primary = (row.get("Primary Category") or "").strip()
                secondary = (row.get("Secondary Category") or "").strip()
                item_name = (row.get("Item Name") or "").strip()
                summary = (row.get("Summary") or "").strip()
                cursor = connection.execute(
                    """
                    INSERT INTO reel_items (
                        reel_id, primary_category, secondary_category, item_name, summary, created_at
                    )
                    VALUES (?, ?, ?, ?, ?, datetime('now'))
                    """,
                    (reel_id, primary, secondary, item_name, summary),
                )
                reel_item_id = cursor.lastrowid
                if (row.get("Contains Product") or "").strip().lower() == "yes" or (row.get("Product Name") or "").strip():
                    connection.execute(
                        """
                        INSERT INTO product_links (
                            reel_item_id, product_name, brand, model, product_type, search_query,
                            best_buy_link, amazon_link, flipkart_link, nykaa_link
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            reel_item_id,
                            (row.get("Product Name") or "").strip(),
                            (row.get("Product Brand") or "").strip(),
                            (row.get("Product Model") or "").strip(),
                            (row.get("Product Type") or "").strip(),
                            (row.get("Product Search Query") or "").strip(),
                            (row.get("Best Buy Link") or "").strip(),
                            (row.get("Amazon Link") or "").strip(),
                            (row.get("Flipkart Link") or "").strip(),
                            (row.get("Nykaa Link") or "").strip(),
                        ),
                    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the parallel personalization v2 graph snapshot.")
    parser.add_argument("--user-id", default="default")
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument("--bootstrap-export-json", type=Path, default=None)
    parser.add_argument("--heuristic-only", action="store_true")
    args = parser.parse_args()

    initialize_database()
    if args.bootstrap_export_json:
        bootstrap_export_user(args.bootstrap_export_json, args.user_id)
    output_dir = args.output_dir or (user_storage_dir(args.user_id) / "personalization_v2")
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = PersonalizationV2Engine()
    snapshot = engine.backfill_user(
        args.user_id,
        use_llm=not args.heuristic_only,
        use_remote_embeddings=not args.heuristic_only,
    )

    snapshot_path = output_dir / "graph_snapshot.json"
    html_path = output_dir / "graph_snapshot.html"
    snapshot_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
    html_path.write_text(render_debug_html(snapshot), encoding="utf-8")

    print(json.dumps(
        {
            "ok": True,
            "user_id": args.user_id,
            "output_dir": str(output_dir),
            "snapshot_json": str(snapshot_path),
            "snapshot_html": str(html_path),
            "feature_count": snapshot["feature_count"],
            "node_count": snapshot["node_count"],
            "membership_count": snapshot["membership_count"],
            "heuristic_only": args.heuristic_only,
        },
        ensure_ascii=False,
        indent=2,
    ))


if __name__ == "__main__":
    main()
