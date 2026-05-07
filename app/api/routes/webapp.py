from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["webapp"])


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


def build_landing_html() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>Reel Organizer</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #07090c;
      --text: #f4f6f8;
      --muted: #9ca4af;
      --line: rgba(255,255,255,0.1);
      --accent: #eed7a6;
      --accent-2: #9fd5c5;
      --shadow: 0 24px 70px rgba(0,0,0,0.38);
      --safe-top: env(safe-area-inset-top, 0px);
      --safe-bottom: env(safe-area-inset-bottom, 0px);
    }
    * { box-sizing: border-box; }
    html, body { margin:0; min-height:100%; background:var(--bg); color:var(--text); font-family: ui-rounded, "SF Pro Rounded", "Avenir Next", system-ui, sans-serif; }
    body {
      background:
        radial-gradient(circle at top left, rgba(238, 215, 166, 0.14), transparent 26rem),
        radial-gradient(circle at top right, rgba(159, 213, 197, 0.12), transparent 24rem),
        linear-gradient(180deg, #10141b 0%, #07090c 50%, #060709 100%);
    }
    .shell {
      width:min(760px, 100%);
      min-height:100vh;
      margin:0 auto;
      padding: calc(24px + var(--safe-top)) 18px calc(32px + var(--safe-bottom));
      display:grid;
      gap:18px;
      align-content:center;
    }
    .hero, .card {
      border:1px solid var(--line);
      border-radius:28px;
      background:linear-gradient(180deg, rgba(255,255,255,0.085), rgba(255,255,255,0.045));
      box-shadow: var(--shadow);
      padding:20px;
    }
    .kicker {
      margin:0 0 8px;
      color:var(--accent-2);
      font-size:.72rem;
      font-weight:900;
      letter-spacing:.11em;
      text-transform:uppercase;
    }
    h1 {
      margin:0;
      font-size: clamp(2rem, 10vw, 3.3rem);
      line-height:.95;
      letter-spacing:-.06em;
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
    .secondary-link {
      display:inline-flex;
      align-items:center;
      justify-content:center;
      width:100%;
      min-height:52px;
      border-radius:18px;
      border:1px solid var(--line);
      background:rgba(255,255,255,0.06);
      color:var(--text);
      text-decoration:none;
      font-size:.98rem;
      font-weight:800;
    }
    input, button {
      width:100%;
      min-height:52px;
      border-radius:18px;
      border:1px solid var(--line);
      background:rgba(255,255,255,0.07);
      color:var(--text);
      padding:0 16px;
      font-size:.98rem;
    }
    button {
      background:rgba(238,215,166,0.14);
      border-color:rgba(238,215,166,0.35);
      font-weight:900;
      cursor:pointer;
    }
    ol {
      margin:14px 0 0;
      padding-left:18px;
      color:var(--muted);
      line-height:1.6;
    }
    .tiny {
      font-size:.82rem;
      color:#7e8694;
    }
  </style>
</head>
<body>
  <main class="shell">
    <section class="hero">
      <p class="kicker">Live Reel Library</p>
      <h1>Send reels to Telegram. Browse them here.</h1>
      <p>Your app organizes saved Instagram reels into clean lists, lets you preview local copies, and keeps failed reels recoverable instead of disappearing.</p>
      <form id="openForm" class="form">
        <input id="userIdInput" type="text" inputmode="numeric" autocomplete="off" placeholder="Enter your Telegram user ID" />
        <button type="submit">Open My Library</button>
        <a class="secondary-link" href="/app/demo">View Demo Library</a>
      </form>
      <p class="tiny">For the current local build, the Telegram user ID is the account key used to separate one person’s library from another’s.</p>
    </section>
    <section class="card">
      <p class="kicker">How It Works</p>
      <ol>
        <li>Send a reel URL to the Telegram bot.</li>
        <li>Wait for the processing center to finish the reel.</li>
        <li>Open your library with the same Telegram user ID.</li>
      </ol>
    </section>
  </main>
  <script>
    document.getElementById('openForm').addEventListener('submit', (event) => {
      event.preventDefault();
      const value = document.getElementById('userIdInput').value.trim();
      if (!value) return;
      window.location.href = `/app/${encodeURIComponent(value)}`;
    });
  </script>
</body>
</html>"""


def build_web_app_html(user_id: str) -> str:
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
    .mini-chip {{
      display:inline-flex; align-items:center; min-height:28px; padding:0 10px; border-radius:999px;
      border:1px solid var(--line); background:rgba(255,255,255,0.045); color:var(--muted); font-size:.72rem; font-weight:850;
    }}
    .card-top {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; margin-bottom:12px; }}
    .card-kicker {{ margin:0 0 8px; color:var(--accent-2); font-size:.7rem; font-weight:900; letter-spacing:.11em; text-transform:uppercase; }}
    .card-title {{ margin:0; font-size:1.08rem; line-height:1.15; letter-spacing:-.02em; }}
    .count {{ padding:6px 8px; border-radius:999px; background:rgba(159,213,197,0.12); color:var(--accent-2); font-size:.72rem; font-weight:900; }}
    .detail {{ display:grid; gap:12px; }}
    .detail-card {{
      border:1px solid var(--line); border-radius:24px; background:linear-gradient(180deg, rgba(255,255,255,0.085), rgba(255,255,255,0.045));
      box-shadow: var(--shadow); padding:16px;
    }}
    .mini-player-shell {{
      position:fixed; right:12px; bottom:calc(12px + var(--safe-bottom)); z-index:38;
      display:none;
    }}
    .mini-player-shell.open {{ display:block; }}
    .mini-player-shell.expanded {{
      inset:0; right:0; bottom:0; display:grid; place-items:center;
      background:rgba(5,7,10,0.72); backdrop-filter:blur(10px); padding:20px;
    }}
    .mini-player-card {{
      position:relative; height:min(35vh, 280px); aspect-ratio:9 / 16; border-radius:22px; overflow:hidden;
      border:1px solid var(--line); background:#050607; box-shadow:var(--shadow);
      touch-action:none;
    }}
    .mini-player-shell.expanded .mini-player-card {{
      height:min(78vh, 680px);
      max-width:min(92vw, 420px);
    }}
    .video-wrap {{
      position:relative; width:100%; height:100%; background:#050607;
    }}
    .mini-player-video {{
      width:100%; height:100%; display:block; object-fit:cover; background:#050607;
    }}
    .mini-player-overlay {{
      position:absolute; inset:0; opacity:0; pointer-events:none; transition:opacity .18s ease;
      background:linear-gradient(180deg, rgba(5,7,10,0.34), rgba(5,7,10,0.02) 34%, rgba(5,7,10,0.42));
    }}
    .mini-player-card.show-ui .mini-player-overlay {{
      opacity:1; pointer-events:none;
    }}
    .mini-player-btn {{
      position:absolute; width:32px; height:32px; border-radius:999px; border:1px solid rgba(255,255,255,0.18);
      background:rgba(7,9,12,0.55); color:var(--text); display:inline-flex; align-items:center; justify-content:center;
      cursor:pointer; font-size:.9rem; pointer-events:auto;
    }}
    .mini-player-btn.expand {{ top:8px; left:8px; }}
    .mini-player-btn.close {{ top:8px; right:8px; }}
    .mini-player-btn.mute {{ right:8px; bottom:8px; }}
    .mini-player-peek {{
      position:absolute; top:50%; left:-14px; transform:translateY(-50%);
      width:28px; height:48px; border-radius:999px; border:1px solid rgba(255,255,255,0.18);
      background:rgba(7,9,12,0.76); color:var(--text); display:none; align-items:center; justify-content:center;
      cursor:pointer; z-index:3;
    }}
    .mini-player-peek.visible {{ display:inline-flex; }}
    .mini-player-dragzone {{
      position:absolute; inset:0; cursor:grab; z-index:1;
    }}
    .mini-player-dragzone:active {{ cursor:grabbing; }}
    .mini-player-center {{
      position:absolute; inset:0; display:grid; place-items:center;
    }}
    .mini-player-play {{
      width:56px; height:56px; border-radius:999px; border:1px solid rgba(255,255,255,0.2);
      background:rgba(7,9,12,0.56); color:#ffffff; display:inline-flex; align-items:center; justify-content:center;
      cursor:pointer; font-size:1.2rem; pointer-events:auto;
    }}
    .video-meta {{ display:grid; gap:10px; }}
    .detail-title {{ margin:0; font-size:1.2rem; line-height:1.05; letter-spacing:-.03em; }}
    .detail-summary {{ margin:0; color:var(--muted); font-size:.94rem; line-height:1.55; }}
    .detail-meta {{ display:flex; gap:8px; flex-wrap:wrap; }}
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
    .item-body {{ display:grid; gap:10px; margin-top:10px; }}
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
          <p class="kicker">Telegram Reel Library</p>
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

  <script>
    const USER_ID = '{safe_user_id}';
    const state = {{
      mode: 'standard',
      query: '',
      library: {{ standard: [], personalized: [] }},
      currentList: null,
      currentItem: 0,
      playerOpen: false,
      playerExpanded: false,
      playerControlsVisible: true,
      playerOffset: {{ x: 0, y: 0 }},
      playerMuted: true,
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
      return `${{item.name}} ${{item.summary}} ${{item.product_name || ''}} ${{item.product_brand || ''}}`.toLowerCase().includes(q);
    }}

    function matchesCollection(collection, q) {{
      if (!q) return true;
      return `${{collection.parent_title || ''}} ${{collection.list_title}}`.toLowerCase().includes(q) || collection.items.some((item) => matchesItem(item, q));
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
      state.dashboard = await dashboardRes.json();
      state.jobs = await jobsRes.json();
      state.loading = false;
      if (state.currentList !== null) {{
        const visibleCollections = modeCollections().filter((c) => matchesCollection(c, state.query));
        if (!visibleCollections[state.currentList]) {{
          state.currentList = null;
          state.currentItem = 0;
        }}
      }}
      render();
      scheduleNextRefresh();
    }}

    let refreshTimer = null;
    function scheduleNextRefresh() {{
      if (refreshTimer) clearTimeout(refreshTimer);
      if (state.currentList !== null) return;
      const dash = state.dashboard || {{}};
      const hasActiveWork = (dash.pending_url_count || 0) > 0 || (dash.running_job_count || 0) > 0 || (dash.failed_url_count || 0) > 0;
      refreshTimer = setTimeout(loadData, hasActiveWork ? 5000 : 20000);
    }}

    function renderStats() {{
      const collections = modeCollections().filter((c) => matchesCollection(c, state.query));
      const items = collections.reduce((sum, c) => sum + c.items.filter((item) => matchesItem(item, state.query)).length, 0);
      const dash = state.dashboard || {{}};
      const jobAttention = (dash.pending_url_count || 0) + (dash.running_job_count || 0) + (dash.failed_url_count || 0);
      statusBadge.textContent = String(jobAttention);
      statusBadge.classList.toggle('visible', jobAttention > 0);
      syncNote.textContent = dash.last_updated
        ? `Last sync ${{new Date(dash.last_updated).toLocaleString()}}`
        : 'Waiting for the first completed sync.';
      stats.innerHTML = '';
    }}

    function renderHome() {{
      if (state.loading) {{
        content.innerHTML = `<div class="loading"><div><h2 style="margin:0 0 8px;">Refreshing your library…</h2><p style="margin:0;">Pulling your latest reels, items, and status.</p></div></div>`;
        return;
      }}
      const collections = modeCollections().filter((c) => matchesCollection(c, state.query));
      header.classList.remove('compact');
      backButton.classList.add('hidden');
      screenTitle.textContent = 'Your Reel Library';
      screenSubtitle.textContent = '';
      if (!collections.length) {{
        content.innerHTML = `<div class="empty"><div><h2 style="margin:0 0 8px;">No collections yet</h2><p style="margin:0;">Send reels to the bot and they’ll appear here.</p></div></div>`;
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
          state.playerOpen = false;
          state.playerExpanded = false;
          state.playerControlsVisible = true;
          state.playerOffset = {{ x: 0, y: 0 }};
          render();
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
      const collections = modeCollections().filter((c) => matchesCollection(c, state.query));
      const collection = collections[state.currentList];
      const items = collection ? collection.items.filter((entry) => matchesItem(entry, state.query)) : [];
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
      const collections = modeCollections().filter((c) => matchesCollection(c, state.query));
      const collection = collections[state.currentList];
      const items = collection ? collection.items.filter((entry) => matchesItem(entry, state.query)) : [];
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

    function clampPlayerOffset(x, y) {{
      const maxLeft = Math.max(0, Math.floor(window.innerWidth * 0.58));
      const maxRight = Math.max(0, Math.floor(window.innerWidth * 0.42));
      const maxY = Math.max(0, Math.floor(window.innerHeight * 0.48));
      return {{
        x: Math.max(-maxLeft, Math.min(maxRight, x)),
        y: Math.max(-maxY, Math.min(maxY, y)),
      }};
    }}

    function attachMiniPlayerDrag(shell) {{
      const handle = shell.querySelector('.mini-player-dragzone');
      const card = shell.querySelector('.mini-player-card');
      if (!handle || !card) return;

      let dragging = false;
      let originX = 0;
      let originY = 0;
      let startX = 0;
      let startY = 0;
      let moved = false;

      const onPointerMove = (event) => {{
        if (!dragging || shell.classList.contains('expanded')) return;
        moved = true;
        const next = clampPlayerOffset(
          originX + (event.clientX - startX),
          originY + (event.clientY - startY),
        );
        state.playerOffset = next;
        card.style.transform = `translate(${{next.x}}px, ${{next.y}}px)`;
        syncMiniPlayerShell();
      }};

      const onPointerUp = () => {{
        if (!dragging) return;
        dragging = false;
        if (!moved) {{
          setMiniPlayerControlsVisible(!state.playerControlsVisible, !state.playerControlsVisible);
        }}
        window.removeEventListener('pointermove', onPointerMove);
        window.removeEventListener('pointerup', onPointerUp);
      }};

      handle.addEventListener('pointerdown', (event) => {{
        if (event.target.closest('button')) return;
        if (shell.classList.contains('expanded')) return;
        dragging = true;
        moved = false;
        startX = event.clientX;
        startY = event.clientY;
        originX = Number(state.playerOffset.x || 0);
        originY = Number(state.playerOffset.y || 0);
        event.preventDefault();
        window.addEventListener('pointermove', onPointerMove);
        window.addEventListener('pointerup', onPointerUp);
      }});
    }}

    let playerUiTimer = null;
    function syncMiniPlayerShell() {{
      const shell = document.getElementById('miniPlayerShell');
      const card = document.querySelector('.mini-player-card');
      const peek = document.getElementById('miniPlayerPeek');
      if (!shell || !card) return;
      shell.classList.toggle('open', state.playerOpen);
      shell.classList.toggle('expanded', state.playerExpanded);
      card.classList.toggle('show-ui', state.playerControlsVisible);
      if (state.playerExpanded) {{
        card.style.transform = '';
      }} else {{
        card.style.transform = `translate(${{state.playerOffset.x}}px, ${{state.playerOffset.y}}px)`;
      }}
      if (peek) {{
        peek.classList.toggle('visible', !state.playerExpanded && state.playerOffset.x > 56);
      }}
    }}

    function setMiniPlayerControlsVisible(visible, autoHide = false) {{
      state.playerControlsVisible = visible;
      if (playerUiTimer) clearTimeout(playerUiTimer);
      syncMiniPlayerShell();
      if (visible && autoHide) {{
        playerUiTimer = setTimeout(() => {{
          state.playerControlsVisible = false;
          syncMiniPlayerShell();
        }}, 1500);
      }}
    }}

    function syncMiniPlayerButtons() {{
      const video = document.getElementById('miniPlayerVideo');
      const playButton = document.getElementById('miniPlayerPlayButton');
      const muteButton = document.getElementById('miniPlayerMuteButton');
      const fullscreenButton = document.getElementById('miniPlayerExpandButton');
      if (video && playButton) playButton.textContent = video.paused ? '▶' : '❚❚';
      if (video && muteButton) muteButton.textContent = video.muted ? '🔇' : '🔈';
      if (fullscreenButton) fullscreenButton.textContent = state.playerExpanded ? '🗗' : '⤢';
      syncMiniPlayerShell();
    }}

    async function openMiniPlayer() {{
      const video = document.getElementById('miniPlayerVideo');
      if (!video) return;
      state.playerOpen = true;
      video.muted = state.playerMuted;
      setMiniPlayerControlsVisible(true, true);
      try {{
        await video.play();
      }} catch (error) {{
        // Autoplay may be blocked until the user presses play.
      }}
      syncMiniPlayerButtons();
    }}

    function closeMiniPlayer() {{
      const video = document.getElementById('miniPlayerVideo');
      if (video) video.pause();
      state.playerOpen = false;
      state.playerExpanded = false;
      state.playerControlsVisible = false;
      syncMiniPlayerButtons();
    }}

    async function toggleMiniPlayerPlayback() {{
      const video = document.getElementById('miniPlayerVideo');
      if (!video) return;
      if (video.paused) {{
        try {{
          await video.play();
        }} catch (error) {{
          return;
        }}
      }} else {{
        video.pause();
      }}
      setMiniPlayerControlsVisible(true, true);
      syncMiniPlayerButtons();
    }}

    function toggleMiniPlayerMute() {{
      const video = document.getElementById('miniPlayerVideo');
      if (!video) return;
      video.muted = !video.muted;
      state.playerMuted = video.muted;
      setMiniPlayerControlsVisible(true, true);
      syncMiniPlayerButtons();
    }}

    function toggleMiniPlayerExpanded() {{
      state.playerExpanded = !state.playerExpanded;
      setMiniPlayerControlsVisible(true, true);
      syncMiniPlayerButtons();
    }}

    function dockMiniPlayerBack() {{
      state.playerOffset = {{ x: 0, y: 0 }};
      syncMiniPlayerShell();
    }}

    function renderDetail() {{
      if (state.loading) {{
        content.innerHTML = `<div class="loading"><div><h2 style="margin:0 0 8px;">Refreshing this list…</h2><p style="margin:0;">Updating the reel player and item cards.</p></div></div>`;
        return;
      }}
      const collections = modeCollections().filter((c) => matchesCollection(c, state.query));
      const collection = collections[state.currentList];
      if (!collection) {{
        state.currentList = null;
        renderHome();
        return;
      }}
      const items = collection.items.filter((item) => matchesItem(item, state.query));
      const item = items[state.currentItem] || items[0];
      header.classList.add('compact');
      backButton.classList.remove('hidden');
      screenTitle.textContent = collection.list_title;
      screenSubtitle.textContent = '';
      if (!item?.local_video_url) {{
        state.playerOpen = false;
      }}
      content.innerHTML = `
        <section class="detail">
          <section class="items">
            ${{
              items.map((entry, index) => `
                <article class="item ${{index === state.currentItem ? 'active' : ''}}" data-item="${{index}}">
                  <h3>${{escapeHtml(entry.name)}}</h3>
                  ${{index === state.currentItem ? `
                    <div class="item-body">
                      <div class="detail-meta">
                        <span class="mini-chip">${{collection.parent_title ? escapeHtml(collection.parent_title) : 'Saved reel'}}</span>
                        <span class="mini-chip">Item ${{index + 1}} of ${{items.length}}</span>
                        ${{entry?.best_buy_link ? '<span class="mini-chip">Buy link ready</span>' : ''}}
                      </div>
                      <p>${{escapeHtml(entry.summary || 'No summary available.')}}</p>
                      ${{buyBox(entry)}}
                      <div class="actions">
                        ${{entry?.media_status === 'failed' || entry?.name === 'Processing Failed' ? '<button id="retryReelButton" class="action" type="button">Retry Reel</button>' : ''}}
                        <button id="deleteReelButton" class="action danger" type="button">Delete Reel</button>
                      </div>
                    </div>
                  ` : `<p>${{escapeHtml(entry.summary || 'No summary available.')}}</p>`}}
                </article>
              `).join('')
            }}
          </section>
          ${{
            item?.local_video_url
              ? `
                <section id="miniPlayerShell" class="mini-player-shell ${{state.playerOpen ? 'open' : ''}} ${{state.playerExpanded ? 'expanded' : ''}}">
                  <article class="mini-player-card ${{state.playerControlsVisible ? 'show-ui' : ''}}" style="${{state.playerExpanded ? '' : `transform:translate(${{state.playerOffset.x}}px, ${{state.playerOffset.y}}px);`}}">
                    <div class="video-wrap">
                      <div class="mini-player-dragzone"></div>
                      <video id="miniPlayerVideo" class="mini-player-video" src="${{escapeHtml(item.local_video_url)}}" ${{item.thumbnail_url ? `poster="${{escapeHtml(item.thumbnail_url)}}"` : ''}} playsinline preload="metadata" muted></video>
                      <div class="mini-player-overlay">
                        <button id="miniPlayerExpandButton" class="mini-player-btn expand" type="button" aria-label="Expand reel">⤢</button>
                        <button id="miniPlayerCloseButton" class="mini-player-btn close" type="button" aria-label="Close reel">✕</button>
                        <div class="mini-player-center">
                          <button id="miniPlayerPlayButton" class="mini-player-play" type="button" aria-label="Play or pause">❚❚</button>
                        </div>
                        <button id="miniPlayerMuteButton" class="mini-player-btn mute" type="button" aria-label="Mute or unmute">🔇</button>
                      </div>
                      <button id="miniPlayerPeek" class="mini-player-peek" type="button" aria-label="Bring reel back">‹</button>
                    </div>
                  </article>
                </section>
              `
              : ''
          }}
        </section>
      `;
      content.querySelectorAll('[data-item]').forEach((node) => {{
        node.addEventListener('click', (event) => {{
          if (event.target.closest('button') || event.target.closest('a')) return;
          state.currentItem = Number(node.dataset.item);
          state.playerOpen = Boolean(items[state.currentItem]?.local_video_url);
          state.playerExpanded = false;
          state.playerControlsVisible = true;
          renderDetail();
        }});
      }});
      const miniPlayerCloseButton = document.getElementById('miniPlayerCloseButton');
      if (miniPlayerCloseButton) {{
        miniPlayerCloseButton.addEventListener('click', closeMiniPlayer);
      }}
      const miniPlayerPlayButton = document.getElementById('miniPlayerPlayButton');
      if (miniPlayerPlayButton) {{
        miniPlayerPlayButton.addEventListener('click', toggleMiniPlayerPlayback);
      }}
      const miniPlayerMuteButton = document.getElementById('miniPlayerMuteButton');
      if (miniPlayerMuteButton) {{
        miniPlayerMuteButton.addEventListener('click', toggleMiniPlayerMute);
      }}
      const miniPlayerExpandButton = document.getElementById('miniPlayerExpandButton');
      if (miniPlayerExpandButton) {{
        miniPlayerExpandButton.addEventListener('click', toggleMiniPlayerExpanded);
      }}
      const miniPlayerPeek = document.getElementById('miniPlayerPeek');
      if (miniPlayerPeek) {{
        miniPlayerPeek.addEventListener('click', dockMiniPlayerBack);
      }}
      const miniPlayerShell = document.getElementById('miniPlayerShell');
      if (miniPlayerShell) {{
        attachMiniPlayerDrag(miniPlayerShell);
        miniPlayerShell.addEventListener('click', (event) => {{
          if (event.target === miniPlayerShell && state.playerExpanded) {{
            toggleMiniPlayerExpanded();
          }}
        }});
      }}
      const miniPlayerVideo = document.getElementById('miniPlayerVideo');
      if (miniPlayerVideo) {{
        miniPlayerVideo.addEventListener('click', () => setMiniPlayerControlsVisible(!state.playerControlsVisible, !state.playerControlsVisible));
        miniPlayerVideo.addEventListener('play', syncMiniPlayerButtons);
        miniPlayerVideo.addEventListener('pause', syncMiniPlayerButtons);
        miniPlayerVideo.addEventListener('volumechange', syncMiniPlayerButtons);
        if (state.playerOpen) {{
          openMiniPlayer();
        }} else {{
          syncMiniPlayerButtons();
        }}
      }} else {{
        state.playerOpen = false;
        syncMiniPlayerButtons();
      }}
      const deleteButton = document.getElementById('deleteReelButton');
      if (deleteButton) {{
        deleteButton.addEventListener('click', deleteCurrentReel);
      }}
      const retryButton = document.getElementById('retryReelButton');
      if (retryButton) {{
        retryButton.addEventListener('click', retryCurrentReel);
      }}
    }}

    function renderStatus() {{
      const dash = state.dashboard || {{}};
      statusSummary.innerHTML = `
        <span class="chip">${{dash.pending_url_count || 0}} Pending</span>
        <span class="chip">${{dash.running_job_count || 0}} Running</span>
        <span class="chip">${{dash.failed_url_count || 0}} Failed</span>
      `;
      if (!state.jobs.length) {{
        statusList.innerHTML = `<div class="empty" style="min-height:20vh;"><div><h3 style="margin:0 0 8px;">No recent jobs</h3><p style="margin:0;">Your processing activity will appear here.</p></div></div>`;
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
      state.playerOpen = false;
      state.playerExpanded = false;
      state.playerControlsVisible = true;
      state.playerOffset = {{ x: 0, y: 0 }};
      render();
    }});
    statusButton.addEventListener('click', () => statusSheet.classList.add('open'));
    refreshButton.addEventListener('click', () => loadData());
    document.getElementById('closeStatus').addEventListener('click', () => statusSheet.classList.remove('open'));
    statusSheet.addEventListener('click', (event) => {{
      if (event.target === statusSheet) statusSheet.classList.remove('open');
    }});
    searchInput.addEventListener('input', (event) => {{
      state.query = event.target.value.trim().toLowerCase();
      state.currentList = null;
      render();
    }});

    loadData();
  </script>
</body>
</html>"""


@router.get("/", response_class=HTMLResponse)
def root_app():
    return HTMLResponse(build_landing_html())


@router.get("/demo/ui-review", response_class=HTMLResponse)
def demo_ui_review():
    return HTMLResponse(build_demo_library_review_html())


@router.get("/app/{user_id}", response_class=HTMLResponse)
def user_app(user_id: str):
    return HTMLResponse(build_web_app_html(user_id))
