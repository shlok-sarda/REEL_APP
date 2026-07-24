from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import settings
from app.services.auth import create_login_csrf, current_user
from app.services.library import is_demo_user
from app.ui_ux.clipnest_v1 import build_clipnest_v1_html
from app.ui_ux.folders_page import build_folders_html


router = APIRouter(tags=["webapp"])


def build_legal_html(title: str, body_html: str) -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #07090c;
      --panel: rgba(255,255,255,0.06);
      --line: rgba(255,255,255,0.1);
      --text: #f4f6f8;
      --muted: #9ca4af;
      --accent: #eed7a6;
      --accent-2: #9fd5c5;
      --shadow: 0 24px 70px rgba(0,0,0,0.38);
    }}
    * {{ box-sizing:border-box; }}
    body {{
      margin:0;
      min-height:100vh;
      background:
        radial-gradient(circle at top left, rgba(238, 215, 166, 0.14), transparent 26rem),
        radial-gradient(circle at top right, rgba(159, 213, 197, 0.12), transparent 24rem),
        linear-gradient(180deg, #10141b 0%, #07090c 50%, #060709 100%);
      color:var(--text);
      font-family: ui-rounded, "SF Pro Rounded", "Avenir Next", system-ui, sans-serif;
      padding: 28px 16px 36px;
    }}
    .shell {{ width:min(860px, 100%); margin:0 auto; }}
    .card {{
      border:1px solid var(--line);
      border-radius:24px;
      background:linear-gradient(180deg, rgba(255,255,255,0.085), rgba(255,255,255,0.045));
      box-shadow: var(--shadow);
      padding:22px;
    }}
    .kicker {{ margin:0 0 8px; color:var(--accent-2); font-size:.72rem; font-weight:900; letter-spacing:.11em; text-transform:uppercase; }}
    h1 {{ margin:0 0 14px; font-size:clamp(1.6rem, 6vw, 2.4rem); line-height:1.02; letter-spacing:-.04em; }}
    h2 {{ margin:22px 0 8px; font-size:1.02rem; }}
    p, li {{ color:var(--muted); line-height:1.6; font-size:.95rem; }}
    a {{ color:var(--accent); }}
    ul {{ padding-left:18px; }}
  </style>
</head>
<body>
  <main class="shell">
    <section class="card">
      {body_html}
    </section>
  </main>
</body>
</html>"""


def build_demo_ui_review_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>Reel Organizer UI Review</title>
  <style>
    :root {
      --bg:#efe6d7;
      --card:#fffaf2;
      --ink:#1d1a16;
      --muted:#675f55;
      --line:rgba(29,26,22,0.12);
      --accent:#ca5b2e;
      --accent-2:#0d665b;
      --shadow:0 24px 50px rgba(48, 31, 14, 0.12);
      --safe-top:env(safe-area-inset-top, 0px);
      --safe-bottom:env(safe-area-inset-bottom, 0px);
    }
    * { box-sizing:border-box; }
    html, body {
      margin:0;
      min-height:100%;
      background:
        radial-gradient(circle at top left, rgba(202,91,46,0.12), transparent 18rem),
        radial-gradient(circle at bottom right, rgba(13,102,91,0.10), transparent 20rem),
        var(--bg);
      color:var(--ink);
      font-family:"Avenir Next", "SF Pro Display", ui-sans-serif, system-ui, sans-serif;
    }
    body { padding-bottom:calc(24px + var(--safe-bottom)); }
    .shell {
      width:min(1120px, 100%);
      margin:0 auto;
      padding:calc(22px + var(--safe-top)) 16px 28px;
      display:grid;
      gap:16px;
    }
    .hero {
      border:1px solid var(--line);
      border-radius:28px;
      background:rgba(255,250,242,0.88);
      box-shadow:var(--shadow);
      padding:20px;
    }
    .eyebrow {
      margin:0 0 10px;
      color:var(--accent-2);
      font-size:.75rem;
      font-weight:900;
      letter-spacing:.12em;
      text-transform:uppercase;
    }
    h1 {
      margin:0;
      font-size:clamp(2rem, 8vw, 4rem);
      line-height:.92;
      letter-spacing:-.06em;
    }
    .hero p {
      margin:12px 0 0;
      color:var(--muted);
      line-height:1.55;
      font-size:.97rem;
      max-width:52rem;
    }
    .hero-meta {
      display:flex;
      flex-wrap:wrap;
      gap:8px;
      margin-top:14px;
    }
    .chip {
      display:inline-flex;
      align-items:center;
      min-height:32px;
      padding:0 12px;
      border:1px solid var(--line);
      border-radius:999px;
      background:rgba(255,255,255,0.72);
      font-size:.78rem;
      font-weight:800;
      color:var(--muted);
    }
    .layout {
      display:grid;
      gap:16px;
    }
    .panel {
      border:1px solid var(--line);
      border-radius:28px;
      background:rgba(255,250,242,0.9);
      box-shadow:var(--shadow);
      overflow:hidden;
    }
    .panel-head {
      padding:16px 16px 12px;
      border-bottom:1px solid var(--line);
      background:linear-gradient(180deg, rgba(255,255,255,0.6), rgba(255,255,255,0.15));
    }
    .panel-head h2 {
      margin:0;
      font-size:1.05rem;
      letter-spacing:-.03em;
    }
    .panel-head p {
      margin:8px 0 0;
      color:var(--muted);
      font-size:.87rem;
      line-height:1.45;
    }
    .reel-grid {
      display:grid;
      gap:14px;
      padding:14px;
    }
    .reel-card {
      border:1px solid var(--line);
      border-radius:22px;
      background:rgba(255,255,255,0.66);
      overflow:hidden;
    }
    .video-frame {
      position:relative;
      aspect-ratio:.66;
      background:#0f1114;
    }
    .video-frame video, .video-frame img {
      width:100%;
      height:100%;
      object-fit:cover;
      display:block;
      background:#0f1114;
    }
    .video-badge {
      position:absolute;
      left:12px;
      bottom:12px;
      display:inline-flex;
      align-items:center;
      gap:6px;
      min-height:30px;
      padding:0 10px;
      border-radius:999px;
      background:rgba(17,18,20,0.74);
      color:#fff7ea;
      font-size:.72rem;
      font-weight:900;
      letter-spacing:.02em;
      border:1px solid rgba(255,255,255,0.12);
      backdrop-filter:blur(8px);
    }
    .reel-body {
      padding:14px;
      display:grid;
      gap:10px;
    }
    .card-kicker {
      margin:0;
      color:var(--accent);
      font-size:.7rem;
      font-weight:900;
      letter-spacing:.11em;
      text-transform:uppercase;
    }
    .card-title {
      margin:0;
      font-size:1.02rem;
      line-height:1.14;
      letter-spacing:-.03em;
    }
    .card-copy {
      margin:0;
      color:var(--muted);
      font-size:.9rem;
      line-height:1.5;
    }
    .item-list {
      display:grid;
      gap:8px;
    }
    .item-pill {
      display:flex;
      gap:8px;
      align-items:flex-start;
      padding:10px 12px;
      border:1px solid var(--line);
      border-radius:16px;
      background:rgba(255,255,255,0.65);
    }
    .item-dot {
      width:8px;
      height:8px;
      border-radius:999px;
      background:var(--accent-2);
      margin-top:6px;
      flex:0 0 auto;
    }
    .item-pill strong {
      display:block;
      font-size:.88rem;
      line-height:1.25;
    }
    .item-pill span {
      display:block;
      margin-top:3px;
      color:var(--muted);
      font-size:.82rem;
      line-height:1.4;
    }
    .notes {
      padding:14px;
      display:grid;
      gap:10px;
    }
    .note {
      border:1px dashed rgba(29,26,22,0.22);
      border-radius:18px;
      padding:12px 13px;
      background:rgba(255,255,255,0.56);
    }
    .note strong {
      display:block;
      font-size:.82rem;
      text-transform:uppercase;
      letter-spacing:.08em;
      color:var(--accent-2);
      margin-bottom:6px;
    }
    .note p {
      margin:0;
      color:var(--muted);
      font-size:.88rem;
      line-height:1.45;
    }
    .footer {
      text-align:center;
      color:var(--muted);
      font-size:.82rem;
      padding:4px 0 0;
    }
    @media (min-width: 900px) {
      .layout {
        grid-template-columns: minmax(0, 1.7fr) minmax(320px, .9fr);
        align-items:start;
      }
      .reel-grid {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <p class="eyebrow">UI Review Prototype</p>
      <h1>How should saved reels feel on a phone?</h1>
      <p>This is a lightweight review page with four sample reel cards, inline video, item extraction, and list framing. The goal is to make it easy to discuss layout, hierarchy, and what should be visible in one screen without getting blocked by backend logic.</p>
      <div class="hero-meta">
        <span class="chip">4 sample reels</span>
        <span class="chip">Mobile-first layout</span>
        <span class="chip">Shareable review link</span>
      </div>
    </section>

    <section class="layout">
      <section class="panel">
        <div class="panel-head">
          <h2>Sample Reel Cards</h2>
          <p>These are intentionally varied so you can discuss travel, food, apps, and advice-style reels in one place.</p>
        </div>
        <div class="reel-grid">
          <article class="reel-card">
            <div class="video-frame">
              <video controls playsinline preload="metadata" poster="/media/thumbnails/reel_20.jpg">
                <source src="/media/videos/reel_20.mp4" type="video/mp4" />
              </video>
              <span class="video-badge">Travel / Destination</span>
            </div>
            <div class="reel-body">
              <p class="card-kicker">Travel</p>
              <h3 class="card-title">European Destinations</h3>
              <p class="card-copy">A destination-led card where the main saved unit is the place itself, not every sub-stop in the itinerary.</p>
              <div class="item-list">
                <div class="item-pill"><span class="item-dot"></span><div><strong>Montenegro</strong><span>Underrated, affordable destination with coastal drives, old towns, and mountain views.</span></div></div>
              </div>
            </div>
          </article>

          <article class="reel-card">
            <div class="video-frame">
              <video controls playsinline preload="metadata" poster="/media/thumbnails/reel_18.jpg">
                <source src="/media/videos/reel_18.mp4" type="video/mp4" />
              </video>
              <span class="video-badge">Food / Restaurant</span>
            </div>
            <div class="reel-body">
              <p class="card-kicker">Food</p>
              <h3 class="card-title">Restaurants in Banaras</h3>
              <p class="card-copy">A place-led food card where the restaurant name becomes the saved item instead of the dish.</p>
              <div class="item-list">
                <div class="item-pill"><span class="item-dot"></span><div><strong>Shahi Dastarkhwan</strong><span>Banaras family restaurant highlighted for chicken mandi and a royal-style presentation.</span></div></div>
              </div>
            </div>
          </article>

          <article class="reel-card">
            <div class="video-frame">
              <video controls playsinline preload="metadata" poster="/media/thumbnails/reel_12.jpg">
                <source src="/media/videos/reel_12.mp4" type="video/mp4" />
              </video>
              <span class="video-badge">App / Tool</span>
            </div>
            <div class="reel-body">
              <p class="card-kicker">Apps</p>
              <h3 class="card-title">Music Sync Apps</h3>
              <p class="card-copy">An example where exact naming matters: the reel should save the app name, not just “an app.”</p>
              <div class="item-list">
                <div class="item-pill"><span class="item-dot"></span><div><strong>Beatsing</strong><span>App for synchronized music playback across multiple devices without needing a shared speaker setup.</span></div></div>
              </div>
            </div>
          </article>

          <article class="reel-card">
            <div class="video-frame">
              <video controls playsinline preload="metadata" poster="/media/thumbnails/reel_10.jpg">
                <source src="/media/videos/reel_10.mp4" type="video/mp4" />
              </video>
              <span class="video-badge">Advice / Generic</span>
            </div>
            <div class="reel-body">
              <p class="card-kicker">Generic</p>
              <h3 class="card-title">Study Abroad Warnings</h3>
              <p class="card-copy">A broad advice reel where the saved unit stays coarse and the supporting detail lives in the summary.</p>
              <div class="item-list">
                <div class="item-pill"><span class="item-dot"></span><div><strong>UK post-study job market warning</strong><span>Warning about poor job outcomes, oversupply, and visa uncertainty for students planning to study abroad.</span></div></div>
              </div>
            </div>
          </article>
        </div>
      </section>

      <aside class="panel">
        <div class="panel-head">
          <h2>What To Review</h2>
          <p>Share this page with your UI/UX reviewer and ask how the core reel, list, item, and summary hierarchy should feel on mobile.</p>
        </div>
        <div class="notes">
          <div class="note">
            <strong>Hierarchy</strong>
            <p>Should the reel video dominate the card, or should the saved list title and extracted item get more visual weight?</p>
          </div>
          <div class="note">
            <strong>Information Density</strong>
            <p>Can a user understand list title, item name, and why it was saved within one fast glance on an iPhone screen?</p>
          </div>
          <div class="note">
            <strong>Preview vs Detail</strong>
            <p>Should this stay card-based like a library, or should the app open into a more immersive reel-first detail screen?</p>
          </div>
          <div class="note">
            <strong>Travel & Food Edge</strong>
            <p>The biggest UX problem is often location-heavy content. Ask whether destination/place context should be emphasized more strongly than we show here.</p>
          </div>
        </div>
      </aside>
    </section>

    <p class="footer">Prototype review page for early UI direction. This is intentionally simple and meant for discussion, not final production UX.</p>
  </main>
</body>
</html>"""


def build_demo_library_review_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>Reel Organizer Demo Library</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #090b10;
      --panel: rgba(255,255,255,0.08);
      --panel-strong: rgba(255,255,255,0.12);
      --line: rgba(255,255,255,0.11);
      --text: #f7f4ee;
      --muted: #a8a19a;
      --accent: #f0ca8f;
      --accent-2: #8fd5c6;
      --safe-top: env(safe-area-inset-top, 0px);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
      --shadow: 0 22px 60px rgba(0,0,0,0.34);
    }
    * { box-sizing: border-box; }
    html, body {
      margin: 0;
      min-height: 100%;
      background:
        radial-gradient(circle at top left, rgba(240, 202, 143, 0.14), transparent 24rem),
        radial-gradient(circle at top right, rgba(143, 213, 198, 0.12), transparent 20rem),
        linear-gradient(180deg, #11151d 0%, #090b10 48%, #07080c 100%);
      color: var(--text);
      font-family: ui-rounded, "SF Pro Rounded", "Avenir Next", system-ui, sans-serif;
    }
    body { padding-bottom: calc(22px + var(--safe-bottom)); }
    .shell {
      width: min(760px, 100%);
      margin: 0 auto;
      padding: calc(10px + var(--safe-top)) 14px 24px;
    }
    .header {
      position: sticky;
      top: 0;
      z-index: 20;
      margin: calc(-10px - var(--safe-top)) -14px 12px;
      padding: calc(10px + var(--safe-top)) 14px 12px;
      background: linear-gradient(180deg, rgba(9,11,16,0.94), rgba(9,11,16,0.76) 82%, transparent);
      backdrop-filter: blur(18px);
    }
    .hero {
      display: grid;
      gap: 8px;
      padding: 12px 14px;
      border: 1px solid var(--line);
      border-radius: 22px;
      background: rgba(255,255,255,0.05);
      box-shadow: var(--shadow);
    }
    .kicker {
      margin: 0;
      color: var(--accent-2);
      font-size: .68rem;
      font-weight: 900;
      letter-spacing: .12em;
      text-transform: uppercase;
    }
    h1 {
      margin: 0;
      font-size: clamp(1.7rem, 7vw, 2.55rem);
      line-height: .96;
      letter-spacing: -.05em;
    }
    .subtitle {
      margin: 0;
      color: var(--muted);
      font-size: .9rem;
      line-height: 1.42;
    }
    .toolbar {
      margin-top: 10px;
      display: grid;
      gap: 10px;
      padding: 8px;
      border: 1px solid var(--line);
      border-radius: 18px;
      background: rgba(255,255,255,0.06);
      backdrop-filter: blur(16px);
    }
    .search {
      width: 100%;
      height: 44px;
      border-radius: 14px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.07);
      color: var(--text);
      padding: 0 14px;
      font-size: .94rem;
    }
    .content {
      display: grid;
      gap: 12px;
    }
    .card {
      border: 1px solid var(--line);
      border-radius: 24px;
      background: linear-gradient(180deg, rgba(255,255,255,0.09), rgba(255,255,255,0.05));
      box-shadow: var(--shadow);
      padding: 15px;
      cursor: pointer;
      overflow: hidden;
    }
    .card-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      align-items: flex-start;
    }
    .card-title {
      margin: 0;
      font-size: 1.02rem;
      line-height: 1.14;
      letter-spacing: -.03em;
    }
    .card-kicker {
      margin: 0 0 7px;
      color: var(--accent);
      font-size: .68rem;
      font-weight: 900;
      letter-spacing: .1em;
      text-transform: uppercase;
    }
    .count {
      padding: 6px 8px;
      border-radius: 999px;
      background: rgba(143,213,198,0.12);
      color: var(--accent-2);
      font-size: .72rem;
      font-weight: 900;
      white-space: nowrap;
    }
    .detail {
      display: grid;
      gap: 12px;
    }
    .back {
      width: 40px;
      height: 40px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.08);
      color: var(--text);
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      margin-bottom: 6px;
    }
    .back.hidden {
      visibility: hidden;
      pointer-events: none;
      height: 0;
      margin: 0;
    }
    .video-panel {
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 26px;
      background: var(--panel);
      box-shadow: var(--shadow);
    }
    .video-wrap {
      position: relative;
      width: 100%;
      height: clamp(220px, 42vh, 340px);
      background: #050607;
    }
    .video-wrap video, .video-wrap img {
      width: 100%;
      height: 100%;
      display: block;
      object-fit: contain;
    }
    .video-meta {
      padding: 16px;
      display: grid;
      gap: 10px;
    }
    .detail-title {
      margin: 0;
      font-size: 1.14rem;
      line-height: 1.05;
      letter-spacing: -.03em;
    }
    .detail-copy {
      margin: 0;
      color: var(--muted);
      font-size: .92rem;
      line-height: 1.55;
    }
    .meta-row {
      display: flex;
      gap: 8px;
      flex-wrap: wrap;
    }
    .pill {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 0 10px;
      border-radius: 999px;
      border: 1px solid var(--line);
      background: rgba(255,255,255,0.06);
      color: var(--muted);
      font-size: .74rem;
      font-weight: 850;
    }
    .item-list {
      display: grid;
      gap: 10px;
    }
    .item {
      border: 1px solid var(--line);
      border-radius: 20px;
      background: rgba(255,255,255,0.05);
      padding: 14px;
      cursor: pointer;
    }
    .item.active {
      border-color: rgba(240,202,143,0.35);
      background: rgba(255,255,255,0.1);
    }
    .item h3 {
      margin: 0;
      font-size: .97rem;
      line-height: 1.22;
    }
    .item p {
      margin: 8px 0 0;
      color: var(--muted);
      font-size: .86rem;
      line-height: 1.42;
    }
    .footer-note {
      margin-top: 8px;
      color: #7d756e;
      font-size: .8rem;
      text-align: center;
    }
  </style>
</head>
<body>
  <main class="shell">
    <header class="header">
      <div class="hero">
        <p class="kicker">Demo Library</p>
        <h1 id="screenTitle">Your Reel Library</h1>
        <p id="screenSubtitle" class="subtitle">A tighter mobile layout with less wasted top space, direct search, and folder-to-item browsing.</p>
        <div class="toolbar">
          <input id="searchInput" class="search" type="search" placeholder="Search folders and items" />
        </div>
      </div>
    </header>
    <section id="content" class="content"></section>
    <p class="footer-note">Static UI review build with 5 folders and local demo reel videos.</p>
  </main>

  <script>
    const DATA = [
      {
        list_title: "European Destinations",
        parent_title: "Travel",
        description: "Destination-led reels where the place itself becomes the saved unit.",
        items: [
          { name: "Montenegro", summary: "Affordable and underrated European destination with old towns, turquoise waters, and dramatic mountain views.", video_url: "/media/videos/reel_20.mp4", thumbnail_url: "/media/thumbnails/reel_20.jpg" },
          { name: "Santorini", summary: "Whitewashed coastal destination known for sea views and sunset scenery.", video_url: "/media/videos/reel_20.mp4", thumbnail_url: "/media/thumbnails/reel_20.jpg" },
          { name: "Kotor", summary: "Historic Adriatic town with fortress views and winding streets.", video_url: "/media/videos/reel_20.mp4", thumbnail_url: "/media/thumbnails/reel_20.jpg" },
          { name: "Venice", summary: "Canal city with romantic architecture and walkable old neighborhoods.", video_url: "/media/videos/reel_20.mp4", thumbnail_url: "/media/thumbnails/reel_20.jpg" },
          { name: "Ibiza", summary: "Island destination mixing beaches, nightlife, and scenic coastlines.", video_url: "/media/videos/reel_20.mp4", thumbnail_url: "/media/thumbnails/reel_20.jpg" }
        ]
      },
      {
        list_title: "Restaurants in Banaras",
        parent_title: "Food",
        description: "Place-led food reels where restaurant identity matters more than the dish alone.",
        items: [
          { name: "Shahi Dastarkhwan", summary: "Family restaurant in Banaras known for royal-style chicken mandi and rich presentation.", video_url: "/media/videos/reel_18.mp4", thumbnail_url: "/media/thumbnails/reel_18.jpg" },
          { name: "Voodoo Cafe", summary: "Cafe-style reel where the place itself is the thing worth remembering later.", video_url: "/media/videos/reel_18.mp4", thumbnail_url: "/media/thumbnails/reel_18.jpg" },
          { name: "Street food place in Banaras", summary: "Fallback place-based label when the exact outlet name is unclear but the location intent is strong.", video_url: "/media/videos/reel_18.mp4", thumbnail_url: "/media/thumbnails/reel_18.jpg" },
          { name: "Royal mandi spot", summary: "Restaurant-focused reel built around one place rather than a loose list of dishes.", video_url: "/media/videos/reel_18.mp4", thumbnail_url: "/media/thumbnails/reel_18.jpg" },
          { name: "Late-night kebab place", summary: "Location-led food recommendation where venue is the saved item.", video_url: "/media/videos/reel_18.mp4", thumbnail_url: "/media/thumbnails/reel_18.jpg" }
        ]
      },
      {
        list_title: "Music Sync Apps",
        parent_title: "Apps",
        description: "Exact-name app reels where vague labels like 'an app' are not enough.",
        items: [
          { name: "Beatsing", summary: "App that syncs the same song across multiple devices for parties or group listening.", video_url: "/media/videos/reel_12.mp4", thumbnail_url: "/media/thumbnails/reel_12.jpg" },
          { name: "AirDroid", summary: "Cross-device utility app that helps move files and manage phone-computer workflows.", video_url: "/media/videos/reel_12.mp4", thumbnail_url: "/media/thumbnails/reel_12.jpg" },
          { name: "Dr.Fone", summary: "Recovery and phone management tool highlighted as a practical software utility.", video_url: "/media/videos/reel_12.mp4", thumbnail_url: "/media/thumbnails/reel_12.jpg" },
          { name: "Hidden camera app", summary: "Exact-name-sensitive app example where on-screen text matters for saved recall.", video_url: "/media/videos/reel_12.mp4", thumbnail_url: "/media/thumbnails/reel_12.jpg" },
          { name: "Mac utility tool", summary: "Software reel where item naming should be more precise than a generic 'tool'.", video_url: "/media/videos/reel_12.mp4", thumbnail_url: "/media/thumbnails/reel_12.jpg" }
        ]
      },
      {
        list_title: "Study Abroad Warnings",
        parent_title: "Study & Career",
        description: "Broad advice reels where the saved unit stays coarse and the summary holds the supporting detail.",
        items: [
          { name: "UK post-study job market warning", summary: "Warning about poor job outcomes, oversupply, and visa uncertainty for students planning to study abroad.", video_url: "/media/videos/reel_10.mp4", thumbnail_url: "/media/thumbnails/reel_10.jpg" },
          { name: "College information", summary: "General college-review reel where the saved unit is the broader institution insight, not each bullet point.", video_url: "/media/videos/reel_10.mp4", thumbnail_url: "/media/thumbnails/reel_10.jpg" },
          { name: "College rankings India", summary: "Comparison-style education reel best saved as one retrievable concept rather than many micro-items.", video_url: "/media/videos/reel_10.mp4", thumbnail_url: "/media/thumbnails/reel_10.jpg" },
          { name: "Safer study destination advice", summary: "Education reel with decision-support framing rather than place-by-place tourism logic.", video_url: "/media/videos/reel_10.mp4", thumbnail_url: "/media/thumbnails/reel_10.jpg" },
          { name: "AI prompt engineering tips", summary: "Advice-led informational reel better saved as one broad concept item.", video_url: "/media/videos/reel_10.mp4", thumbnail_url: "/media/thumbnails/reel_10.jpg" }
        ]
      },
      {
        list_title: "Style & Social Ideas",
        parent_title: "Lifestyle",
        description: "Mixed light-interest reels where the layout should still feel intentional and easy to scan.",
        items: [
          { name: "Men's suit color guide", summary: "Style advice reel focused on helping users choose coordinated suit colors.", video_url: "/media/videos/reel_11.mp4", thumbnail_url: "/media/thumbnails/reel_11.jpg" },
          { name: "AI hairstyle tutorials", summary: "Beauty-tech reel where the saved unit is the hairstyle try-on concept, not every look variation.", video_url: "/media/videos/reel_11.mp4", thumbnail_url: "/media/thumbnails/reel_11.jpg" },
          { name: "Social media humor", summary: "Humor reel that still needs a clean saved-unit treatment instead of getting lost as noise.", video_url: "/media/videos/reel_11.mp4", thumbnail_url: "/media/thumbnails/reel_11.jpg" },
          { name: "Date ideas", summary: "Lifestyle reel where the broader social idea matters more than each tiny activity inside it.", video_url: "/media/videos/reel_11.mp4", thumbnail_url: "/media/thumbnails/reel_11.jpg" },
          { name: "Relationship communication", summary: "Advice-based social reel saved as one broad conversation topic.", video_url: "/media/videos/reel_11.mp4", thumbnail_url: "/media/thumbnails/reel_11.jpg" }
        ]
      }
    ];

    const state = {
      query: '',
      currentList: null,
      currentItem: 0
    };

    const content = document.getElementById('content');
    const screenTitle = document.getElementById('screenTitle');
    const screenSubtitle = document.getElementById('screenSubtitle');
    const searchInput = document.getElementById('searchInput');

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }

    function matchesItem(item, q) {
      if (!q) return true;
      return `${item.name} ${item.summary}`.toLowerCase().includes(q);
    }

    function matchesList(list, q) {
      if (!q) return true;
      return `${list.parent_title} ${list.list_title} ${list.description}`.toLowerCase().includes(q)
        || list.items.some((item) => matchesItem(item, q));
    }

    function visibleLists() {
      return DATA.filter((list) => matchesList(list, state.query));
    }

    function renderHome() {
      const lists = visibleLists();
      screenTitle.textContent = 'Your Reel Library';
      screenSubtitle.textContent = 'A tighter mobile layout with less wasted top space, direct search, and folder-to-item browsing.';
      if (!lists.length) {
        content.innerHTML = `<article class="card"><h2 class="card-title">No matches</h2><p class="card-copy">Try a different search term.</p></article>`;
        return;
      }
      content.innerHTML = lists.map((list, index) => {
        return `
          <article class="card" data-list="${index}">
            <div class="card-top">
              <div>
                <p class="card-kicker">${escapeHtml(list.parent_title)}</p>
                <h2 class="card-title">${escapeHtml(list.list_title)}</h2>
              </div>
              <span class="count">${list.items.length} items</span>
            </div>
          </article>
        `;
      }).join('');
      content.querySelectorAll('[data-list]').forEach((node) => {
        node.addEventListener('click', () => {
          state.currentList = Number(node.dataset.list);
          state.currentItem = 0;
          render();
        });
      });
    }

    function renderDetail() {
      const lists = visibleLists();
      const list = lists[state.currentList];
      if (!list) {
        state.currentList = null;
        render();
        return;
      }
      const items = list.items.filter((item) => matchesItem(item, state.query));
      const activeItem = items[state.currentItem] || items[0];
      screenTitle.textContent = list.list_title;
      screenSubtitle.textContent = `${list.parent_title} · ${list.items.length} saved items`;
      content.innerHTML = `
        <button id="backButton" class="back">‹</button>
        <section class="detail">
          <article class="video-panel">
            <div class="video-wrap">
              <video controls playsinline preload="metadata" poster="${escapeHtml(activeItem.thumbnail_url)}">
                <source src="${escapeHtml(activeItem.video_url)}" type="video/mp4" />
              </video>
            </div>
            <div class="video-meta">
              <div class="meta-row">
                <span class="pill">${escapeHtml(list.parent_title)}</span>
                <span class="pill">${escapeHtml(list.list_title)}</span>
              </div>
              <h2 class="detail-title">${escapeHtml(activeItem.name)}</h2>
              <p class="detail-copy">${escapeHtml(activeItem.summary)}</p>
            </div>
          </article>
          <section class="item-list">
            ${items.map((item, index) => `
              <article class="item ${index === state.currentItem ? 'active' : ''}" data-item="${index}">
                <h3>${escapeHtml(item.name)}</h3>
                <p>${escapeHtml(item.summary)}</p>
              </article>
            `).join('')}
          </section>
        </section>
      `;
      document.getElementById('backButton').addEventListener('click', () => {
        state.currentList = null;
        state.currentItem = 0;
        render();
      });
      content.querySelectorAll('[data-item]').forEach((node) => {
        node.addEventListener('click', () => {
          state.currentItem = Number(node.dataset.item);
          render();
          window.scrollTo({ top: 0, behavior: 'smooth' });
        });
      });
    }

    function render() {
      if (state.currentList === null) renderHome();
      else renderDetail();
    }

    searchInput.addEventListener('input', (event) => {
      state.query = event.target.value.trim().toLowerCase();
      state.currentList = null;
      state.currentItem = 0;
      render();
    });

    render();
  </script>
</body>
</html>"""


def build_privacy_html() -> str:
    return build_legal_html(
        "Reel Organizer Privacy Policy",
        """
      <p class="kicker">Privacy Policy</p>
      <h1>Reel Organizer Privacy Policy</h1>
      <p>Reel Organizer helps users collect Instagram reel links they intentionally share and organizes them into a personal library. This page explains what data we store and how we use it.</p>
      <h2>Information We Collect</h2>
      <ul>
        <li>Google account identity needed to create and maintain your Reel Organizer account.</li>
        <li>Instagram reel URLs that you choose to send to our connected ingestion channel.</li>
        <li>Processed reel metadata such as extracted item names, summaries, categories, transcript availability, visual extraction results, and personalization outputs.</li>
        <li>Operational metadata such as linked Telegram or Instagram account IDs, processing status, and media file locations required to keep your library working.</li>
      </ul>
      <h2>How We Use Information</h2>
      <ul>
        <li>To ingest the reels you send us and attach them to your account.</li>
        <li>To generate summaries, product extraction, and personalized lists.</li>
        <li>To troubleshoot failed processing and improve product quality.</li>
      </ul>
      <h2>What We Do Not Do</h2>
      <ul>
        <li>We do not access arbitrary personal Instagram messages outside the messages you intentionally send to the app’s connected account.</li>
        <li>We do not sell your personal data.</li>
      </ul>
      <h2>Storage and Retention</h2>
      <p>Saved reels, extracted metadata, and generated media assets may be stored as long as needed to operate your library, unless you ask for deletion.</p>
      <h2>Your Choices</h2>
      <p>You can request deletion of your account-linked data using the instructions on the Data Deletion page.</p>
      <h2>Contact</h2>
      <p>For privacy questions, contact the app operator using the email configured in the associated Meta app settings.</p>
        """,
    )


def build_terms_html() -> str:
    return build_legal_html(
        "Reel Organizer Terms of Service",
        """
      <p class="kicker">Terms of Service</p>
      <h1>Reel Organizer Terms of Service</h1>
      <p>By using Reel Organizer, you agree to use the service only for reels and content you are permitted to share with the app.</p>
      <h2>Service Description</h2>
      <p>Reel Organizer receives reel links you intentionally send, processes them, and organizes the results into a personal library.</p>
      <h2>Acceptable Use</h2>
      <ul>
        <li>Do not use the service for unlawful activity.</li>
        <li>Do not attempt to break, overload, or interfere with the service.</li>
        <li>Do not send content you do not have the right to share.</li>
      </ul>
      <h2>Availability</h2>
      <p>The service may change, improve, or go offline temporarily while features are being developed or maintained.</p>
      <h2>Data and Deletion</h2>
      <p>You may request deletion of your account-linked data using the instructions on the Data Deletion page.</p>
      <h2>Disclaimer</h2>
      <p>The service is provided on an as-is basis during active product development and beta testing.</p>
        """,
    )


def build_data_deletion_html() -> str:
    return build_legal_html(
        "Reel Organizer Data Deletion",
        """
      <p class="kicker">Data Deletion</p>
      <h1>Data Deletion Instructions</h1>
      <p>If you want your Reel Organizer data removed, email the app operator from the email address associated with your Google sign-in and request deletion of your account data.</p>
      <h2>What Will Be Deleted</h2>
      <ul>
        <li>Your linked account identifiers</li>
        <li>Your saved reel records</li>
        <li>Extracted reel items, summaries, diagnostics, and personalization data</li>
        <li>Associated cached local media generated for your library</li>
      </ul>
      <h2>What To Include</h2>
      <ul>
        <li>Your Google account email used in the app</li>
        <li>Your Instagram username if you linked Instagram</li>
        <li>Your Telegram username if you linked Telegram</li>
      </ul>
      <p>Deletion requests are handled manually during the current beta phase.</p>
        """,
    )


def build_landing_html(csrf_token: str, user: dict | None) -> str:
    google_client_id = settings.google_client_id
    instagram_app_username = settings.instagram_app_username
    google_script = (
        '<script src="https://accounts.google.com/gsi/client" async defer></script>'
        if google_client_id
        else ""
    )
    auth_section = ""
    if user:
        instagram_connected = bool(user.get("instagram_user_id"))
        instagram_label = "Instagram connected" if instagram_connected else "Connect Instagram"
        instagram_href = f"https://www.instagram.com/{instagram_app_username}/" if instagram_connected and instagram_app_username else "#"
        instagram_dm_href = f"https://ig.me/m/{instagram_app_username}" if instagram_app_username else instagram_href
        instagram_meta = (
            f"<p class=\"tiny\">Instagram linked as @{user.get('instagram_username') or instagram_app_username}</p>"
            if instagram_connected
            else "<p class=\"tiny\">Link Instagram once so every reel DM goes into the right library automatically.</p>"
        )
        auth_section = f"""
      <div class="user-card">
        <div class="user-row">
          <div>
            <p class="tiny-label">Signed in as</p>
            <h2>{user.get("display_name", "User")}</h2>
            <p class="tiny">{user.get("email", "")}</p>
            {instagram_meta}
          </div>
          {f'<img class="avatar" src="{user.get("picture_url", "")}" alt="Profile" />' if user.get("picture_url") else ""}
        </div>
        <div class="action-grid">
          <a class="primary-link" href="/app">Open My Library</a>
          {f'<a class="secondary-link" href="{instagram_href}" target="_blank" rel="noopener noreferrer">{instagram_label}</a>' if instagram_connected else '<button id="instagramConnectButton" type="button">Connect Instagram</button>'}
        </div>
        <button id="logoutButton" type="button" class="ghost-button">Sign out</button>
      </div>
      <div id="instagramModal" class="connect-modal hidden" aria-hidden="true">
        <div class="connect-card">
          <div class="connect-head">
            <div>
              <p class="kicker">Connect Instagram</p>
              <h3 style="margin:0;">Link your Instagram once</h3>
            </div>
            <button id="instagramModalClose" type="button" class="ghost-button small-ghost">Close</button>
          </div>
          <p class="tiny" style="margin-top:0;">DM this one-time code to @{instagram_app_username or 'yourapp'} on Instagram. After that, reels you share in that DM will go to this Google account.</p>
          <div class="code-box" id="instagramCodeBox">Loading code…</div>
          <div class="action-grid" style="margin-top:8px;">
            <button id="openInstagramDmButton" type="button">Copy code + Open Instagram DM</button>
            <button id="copyInstagramCodeButton" type="button">Copy code</button>
          </div>
          <p class="tiny" id="instagramExpiryText"></p>
          <p class="tiny" id="instagramStatusText">Waiting for your Instagram DM…</p>
          <ol>
            <li>Tap <strong>Copy code + Open Instagram DM</strong>.</li>
            <li>Send the exact code once in the chat with <strong>@{instagram_app_username or 'yourapp'}</strong>.</li>
            <li>After linking, just share reel links in that same DM.</li>
          </ol>
          <p class="tiny">If Instagram opens in a browser instead of the app, the code is still copied. Just paste it into the same DM once.</p>
        </div>
      </div>
        """
    else:
        disabled_note = "<p class='tiny'>Google sign-in is not configured yet. Add `GOOGLE_CLIENT_ID` before launch.</p>" if not google_client_id else ""
        auth_section = f"""
      <div class="auth-card">
        <p class="kicker">Step 1</p>
        <h2>Continue with Google</h2>
        <p>Use your Google account once. After that, your library stays attached to you and you can link Instagram as the ingest channel.</p>
        <div id="googleButton" class="google-button-shell"></div>
        {disabled_note}
      </div>
        """
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>ClipNest</title>
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png" />
  <link rel="icon" type="image/png" href="/static/favicon.png" />
  <link rel="manifest" href="/static/manifest.json" />
  __GOOGLE_SCRIPT__
  <style>
    /* Matches the in-app theme (app/ui_ux/clipnest_v1.py): near-black flat
       background, #161619 cards, serif display headings, tan action color. */
    :root {
      color-scheme: dark;
      --bg:#0a0a0b;
      --card:#161619;
      --soft:#1c1c20;
      --line:#232327;
      --text:#f4f4f5;
      --muted:#8e8e96;
      --faint:#5c5c64;
      --tan:#f2a866;
      --brand-grad:linear-gradient(135deg, #f9a660 0%, #ee7f2f 100%);
      --serif:ui-serif, "New York", Georgia, "Times New Roman", serif;
      --safe-top: env(safe-area-inset-top, 0px);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
    }
    * { box-sizing: border-box; }
    html, body {
      margin:0;
      min-height:100%;
      background:var(--bg);
      color:var(--text);
      font-family:-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
    }
    .shell {
      width:min(680px, 100%);
      min-height:100vh;
      margin:0 auto;
      padding: calc(28px + var(--safe-top)) 20px calc(36px + var(--safe-bottom));
      display:grid;
      gap:16px;
      align-content:center;
    }
    .hero, .card {
      border:1px solid var(--line);
      border-radius:20px;
      background:var(--card);
      padding:22px 20px;
    }
    .hero-logo {
      width:72px;
      height:72px;
      border-radius:18px;
      display:block;
      margin:0 0 16px;
    }
    .kicker {
      margin:0 0 10px;
      color:var(--tan);
      font-size:.7rem;
      font-weight:700;
      letter-spacing:.12em;
      text-transform:uppercase;
    }
    h1 {
      margin:0;
      font-family:var(--serif);
      font-weight:600;
      font-size: clamp(1.9rem, 8vw, 2.7rem);
      line-height:1.08;
      letter-spacing:-.01em;
    }
    p {
      color:var(--muted);
      line-height:1.55;
      margin:10px 0 0;
      font-size:.95rem;
    }
    .form {
      display:grid;
      gap:12px;
      margin-top:18px;
    }
    .auth-card, .user-card {
      display:grid;
      gap:14px;
      margin-top:20px;
      border-top:1px solid var(--line);
      padding-top:18px;
    }
    .auth-card h2, .user-row h2 {
      margin:0;
      font-family:var(--serif);
      font-weight:600;
      font-size:1.35rem;
    }
    .user-row {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:14px;
    }
    .tiny-label {
      margin:0 0 4px;
      color:var(--tan);
      font-size:.7rem;
      font-weight:700;
      letter-spacing:.1em;
      text-transform:uppercase;
    }
    .avatar {
      width:56px;
      height:56px;
      border-radius:50%;
      border:1px solid var(--line);
      object-fit:cover;
    }
    .action-grid {
      display:grid;
      gap:10px;
    }
    .google-button-shell {
      min-height:46px;
      display:flex;
      align-items:center;
      justify-content:flex-start;
    }
    .google-fallback {
      min-height:46px;
      display:flex;
      align-items:center;
      padding:0 14px;
      border-radius:16px;
      border:1px dashed var(--line);
      color:var(--muted);
      font-size:.88rem;
      line-height:1.35;
    }
    .primary-link,
    .secondary-link {
      display:inline-flex;
      align-items:center;
      justify-content:center;
      width:100%;
      min-height:52px;
      border-radius:26px;
      border:1px solid var(--line);
      background:var(--soft);
      color:var(--text);
      text-decoration:none;
      font-size:.95rem;
      font-weight:700;
    }
    .primary-link {
      background:var(--brand-grad);
      border:0;
      color:#fff;
    }
    .ghost-button {
      min-height:44px;
      border-radius:22px;
      border:1px solid var(--line);
      background:transparent;
      color:var(--muted);
      font-size:.9rem;
      font-weight:650;
      cursor:pointer;
    }
    .small-ghost {
      width:auto;
      min-height:38px;
      padding:0 14px;
      font-size:.84rem;
    }
    input, button {
      width:100%;
      min-height:52px;
      border-radius:26px;
      border:1px solid var(--line);
      background:var(--soft);
      color:var(--text);
      padding:0 16px;
      font-size:.95rem;
    }
    button {
      background:var(--brand-grad);
      border:0;
      color:#fff;
      font-weight:700;
      cursor:pointer;
    }
    button:active { filter:brightness(1.1); }
    ol {
      margin:14px 0 0;
      padding-left:18px;
      color:var(--muted);
      line-height:1.7;
      font-size:.92rem;
    }
    .tiny {
      font-size:.82rem;
      color:var(--faint);
    }
    .connect-modal {
      position: fixed;
      inset: 0;
      background: rgba(10, 10, 11, 0.78);
      backdrop-filter: blur(10px);
      display: grid;
      place-items: center;
      padding: 20px;
      z-index: 50;
    }
    .connect-modal.hidden {
      display: none;
    }
    .connect-card {
      width: min(520px, 100%);
      border: 1px solid var(--line);
      border-radius: 20px;
      background: var(--card);
      padding: 18px;
    }
    .connect-head {
      display:flex;
      justify-content:space-between;
      gap:12px;
      align-items:flex-start;
      margin-bottom:12px;
    }
    .connect-head h3 { font-family:var(--serif); font-weight:600; font-size:1.15rem; }
    .code-box {
      width:100%;
      min-height:60px;
      border-radius:16px;
      border:1px dashed rgba(242,140,56,.55);
      background: rgba(242,140,56,.12);
      display:grid;
      place-items:center;
      font-size:1.25rem;
      font-weight:800;
      letter-spacing:.1em;
      color: var(--tan);
      margin: 14px 0 8px;
      padding: 10px 14px;
      text-align:center;
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <img class="hero-logo" src="/static/icon-192.png" alt="ClipNest" />
      <p class="kicker">Live Reel Library</p>
      <h1>Sign in once. Connect Instagram once. Your reels stay yours.</h1>
      <p>Your app organizes saved Instagram reels into clean lists, keeps each person’s library separate, and lets each person DM reels to your Instagram account without mixing libraries.</p>
      __AUTH_SECTION__
    </section>
    <section class="card">
      <p class="kicker">How It Works</p>
      <ol>
        <li>Continue with Google.</li>
        <li>Tap Connect Instagram once and DM the one-time code to your app’s Instagram account.</li>
        <li>From then on, send reel links in that DM and they appear in your own library.</li>
      </ol>
    </section>
  </main>
  <script>
    const LOGIN_CSRF = __CSRF_TOKEN__;
    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || 'Request failed');
      }
      return data;
    }

    function mountGoogleButton() {
      const target = document.getElementById('googleButton');
      if (!target || !window.google || !window.google.accounts || !window.google.accounts.id) {
        return false;
      }
      if (target.dataset.mounted === '1') {
        return true;
      }
      target.dataset.mounted = '1';
      window.google.accounts.id.initialize({
        client_id: __GOOGLE_CLIENT_ID__,
        callback: async (response) => {
          try {
            await postJson('/auth/google', {
              credential: response.credential,
              csrf_token: LOGIN_CSRF
            });
            window.location.reload();
          } catch (error) {
            alert(error.message || 'Google login failed');
          }
        }
      });
      window.google.accounts.id.renderButton(
        target,
        { theme: 'filled_black', size: 'large', shape: 'pill', text: 'continue_with', width: 320 }
      );
      return true;
    }

    if (document.getElementById('googleButton')) {
      if (!mountGoogleButton()) {
        let attempts = 0;
        const googleMountTimer = setInterval(() => {
          attempts += 1;
          if (mountGoogleButton() || attempts > 40) {
            clearInterval(googleMountTimer);
            if (attempts > 40 && !document.getElementById('googleButton').dataset.mounted) {
              document.getElementById('googleButton').innerHTML =
                '<div class="google-fallback">Google Sign-In is being blocked in this browser. Open this page in Incognito or disable extensions for this site, then refresh.</div>';
            }
          }
        }, 250);
      }
    }

    const logoutButton = document.getElementById('logoutButton');
    if (logoutButton) {
      logoutButton.addEventListener('click', async () => {
        await postJson('/auth/logout', {});
        window.location.href = '/';
      });
    }

    const instagramConnectButton = document.getElementById('instagramConnectButton');
    const instagramModal = document.getElementById('instagramModal');
    const instagramModalClose = document.getElementById('instagramModalClose');
    const instagramCodeBox = document.getElementById('instagramCodeBox');
    const instagramExpiryText = document.getElementById('instagramExpiryText');
    const instagramStatusText = document.getElementById('instagramStatusText');
    const copyInstagramCodeButton = document.getElementById('copyInstagramCodeButton');
    const openInstagramDmButton = document.getElementById('openInstagramDmButton');
    const instagramDmHref = __INSTAGRAM_DM_HREF__;
    let instagramSessionPoll = null;

    async function refreshSessionState() {
      const response = await fetch('/auth/session');
      const payload = await response.json();
      return payload;
    }

    async function copyInstagramCode() {
      const code = (instagramCodeBox?.textContent || '').trim();
      if (!code || code === 'Loading code…') return false;
      try {
        await navigator.clipboard.writeText(code);
        return true;
      } catch (error) {
        return false;
      }
    }

    async function openInstagramConnectModal() {
      if (!instagramModal) return;
      instagramModal.classList.remove('hidden');
      instagramModal.setAttribute('aria-hidden', 'false');
      instagramCodeBox.textContent = 'Loading code…';
      instagramExpiryText.textContent = '';
      if (instagramStatusText) {
        instagramStatusText.textContent = 'Waiting for your Instagram DM…';
      }
      try {
        const payload = await postJson('/auth/instagram/connect', {});
        instagramCodeBox.textContent = payload.code;
        instagramExpiryText.textContent = `This code expires at ${new Date(payload.expires_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}.`;
        const copied = await copyInstagramCode();
        if (instagramStatusText) {
          instagramStatusText.textContent = copied
            ? 'Code copied. Tap “Copy code + Open Instagram DM”.'
            : 'Code ready. Tap “Copy code + Open Instagram DM”.';
        }
        if (instagramSessionPoll) clearInterval(instagramSessionPoll);
        instagramSessionPoll = setInterval(async () => {
          try {
            const session = await refreshSessionState();
            if (session.instagram_connected) {
              if (instagramStatusText) {
                const handle = session.user?.instagram_username ? `@${session.user.instagram_username}` : 'your Instagram account';
                instagramStatusText.textContent = `Linked successfully as ${handle}. Refreshing…`;
              }
              clearInterval(instagramSessionPoll);
              setTimeout(() => window.location.reload(), 900);
            }
          } catch (error) {
            // Ignore transient polling failures while waiting for the DM.
          }
        }, 2500);
      } catch (error) {
        instagramCodeBox.textContent = error.message || 'Could not create Instagram code.';
        if (instagramStatusText) {
          instagramStatusText.textContent = 'Could not start Instagram linking. Please try again.';
        }
      }
    }

    function closeInstagramConnectModal() {
      if (!instagramModal) return;
      if (instagramSessionPoll) {
        clearInterval(instagramSessionPoll);
        instagramSessionPoll = null;
      }
      instagramModal.classList.add('hidden');
      instagramModal.setAttribute('aria-hidden', 'true');
    }

    if (instagramConnectButton) {
      instagramConnectButton.addEventListener('click', openInstagramConnectModal);
    }
    if (instagramModalClose) {
      instagramModalClose.addEventListener('click', closeInstagramConnectModal);
    }
    if (instagramModal) {
      instagramModal.addEventListener('click', (event) => {
        if (event.target === instagramModal) closeInstagramConnectModal();
      });
    }
    if (copyInstagramCodeButton) {
      copyInstagramCodeButton.addEventListener('click', async () => {
        const copied = await copyInstagramCode();
        if (instagramStatusText) {
          instagramStatusText.textContent = copied
            ? 'Code copied. Send it in Instagram DM, then come back here.'
            : 'Copy failed. You can still type the code manually in Instagram.';
        }
      });
    }
    if (openInstagramDmButton) {
      openInstagramDmButton.addEventListener('click', async () => {
        const copied = await copyInstagramCode();
        if (instagramStatusText) {
          instagramStatusText.textContent = copied
            ? 'Instagram is opening. Paste the copied code in the DM once.'
            : 'Instagram is opening. If copy failed, type the code manually once.';
        }
        if (instagramDmHref && instagramDmHref !== '#') {
          window.open(instagramDmHref, '_blank', 'noopener,noreferrer');
        }
      });
    }
  </script>
</body>
</html>""".replace("__GOOGLE_SCRIPT__", google_script).replace("__AUTH_SECTION__", auth_section).replace("__CSRF_TOKEN__", repr(csrf_token)).replace("__GOOGLE_CLIENT_ID__", repr(google_client_id)).replace("__INSTAGRAM_DM_HREF__", repr(instagram_dm_href if user else "#"))


def build_web_app_html(user_id: str) -> str:
    return build_clipnest_v1_html(user_id)


def build_legacy_web_app_html(user_id: str) -> str:
    safe_user_id = user_id.replace("\\", "\\\\").replace("'", "\\'")
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>Reel Organizer</title>
  <style>
    :root {{
      color-scheme: dark;
      --bg: #07090c;
      --panel: rgba(255,255,255,0.06);
      --panel-strong: rgba(255,255,255,0.09);
      --line: rgba(255,255,255,0.1);
      --text: #f4f6f8;
      --muted: #9ca4af;
      --soft: #707987;
      --accent: #eed7a6;
      --accent-2: #9fd5c5;
      --danger: #ff847c;
      --shadow: 0 24px 70px rgba(0,0,0,0.38);
      --safe-top: env(safe-area-inset-top, 0px);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
    }}
    * {{ box-sizing: border-box; }}
    html, body {{ margin:0; min-height:100%; background:var(--bg); color:var(--text); font-family: ui-rounded, "SF Pro Rounded", "Avenir Next", system-ui, sans-serif; }}
    body {{
      background:
        radial-gradient(circle at top left, rgba(238, 215, 166, 0.14), transparent 26rem),
        radial-gradient(circle at top right, rgba(159, 213, 197, 0.12), transparent 24rem),
        linear-gradient(180deg, #10141b 0%, #07090c 50%, #060709 100%);
    }}
    .shell {{
      width:min(760px, 100%);
      margin:0 auto;
      min-height:100vh;
      padding: calc(16px + var(--safe-top)) 16px calc(30px + var(--safe-bottom));
    }}
    .header {{
      position: sticky; top:0; z-index:20;
      margin: calc(-16px - var(--safe-top)) -16px 8px;
      padding: calc(10px + var(--safe-top)) 16px 10px;
      background: linear-gradient(180deg, rgba(7,9,12,0.96), rgba(7,9,12,0.8) 72%, transparent);
      backdrop-filter: blur(18px);
    }}
    .topbar {{ display:flex; gap:10px; align-items:center; margin-bottom:8px; }}
    .back, .status-btn, .refresh-btn {{
      width:38px; height:38px; border-radius:999px; border:1px solid var(--line);
      background: rgba(255,255,255,0.08); color:var(--text); display:inline-flex; align-items:center; justify-content:center;
      font-size:.95rem; cursor:pointer;
    }}
    .status-wrap {{ position:relative; }}
    .status-badge {{
      position:absolute; top:-3px; right:-3px; min-width:19px; height:19px; padding:0 5px;
      border-radius:999px; background:var(--danger); color:white; display:none; align-items:center; justify-content:center;
      font-size:.68rem; font-weight:900; border:2px solid var(--bg);
    }}
    .status-badge.visible {{ display:flex; }}
    .back.hidden {{ visibility:hidden; pointer-events:none; }}
    .title-wrap {{ flex:1; min-width:0; }}
    .kicker {{ margin:0 0 2px; color:var(--accent-2); font-size:.64rem; font-weight:900; letter-spacing:.1em; text-transform:uppercase; }}
    .title {{ margin:0; font-size: clamp(1.02rem, 5vw, 1.3rem); letter-spacing:-.03em; line-height:1.02; }}
    .subtitle {{ margin:2px 0 0; color:var(--muted); font-size:.75rem; line-height:1.3; }}
    .search {{
      width:100%; height:42px; margin-top:4px; border-radius:16px; border:1px solid var(--line);
      background:rgba(255,255,255,0.07); color:var(--text); padding:0 14px; font-size:.9rem;
    }}
    .stats {{ display:none; }}
    .stats::-webkit-scrollbar {{ display:none; }}
    .chip {{
      flex:0 0 auto; padding:8px 11px; border:1px solid var(--line); border-radius:999px;
      color:var(--muted); background:rgba(255,255,255,0.055); font-size:.74rem; font-weight:900;
    }}
    .sync-note {{ margin: 2px 0 0; color: var(--soft); font-size: .72rem; }}
    .content {{ display:grid; gap:12px; }}
    .card {{
      border:1px solid var(--line); border-radius:24px; background:linear-gradient(180deg, rgba(255,255,255,0.085), rgba(255,255,255,0.045));
      box-shadow: var(--shadow); padding:16px; cursor:pointer; overflow:hidden;
    }}
    .card-meta-row {{
      display:flex; gap:8px; flex-wrap:wrap; margin-top:10px;
    }}
    .search-reason {{
      margin:10px 0 0; color:var(--muted); font-size:.82rem; line-height:1.45;
    }}
    .mini-chip {{
      display:inline-flex; align-items:center; min-height:28px; padding:0 10px; border-radius:999px;
      border:1px solid var(--line); background:rgba(255,255,255,0.045); color:var(--muted); font-size:.72rem; font-weight:850;
    }}
    .card-top {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:12px; }}
    .card-kicker {{ margin:0 0 8px; color:var(--accent-2); font-size:.7rem; font-weight:900; letter-spacing:.11em; text-transform:uppercase; }}
    .card-title {{ margin:0; font-size:1.08rem; line-height:1.15; letter-spacing:-.02em; }}
    .count {{ padding:6px 8px; border-radius:999px; background:rgba(159,213,197,0.12); color:var(--accent-2); font-size:.72rem; font-weight:900; }}
    .detail {{ display:grid; gap:12px; padding-bottom:calc(min(42vh, 360px) + 28px + var(--safe-bottom)); }}
    .detail-card {{
      border:1px solid var(--line); border-radius:24px; background:linear-gradient(180deg, rgba(255,255,255,0.085), rgba(255,255,255,0.045));
      box-shadow:var(--shadow); padding:16px;
    }}
    .video-wrap {{ position:relative; width:100%; height:100%; background:#050607; }}
    .video-wrap video, .video-wrap img {{ width:100%; height:100%; display:block; object-fit:cover; }}
    .video-empty {{
      position:absolute; inset:0; display:grid; place-items:center; padding:24px; text-align:center; color:var(--muted);
      font-size:.95rem; line-height:1.5;
    }}
    .video-meta {{ display:grid; gap:10px; }}
    .detail-title {{ margin:0; font-size:1.2rem; line-height:1.05; letter-spacing:-.03em; }}
    .detail-summary {{ margin:0; color:var(--muted); font-size:.94rem; line-height:1.55; }}
    .detail-meta {{ display:flex; gap:8px; flex-wrap:wrap; }}
    .floating-player-root {{
      position:fixed; inset:0; z-index:35; pointer-events:none;
    }}
    .floating-player-root.hidden {{ display:none; }}
    .floating-player-root.expanded {{ pointer-events:auto; }}
    .floating-player-backdrop {{
      position:absolute; inset:0; background:rgba(5,7,10,0.76); backdrop-filter:blur(12px); opacity:0; pointer-events:none;
      transition:opacity 180ms ease;
    }}
    .floating-player-root.expanded .floating-player-backdrop {{
      opacity:1; pointer-events:auto;
    }}
    .floating-player-frame {{
      position:absolute; top:0; left:0; width:202px; height:360px; overflow:hidden; border-radius:26px;
      border:1px solid rgba(255,255,255,0.14); background:#050607; box-shadow:0 24px 52px rgba(0,0,0,0.36);
      pointer-events:auto; touch-action:none; user-select:none; -webkit-user-select:none;
      will-change:transform,width,height,box-shadow,opacity;
    }}
    .floating-player-frame.dragging {{
      box-shadow:0 32px 64px rgba(0,0,0,0.46);
    }}
    .floating-player-frame.compact {{
      border-radius:24px;
    }}
    .floating-player-frame.docked {{
      opacity:0.98;
    }}
    .floating-player-media {{
      position:relative; width:100%; height:100%; background:#050607; overflow:hidden;
    }}
    .floating-player-media video,
    .floating-player-media img {{
      width:100%; height:100%; display:block; object-fit:cover;
      background:#050607;
      pointer-events:none;
    }}
    .floating-player-bar {{
      position:absolute; top:10px; left:10px; right:10px; display:flex; justify-content:space-between; align-items:flex-start;
      z-index:3; pointer-events:none;
    }}
    .floating-player-side {{
      display:flex; gap:8px; pointer-events:none;
    }}
    .player-control {{
      width:34px; height:34px; border-radius:999px; border:1px solid rgba(255,255,255,0.16);
      background:rgba(6,8,11,0.56); color:var(--text); display:inline-flex; align-items:center; justify-content:center;
      font-size:.88rem; font-weight:900; cursor:pointer; pointer-events:auto; backdrop-filter:blur(12px);
      box-shadow:0 10px 22px rgba(0,0,0,0.22);
    }}
    .player-control.bottom-right {{
      position:absolute; right:10px; bottom:10px; z-index:3;
    }}
    .player-center {{
      position:absolute; inset:0; display:grid; place-items:center; z-index:2; pointer-events:none;
    }}
    .player-play {{
      width:58px; height:58px; border-radius:999px; border:1px solid rgba(255,255,255,0.16);
      background:rgba(6,8,11,0.58); color:var(--text); display:inline-flex; align-items:center; justify-content:center;
      font-size:1rem; font-weight:900; cursor:pointer; pointer-events:auto; backdrop-filter:blur(12px);
      box-shadow:0 14px 32px rgba(0,0,0,0.26); opacity:0; transform:scale(0.94); transition:opacity 160ms ease, transform 160ms ease;
    }}
    .floating-player-frame.paused .player-play,
    .floating-player-frame.show-controls .player-play {{
      opacity:1; transform:scale(1);
    }}
    .floating-player-peek {{
      position:absolute; top:0; width:28px; height:88px; border:1px solid rgba(255,255,255,0.14);
      background:rgba(7,9,12,0.72); color:var(--text); display:none; align-items:center; justify-content:center;
      font-size:1rem; font-weight:900; cursor:pointer; pointer-events:auto; backdrop-filter:blur(12px);
      box-shadow:0 12px 28px rgba(0,0,0,0.24);
    }}
    .floating-player-root.docked-left .floating-player-peek {{
      left:0; display:flex; border-radius:0 18px 18px 0;
    }}
    .floating-player-root.docked-right .floating-player-peek {{
      right:0; display:flex; border-radius:18px 0 0 18px;
    }}
    .buy-box {{
      display:grid; gap:10px; padding:12px; border:1px solid var(--line); border-radius:18px; background:rgba(255,255,255,0.05);
    }}
    .actions {{ display:flex; flex-wrap:wrap; gap:8px; }}
    .action {{
      display:inline-flex; align-items:center; justify-content:center; min-height:38px; padding:0 13px; border-radius:999px;
      border:1px solid var(--line); background:rgba(255,255,255,0.065); color:var(--text); text-decoration:none; font-size:.78rem; font-weight:900;
    }}
    .action.primary {{ background:rgba(238,215,166,0.14); color:#fff2da; border-color:rgba(238,215,166,0.35); }}
    .action.danger {{ background:rgba(255,132,124,0.12); color:#ffd7d4; border-color:rgba(255,132,124,0.35); }}
    .items {{ display:grid; gap:10px; }}
    .item {{
      border:1px solid var(--line); border-radius:20px; background:rgba(255,255,255,0.06); padding:14px;
      cursor:pointer;
    }}
    .item.active {{ border-color: rgba(238,215,166,0.34); background: rgba(255,255,255,0.09); }}
    .item h3 {{ margin:0; font-size:.98rem; line-height:1.22; }}
    .item p {{ margin:8px 0 0; color:var(--muted); font-size:.88rem; line-height:1.45; }}
    .status-sheet {{
      position:fixed; inset:0; background:rgba(5,7,10,0.62); backdrop-filter: blur(10px);
      display:none; align-items:flex-end; z-index:40;
    }}
    .status-sheet.open {{ display:flex; }}
    .status-panel {{
      width:min(760px,100%); margin:0 auto; border-radius:28px 28px 0 0; border:1px solid var(--line);
      background:linear-gradient(180deg, rgba(20,25,31,0.96), rgba(10,12,16,0.98)); padding:18px 16px calc(24px + var(--safe-bottom));
      max-height:76vh; overflow:auto;
    }}
    .status-head {{ display:flex; justify-content:space-between; gap:12px; align-items:center; margin-bottom:14px; }}
    .status-list {{ display:grid; gap:10px; }}
    .status-row {{
      padding:12px; border:1px solid var(--line); border-radius:18px; background:rgba(255,255,255,0.05);
    }}
    .status-row .state {{ font-size:.76rem; font-weight:900; letter-spacing:.08em; text-transform:uppercase; color:var(--accent-2); }}
    .status-row.failed .state {{ color:var(--danger); }}
    .status-label {{ margin-top:6px; font-weight:800; line-height:1.35; }}
    .status-sub {{ margin-top:6px; color:var(--muted); font-size:.84rem; line-height:1.45; }}
    .status-actions {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:10px; }}
    .empty {{
      min-height:36vh; display:grid; place-items:center; border:1px dashed rgba(255,255,255,0.16); border-radius:24px; color:var(--muted); text-align:center; padding:24px;
    }}
    .loading {{
      min-height:36vh; display:grid; place-items:center; border:1px dashed rgba(255,255,255,0.12); border-radius:24px; color:var(--muted); text-align:center; padding:24px;
    }}
    .header.compact {{
      padding-bottom:8px;
      margin-bottom:4px;
    }}
    .header.compact .kicker,
    .header.compact .subtitle,
    .header.compact .sync-note {{
      display:none;
    }}
    .header.compact .title {{
      font-size:1rem;
      line-height:1.12;
    }}
  </style>
</head>
<body>
  <main class="shell">
    <header id="header" class="header">
      <div class="topbar">
        <button id="backButton" class="back hidden">‹</button>
        <div class="title-wrap">
          <p class="kicker">Instagram Reel Library</p>
          <h1 id="screenTitle" class="title">Reel Organizer</h1>
          <p id="screenSubtitle" class="subtitle">A mobile-first reel library that stays clean and actionable.</p>
          <p id="syncNote" class="sync-note">Connecting to your live reel library…</p>
        </div>
        <button id="refreshButton" class="refresh-btn">↻</button>
        <div class="status-wrap">
          <button id="statusButton" class="status-btn">◎</button>
          <span id="statusBadge" class="status-badge">0</span>
        </div>
      </div>
      <input id="searchInput" class="search" type="search" placeholder="Search lists and items" />
    </header>
    <section id="stats" class="stats"></section>
    <section id="content" class="content"></section>
  </main>

  <section id="statusSheet" class="status-sheet">
    <div class="status-panel">
      <div class="status-head">
        <div>
          <p class="kicker">Processing Center</p>
          <h2 style="margin:0; font-size:1.35rem;">Reel Status</h2>
        </div>
        <button id="closeStatus" class="status-btn">×</button>
      </div>
      <div id="statusSummary" class="stats"></div>
      <div id="statusList" class="status-list"></div>
    </div>
  </section>

  <section id="floatingPlayerRoot" class="floating-player-root hidden" aria-live="polite">
    <div id="floatingPlayerBackdrop" class="floating-player-backdrop"></div>
    <article id="floatingPlayerFrame" class="floating-player-frame hidden">
      <div id="floatingPlayerSurface" class="floating-player-media">
        <video id="floatingPlayerVideo" playsinline preload="metadata"></video>
        <img id="floatingPlayerPoster" alt="" hidden />
        <div id="floatingPlayerEmpty" class="video-empty">This reel is still waiting for local playback or media extraction.</div>
        <div class="floating-player-bar">
          <div class="floating-player-side">
            <button id="playerExpandButton" class="player-control" type="button" aria-label="Expand reel">⤢</button>
          </div>
          <div class="floating-player-side">
            <button id="playerCloseButton" class="player-control" type="button" aria-label="Close reel">×</button>
          </div>
        </div>
        <button id="playerMuteButton" class="player-control bottom-right" type="button" aria-label="Toggle sound">M</button>
        <div class="player-center">
          <button id="playerPlayButton" class="player-play" type="button" aria-label="Play or pause reel">❚❚</button>
        </div>
      </div>
    </article>
    <button id="floatingPlayerPeek" class="floating-player-peek" type="button" aria-label="Restore reel player">›</button>
  </section>

  <script>
    const USER_ID = '{safe_user_id}';
    const state = {{
      mode: 'personalized',
      query: '',
      library: {{ standard: [], personalized: [] }},
      deepSearch: {{ query: '', loading: false, error: '', results: [] }},
      currentList: null,
      currentItem: 0,
      jobs: [],
      dashboard: null,
      loading: true
    }};

    const content = document.getElementById('content');
    const stats = document.getElementById('stats');
    const screenTitle = document.getElementById('screenTitle');
    const screenSubtitle = document.getElementById('screenSubtitle');
    const backButton = document.getElementById('backButton');
    const statusButton = document.getElementById('statusButton');
    const refreshButton = document.getElementById('refreshButton');
    const statusSheet = document.getElementById('statusSheet');
    const statusSummary = document.getElementById('statusSummary');
    const statusList = document.getElementById('statusList');
    const searchInput = document.getElementById('searchInput');
    const syncNote = document.getElementById('syncNote');
    const statusBadge = document.getElementById('statusBadge');
    const header = document.getElementById('header');
    const floatingPlayerRoot = document.getElementById('floatingPlayerRoot');
    const floatingPlayerBackdrop = document.getElementById('floatingPlayerBackdrop');
    const floatingPlayerFrame = document.getElementById('floatingPlayerFrame');
    const floatingPlayerVideo = document.getElementById('floatingPlayerVideo');
    const floatingPlayerPoster = document.getElementById('floatingPlayerPoster');
    const floatingPlayerEmpty = document.getElementById('floatingPlayerEmpty');
    const playerExpandButton = document.getElementById('playerExpandButton');
    const playerCloseButton = document.getElementById('playerCloseButton');
    const playerMuteButton = document.getElementById('playerMuteButton');
    const playerPlayButton = document.getElementById('playerPlayButton');
    const floatingPlayerPeek = document.getElementById('floatingPlayerPeek');

    const playerUi = {{
      active: false,
      ready: false,
      mode: 'mini',
      dockedSide: null,
      x: 0,
      y: 0,
      width: 0,
      height: 0,
      vx: 0,
      vy: 0,
      dragging: false,
      pointerId: null,
      gesture: null,
      startPointerX: 0,
      startPointerY: 0,
      dragOriginX: 0,
      dragOriginY: 0,
      dragMoved: false,
      lastMoveTs: 0,
      lastMoveX: 0,
      lastMoveY: 0,
      animationFrame: 0,
      paintFrame: 0,
      restoreX: 0,
      restoreY: 0,
      restoreMode: 'mini',
      controlsVisible: false,
      controlsTimer: 0,
      muted: true,
      itemKey: '',
      mediaReadyKey: '',
    }};

    function escapeHtml(value) {{
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }}

    function modeCollections() {{
      return state.library[state.mode] || [];
    }}

    function matchesItem(item, q) {{
      if (!q) return true;
      const normalizedQuery = q.toLowerCase();
      return `${{item.name}} ${{item.summary}} ${{item.product_name || ''}} ${{item.product_brand || ''}}`.toLowerCase().includes(normalizedQuery);
    }}

    function matchesCollection(collection, q) {{
      if (!q) return true;
      const normalizedQuery = q.toLowerCase();
      return `${{collection.parent_title || ''}} ${{collection.list_title}}`.toLowerCase().includes(normalizedQuery) || collection.items.some((item) => matchesItem(item, q));
    }}

    function visibleCollections() {{
      return modeCollections().filter((collection) => matchesCollection(collection, state.query));
    }}

    function visibleItemsForCurrentList() {{
      const collection = visibleCollections()[state.currentList];
      return collection ? collection.items.filter((item) => matchesItem(item, state.query)) : [];
    }}

    function normalizeDeepSearchPayload(payload) {{
      if (Array.isArray(payload?.results)) return payload.results;
      if (Array.isArray(payload?.result?.hits)) {{
        return payload.result.hits.map((hit) => ({{
          score: hit._rankingScore || 0,
          matched_fields: [],
          id: hit.id,
          reel_id: hit.reel_id,
          shortcode: hit.shortcode,
          url: hit.url,
          received_at: hit.received_at,
          item_names: hit.item_names || [],
          product_names: hit.product_names || [],
          brands: hit.brands || [],
          entities: hit.entities || [],
          locations: hit.locations || [],
          visual_entities: hit.visual_entities || [],
          visible_text: hit.visible_text || [],
          visual_supporting_points: hit.visual_supporting_points || [],
          visual_summary: hit.visual_summary || '',
          visual_theme: hit.visual_theme || '',
          match_reasons: hit.match_reasons || [],
          media: hit.media || {{}},
        }}));
      }}
      return [];
    }}

    function primaryDeepSearchTitle(result) {{
      return result.item_names?.[0]
        || result.product_names?.[0]
        || result.brands?.[0]
        || result.shortcode
        || 'Saved reel';
    }}

    function deepSearchSummary(result) {{
      const reasons = result.match_reasons || [];
      if (reasons.length) return reasons.slice(0, 3).join(' · ');
      if (result.visual_summary) return result.visual_summary;
      const parts = [
        ...(result.product_names || []),
        ...(result.brands || []),
        ...(result.entities || []),
        ...(result.locations || []),
        ...(result.visual_entities || []),
        ...(result.visible_text || []),
        ...(result.visual_supporting_points || []),
      ].filter(Boolean);
      return parts.slice(0, 8).join(' · ') || 'Matched from your saved reel metadata.';
    }}

    function deepSearchPlayerItem(result) {{
      const media = result.media || {{}};
      return {{
        reel_id: result.reel_id || result.id,
        name: primaryDeepSearchTitle(result),
        summary: deepSearchSummary(result),
        local_video_url: media.local_video_url || '',
        thumbnail_url: media.thumbnail_url || '',
        media_status: media.media_status || '',
      }};
    }}

    function deepSearchSourceLabel(result) {{
      const fields = new Set((result.matched_fields || []).map((field) => String(field).split(':')[0]));
      const hasAny = (names) => names.some((name) => fields.has(name));
      if (hasAny(['item_names', 'product_names', 'brands', 'models', 'entities'])) return 'Best match';
      if (hasAny(['visual_entities', 'visual_summary', 'visible_text'])) return 'Visual match';
      if (hasAny(['caption', 'transcript', 'hashtags'])) return 'Text match';
      if (hasAny(['locations', 'subdomains', 'canonical_domains', 'primary_category', 'secondary_category'])) return 'Category match';
      return 'Deep Search';
    }}

    let deepSearchTimer = null;
    let deepSearchRequestId = 0;
    function scheduleDeepSearch(query) {{
      if (deepSearchTimer) clearTimeout(deepSearchTimer);
      const trimmed = query.trim();
      if (!trimmed) {{
        state.deepSearch = {{ query: '', loading: false, error: '', results: [] }};
        render();
        return;
      }}
      state.deepSearch = {{ ...state.deepSearch, query: trimmed, loading: true, error: '' }};
      render();
      deepSearchTimer = setTimeout(() => runDeepSearch(trimmed), 220);
    }}

    async function runDeepSearch(query) {{
      const requestId = ++deepSearchRequestId;
      try {{
        const response = await fetch(`/deep-search?q=${{encodeURIComponent(query)}}&user_id=${{encodeURIComponent(USER_ID)}}&limit=30`);
        if (!response.ok) throw new Error('Search failed');
        const payload = await response.json();
        if (requestId !== deepSearchRequestId) return;
        state.deepSearch = {{
          query,
          loading: false,
          error: '',
          results: normalizeDeepSearchPayload(payload),
        }};
      }} catch (error) {{
        if (requestId !== deepSearchRequestId) return;
        state.deepSearch = {{ query, loading: false, error: 'Search is unavailable right now.', results: [] }};
      }}
      render();
    }}

    async function loadData() {{
      state.loading = true;
      render();
      const [libraryRes, dashboardRes, jobsRes] = await Promise.all([
        fetch(`/library?user_id=${{encodeURIComponent(USER_ID)}}`),
        fetch(`/dashboard?user_id=${{encodeURIComponent(USER_ID)}}`),
        fetch(`/jobs?user_id=${{encodeURIComponent(USER_ID)}}&limit=50`)
      ]);
      state.library = await libraryRes.json();
      state.mode = state.library.personalized?.length ? 'personalized' : 'standard';
      state.dashboard = await dashboardRes.json();
      state.jobs = await jobsRes.json();
      state.loading = false;
      if (state.currentList !== null) {{
        const collections = visibleCollections();
        if (!collections[state.currentList]) {{
          state.currentList = null;
          state.currentItem = 0;
          hideFloatingPlayer();
        }}
      }}
      render();
      scheduleNextRefresh();
    }}

    let refreshTimer = null;
    function scheduleNextRefresh() {{
      if (refreshTimer) clearTimeout(refreshTimer);
      if (state.currentList !== null || playerUi.active || playerUi.dragging) return;
      const dash = state.dashboard || {{}};
      const hasActiveWork = (dash.queued_job_count || 0) > 0 || (dash.running_job_count || 0) > 0;
      refreshTimer = setTimeout(loadData, hasActiveWork ? 5000 : 20000);
    }}

    function renderStats() {{
      const collections = modeCollections().filter((c) => matchesCollection(c, state.query));
      const items = collections.reduce((sum, c) => sum + c.items.filter((item) => matchesItem(item, state.query)).length, 0);
      const dash = state.dashboard || {{}};
      const jobAttention = (dash.queued_job_count || 0) + (dash.running_job_count || 0);
      statusBadge.textContent = String(jobAttention);
      statusBadge.classList.toggle('visible', jobAttention > 0);
      syncNote.textContent = dash.last_updated
        ? `Last sync ${{new Date(dash.last_updated).toLocaleString()}}`
        : 'Waiting for the first completed sync.';
      stats.innerHTML = '';
    }}

    function clamp(value, min, max) {{
      return Math.min(max, Math.max(min, value));
    }}

    function readInset(name) {{
      return parseFloat(getComputedStyle(document.documentElement).getPropertyValue(name)) || 0;
    }}

    function playerViewport() {{
      return {{
        width: window.innerWidth,
        height: window.innerHeight,
        safeTop: readInset('--safe-top'),
        safeBottom: readInset('--safe-bottom'),
        margin: 12,
        peek: 26,
      }};
    }}

    function playerSizeForMode(mode) {{
      const view = playerViewport();
      if (mode === 'expanded') {{
        let height = Math.min(view.height - view.safeTop - view.safeBottom - 40, 720);
        let width = Math.round(height * 9 / 16);
        if (width > view.width - 24) {{
          width = view.width - 24;
          height = Math.round(width * 16 / 9);
        }}
        return {{ width, height }};
      }}
      const baseHeight = clamp(Math.round(view.height * 0.35), 240, 360);
      let height = clamp(Math.round(baseHeight * 1.4), 320, 500);
      if (mode === 'compact') height = Math.round(height * 0.84);
      return {{ width: Math.round(height * 9 / 16), height }};
    }}

    function playerBoundsForMode(mode) {{
      const view = playerViewport();
      const size = playerSizeForMode(mode);
      return {{
        minX: view.margin,
        maxX: view.width - view.margin - size.width,
        minY: view.safeTop + 10,
        maxY: view.height - view.safeBottom - 12 - size.height,
      }};
    }}

    function playerDragBoundsForMode(mode) {{
      const view = playerViewport();
      const size = playerSizeForMode(mode);
      const snapBounds = playerBoundsForMode(mode);
      return {{
        minX: -size.width + view.peek,
        maxX: view.width - view.peek,
        minY: snapBounds.minY - 8,
        maxY: snapBounds.maxY + 8,
      }};
    }}

    function playerCornerTargets(mode) {{
      const bounds = playerBoundsForMode(mode);
      return [
        {{ name: 'top-left', x: bounds.minX, y: bounds.minY, mode }},
        {{ name: 'top-right', x: bounds.maxX, y: bounds.minY, mode }},
        {{ name: 'bottom-left', x: bounds.minX, y: bounds.maxY, mode }},
        {{ name: 'bottom-right', x: bounds.maxX, y: bounds.maxY, mode }},
      ];
    }}

    function centerTargetForExpanded() {{
      const view = playerViewport();
      const size = playerSizeForMode('expanded');
      return {{
        mode: 'expanded',
        x: Math.round((view.width - size.width) / 2),
        y: Math.round(Math.max(view.safeTop + 12, (view.height - view.safeBottom - size.height) / 2)),
        width: size.width,
        height: size.height,
        dockedSide: null,
      }};
    }}

    function nearestCornerTarget(x, y, mode, vx = 0, vy = 0) {{
      const projectedX = x + (vx * 180);
      const projectedY = y + (vy * 180);
      return playerCornerTargets(mode).reduce((best, target) => {{
        const score = Math.hypot(projectedX - target.x, projectedY - target.y);
        if (!best || score < best.score) return {{ target, score }};
        return best;
      }}, null).target;
    }}

    function dockTarget(side, y, mode) {{
      const view = playerViewport();
      const size = playerSizeForMode(mode);
      const bounds = playerBoundsForMode(mode);
      return {{
        mode,
        x: side === 'left' ? -size.width + view.peek : view.width - view.peek,
        y: clamp(y, bounds.minY, bounds.maxY),
        width: size.width,
        height: size.height,
        dockedSide: side,
      }};
    }}

    function queuePlayerPaint() {{
      if (playerUi.paintFrame) return;
      playerUi.paintFrame = window.requestAnimationFrame(() => {{
        playerUi.paintFrame = 0;
        applyPlayerLayout();
      }});
    }}

    function clearPlayerControlsTimer() {{
      if (playerUi.controlsTimer) {{
        clearTimeout(playerUi.controlsTimer);
        playerUi.controlsTimer = 0;
      }}
    }}

    function showPlayerControls(duration = 1000) {{
      playerUi.controlsVisible = true;
      queuePlayerPaint();
      clearPlayerControlsTimer();
      if (playerUi.mode === 'expanded') return;
      playerUi.controlsTimer = window.setTimeout(() => {{
        playerUi.controlsVisible = false;
        queuePlayerPaint();
      }}, duration);
    }}

    function stopPlayerAnimation() {{
      if (playerUi.animationFrame) {{
        cancelAnimationFrame(playerUi.animationFrame);
        playerUi.animationFrame = 0;
      }}
    }}

    function applyPlayerLayout() {{
      if (!playerUi.active) {{
        floatingPlayerRoot.classList.add('hidden');
        floatingPlayerFrame.classList.add('hidden');
        return;
      }}
      floatingPlayerRoot.classList.remove('hidden');
      floatingPlayerFrame.classList.remove('hidden');
      floatingPlayerRoot.classList.toggle('expanded', playerUi.mode === 'expanded');
      floatingPlayerRoot.classList.toggle('docked-left', playerUi.dockedSide === 'left');
      floatingPlayerRoot.classList.toggle('docked-right', playerUi.dockedSide === 'right');
      floatingPlayerFrame.classList.toggle('dragging', playerUi.dragging);
      floatingPlayerFrame.classList.toggle('compact', playerUi.mode === 'compact');
      floatingPlayerFrame.classList.toggle('docked', Boolean(playerUi.dockedSide));
      floatingPlayerFrame.classList.toggle('paused', !!floatingPlayerVideo.src && floatingPlayerVideo.paused);
      floatingPlayerFrame.classList.toggle('show-controls', playerUi.controlsVisible || playerUi.mode === 'expanded');
      floatingPlayerFrame.style.width = `${{playerUi.width}}px`;
      floatingPlayerFrame.style.height = `${{playerUi.height}}px`;
      floatingPlayerFrame.style.borderRadius = playerUi.mode === 'expanded' ? '30px' : (playerUi.mode === 'compact' ? '24px' : '26px');
      floatingPlayerFrame.style.transform = `translate3d(${{playerUi.x}}px, ${{playerUi.y}}px, 0)`;
      playerExpandButton.textContent = playerUi.mode === 'expanded' ? '↘' : '⤢';
      playerMuteButton.textContent = floatingPlayerVideo.muted ? 'M' : 'S';
      playerPlayButton.textContent = floatingPlayerVideo.paused ? '▶' : '❚❚';
      floatingPlayerPeek.textContent = playerUi.dockedSide === 'left' ? '›' : '‹';
      const view = playerViewport();
      const peekTop = clamp(playerUi.y + (playerUi.height / 2) - 44, view.safeTop + 10, view.height - view.safeBottom - 98);
      floatingPlayerPeek.style.top = `${{Math.round(peekTop)}}px`;
    }}

    function commitPlayerTarget(target) {{
      playerUi.mode = target.mode;
      playerUi.dockedSide = target.dockedSide || null;
      playerUi.x = target.x;
      playerUi.y = target.y;
      playerUi.width = target.width;
      playerUi.height = target.height;
      queuePlayerPaint();
    }}

    function syncFloatingPlayerSurface() {{
      const hasSrc = Boolean(floatingPlayerVideo.getAttribute('src'));
      const hasPoster = Boolean(floatingPlayerPoster.getAttribute('src'));
      const showPoster = hasPoster && (
        !hasSrc ||
        playerUi.mediaReadyKey !== playerUi.itemKey ||
        (floatingPlayerVideo.paused && floatingPlayerVideo.currentTime < 0.05)
      );
      const showVideo = hasSrc && !showPoster;
      floatingPlayerPoster.hidden = !showPoster;
      floatingPlayerVideo.hidden = !showVideo;
      floatingPlayerEmpty.hidden = hasSrc || hasPoster;
    }}

    function animatePlayerTo(target, options = {{}}) {{
      stopPlayerAnimation();
      clearPlayerControlsTimer();
      playerUi.mode = target.mode;
      playerUi.dockedSide = target.dockedSide || null;
      const stiffness = options.stiffness || 0.11;
      const damping = options.damping || 0.68;
      const sizeLerp = options.sizeLerp || 0.18;
      let lastTs = performance.now();
      const finish = () => {{
        playerUi.vx = 0;
        playerUi.vy = 0;
        commitPlayerTarget(target);
        if (options.onComplete) options.onComplete();
      }};
      const step = (now) => {{
        const dt = Math.min(26, now - lastTs) / 16.6667;
        lastTs = now;
        playerUi.vx += (target.x - playerUi.x) * stiffness * dt;
        playerUi.vy += (target.y - playerUi.y) * stiffness * dt;
        playerUi.vx *= Math.pow(damping, dt);
        playerUi.vy *= Math.pow(damping, dt);
        playerUi.x += playerUi.vx * dt;
        playerUi.y += playerUi.vy * dt;
        playerUi.width += (target.width - playerUi.width) * sizeLerp * dt;
        playerUi.height += (target.height - playerUi.height) * sizeLerp * dt;
        queuePlayerPaint();
        const settled = Math.abs(target.x - playerUi.x) < 0.8
          && Math.abs(target.y - playerUi.y) < 0.8
          && Math.abs(target.width - playerUi.width) < 0.8
          && Math.abs(target.height - playerUi.height) < 0.8
          && Math.abs(playerUi.vx) < 0.12
          && Math.abs(playerUi.vy) < 0.12;
        if (settled) {{
          finish();
          return;
        }}
        playerUi.animationFrame = requestAnimationFrame(step);
      }};
      playerUi.animationFrame = requestAnimationFrame(step);
    }}

    function ensureMiniAnchor(mode = 'mini') {{
      const targetMode = mode === 'compact' ? 'compact' : 'mini';
      const size = playerSizeForMode(targetMode);
      if (!playerUi.ready) {{
        const target = playerCornerTargets(targetMode)[3];
        playerUi.ready = true;
        playerUi.mode = targetMode;
        playerUi.width = size.width;
        playerUi.height = size.height;
        playerUi.x = target.x;
        playerUi.y = target.y;
        playerUi.restoreX = target.x;
        playerUi.restoreY = target.y;
        playerUi.restoreMode = targetMode;
        return;
      }}
      if (playerUi.mode === 'expanded') return;
      const bounds = playerBoundsForMode(targetMode);
      playerUi.mode = targetMode;
      playerUi.width = size.width;
      playerUi.height = size.height;
      playerUi.x = clamp(playerUi.x, bounds.minX, bounds.maxX);
      playerUi.y = clamp(playerUi.y, bounds.minY, bounds.maxY);
    }}

    function syncPlayerMedia(item) {{
      const itemKey = item?.reel_id || item?.local_video_url || item?.thumbnail_url || item?.name || '';
      const sameItem = playerUi.itemKey === itemKey;
      playerUi.itemKey = itemKey;
      floatingPlayerVideo.loop = true;
      floatingPlayerVideo.muted = playerUi.muted;
      floatingPlayerVideo.preload = 'auto';
      if (item?.local_video_url) {{
        const hasThumb = Boolean(item.thumbnail_url);
        if (hasThumb && floatingPlayerPoster.getAttribute('src') !== item.thumbnail_url) {{
          floatingPlayerPoster.setAttribute('src', item.thumbnail_url);
        }}
        if (!sameItem || floatingPlayerVideo.getAttribute('src') !== item.local_video_url) {{
          playerUi.mediaReadyKey = '';
          floatingPlayerVideo.pause();
          floatingPlayerVideo.currentTime = 0;
          floatingPlayerVideo.setAttribute('src', item.local_video_url);
          if (item.thumbnail_url) floatingPlayerVideo.setAttribute('poster', item.thumbnail_url);
          else floatingPlayerVideo.removeAttribute('poster');
          floatingPlayerVideo.load();
        }}
        syncFloatingPlayerSurface();
        floatingPlayerVideo.play().catch(() => {{
          syncFloatingPlayerSurface();
          queuePlayerPaint();
        }});
      }} else if (item?.thumbnail_url) {{
        playerUi.mediaReadyKey = '';
        if (floatingPlayerVideo.getAttribute('src')) {{
          floatingPlayerVideo.pause();
          floatingPlayerVideo.removeAttribute('src');
          floatingPlayerVideo.load();
        }}
        if (floatingPlayerPoster.getAttribute('src') !== item.thumbnail_url) {{
          floatingPlayerPoster.setAttribute('src', item.thumbnail_url);
        }}
        syncFloatingPlayerSurface();
      }} else {{
        playerUi.mediaReadyKey = '';
        if (floatingPlayerVideo.getAttribute('src')) {{
          floatingPlayerVideo.pause();
          floatingPlayerVideo.removeAttribute('src');
          floatingPlayerVideo.load();
        }}
        floatingPlayerPoster.removeAttribute('src');
        syncFloatingPlayerSurface();
      }}
      queuePlayerPaint();
    }}

    function openFloatingPlayer(item) {{
      if (!item) return;
      ensureMiniAnchor(playerUi.mode === 'compact' ? 'compact' : 'mini');
      playerUi.active = true;
      syncPlayerMedia(item);
      showPlayerControls(900);
      queuePlayerPaint();
    }}

    function hideFloatingPlayer() {{
      playerUi.active = false;
      playerUi.dragging = false;
      playerUi.dockedSide = null;
      playerUi.controlsVisible = false;
      clearPlayerControlsTimer();
      stopPlayerAnimation();
      floatingPlayerVideo.pause();
      queuePlayerPaint();
    }}

    function expandFloatingPlayer() {{
      if (!playerUi.active) return;
      if (playerUi.mode !== 'expanded') {{
        if (!playerUi.dockedSide) {{
          playerUi.restoreX = playerUi.x;
          playerUi.restoreY = playerUi.y;
          playerUi.restoreMode = playerUi.mode === 'compact' ? 'compact' : 'mini';
        }}
      }}
      showPlayerControls();
      animatePlayerTo(centerTargetForExpanded(), {{ stiffness: 0.12, damping: 0.72, sizeLerp: 0.18 }});
    }}

    function collapseFloatingPlayer() {{
      if (!playerUi.active) return;
      const mode = playerUi.restoreMode === 'compact' ? 'compact' : 'mini';
      ensureMiniAnchor(mode);
      const bounds = playerBoundsForMode(mode);
      const target = {{
        mode,
        x: clamp(playerUi.restoreX || playerUi.x, bounds.minX, bounds.maxX),
        y: clamp(playerUi.restoreY || playerUi.y, bounds.minY, bounds.maxY),
        width: playerSizeForMode(mode).width,
        height: playerSizeForMode(mode).height,
        dockedSide: null,
      }};
      showPlayerControls(900);
      animatePlayerTo(target, {{ stiffness: 0.11, damping: 0.72 }});
    }}

    function restoreDockedPlayer(startDrag = false) {{
      if (!playerUi.dockedSide) return;
      const mode = playerUi.restoreMode === 'compact' ? 'compact' : 'mini';
      const bounds = playerBoundsForMode(mode);
      const size = playerSizeForMode(mode);
      playerUi.mode = mode;
      playerUi.dockedSide = null;
      playerUi.width = size.width;
      playerUi.height = size.height;
      playerUi.x = clamp(playerUi.restoreX || playerUi.x, bounds.minX, bounds.maxX);
      playerUi.y = clamp(playerUi.restoreY || playerUi.y, bounds.minY, bounds.maxY);
      if (!startDrag) {{
        showPlayerControls(900);
        animatePlayerTo({{
          mode,
          x: playerUi.x,
          y: playerUi.y,
          width: size.width,
          height: size.height,
          dockedSide: null,
        }}, {{ stiffness: 0.11, damping: 0.72 }});
      }} else {{
        queuePlayerPaint();
      }}
    }}

    function releaseTargetForMiniPlayer() {{
      const mode = playerUi.mode === 'compact' ? 'compact' : 'mini';
      const size = playerSizeForMode(mode);
      const snapBounds = playerBoundsForMode(mode);
      const projectedX = playerUi.x + (playerUi.vx * 180);
      const projectedY = playerUi.y + (playerUi.vy * 180);
      const shouldDockLeft = (projectedX < snapBounds.minX + 18 && playerUi.vx < -0.12)
        || playerUi.x < (snapBounds.minX - (size.width * 0.28));
      const shouldDockRight = (projectedX > snapBounds.maxX - 18 && playerUi.vx > 0.12)
        || playerUi.x > (snapBounds.maxX + (size.width * 0.28));
      if (shouldDockLeft) {{
        const fallback = nearestCornerTarget(playerUi.x, playerUi.y, mode, playerUi.vx, playerUi.vy);
        playerUi.restoreX = fallback.x;
        playerUi.restoreY = fallback.y;
        playerUi.restoreMode = mode;
        return dockTarget('left', projectedY, mode);
      }}
      if (shouldDockRight) {{
        const fallback = nearestCornerTarget(playerUi.x, playerUi.y, mode, playerUi.vx, playerUi.vy);
        playerUi.restoreX = fallback.x;
        playerUi.restoreY = fallback.y;
        playerUi.restoreMode = mode;
        return dockTarget('right', projectedY, mode);
      }}
      const snap = nearestCornerTarget(playerUi.x, playerUi.y, mode, playerUi.vx, playerUi.vy);
      playerUi.restoreX = snap.x;
      playerUi.restoreY = snap.y;
      playerUi.restoreMode = mode;
      return {{
        mode,
        x: snap.x,
        y: snap.y,
        width: size.width,
        height: size.height,
        dockedSide: null,
      }};
    }}

    function beginPlayerGesture(event, gesture) {{
      stopPlayerAnimation();
      clearPlayerControlsTimer();
      playerUi.pointerId = event.pointerId;
      playerUi.dragging = true;
      playerUi.gesture = gesture;
      playerUi.dragMoved = false;
      playerUi.startPointerX = event.clientX;
      playerUi.startPointerY = event.clientY;
      playerUi.dragOriginX = playerUi.x;
      playerUi.dragOriginY = playerUi.y;
      playerUi.lastMoveX = event.clientX;
      playerUi.lastMoveY = event.clientY;
      playerUi.lastMoveTs = performance.now();
      showPlayerControls(800);
      queuePlayerPaint();
      window.addEventListener('pointermove', onPlayerPointerMove);
      window.addEventListener('pointerup', onPlayerPointerUp);
      window.addEventListener('pointercancel', onPlayerPointerUp);
    }}

    function onPlayerPointerMove(event) {{
      if (!playerUi.dragging || event.pointerId !== playerUi.pointerId) return;
      const now = performance.now();
      const dx = event.clientX - playerUi.startPointerX;
      const dy = event.clientY - playerUi.startPointerY;
      if (Math.abs(dx) > 3 || Math.abs(dy) > 3) playerUi.dragMoved = true;
      const dt = Math.max(8, now - playerUi.lastMoveTs);
      const instantVx = (event.clientX - playerUi.lastMoveX) / dt;
      const instantVy = (event.clientY - playerUi.lastMoveY) / dt;
      playerUi.vx = (playerUi.vx * 0.65) + (instantVx * 0.35);
      playerUi.vy = (playerUi.vy * 0.65) + (instantVy * 0.35);
      playerUi.lastMoveX = event.clientX;
      playerUi.lastMoveY = event.clientY;
      playerUi.lastMoveTs = now;

      if (playerUi.gesture === 'expanded-pan') {{
        const expanded = centerTargetForExpanded();
        const lift = Math.max(0, dy);
        const friction = lift * 0.92;
        playerUi.mode = 'expanded';
        playerUi.width = expanded.width;
        playerUi.height = expanded.height;
        playerUi.x = expanded.x;
        playerUi.y = expanded.y + friction;
        queuePlayerPaint();
        return;
      }}

      const mode = playerUi.mode === 'compact' ? 'compact' : 'mini';
      const bounds = playerDragBoundsForMode(mode);
      playerUi.mode = mode;
      playerUi.width = playerSizeForMode(mode).width;
      playerUi.height = playerSizeForMode(mode).height;
      playerUi.dockedSide = null;
      playerUi.x = clamp(playerUi.dragOriginX + dx, bounds.minX, bounds.maxX);
      playerUi.y = clamp(playerUi.dragOriginY + dy, bounds.minY, bounds.maxY);
      queuePlayerPaint();
    }}

    function onPlayerPointerUp(event) {{
      if (event.pointerId !== playerUi.pointerId) return;
      window.removeEventListener('pointermove', onPlayerPointerMove);
      window.removeEventListener('pointerup', onPlayerPointerUp);
      window.removeEventListener('pointercancel', onPlayerPointerUp);
      const gesture = playerUi.gesture;
      const moved = playerUi.dragMoved;
      const vx = playerUi.vx;
      const vy = playerUi.vy;
      playerUi.dragging = false;
      playerUi.pointerId = null;
      playerUi.gesture = null;
      if (gesture === 'expanded-pan') {{
        const releaseDy = event.clientY - playerUi.startPointerY;
        if (releaseDy > 120 || vy > 0.32) {{
          collapseFloatingPlayer();
        }} else {{
          animatePlayerTo(centerTargetForExpanded(), {{ stiffness: 0.12, damping: 0.72, sizeLerp: 0.18 }});
        }}
        return;
      }}
      if (!moved) {{
        showPlayerControls();
        queuePlayerPaint();
        return;
      }}
      if (Math.abs(vy) > Math.abs(vx) * 1.35 && vy > 0.55 && playerUi.mode === 'mini') {{
        const size = playerSizeForMode('compact');
        const target = nearestCornerTarget(playerUi.x, playerUi.y, 'compact', vx, vy);
        playerUi.restoreX = target.x;
        playerUi.restoreY = target.y;
        playerUi.restoreMode = 'compact';
        animatePlayerTo({{
          mode: 'compact',
          x: target.x,
          y: target.y,
          width: size.width,
          height: size.height,
          dockedSide: null,
        }}, {{ stiffness: 0.11, damping: 0.72 }});
        return;
      }}
      if (Math.abs(vy) > Math.abs(vx) * 1.35 && vy < -0.55) {{
        expandFloatingPlayer();
        return;
      }}
      animatePlayerTo(releaseTargetForMiniPlayer(), {{ stiffness: 0.11, damping: 0.72 }});
    }}

    function bindFloatingPlayer() {{
      const isControl = (target) => Boolean(target.closest('.player-control') || target.closest('.player-play'));

      floatingPlayerFrame.addEventListener('pointerdown', (event) => {{
        if (!playerUi.active || isControl(event.target)) return;
        if (playerUi.mode === 'expanded') beginPlayerGesture(event, 'expanded-pan');
        else beginPlayerGesture(event, 'drag');
      }});

      floatingPlayerFrame.addEventListener('click', (event) => {{
        if (!playerUi.active || playerUi.dragMoved || isControl(event.target)) return;
        showPlayerControls();
      }});

      floatingPlayerFrame.addEventListener('dblclick', (event) => {{
        if (!playerUi.active || isControl(event.target)) return;
        if (playerUi.mode === 'expanded') collapseFloatingPlayer();
        else expandFloatingPlayer();
      }});

      floatingPlayerPeek.addEventListener('pointerdown', (event) => {{
        if (!playerUi.dockedSide) return;
        restoreDockedPlayer(true);
        beginPlayerGesture(event, 'drag');
      }});

      floatingPlayerPeek.addEventListener('click', () => {{
        if (!playerUi.dockedSide) return;
        restoreDockedPlayer(false);
      }});

      floatingPlayerBackdrop.addEventListener('click', () => {{
        if (playerUi.mode === 'expanded') collapseFloatingPlayer();
      }});

      playerExpandButton.addEventListener('click', (event) => {{
        event.stopPropagation();
        if (playerUi.mode === 'expanded') collapseFloatingPlayer();
        else expandFloatingPlayer();
      }});

      playerCloseButton.addEventListener('click', (event) => {{
        event.stopPropagation();
        hideFloatingPlayer();
      }});

      playerMuteButton.addEventListener('click', (event) => {{
        event.stopPropagation();
        playerUi.muted = !floatingPlayerVideo.muted;
        floatingPlayerVideo.muted = playerUi.muted;
        showPlayerControls(900);
        queuePlayerPaint();
      }});

      playerPlayButton.addEventListener('click', (event) => {{
        event.stopPropagation();
        if (!floatingPlayerVideo.getAttribute('src')) return;
        if (floatingPlayerVideo.paused) {{
          floatingPlayerVideo.play().catch(() => {{
            queuePlayerPaint();
          }});
        }} else {{
          floatingPlayerVideo.pause();
        }}
        showPlayerControls(900);
        queuePlayerPaint();
      }});

      floatingPlayerVideo.addEventListener('play', () => {{
        playerUi.mediaReadyKey = playerUi.itemKey || '';
        syncFloatingPlayerSurface();
        queuePlayerPaint();
      }});
      floatingPlayerVideo.addEventListener('pause', () => {{
        syncFloatingPlayerSurface();
        queuePlayerPaint();
      }});
      floatingPlayerVideo.addEventListener('loadeddata', () => {{
        syncFloatingPlayerSurface();
        queuePlayerPaint();
      }});
      floatingPlayerVideo.addEventListener('timeupdate', () => {{
        if (floatingPlayerVideo.currentTime >= 0.05) {{
          playerUi.mediaReadyKey = playerUi.itemKey || '';
          syncFloatingPlayerSurface();
          queuePlayerPaint();
        }}
      }});
      floatingPlayerVideo.addEventListener('error', () => {{
        playerUi.mediaReadyKey = '';
        syncFloatingPlayerSurface();
        queuePlayerPaint();
      }});
      floatingPlayerVideo.addEventListener('volumechange', () => {{
        playerUi.muted = floatingPlayerVideo.muted;
        queuePlayerPaint();
      }});

      window.addEventListener('resize', () => {{
        if (!playerUi.active) return;
        if (playerUi.mode === 'expanded') {{
          commitPlayerTarget(centerTargetForExpanded());
          return;
        }}
        ensureMiniAnchor(playerUi.mode === 'compact' ? 'compact' : 'mini');
        queuePlayerPaint();
      }});
    }}

    function renderHome() {{
      if (state.loading) {{
        content.innerHTML = `<div class="loading"><div><h2 style="margin:0 0 8px;">Refreshing your library…</h2><p style="margin:0;">Pulling your latest reels, items, and status.</p></div></div>`;
        return;
      }}
      if (state.query) {{
        renderDeepSearchHome();
        return;
      }}
      const collections = visibleCollections();
      header.classList.remove('compact');
      backButton.classList.add('hidden');
      screenTitle.textContent = 'Your Reel Library';
      screenSubtitle.textContent = '';
      hideFloatingPlayer();
      if (!collections.length) {{
        content.innerHTML = `<div class="empty"><div><h2 style="margin:0 0 8px;">No collections yet</h2><p style="margin:0;">Send a reel link through your connected Instagram DM and it’ll appear here.</p></div></div>`;
        return;
      }}
      content.innerHTML = collections.map((collection, index) => {{
        return `
          <article class="card" data-collection="${{index}}">
            <div class="card-top">
              <div>
                ${{collection.parent_title ? `<p class="card-kicker">${{escapeHtml(collection.parent_title)}}</p>` : ''}}
                <h2 class="card-title">${{escapeHtml(collection.list_title)}}</h2>
              </div>
              <span class="count">${{collection.items.length}} items</span>
            </div>
          </article>
        `;
      }}).join('');
      content.querySelectorAll('[data-collection]').forEach((node) => {{
        node.addEventListener('click', () => {{
          state.currentList = Number(node.dataset.collection);
          state.currentItem = 0;
          render();
        }});
      }});
    }}

    function renderDeepSearchHome() {{
      header.classList.remove('compact');
      backButton.classList.add('hidden');
      screenTitle.textContent = 'Search Results';
      screenSubtitle.textContent = '';
      hideFloatingPlayer();
      const search = state.deepSearch;
      if (search.loading && search.query === state.query) {{
        content.innerHTML = `<div class="loading"><div><h2 style="margin:0 0 8px;">Searching saved reels…</h2><p style="margin:0;">Checking items, products, captions, transcripts, and visuals.</p></div></div>`;
        return;
      }}
      if (search.error) {{
        content.innerHTML = `<div class="empty"><div><h2 style="margin:0 0 8px;">Search unavailable</h2><p style="margin:0;">${{escapeHtml(search.error)}}</p></div></div>`;
        return;
      }}
      const results = search.query === state.query ? search.results : [];
      if (!results.length) {{
        content.innerHTML = `<div class="empty"><div><h2 style="margin:0 0 8px;">No matching reels</h2><p style="margin:0;">Try a broader word like perfume, cafe, gym, bottle, app, or nike.</p></div></div>`;
        return;
      }}
      content.innerHTML = results.map((result, index) => {{
        const title = primaryDeepSearchTitle(result);
        const media = result.media || {{}};
        const chips = [
          ...(result.product_names || []).slice(0, 2),
          ...(result.brands || []).slice(0, 2),
          ...(result.visual_entities || []).slice(0, 3),
          ...(result.visible_text || []).slice(0, 2),
          ...(result.visual_supporting_points || []).slice(0, 1),
          ...(result.locations || []).slice(0, 2),
        ].filter(Boolean).slice(0, 5);
        return `
          <article class="card" data-search-result="${{index}}">
            <div class="card-top">
              <div>
                <p class="card-kicker">${{escapeHtml(deepSearchSourceLabel(result))}}</p>
                <h2 class="card-title">${{escapeHtml(title)}}</h2>
              </div>
            </div>
            <p class="search-reason">${{escapeHtml(deepSearchSummary(result))}}</p>
            <div class="card-meta-row">
              ${{chips.map((chip) => `<span class="mini-chip">${{escapeHtml(chip)}}</span>`).join('')}}
            </div>
          </article>
        `;
      }}).join('');
      content.querySelectorAll('[data-search-result]').forEach((node) => {{
        node.addEventListener('click', () => {{
          const result = results[Number(node.dataset.searchResult)];
          const item = deepSearchPlayerItem(result);
          if (item.local_video_url || item.thumbnail_url) {{
            openFloatingPlayer(item);
            return;
          }}
          if (result.url) window.open(result.url, '_blank', 'noopener,noreferrer');
        }});
      }});
    }}

    function buyBox(item) {{
      if (!item.best_buy_link) return '';
      return `
        <section class="buy-box">
          <p class="kicker" style="margin:0;">Buy Link</p>
          <div style="font-weight:850;">${{escapeHtml(item.product_name || item.name)}}</div>
          <div class="actions">
            <a class="action primary" href="${{escapeHtml(item.best_buy_link)}}" target="_blank" rel="noopener noreferrer">Best Link</a>
            ${{item.amazon_link ? `<a class="action" href="${{escapeHtml(item.amazon_link)}}" target="_blank" rel="noopener noreferrer">Amazon</a>` : ''}}
            ${{item.flipkart_link ? `<a class="action" href="${{escapeHtml(item.flipkart_link)}}" target="_blank" rel="noopener noreferrer">Flipkart</a>` : ''}}
            ${{item.nykaa_link ? `<a class="action" href="${{escapeHtml(item.nykaa_link)}}" target="_blank" rel="noopener noreferrer">Nykaa</a>` : ''}}
          </div>
        </section>
      `;
    }}

    async function deleteCurrentReel() {{
      const collections = visibleCollections();
      const collection = collections[state.currentList];
      const items = visibleItemsForCurrentList();
      const item = items[state.currentItem];
      if (!item?.reel_id) {{
        window.alert('This reel is missing its backend id, so it cannot be deleted yet.');
        return;
      }}
      const confirmed = window.confirm(`Delete "${{item.name}}" from your library? This removes the local reel files too.`);
      if (!confirmed) return;
      const response = await fetch(`/reels/${{encodeURIComponent(item.reel_id)}}`, {{ method: 'DELETE' }});
      if (!response.ok) {{
        window.alert('Delete failed. Please try again.');
        return;
      }}
      state.currentList = null;
      state.currentItem = 0;
      await loadData();
    }}

    async function retryCurrentReel() {{
      const collections = visibleCollections();
      const collection = collections[state.currentList];
      const items = visibleItemsForCurrentList();
      const item = items[state.currentItem];
      if (!item?.reel_id) {{
        window.alert('This reel is missing its backend id, so it cannot be retried yet.');
        return;
      }}
      const response = await fetch(`/reels/${{encodeURIComponent(item.reel_id)}}/retry`, {{ method: 'POST' }});
      if (!response.ok) {{
        window.alert('Retry failed to start. Please try again.');
        return;
      }}
      await loadData();
      statusSheet.classList.add('open');
    }}

    async function retryJobReel(reelId) {{
      const response = await fetch(`/reels/${{encodeURIComponent(reelId)}}/retry`, {{ method: 'POST' }});
      if (!response.ok) {{
        window.alert('Retry failed to start. Please try again.');
        return;
      }}
      await loadData();
    }}

    function renderDetail() {{
      if (state.loading) {{
        content.innerHTML = `<div class="loading"><div><h2 style="margin:0 0 8px;">Refreshing this list…</h2><p style="margin:0;">Updating the reel player and item cards.</p></div></div>`;
        return;
      }}
      const collections = visibleCollections();
      const collection = collections[state.currentList];
      if (!collection) {{
        state.currentList = null;
        hideFloatingPlayer();
        renderHome();
        return;
      }}
      const items = visibleItemsForCurrentList();
      const item = items[state.currentItem] || items[0];
      if (!item) {{
        hideFloatingPlayer();
        content.innerHTML = `<div class="empty"><div><h2 style="margin:0 0 8px;">No matching items</h2><p style="margin:0;">Try a different search or wait for this reel to finish processing.</p></div></div>`;
        return;
      }}
      state.currentItem = Math.max(0, items.indexOf(item));
      header.classList.add('compact');
      backButton.classList.remove('hidden');
      screenTitle.textContent = collection.list_title;
      screenSubtitle.textContent = '';
      content.innerHTML = `
        <section class="detail">
          <article class="detail-card">
            <div class="video-meta">
              <h2 class="detail-title">${{escapeHtml(item?.name || '')}}</h2>
              <div class="detail-meta">
                <span class="mini-chip">${{collection.parent_title ? escapeHtml(collection.parent_title) : 'Saved reel'}}</span>
                <span class="mini-chip">Item ${{Math.min(state.currentItem + 1, items.length)}} of ${{items.length}}</span>
                ${{item?.best_buy_link ? '<span class="mini-chip">Buy link ready</span>' : ''}}
              </div>
              <p class="detail-summary">${{escapeHtml(item?.summary || '')}}</p>
              ${{buyBox(item)}}
              <div class="actions">
                ${{item?.media_status === 'failed' || item?.name === 'Processing Failed' ? '<button id="retryReelButton" class="action" type="button">Retry Reel</button>' : ''}}
                <button id="deleteReelButton" class="action danger" type="button">Delete Reel</button>
              </div>
            </div>
          </article>
          <section class="items">
            ${{
              items.map((entry, index) => `
                <article class="item ${{index === state.currentItem ? 'active' : ''}}" data-item="${{index}}">
                  <h3>${{escapeHtml(entry.name)}}</h3>
                  <p>${{escapeHtml(entry.summary || 'No summary available.')}}</p>
                </article>
              `).join('')
            }}
          </section>
        </section>
      `;
      content.querySelectorAll('[data-item]').forEach((node) => {{
        node.addEventListener('click', () => {{
          state.currentItem = Number(node.dataset.item);
          renderDetail();
        }});
      }});
      const deleteButton = document.getElementById('deleteReelButton');
      if (deleteButton) {{
        deleteButton.addEventListener('click', deleteCurrentReel);
      }}
      const retryButton = document.getElementById('retryReelButton');
      if (retryButton) {{
        retryButton.addEventListener('click', retryCurrentReel);
      }}
      openFloatingPlayer(item);
    }}

    function renderStatus() {{
      const dash = state.dashboard || {{}};
      statusSummary.innerHTML = `
        <span class="chip">${{dash.queued_job_count || 0}} Queued</span>
        <span class="chip">${{dash.running_job_count || 0}} Running</span>
        <span class="chip">${{dash.failed_url_count || 0}} Failed reels</span>
      `;
      if (!state.jobs.length) {{
        const pendingReels = dash.pending_url_count || 0;
        const message = pendingReels > 0
          ? `${{pendingReels}} saved reels are still marked pending, but there are no active processing jobs right now. Use refresh/retry on a reel if one looks stuck.`
          : 'Your processing activity will appear here.';
        statusList.innerHTML = `<div class="empty" style="min-height:20vh;"><div><h3 style="margin:0 0 8px;">No recent jobs</h3><p style="margin:0;">${{escapeHtml(message)}}</p></div></div>`;
        return;
      }}
      const describeJob = (job) => {{
        if (job.job_type === 'rebuild_library') return 'Refreshing your library';
        if (job.reel_shortcode) return `Reel ${{job.reel_shortcode}}`;
        if (job.reel_url) return job.reel_url;
        return job.reel_id;
      }};
      statusList.innerHTML = state.jobs.map((job) => `
        <article class="status-row ${{job.status === 'failed' ? 'failed' : ''}}">
          <div class="state">${{escapeHtml(job.status)}}</div>
          <div class="status-label">${{escapeHtml(describeJob(job))}}</div>
          <div class="status-sub">
            Attempts: ${{job.attempts}}${{job.error_message ? ` · ${{escapeHtml(job.error_message)}}` : ''}}
          </div>
          <div class="status-actions">
            ${{job.status === 'failed' && job.job_type === 'process_reel' && job.reel_id ? `<button class="action" type="button" data-retry-job="${{escapeHtml(job.reel_id)}}">Retry Reel</button>` : ''}}
          </div>
        </article>
      `).join('');
      statusList.querySelectorAll('[data-retry-job]').forEach((node) => {{
        node.addEventListener('click', () => retryJobReel(node.dataset.retryJob));
      }});
    }}

    function render() {{
      renderStats();
      renderStatus();
      if (state.currentList === null) renderHome();
      else renderDetail();
      scheduleNextRefresh();
    }}
    backButton.addEventListener('click', () => {{
      state.currentList = null;
      state.currentItem = 0;
      hideFloatingPlayer();
      render();
    }});
    statusButton.addEventListener('click', () => statusSheet.classList.add('open'));
    refreshButton.addEventListener('click', () => loadData());
    document.getElementById('closeStatus').addEventListener('click', () => statusSheet.classList.remove('open'));
    statusSheet.addEventListener('click', (event) => {{
      if (event.target === statusSheet) statusSheet.classList.remove('open');
    }});
    searchInput.addEventListener('input', (event) => {{
      state.query = event.target.value.trim();
      state.currentList = null;
      hideFloatingPlayer();
      scheduleDeepSearch(state.query);
      render();
    }});

    bindFloatingPlayer();
    loadData();
  </script>
</body>
</html>"""


# App-shell pages must NEVER be browser-cached: with no Cache-Control header,
# iOS Safari (especially saved-to-home-screen) serves a days-old cached build
# after deploys, so users keep seeing bugs that are already fixed in prod.
def app_shell(html: str) -> HTMLResponse:
    return HTMLResponse(html, headers={"Cache-Control": "no-store, must-revalidate"})


@router.get("/", response_class=HTMLResponse)
def root_app(request: Request):
    csrf_token = create_login_csrf(request)
    return app_shell(build_landing_html(csrf_token, current_user(request)))


@router.get("/privacy", response_class=HTMLResponse)
def privacy_page():
    return HTMLResponse(build_privacy_html())


@router.get("/terms", response_class=HTMLResponse)
def terms_page():
    return HTMLResponse(build_terms_html())


@router.get("/data-deletion", response_class=HTMLResponse)
def data_deletion_page():
    return HTMLResponse(build_data_deletion_html())


@router.get("/demo/ui-review", response_class=HTMLResponse)
def demo_ui_review():
    return HTMLResponse(build_demo_library_review_html())


@router.get("/app", response_class=HTMLResponse)
def my_app(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    return app_shell(build_web_app_html(user["id"]))


@router.get("/folders-app", response_class=HTMLResponse)
def folders_app(request: Request):
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    from app.api.routes.folders import folders_enabled

    if not folders_enabled(user["id"]):
        return RedirectResponse(url="/app", status_code=303)
    return app_shell(build_folders_html(user["id"]))


@router.get("/dev-login")
def dev_login(request: Request, user_id: str = "default"):
    """Local-only session shortcut so the app can be tested without Google.
    Hard-disabled wherever sessions are https-only (prod/staging) and for any
    non-localhost client."""
    from app.services.auth import SESSION_USER_KEY, get_user_by_id

    client_host = request.client.host if request.client else ""
    if settings.session_https_only or client_host not in {"127.0.0.1", "::1"}:
        return RedirectResponse(url="/", status_code=303)
    if not get_user_by_id(user_id):
        return RedirectResponse(url="/", status_code=303)
    request.session[SESSION_USER_KEY] = user_id
    return RedirectResponse(url="/app", status_code=303)


@router.get("/demo-login/{token}")
def demo_link_login(token: str, request: Request):
    """Shareable magic link that signs the visitor into the curated demo account.

    Enabled only when DEMO_ACCESS_TOKEN (16+ chars) and DEMO_ACCOUNT_EMAIL are
    both set. Never opens an admin account, and marks the session so
    destructive endpoints refuse it. Rotate DEMO_ACCESS_TOKEN to kill a leaked
    link instantly."""
    import secrets as _secrets

    from app.services.auth import (
        DEMO_LINK_SESSION_KEY,
        SESSION_USER_KEY,
        get_user_by_email,
        user_is_admin,
    )

    expected = settings.demo_access_token
    if not expected or len(expected) < 16 or not settings.demo_account_email:
        return RedirectResponse(url="/", status_code=303)
    if not _secrets.compare_digest(token.encode("utf-8"), expected.encode("utf-8")):
        return RedirectResponse(url="/", status_code=303)
    user = get_user_by_email(settings.demo_account_email)
    if not user or user_is_admin(user):
        return RedirectResponse(url="/", status_code=303)
    request.session.clear()
    request.session[SESSION_USER_KEY] = user["id"]
    request.session[DEMO_LINK_SESSION_KEY] = True
    return RedirectResponse(url="/app", status_code=303)


@router.get("/app/{user_id}", response_class=HTMLResponse)
def user_app(user_id: str, request: Request):
    if is_demo_user(user_id):
        return app_shell(build_web_app_html(user_id))
    user = current_user(request)
    if not user:
        return RedirectResponse(url="/", status_code=303)
    if user["id"] != user_id:
        return RedirectResponse(url="/app", status_code=303)
    return app_shell(build_web_app_html(user_id))
