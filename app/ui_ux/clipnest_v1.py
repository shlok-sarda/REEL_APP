def build_clipnest_v1_html(user_id: str) -> str:
    safe_user_id = user_id.replace("\\", "\\\\").replace("'", "\\'")
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>ClipNest</title>
  <style>
    :root {
      color-scheme: dark;
      --bg:#0a0a0b;
      --card:#161619;
      --soft:#1c1c20;
      --line:#232327;
      --text:#f4f4f5;
      --muted:#8e8e96;
      --faint:#5c5c64;
      --accent:#8b7bff;
      --danger:#ff5b4d;
      --serif:ui-serif, "New York", Georgia, "Times New Roman", serif;
      --safe-top:env(safe-area-inset-top, 0px);
      --safe-bottom:env(safe-area-inset-bottom, 0px);
    }
    * { box-sizing:border-box; }
    html, body {
      margin:0;
      min-height:100%;
      background:var(--bg);
      color:var(--text);
      font-family:-apple-system, BlinkMacSystemFont, "SF Pro Text", "Helvetica Neue", Arial, sans-serif;
    }
    body { overflow-x:hidden; }
    button, input, a { font:inherit; -webkit-tap-highlight-color:transparent; }
    button { border:0; background:none; color:inherit; cursor:pointer; padding:0; }
    .phone-shell {
      width:min(430px, 100%);
      min-height:100vh;
      margin:0 auto;
      background:var(--bg);
      position:relative;
    }
    .screen {
      min-height:100vh;
      padding:calc(16px + var(--safe-top)) 18px calc(104px + var(--safe-bottom));
    }

    /* ---------- header ---------- */
    .home-head {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      margin:6px 0 18px;
    }
    .greeting {
      margin:0;
      font-family:var(--serif);
      font-size:2.1rem;
      line-height:1.05;
      font-weight:600;
      letter-spacing:.2px;
    }
    .icon-row { display:flex; align-items:center; gap:8px; }
    .icon-button, .back-button {
      width:40px;
      height:40px;
      border-radius:50%;
      display:grid;
      place-items:center;
      background:transparent;
      color:var(--text);
    }
    .icon-button:active, .back-button:active { background:var(--soft); }
    .icon-button svg, .back-button svg { width:22px; height:22px; }

    .section-head {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      margin:26px 0 14px;
    }
    .section-title {
      margin:0;
      font-family:var(--serif);
      font-size:1.42rem;
      line-height:1.1;
      font-weight:600;
      display:inline-flex;
      align-items:center;
      gap:6px;
    }
    .section-title .chev { color:var(--faint); font-family:var(--serif); }
    .section-side { color:var(--muted); font-size:.82rem; font-weight:600; }

    /* ---------- search bar ---------- */
    .search { position:relative; margin:4px 0 18px; }
    .search input {
      width:100%;
      height:50px;
      border:0;
      border-radius:25px;
      background:var(--soft);
      color:var(--text);
      padding:0 20px 0 48px;
      outline:none;
      font-size:.98rem;
      font-weight:500;
    }
    .search input::placeholder { color:var(--muted); }
    .search .glyph {
      position:absolute;
      left:17px;
      top:50%;
      transform:translateY(-50%);
      color:var(--muted);
      pointer-events:none;
      display:grid;
      place-items:center;
    }
    .search .glyph svg { width:18px; height:18px; }

    /* ---------- category rail ---------- */
    .cat-rail {
      display:flex;
      gap:16px;
      overflow-x:auto;
      padding:2px 2px 6px;
      scrollbar-width:none;
    }
    .cat-rail::-webkit-scrollbar { display:none; }
    .cat-tile {
      flex:0 0 auto;
      width:72px;
      display:grid;
      justify-items:center;
      gap:8px;
    }
    .cat-icon {
      position:relative;
      width:60px;
      height:60px;
      border-radius:19px;
      display:grid;
      place-items:center;
      font-size:27px;
      background:var(--card);
      border:1px solid var(--line);
      transition:transform 120ms ease;
    }
    .cat-tile:active .cat-icon { transform:scale(.93); }
    .cat-tile.active .cat-icon { border-color:#fff; }
    .cat-count {
      position:absolute;
      top:-7px;
      right:-7px;
      min-width:22px;
      height:22px;
      padding:0 6px;
      border-radius:11px;
      display:grid;
      place-items:center;
      background:#fff;
      color:#000;
      font-size:.72rem;
      font-weight:800;
    }
    .cat-label {
      max-width:74px;
      color:var(--muted);
      font-size:.74rem;
      font-weight:600;
      text-align:center;
      white-space:nowrap;
      overflow:hidden;
      text-overflow:ellipsis;
    }
    .cat-tile.active .cat-label { color:var(--text); }

    /* ---------- recently saved rail ---------- */
    .recent-rail {
      display:flex;
      gap:12px;
      overflow-x:auto;
      padding:2px 2px 6px;
      scrollbar-width:none;
    }
    .recent-rail::-webkit-scrollbar { display:none; }
    .recent-card {
      flex:0 0 auto;
      width:132px;
      text-align:left;
    }
    .recent-thumb {
      display:block;
      position:relative;
      width:132px;
      aspect-ratio:9/15;
      border-radius:18px;
      overflow:hidden;
      background:var(--card);
      border:1px solid var(--line);
    }
    .recent-thumb img, .recent-thumb video {
      width:100%; height:100%; object-fit:cover; display:block;
    }
    .recent-thumb .mini-badge {
      position:absolute;
      left:8px;
      bottom:8px;
      display:flex;
      gap:4px;
    }
    .badge-dot {
      width:26px;
      height:26px;
      border-radius:50%;
      display:grid;
      place-items:center;
      background:rgba(255,255,255,.92);
      color:#000;
      font-size:.78rem;
    }
    .recent-source {
      margin:9px 0 0;
      color:var(--muted);
      font-size:.72rem;
      font-weight:600;
      letter-spacing:.02em;
    }
    .recent-title {
      margin:3px 0 0;
      color:var(--text);
      font-size:.88rem;
      line-height:1.22;
      font-weight:700;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }

    /* ---------- library rows ---------- */
    .lib-list { display:grid; }
    .lib-row {
      display:grid;
      grid-template-columns:56px minmax(0,1fr) auto;
      align-items:center;
      gap:14px;
      padding:12px 0;
      text-align:left;
      border-bottom:1px solid var(--line);
    }
    .lib-row:last-child { border-bottom:0; }
    .lib-icon {
      width:56px;
      height:56px;
      border-radius:16px;
      overflow:hidden;
      display:grid;
      place-items:center;
      font-size:25px;
      background:var(--card);
      border:1px solid var(--line);
    }
    .lib-icon img, .lib-icon video { width:100%; height:100%; object-fit:cover; }
    .lib-name {
      margin:0;
      font-size:1rem;
      font-weight:700;
      line-height:1.2;
      display:-webkit-box;
      -webkit-line-clamp:1;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .lib-meta {
      margin:4px 0 0;
      color:var(--muted);
      font-size:.8rem;
      font-weight:500;
    }
    .lib-meta .dot-sep { color:var(--faint); margin:0 4px; }
    .row-chev { color:var(--faint); }
    .row-chev svg { width:18px; height:18px; }

    /* ---------- pipeline pill ---------- */
    .sync-pill {
      display:flex;
      align-items:center;
      gap:10px;
      border-radius:16px;
      background:var(--card);
      border:1px solid var(--line);
      padding:11px 14px;
      margin:0 0 18px;
    }
    .sync-dot {
      flex:0 0 auto;
      width:8px;
      height:8px;
      border-radius:50%;
      background:#33c47f;
    }
    .sync-pill.active .sync-dot { background:var(--accent); animation:pulse 1.2s ease-in-out infinite; }
    .sync-pill.issue .sync-dot { background:#e58f3a; }
    @keyframes pulse {
      0%, 100% { transform:scale(1); opacity:1; }
      50% { transform:scale(.6); opacity:.5; }
    }
    .sync-text { margin:0; font-size:.82rem; font-weight:600; color:var(--muted); min-width:0; }
    .sync-text b { color:var(--text); font-weight:700; }

    /* ---------- activity popover ---------- */
    .icon-row { position:relative; }
    .icon-button { position:relative; }
    .notif-dot {
      position:absolute;
      top:7px;
      right:7px;
      width:8px;
      height:8px;
      border-radius:50%;
      background:var(--accent);
      box-shadow:0 0 0 2px var(--bg);
    }
    .notif-dot.issue { background:#e58f3a; }
    .notif-popover {
      position:absolute;
      top:calc(100% + 8px);
      right:0;
      z-index:60;
      width:min(290px, 82vw);
      background:var(--card);
      border:1px solid var(--line);
      border-radius:16px;
      padding:12px 12px 4px;
      box-shadow:0 18px 44px rgba(0,0,0,.5);
    }
    .notif-popover[hidden] { display:none; }
    .notif-head {
      margin:0 0 9px;
      font-size:.7rem;
      letter-spacing:.5px;
      text-transform:uppercase;
      font-weight:700;
      color:var(--muted);
    }
    .notif-popover .sync-pill { margin:0 0 10px; }
    .notif-stats {
      display:flex;
      gap:16px;
      padding:2px 2px 10px;
      font-size:.74rem;
      font-weight:600;
      color:var(--muted);
    }
    .notif-stats b { color:var(--text); font-weight:700; margin-left:3px; }

    /* ---------- chips (folder filters) ---------- */
    .chips {
      display:flex;
      gap:8px;
      overflow-x:auto;
      padding:2px 0 16px;
      scrollbar-width:none;
    }
    .chips::-webkit-scrollbar { display:none; }
    .chip {
      flex:0 0 auto;
      height:38px;
      border-radius:19px;
      padding:0 16px;
      background:var(--soft);
      color:var(--muted);
      font-size:.85rem;
      font-weight:650;
      white-space:nowrap;
      display:inline-flex;
      align-items:center;
      gap:6px;
    }
    .chip.active { background:#fff; color:#000; }

    /* ---------- folder screen ---------- */
    .list-heading {
      display:grid;
      grid-template-columns:40px minmax(0,1fr) auto;
      align-items:center;
      gap:10px;
      margin:2px 0 16px;
    }
    .list-title-block h1 {
      margin:0;
      font-family:var(--serif);
      font-size:1.5rem;
      line-height:1.08;
      font-weight:600;
    }
    .count-text {
      margin:4px 0 0;
      color:var(--muted);
      font-size:.78rem;
      font-weight:600;
    }
    .masonry {
      columns:2;
      column-gap:12px;
    }
    .m-card {
      break-inside:avoid;
      margin:0 0 18px;
      width:100%;
      text-align:left;
    }
    .m-thumb {
      display:block;
      position:relative;
      width:100%;
      aspect-ratio:9/13;
      border-radius:18px;
      overflow:hidden;
      background:var(--card);
      border:1px solid var(--line);
    }
    .m-thumb img, .m-thumb video { width:100%; height:100%; object-fit:cover; display:block; }
    .m-badges {
      position:absolute;
      left:9px;
      bottom:9px;
      display:flex;
      gap:5px;
    }
    .m-title-row {
      display:grid;
      grid-template-columns:minmax(0,1fr) 22px;
      gap:6px;
      align-items:start;
      margin-top:9px;
    }
    .m-title {
      margin:0;
      font-size:.9rem;
      line-height:1.22;
      font-weight:700;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .m-kebab { color:var(--faint); font-weight:800; letter-spacing:1px; }
    .m-summary {
      margin:5px 0 0;
      color:var(--muted);
      font-size:.76rem;
      line-height:1.35;
      font-weight:500;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .buy-row { display:flex; flex-wrap:wrap; gap:6px; margin-top:8px; }
    .buy-link {
      min-height:28px;
      border-radius:14px;
      padding:6px 11px;
      background:var(--soft);
      border:1px solid var(--line);
      color:var(--text);
      text-decoration:none;
      font-size:.72rem;
      line-height:1;
      font-weight:750;
    }

    /* ---------- search screen ---------- */
    .search-stage {
      min-height:calc(100vh - 150px - var(--safe-bottom));
      display:grid;
      align-content:start;
      padding:8px 0 40px;
    }
    .magic-head { text-align:left; margin:14px 0 22px; }
    .magic-title {
      margin:0;
      font-family:var(--serif);
      font-size:2rem;
      line-height:1.1;
      font-weight:600;
    }
    .magic-copy {
      margin:10px 0 0;
      color:var(--muted);
      font-size:.9rem;
      line-height:1.45;
      font-weight:500;
      max-width:21rem;
    }
    .magic-bar { position:relative; }
    .magic-bar input {
      width:100%;
      height:56px;
      border:1px solid var(--line);
      border-radius:28px;
      background:var(--soft);
      color:var(--text);
      outline:none;
      padding:0 56px 0 20px;
      font-size:1rem;
      font-weight:550;
    }
    .magic-bar input::placeholder { color:var(--muted); }
    .magic-bar input:focus { border-color:#3a3a40; }
    .magic-submit {
      position:absolute;
      right:7px;
      top:50%;
      transform:translateY(-50%);
      width:42px;
      height:42px;
      border-radius:50%;
      display:grid;
      place-items:center;
      background:#fff;
      color:#000;
    }
    .magic-submit svg { width:18px; height:18px; }
    .result-list { display:grid; gap:10px; width:100%; margin-top:20px; }
    .result-card {
      display:grid;
      grid-template-columns:56px minmax(0,1fr);
      gap:12px;
      align-items:center;
      padding:9px;
      border:1px solid var(--line);
      border-radius:18px;
      background:var(--card);
      color:var(--text);
      text-align:left;
    }
    .result-thumb {
      display:block;
      width:56px;
      height:56px;
      border-radius:13px;
      overflow:hidden;
      background:var(--soft);
    }
    .ph-glyph {
      display:grid;
      place-items:center;
      width:100%;
      height:100%;
      color:rgba(255,255,255,.5);
      font-size:1.1em;
    }
    .m-thumb .ph-glyph, .recent-thumb .ph-glyph { font-size:1.7em; }
    .result-thumb img, .result-thumb video { width:100%; height:100%; object-fit:cover; display:block; }
    .result-card h3 {
      margin:0;
      font-size:.9rem;
      line-height:1.2;
      font-weight:700;
      overflow:hidden;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
    }
    .result-card p {
      margin:4px 0 0;
      color:var(--muted);
      font-size:.75rem;
      line-height:1.3;
      overflow:hidden;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
    }

    /* ---------- profile / settings ---------- */
    .metric-grid {
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:10px;
      margin:6px 0 10px;
    }
    .metric-card {
      border:1px solid var(--line);
      border-radius:18px;
      background:var(--card);
      padding:14px;
    }
    .metric-card span {
      display:block;
      color:var(--muted);
      font-size:.68rem;
      font-weight:700;
      text-transform:uppercase;
      letter-spacing:.05em;
    }
    .metric-card b {
      display:block;
      margin-top:8px;
      font-family:var(--serif);
      font-size:1.5rem;
      line-height:1;
      font-weight:600;
    }
    .set-section {
      margin:22px 0 0;
    }
    .set-title {
      margin:0 0 6px;
      color:var(--muted);
      font-size:.74rem;
      font-weight:750;
      text-transform:uppercase;
      letter-spacing:.06em;
    }
    .set-card {
      border:1px solid var(--line);
      border-radius:18px;
      background:var(--card);
      overflow:hidden;
    }
    .set-row {
      width:100%;
      min-height:52px;
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      padding:0 15px;
      border-bottom:1px solid var(--line);
      font-size:.92rem;
      font-weight:600;
      text-align:left;
      color:var(--text);
      text-decoration:none;
    }
    .set-card .set-row:last-child { border-bottom:0; }
    .set-row .value {
      color:var(--muted);
      font-size:.84rem;
      font-weight:550;
      max-width:55%;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }
    .set-row.danger { color:var(--danger); }
    .set-row.action { color:var(--accent); }
    .ig-code {
      font-family:var(--serif);
      font-size:1.5rem;
      font-weight:600;
      letter-spacing:.14em;
      text-align:center;
      padding:14px;
      margin:12px 15px;
      border:1px dashed var(--line);
      border-radius:14px;
      user-select:all;
    }
    .ig-help {
      margin:0 15px 14px;
      color:var(--muted);
      font-size:.82rem;
      line-height:1.45;
      font-weight:500;
    }
    .job-list { display:grid; gap:10px; }
    .job-card {
      border:1px solid var(--line);
      border-radius:16px;
      background:var(--card);
      padding:13px;
    }
    .job-head {
      display:grid;
      grid-template-columns:minmax(0,1fr) auto;
      gap:8px;
      align-items:start;
    }
    .job-title {
      margin:0;
      font-size:.86rem;
      line-height:1.25;
      font-weight:700;
      overflow:hidden;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
    }
    .status-pill {
      min-height:24px;
      border-radius:12px;
      padding:5px 9px;
      background:var(--soft);
      color:var(--muted);
      font-size:.64rem;
      line-height:1;
      font-weight:800;
      text-transform:uppercase;
      letter-spacing:.04em;
    }
    .status-pill.running, .status-pill.queued, .status-pill.pending { color:var(--accent); }
    .status-pill.completed { color:#33c47f; }
    .status-pill.failed { color:#e58f3a; }
    .job-meta {
      margin:8px 0 0;
      color:var(--muted);
      font-size:.74rem;
      line-height:1.35;
      font-weight:500;
      word-break:break-word;
    }
    .json-box {
      margin-top:10px;
      border-radius:12px;
      background:#0f0f11;
      border:1px solid var(--line);
      color:#c9c9cf;
      overflow:hidden;
    }
    .json-box summary { cursor:pointer; padding:10px 12px; font-size:.72rem; font-weight:750; }
    .json-box pre {
      margin:0;
      max-height:260px;
      overflow:auto;
      padding:0 12px 12px;
      font-size:.68rem;
      line-height:1.45;
      white-space:pre-wrap;
      word-break:break-word;
    }
    .empty {
      padding:44px 8px;
      text-align:center;
      color:var(--muted);
      font-weight:600;
      font-size:.9rem;
    }

    /* ---------- bottom nav ---------- */
    .bottom-nav {
      position:fixed;
      left:50%;
      bottom:0;
      z-index:30;
      width:min(430px, 100%);
      transform:translateX(-50%);
      display:grid;
      grid-template-columns:repeat(3,1fr);
      border-top:1px solid var(--line);
      background:rgba(10,10,11,.86);
      -webkit-backdrop-filter:blur(18px);
      backdrop-filter:blur(18px);
      padding:10px 26px calc(10px + var(--safe-bottom));
    }
    .nav-button {
      display:grid;
      gap:4px;
      place-items:center;
      color:var(--faint);
      font-size:.68rem;
      font-weight:650;
    }
    .nav-button svg { width:23px; height:23px; }
    .nav-button.active { color:var(--text); }

    /* ---------- mini player ---------- */
    .reel-player {
      position:fixed;
      inset:0;
      z-index:40;
      display:flex;
      flex-direction:column;
      background:#0a0a0c;
      opacity:0;
      pointer-events:none;
      transition:opacity 180ms ease;
    }
    .reel-player.visible {
      opacity:1;
      pointer-events:auto;
    }
    .player-top {
      display:flex;
      align-items:center;
      gap:12px;
      padding:calc(12px + var(--safe-top)) 16px 10px;
    }
    .player-title {
      flex:1;
      margin:0;
      font-size:.95rem;
      line-height:1.25;
      font-weight:700;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .player-action {
      min-width:38px;
      height:38px;
      display:grid;
      place-items:center;
      border-radius:50%;
      background:rgba(255,255,255,.08);
      color:var(--text);
      font-size:.88rem;
      font-weight:650;
    }
    .player-action[hidden] { display:none; }
    .player-stage {
      position:relative;
      flex:1;
      min-height:0;
      display:flex;
      overflow:hidden;
      touch-action:none;
    }
    .player-canvas {
      flex:1;
      min-width:0;
      display:grid;
      place-items:center;
      padding:0 12px;
    }
    .player-canvas video {
      max-width:100%;
      max-height:100%;
      height:100%;
      border-radius:18px;
      background:#000;
      object-fit:contain;
    }
    @keyframes reel-enter-up { from { opacity:.3; transform:translateY(28px); } to { opacity:1; transform:none; } }
    @keyframes reel-enter-down { from { opacity:.3; transform:translateY(-28px); } to { opacity:1; transform:none; } }
    .player-canvas.enter-up { animation:reel-enter-up 200ms ease; }
    .player-canvas.enter-down { animation:reel-enter-down 200ms ease; }
    .player-flash {
      position:absolute;
      left:50%;
      top:50%;
      transform:translate(-50%, -50%) scale(.86);
      width:78px;
      height:78px;
      border-radius:50%;
      background:rgba(0,0,0,.55);
      display:grid;
      place-items:center;
      color:#fff;
      font-size:1.7rem;
      opacity:0;
      pointer-events:none;
      transition:opacity 160ms ease, transform 160ms ease;
    }
    .player-flash.showing { opacity:1; transform:translate(-50%, -50%) scale(1); }
    @keyframes buffer-pulse { 0%, 100% { opacity:.55; } 50% { opacity:1; } }
    .player-buffer {
      position:absolute;
      left:50%;
      bottom:16px;
      transform:translateX(-50%);
      padding:6px 13px;
      border-radius:99px;
      background:rgba(0,0,0,.55);
      color:#d6d6db;
      font-size:.74rem;
      font-weight:650;
      pointer-events:none;
      animation:buffer-pulse 1.1s ease infinite;
    }
    .player-buffer[hidden] { display:none; }
    .player-counter {
      color:var(--muted);
      background:rgba(255,255,255,.07);
      padding:5px 10px;
      border-radius:99px;
      font-size:.72rem;
      font-weight:650;
      white-space:nowrap;
    }
    .player-counter[hidden] { display:none; }
    .player-scrub { padding:10px 0 6px; cursor:pointer; touch-action:none; }
    .player-scrub .player-track { transition:height 120ms ease; }
    .player-scrub.active .player-track { height:7px; }
    .player-fallback {
      display:grid;
      justify-items:center;
      gap:14px;
      text-align:center;
      padding:20px;
    }
    .player-fallback img {
      max-width:min(300px, 70vw);
      max-height:38vh;
      border-radius:16px;
      object-fit:cover;
      opacity:.85;
    }
    .player-fallback p { margin:0; color:var(--muted); font-size:.88rem; font-weight:650; }
    .player-fallback a {
      color:var(--text);
      font-size:.88rem;
      font-weight:700;
      text-decoration:underline;
      text-underline-offset:3px;
    }
    .player-bottom { padding:12px 18px calc(18px + var(--safe-bottom)); }
    .player-track { height:4px; border-radius:99px; background:#232327; overflow:hidden; }
    .player-fill { width:0%; height:100%; background:#fff; }
    .player-meta {
      display:flex;
      align-items:center;
      gap:10px;
      margin-top:12px;
      color:var(--muted);
      font-size:.78rem;
      font-weight:650;
    }
    .player-meta span { flex:1; }

    /* ---------- action sheet ---------- */
    .sheet-backdrop {
      position:fixed;
      inset:0;
      z-index:50;
      background:rgba(0,0,0,.5);
      opacity:0;
      pointer-events:none;
      transition:opacity 180ms ease;
    }
    .sheet-backdrop.visible { opacity:1; pointer-events:auto; }
    .action-sheet {
      position:fixed;
      left:50%;
      bottom:0;
      z-index:60;
      width:min(430px,100%);
      transform:translate(-50%,104%);
      border-radius:24px 24px 0 0;
      background:#141417;
      border:1px solid var(--line);
      border-bottom:0;
      overflow:hidden;
      transition:transform 220ms cubic-bezier(.32,.72,.35,1);
    }
    .action-sheet.visible { transform:translate(-50%,0); }
    /* ---------- smart folders ---------- */
    .folder-toolbar { display:flex; justify-content:flex-end; margin:8px 0 2px; }
    .folder-toolbar[hidden] { display:none; }
    .newlist-btn { display:inline-flex; align-items:center; gap:6px; font-size:.8rem; font-weight:650;
      color:#fff; background:#a9744a; border:none; border-radius:20px; padding:7px 15px; cursor:pointer; }
    .newlist-btn.ghost { background:none; color:var(--accent); border:1px solid rgba(169,116,74,.6); }
    .newlist-btn:disabled { opacity:.45; }
    .m-card.selectable { cursor:pointer; position:relative; }
    .m-card.selected { outline:2px solid #a9744a; outline-offset:-2px; border-radius:16px; }
    .m-card .selring { position:absolute; top:10px; right:10px; width:22px; height:22px; border-radius:50%;
      border:2px solid rgba(255,255,255,.7); background:rgba(0,0,0,.35); z-index:3; display:none; }
    .m-card.selectable .selring { display:block; }
    .m-card.selected .selring { background:#a9744a; border-color:#a9744a; }
    .m-card.selected .selring::after { content:"✓"; color:#fff; font-size:13px; position:absolute; top:-1px; left:4px; }
    .selbar { position:fixed; left:50%; transform:translateX(-50%); bottom:84px; z-index:40; width:min(720px,92%);
      background:rgba(16,20,27,.96); border:1px solid var(--line); border-radius:16px; padding:10px 14px;
      display:none; justify-content:space-between; align-items:center; box-shadow:0 18px 50px rgba(0,0,0,.5); }
    .selbar.show { display:flex; }
    .folder-overlay { position:fixed; inset:0; background:rgba(0,0,0,.62); z-index:60; display:none;
      align-items:center; justify-content:center; padding:16px; }
    .folder-overlay.show { display:flex; }
    .folder-modal { background:#12161d; border:1px solid var(--line); border-radius:18px; padding:18px; width:min(460px,100%); }
    .folder-modal h3 { margin:0 0 2px; } .folder-modal .sub { color:var(--muted); font-size:.8rem; margin-bottom:8px; }
    .folder-modal label { display:block; font-size:.72rem; color:var(--muted); margin:12px 0 5px; }
    .folder-modal input, .folder-modal textarea { width:100%; background:var(--panel); border:1px solid var(--line);
      border-radius:10px; padding:10px 12px; color:var(--text); font-size:.92rem; font-family:inherit; }
    .folder-modal textarea { min-height:84px; resize:vertical; line-height:1.45; }
    .folder-modal .hint { font-size:.72rem; color:var(--accent); margin-top:5px; }
    .folder-modal .row { display:flex; gap:8px; justify-content:flex-end; margin-top:16px; }
    .folder-card { background:var(--panel); border:1px solid var(--line); border-radius:14px; padding:13px 15px; margin-top:10px; cursor:pointer; }
    .folder-card h3 { margin:0 0 3px; font-size:1rem; } .folder-card .sub { color:var(--muted); font-size:.82rem; line-height:1.4; }
    .folder-card .count { float:right; font-size:.72rem; color:var(--muted); border:1px solid var(--line); border-radius:20px; padding:2px 9px; }
    .sug-chip { font-size:.66rem; color:#08121f; background:var(--accent); border-radius:20px; padding:2px 8px; margin-left:6px; }
    .sheet-media { position:relative; height:200px; background:#0f0f11; cursor:pointer; }
    .sheet-media img, .sheet-media video { width:100%; height:100%; object-fit:cover; display:block; opacity:.92; }
    .sheet-play {
      position:absolute;
      left:50%;
      top:50%;
      transform:translate(-50%, -50%);
      width:56px;
      height:56px;
      border-radius:50%;
      background:rgba(0,0,0,.6);
      border:1px solid rgba(255,255,255,.28);
      display:grid;
      place-items:center;
      color:#fff;
      font-size:1.15rem;
      pointer-events:none;
    }
    .sheet-close {
      position:absolute;
      top:14px;
      left:14px;
      width:34px;
      height:34px;
      border-radius:50%;
      display:grid;
      place-items:center;
      background:rgba(0,0,0,.65);
      color:#fff;
      font-size:.9rem;
    }
    .sheet-body { padding:14px 18px calc(20px + var(--safe-bottom)); }
    .sheet-handle { width:38px; height:4px; border-radius:3px; background:#3a3a40; margin:0 auto 14px; }
    .sheet-title-row { display:flex; justify-content:space-between; gap:12px; align-items:start; margin-bottom:14px; }
    .sheet-title { margin:0; font-family:var(--serif); font-size:1.08rem; line-height:1.25; font-weight:600; }
    .type-badge {
      flex:0 0 auto;
      border-radius:12px;
      background:var(--soft);
      border:1px solid var(--line);
      color:var(--muted);
      padding:5px 10px;
      font-size:.7rem;
      font-weight:750;
    }
    .quick-actions { display:grid; grid-template-columns:repeat(3,1fr); gap:8px; margin-bottom:16px; }
    .quick-action { display:grid; place-items:center; gap:6px; color:var(--muted); font-size:.68rem; font-weight:650; text-decoration:none; }
    .quick-action span {
      width:40px;
      height:40px;
      border:1px solid var(--line);
      border-radius:50%;
      display:grid;
      place-items:center;
      font-size:1rem;
      color:var(--text);
      background:var(--soft);
    }
    .sheet-list { border-top:1px solid var(--line); }
    .sheet-row {
      min-height:50px;
      border-bottom:1px solid var(--line);
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      color:var(--text);
      text-decoration:none;
      font-size:.9rem;
      font-weight:600;
      width:100%;
    }
    .sheet-row .new {
      margin-left:7px;
      border-radius:9px;
      background:rgba(139,123,255,.16);
      color:var(--accent);
      padding:2px 7px;
      font-size:.64rem;
      font-weight:800;
    }
    .sheet-row.danger { color:var(--danger); }
    .hidden { display:none !important; }
    @media (min-width:760px) {
      body { background:#000; }
      .phone-shell {
        margin-top:24px;
        margin-bottom:24px;
        min-height:calc(100vh - 48px);
        border:1px solid var(--line);
        border-radius:32px;
        overflow:hidden;
      }
    }
  </style>
</head>
<body>
  <div class="phone-shell">
    <main id="app" class="screen"></main>
    <section id="miniPlayer" class="reel-player" aria-label="Reel player">
      <div class="player-top">
        <button id="miniClose" class="player-action" type="button" aria-label="Close player">✕</button>
        <p id="miniTitle" class="player-title"></p>
        <span id="playerCounter" class="player-counter" hidden></span>
        <button id="miniMore" class="player-action" type="button" aria-label="More actions">···</button>
      </div>
      <div id="playerStage" class="player-stage">
        <div id="miniThumb" class="player-canvas"></div>
        <div id="playerFlash" class="player-flash">▶</div>
        <div id="playerBuffer" class="player-buffer" hidden>Loading…</div>
      </div>
      <div class="player-bottom">
        <div id="playerScrub" class="player-scrub"><div class="player-track"><div id="miniProgress" class="player-fill"></div></div></div>
        <div class="player-meta">
          <span id="miniTime">0:00 / 0:00</span>
          <button id="miniSound" class="player-action" type="button" aria-label="Toggle sound" hidden>🔇</button>
          <button id="miniToggle" class="player-action" type="button" aria-label="Play or pause">⏸</button>
        </div>
      </div>
    </section>
    <div id="sheetBackdrop" class="sheet-backdrop"></div>
    <section id="actionSheet" class="action-sheet" aria-label="Item actions"></section>
    <nav class="bottom-nav" aria-label="Primary">
      <button id="libraryNav" class="nav-button active" type="button">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>
        <span>Home</span>
      </button>
      <button id="foldersNav" class="nav-button" type="button">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/></svg>
        <span>Folders</span>
      </button>
      <button id="profileNav" class="nav-button" type="button">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.8-3.4 4.5-5 8-5s6.2 1.6 8 5"/></svg>
        <span>Profile</span>
      </button>
    </nav>
  </div>
  <script>
    const USER_ID = '__USER_ID__';
    const state = {
      data: [],
      dashboard: {},
      jobs: [],
      diagnostics: [],
      screen: 'library',
      currentListId: '',
      query: '',
      chip: 'All',
      itemQuery: '',
      itemChip: 'All',
      magicQuery: '',
      deepSearch: { query: '', loading: false, error: '', results: [] },
      deepSearchTimer: null,
      deepSearchRequestId: 0,
      notifOpen: false,
      miniItem: null,
      miniIndex: 0,
      miniList: [],
      sheetIndex: 0,
      sheetList: [],
      playing: false,
      soundOn: (localStorage.getItem('clipnest_sound') ?? '1') === '1',
      bufferTimer: null,
      scrubbing: false,
      stageTouch: null,
      preloadEl: null,
      pollTimer: null,
      session: null,
      igLink: null,
      loading: true,
      folders: [],
      foldersLoaded: false,
      folderDetail: null,
      selecting: false,
      selectedReels: [],
      lastSearchResults: []
    };
    const app = document.getElementById('app');
    const libraryNav = document.getElementById('libraryNav');
    const profileNav = document.getElementById('profileNav');
    const foldersNav = document.getElementById('foldersNav');
    const miniPlayer = document.getElementById('miniPlayer');
    const miniThumb = document.getElementById('miniThumb');
    const miniTitle = document.getElementById('miniTitle');
    const miniTime = document.getElementById('miniTime');
    const miniProgress = document.getElementById('miniProgress');
    const miniToggle = document.getElementById('miniToggle');
    const miniMore = document.getElementById('miniMore');
    const miniClose = document.getElementById('miniClose');
    const miniSound = document.getElementById('miniSound');
    const playerStage = document.getElementById('playerStage');
    const playerFlash = document.getElementById('playerFlash');
    const playerBuffer = document.getElementById('playerBuffer');
    const playerCounter = document.getElementById('playerCounter');
    const playerScrub = document.getElementById('playerScrub');
    const actionSheet = document.getElementById('actionSheet');
    const sheetBackdrop = document.getElementById('sheetBackdrop');

    const SEARCH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>';
    const CHEV_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>';
    const BACK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 6-6 6 6 6"/></svg>';
    const ARROW_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>';
    const REFRESH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 1 0-2.3 6.3"/><path d="M20 5v6h-6"/></svg>';
    const BELL_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8a6 6 0 0 0-12 0c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.7 21a2 2 0 0 1-3.4 0"/></svg>';

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
    }
    function greeting() {
      const hour = new Date().getHours();
      if (hour < 5) return 'Late night';
      if (hour < 12) return 'Morning';
      if (hour < 17) return 'Afternoon';
      return 'Evening';
    }
    function prettyTitle(value) {
      const raw = String(value || '').trim();
      return /^(generic|miscellaneous|uncertain|general|personalized|unsorted)$/i.test(raw) ? 'Unsorted' : raw;
    }
    const EMOJI_RULES = [
      [/miscellaneous|generic|uncertain|unsorted/i, '🗂️'],
      [/product|shop|buy|gadget|tech/i, '🛍️'],
      [/recipe|food|cook|craving|snack|street/i, '🍲'],
      [/place|travel|trip|city|location/i, '🗺️'],
      [/fitness|workout|gym|sport|swim|exercise/i, '💪'],
      [/meme|funny|laugh|humor|comedy/i, '😂'],
      [/fashion|outfit|style|wear/i, '👕'],
      [/software|code|app|ai|computer/i, '💻'],
      [/film|movie|tv|show|series/i, '🎬'],
      [/music|song|album/i, '🎵'],
      [/book|read|learn|tutorial|study/i, '📘'],
      [/car|bike|drive|auto/i, '🏎️'],
      [/game|gaming|play/i, '🎮'],
      [/beauty|skin|makeup/i, '✨'],
      [/finance|money|invest|business/i, '💸'],
      [/hobby|diy|craft|build/i, '🧩'],
    ];
    function emojiFor(name) {
      const value = String(name || '');
      for (const [pattern, emoji] of EMOJI_RULES) {
        if (pattern.test(value)) return emoji;
      }
      return '📎';
    }
    function sourceFor(item) {
      const url = String(item.url || '');
      if (/instagram\\.com/i.test(url)) return 'Instagram';
      if (/youtube\\.com|youtu\\.be/i.test(url)) return 'YouTube';
      if (/tiktok\\.com/i.test(url)) return 'TikTok';
      if (url) return 'Saved link';
      return 'Saved';
    }
    function realItems(list) {
      return (list.items || []).filter((item) => {
        const name = String(item.name || '').trim().toLowerCase();
        return name && name !== 'processing failed' && (item.reel_id || item.url || item.local_video_url || item.thumbnail_url);
      });
    }
    function sortedCollections() {
      return state.data
        .map((list, sourceIndex) => ({ ...list, sourceIndex, items: realItems(list), real_count: realItems(list).length }))
        .filter((list) => list.real_count > 0)
        .sort((a, b) => (b.real_count - a.real_count)
          || String(a.list_title || '').localeCompare(String(b.list_title || '')));
    }
    function currentList() {
      return sortedCollections().find((list) => list.list_id === state.currentListId) || null;
    }
    function hasText(text, query) {
      return String(text || '').toLowerCase().includes(String(query || '').toLowerCase());
    }
    function activeJobCount() {
      return Number(state.dashboard.queued_job_count || 0) + Number(state.dashboard.running_job_count || 0);
    }
    function recentJobs() {
      return Array.isArray(state.jobs) ? state.jobs.slice(0, 8) : [];
    }
    function pipelineStatus() {
      const active = activeJobCount();
      const failed = Number(state.dashboard.failed_url_count || 0);
      const pending = Number(state.dashboard.pending_url_count || 0);
      if (active > 0) {
        return {
          tone: 'active',
          title: active === 1 ? 'Processing 1 reel' : `Processing ${active} reels`,
          copy: 'New saves are being downloaded, extracted, and added to search.',
          count: `${active} active`
        };
      }
      if (pending > 0) {
        return {
          tone: 'active',
          title: pending === 1 ? '1 reel waiting' : `${pending} reels waiting`,
          copy: 'The queue has pending reels that should move into processing shortly.',
          count: `${pending} queued`
        };
      }
      if (failed > 0) {
        return {
          tone: 'issue',
          title: failed === 1 ? '1 reel needs attention' : `${failed} reels need attention`,
          copy: 'Open Profile diagnostics to inspect recent job errors.',
          count: `${failed} failed`
        };
      }
      const processed = Number(state.dashboard.processed_url_count || 0);
      return {
        tone: 'idle',
        title: 'Pipeline ready',
        copy: processed ? `${processed} reels processed. New saves will appear here while they run.` : 'No active reel jobs right now.',
        count: 'Ready'
      };
    }
    function renderSyncPill(compact = false) {
      const status = pipelineStatus();
      if (compact && status.tone === 'idle') return '';
      return `<section class="sync-pill ${status.tone}">
        <span class="sync-dot" aria-hidden="true"></span>
        <p class="sync-text"><b>${escapeHtml(status.title)}.</b> ${escapeHtml(status.copy)}</p>
      </section>`;
    }
    function formatTime(value) {
      if (!value) return '';
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return date.toLocaleString([], { month:'short', day:'numeric', hour:'2-digit', minute:'2-digit' });
    }
    function jobTitle(job) {
      return job.reel_shortcode || job.reel_id || job.reel_url || `Job ${job.id}`;
    }
    function renderJobCard(job) {
      const status = String(job.status || 'unknown').toLowerCase();
      const url = job.reel_url || '';
      const time = job.finished_at || job.started_at || job.created_at || '';
      return `<article class="job-card">
        <div class="job-head">
          <h3 class="job-title">${escapeHtml(jobTitle(job))}</h3>
          <span class="status-pill ${escapeHtml(status)}">${escapeHtml(status)}</span>
        </div>
        <p class="job-meta">${escapeHtml(job.job_type || 'processing')} · ${escapeHtml(formatTime(time) || 'time unavailable')} · attempts ${escapeHtml(job.attempts ?? 0)}</p>
        ${url ? `<p class="job-meta">${escapeHtml(url)}</p>` : ''}
        ${job.error_message ? `<p class="job-meta">${escapeHtml(job.error_message)}</p>` : ''}
      </article>`;
    }
    function recentDiagnostics() {
      return Array.isArray(state.diagnostics) ? state.diagnostics.slice(0, 8) : [];
    }
    function renderReelDiagnosticCard(reel) {
      const status = String(reel.status || 'unknown').toLowerCase();
      const title = reel.shortcode || reel.id || reel.url || 'Recent reel';
      const counts = `${reel.item_count || 0} items · ${reel.feature_count || 0} features · ${reel.product_count || 0} products`;
      const firstItems = (reel.items || [])
        .slice(0, 3)
        .map((item) => item.item_name || item.product_name)
        .filter(Boolean)
        .join(' • ');
      return `<article class="job-card">
        <div class="job-head">
          <h3 class="job-title">${escapeHtml(title)}</h3>
          <span class="status-pill ${escapeHtml(status)}">${escapeHtml(status)}</span>
        </div>
        <p class="job-meta">${escapeHtml(counts)} · ${escapeHtml(formatTime(reel.updated_at || reel.received_at) || 'time unavailable')}</p>
        ${reel.video_download_status || reel.transcript_status ? `<p class="job-meta">⬇ video: ${escapeHtml(reel.video_download_status || '—')} · 🎙 transcript: ${escapeHtml(reel.transcript_status || '—')} · 👁 visual: ${escapeHtml(reel.visual_status || '—')}</p>` : ''}
        ${reel.transcript_error ? `<p class="job-meta">🎙 transcript error: ${escapeHtml(reel.transcript_error)}</p>` : ''}
        ${reel.visual_error ? `<p class="job-meta">👁 visual error: ${escapeHtml(reel.visual_error)}</p>` : ''}
        ${firstItems ? `<p class="job-meta">${escapeHtml(firstItems)}</p>` : ''}
        ${reel.url ? `<p class="job-meta">${escapeHtml(reel.url)}</p>` : ''}
      </article>`;
    }
    function listMatches(list) {
      const q = state.query.trim();
      const chipOk = state.chip === 'All' || (list.parent_title || list.list_title) === state.chip;
      if (!chipOk) return false;
      if (!q) return true;
      return hasText(`${list.list_title} ${list.parent_title || ''}`, q)
        || list.items.some((item) => hasText(`${item.name} ${item.product_name || ''} ${item.summary || ''}`, q));
    }
    function itemMatches(item) {
      const q = state.itemQuery.trim();
      const chipOk = state.itemChip === 'All'
        || (state.itemChip === 'Saved')
        || (state.itemChip === 'Video' && videoFor(item));
      if (!chipOk) return false;
      if (!q) return true;
      return hasText(`${item.name} ${item.summary || ''}`, q);
    }
    function thumbnailFor(item) {
      return item.item_thumbnail || item.reel_thumbnail || item.thumbnail_url || item.thumbnail_path || '';
    }
    function videoFor(item) {
      return item.local_video_url || item.video_url || '';
    }
    function mediaFor(item) {
      return item.item_thumbnail || item.reel_thumbnail || thumbnailFor(item) || videoFor(item);
    }
    const PH_PALETTES = [
      ['#1c2b4a', '#3d5a80'], ['#2d1b3d', '#6d3b6e'], ['#1b3a2d', '#3f7a5a'],
      ['#3a2a1b', '#7a5a3f'], ['#1b2d3a', '#3f5f7a'], ['#3a1b1f', '#7a3f4a'],
      ['#26203a', '#4f4478'], ['#33301b', '#6e683f'],
    ];
    function gradFor(name) {
      let hash = 0;
      for (const char of String(name || 'reel')) hash = (hash + char.codePointAt(0)) % 9973;
      const [dark, mid] = PH_PALETTES[hash % PH_PALETTES.length];
      return `linear-gradient(135deg, ${dark}, ${mid} 60%, ${dark})`;
    }
    // Reels are always represented by their real thumbnail/video. When a reel has
    // no stored media yet, we show a neutral "no preview" glyph over a gradient —
    // never a topical emoji, which would misleadingly look like the reel's content.
    function reelThumb(item, className, loading = 'lazy', inner = '') {
      const src = mediaFor(item);
      const label = item.name || item.list_title || 'reel';
      const media = src ? renderMedia(item, loading) : '<span class="ph-glyph">▶</span>';
      return `<span class="${className}" style="background:${gradFor(label)}">${media}${inner}</span>`;
    }
    function renderMedia(item, loading = 'lazy') {
      const src = mediaFor(item);
      if (!src) return '<div aria-hidden="true"></div>';
      if (/\\.mp4($|[?#])/i.test(src)) return `<video src="${escapeHtml(src)}#t=0.1" muted playsinline preload="metadata"></video>`;
      return `<img src="${escapeHtml(src)}" alt="" loading="${loading}" onerror="this.remove()" />`;
    }
    function coverItem(list) {
      return list.items.find((item) => mediaFor(item)) || list.items[0] || {};
    }
    function chips() {
      return ['All', ...Array.from(new Set(sortedCollections().map((list) => list.parent_title || list.list_title))).filter(Boolean)];
    }
    // A folder is "unsorted" when its category is one of the generic buckets the
    // pipeline falls back to. These loose reels live only in Recently saved — they
    // are NOT shown as real folders in the Library section.
    function isUnsortedList(list) {
      const key = String(list.parent_title || list.list_title || '').trim().toLowerCase();
      return ['', 'generic', 'miscellaneous', 'uncertain', 'general', 'personalized', 'unsorted'].includes(key);
    }
    function realFolders() {
      return sortedCollections().filter((list) => !isUnsortedList(list));
    }
    function categoryTiles() {
      const groups = new Map();
      for (const list of realFolders()) {
        const key = list.parent_title || list.list_title;
        if (!key) continue;
        groups.set(key, (groups.get(key) || 0) + list.real_count);
      }
      return Array.from(groups.entries());
    }
    function flatItems() {
      return sortedCollections().flatMap((list) =>
        list.items.map((item) => ({ ...item, list_id: list.list_id, list_title: list.list_title, parent_title: list.parent_title })));
    }
    function recentItems(limit = 24) {
      const seen = new Set();
      const items = [];
      for (const item of flatItems()) {
        const key = item.reel_id || item.url || item.name;
        if (!key || seen.has(key)) continue;
        seen.add(key);
        items.push(item);
        if (items.length >= limit) break;
      }
      return items;
    }
    function renderSearchBox(placeholder, value, id) {
      return `<label class="search"><span class="glyph">${SEARCH_SVG}</span><input id="${id}" type="search" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}" autocomplete="off" /></label>`;
    }
    function renderChips(values, active, kind) {
      return `<div class="chips" aria-label="${kind} filters">${values.map((chip) => `<button class="chip ${chip === active ? 'active' : ''}" type="button" data-chip-kind="${kind}" data-chip="${escapeHtml(chip)}">${escapeHtml(prettyTitle(chip))}</button>`).join('')}</div>`;
    }

    /* ---------- HOME ---------- */
    function renderLibrary() {
      const lists = realFolders().filter(listMatches);
      const recents = recentItems(24);
      const hasAnyItems = flatItems().length > 0;
      const searching = state.magicQuery.trim().length > 0;
      const status = pipelineStatus();
      app.innerHTML = `
        <div class="home-head">
          <h1 class="greeting">${escapeHtml(greeting())}</h1>
          <div class="icon-row">
            <button class="icon-button" type="button" aria-label="Activity" id="notifButton">${BELL_SVG}${status.tone !== 'idle' ? `<span class="notif-dot ${status.tone}"></span>` : ''}</button>
            <button class="icon-button" type="button" aria-label="Refresh" id="refreshButton">${REFRESH_SVG}</button>
            <div id="notifPopover" class="notif-popover" ${state.notifOpen ? '' : 'hidden'}>
              <p class="notif-head">Activity</p>
              ${renderSyncPill()}
              <div class="notif-stats">
                <span>Queued <b>${state.dashboard.queued_job_count || 0}</b></span>
                <span>Running <b>${state.dashboard.running_job_count || 0}</b></span>
                <span>Failed <b>${state.dashboard.failed_url_count || 0}</b></span>
              </div>
            </div>
          </div>
        </div>
        <label class="search"><span class="glyph">${SEARCH_SVG}</span><input id="deepSearchInput" type="search" value="${escapeHtml(state.magicQuery)}" placeholder="Search anything you saved..." autocomplete="off" /></label>
        <div class="folder-toolbar" ${searching ? '' : 'hidden'}>
          ${state.selecting
            ? '<button class="newlist-btn ghost" id="cancelSelectBtn" type="button">Cancel</button>'
            : '<button class="newlist-btn" id="startSelectBtn" type="button">＋ New list</button>'}
        </div>
        <section id="homeResults" ${searching ? '' : 'hidden'}></section>
        <div id="homeBrowse" ${searching ? 'hidden' : ''}>
          ${recents.length ? `
            <div class="section-head"><h2 class="section-title">Recently saved <span class="chev">›</span></h2></div>
            <div class="recent-rail">${recents.map((item, index) => `
              <button class="recent-card" type="button" data-recent-item="${index}">
                ${reelThumb(item, 'recent-thumb', index < 4 ? 'eager' : 'lazy')}
                <p class="recent-source">${escapeHtml(sourceFor(item))}</p>
                <p class="recent-title">${escapeHtml(item.name)}</p>
              </button>`).join('')}</div>` : ''}
          <div class="section-head">
            <h2 class="section-title">Library <span class="chev">›</span></h2>
            <span class="section-side">${lists.length} ${lists.length === 1 ? 'folder' : 'folders'}</span>
          </div>
          ${state.loading ? '<div class="empty">Loading your library...</div>' : ''}
          ${!state.loading && lists.length ? `<section class="lib-list">${lists.map(renderLibRow).join('')}</section>` : ''}
          ${!state.loading && !lists.length && hasAnyItems ? '<div class="empty">No folders yet. Your saved reels are in Recently saved above — folders appear here as they get organized.</div>' : ''}
          ${!state.loading && !lists.length && !hasAnyItems ? '<div class="empty">Nothing here yet. Save a reel to get started.</div>' : ''}
        </div>
      `;
      const deepInput = document.getElementById('deepSearchInput');
      deepInput?.addEventListener('input', (event) => {
        state.magicQuery = event.target.value;
        const active = state.magicQuery.trim().length > 0;
        document.getElementById('homeResults')?.toggleAttribute('hidden', !active);
        document.getElementById('homeBrowse')?.toggleAttribute('hidden', active);
        document.querySelector('.folder-toolbar')?.toggleAttribute('hidden', !active);
        scheduleDeepSearch();
      });
      document.getElementById('startSelectBtn')?.addEventListener('click', enterSelect);
      document.getElementById('cancelSelectBtn')?.addEventListener('click', exitSelect);
      const notifButton = document.getElementById('notifButton');
      notifButton?.addEventListener('click', (event) => {
        event.stopPropagation();
        state.notifOpen = !state.notifOpen;
        document.getElementById('notifPopover')?.toggleAttribute('hidden', !state.notifOpen);
      });
      if (!window.__notifBound) {
        window.__notifBound = true;
        document.addEventListener('click', (ev) => {
          if (!state.notifOpen) return;
          const pop = document.getElementById('notifPopover');
          if (pop && !pop.contains(ev.target) && !ev.target.closest('#notifButton')) {
            state.notifOpen = false;
            pop.setAttribute('hidden', '');
          }
        });
      }
      document.getElementById('refreshButton')?.addEventListener('click', loadData);
      bindChips();
      const recentsData = recentItems(24);
      app.querySelectorAll('[data-recent-item]').forEach((button) => {
        button.addEventListener('click', () => openActionSheet(recentsData[Number(button.dataset.recentItem)], Number(button.dataset.recentItem), recentsData));
      });
      app.querySelectorAll('[data-open-list]').forEach((button) => {
        button.addEventListener('click', () => {
          state.currentListId = button.dataset.openList;
          state.itemQuery = '';
          state.itemChip = 'All';
          state.screen = 'list';
          state.notifOpen = false;
          window.scrollTo({ top: 0, behavior: 'instant' });
          render();
        });
      });
      if (searching) {
        if (state.deepSearch.query !== state.magicQuery.trim()) scheduleDeepSearch();
        else renderSearchResults();
        if (deepInput) { deepInput.focus(); deepInput.setSelectionRange(deepInput.value.length, deepInput.value.length); }
      }
    }
    function renderLibRow(list) {
      // Folders are represented by a clean logo (emoji), never a random reel frame.
      return `<button class="lib-row" type="button" data-open-list="${escapeHtml(list.list_id)}" aria-label="Open ${escapeHtml(list.list_title)}">
        <span class="lib-icon" style="background:${gradFor(list.parent_title || list.list_title)}">${emojiFor(list.parent_title || list.list_title)}</span>
        <span>
          <p class="lib-name">${escapeHtml(prettyTitle(list.list_title))}</p>
          <p class="lib-meta">${emojiFor(list.parent_title || list.list_title)} ${list.real_count} ${list.real_count === 1 ? 'item' : 'items'}${list.parent_title ? `<span class="dot-sep">·</span>${escapeHtml(prettyTitle(list.parent_title))}` : ''}</p>
        </span>
        <span class="row-chev">${CHEV_SVG}</span>
      </button>`;
    }

    /* ---------- FOLDER ---------- */
    function renderListScreen() {
      const list = currentList();
      if (!list) {
        state.screen = 'library';
        state.currentListId = '';
        render();
        return;
      }
      app.innerHTML = `
        <div class="list-heading">
          <button id="backToLibrary" class="back-button" type="button" aria-label="Back to library">${BACK_SVG}</button>
          <div class="list-title-block"><h1>${escapeHtml(prettyTitle(list.list_title))}</h1><p class="count-text" id="folderCount"></p></div>
          <div class="icon-row"></div>
        </div>
        ${renderSearchBox(`Search in ${prettyTitle(list.list_title)}...`, state.itemQuery, 'itemSearch')}
        ${renderChips(['All', 'Video'], state.itemChip, 'item')}
        <section id="folderResults"></section>
      `;
      // Re-render only the results grid (never the whole screen) so the search
      // input keeps focus and the header doesn't flicker on every keystroke.
      function renderFolderResults() {
        const items = list.items.filter(itemMatches);
        const count = document.getElementById('folderCount');
        if (count) count.textContent = `${items.length} ${items.length === 1 ? 'item' : 'items'}`;
        const results = document.getElementById('folderResults');
        if (!results) return;
        results.innerHTML = items.length
          ? `<section class="masonry">${items.map(renderItemCard).join('')}</section>`
          : '<div class="empty">No items found</div>';
        results.querySelectorAll('[data-open-item]').forEach((button) => {
          button.addEventListener('click', () => openActionSheet(items[Number(button.dataset.openItem)], Number(button.dataset.openItem), items));
        });
        results.querySelectorAll('[data-item-menu]').forEach((el) => {
          el.addEventListener('click', (event) => {
            event.stopPropagation();
            openActionSheet(items[Number(el.dataset.itemMenu)], Number(el.dataset.itemMenu), items);
          });
        });
      }
      document.getElementById('backToLibrary').addEventListener('click', () => {
        state.screen = 'library';
        state.currentListId = '';
        render();
      });
      document.getElementById('itemSearch').addEventListener('input', (event) => {
        state.itemQuery = event.target.value;
        renderFolderResults();
      });
      app.querySelectorAll('[data-chip-kind="item"]').forEach((button) => {
        button.addEventListener('click', () => {
          state.itemChip = button.dataset.chip;
          app.querySelectorAll('[data-chip-kind="item"]').forEach((chip) =>
            chip.classList.toggle('active', chip.dataset.chip === state.itemChip));
          renderFolderResults();
        });
      });
      renderFolderResults();
    }
    function renderItemCard(item, index) {
      const rid = item.reel_id || '';
      const sel = state.selecting && state.selectedReels.includes(rid);
      return `<article class="m-card${state.selecting ? ' selectable' : ''}${sel ? ' selected' : ''}" data-reel="${escapeHtml(rid)}">
        <span class="selring"></span>
        <button style="width:100%;text-align:left" type="button" data-open-item="${index}" aria-label="Preview ${escapeHtml(item.name)}">
          ${reelThumb(item, 'm-thumb', 'lazy', `<span class="m-badges">${videoFor(item) ? '<span class="badge-dot">▶</span>' : ''}</span>`)}
          <span class="m-title-row"><p class="m-title">${escapeHtml(item.name)}</p><span class="m-kebab" data-item-menu="${index}">···</span></span>
          ${item.summary ? `<p class="m-summary">${escapeHtml(item.summary)}</p>` : ''}
        </button>
      </article>`;
    }

    /* ---------- SEARCH ---------- */
    function searchTabResults() {
      const q = state.magicQuery.trim();
      const allItems = flatItems();
      return q
        ? allItems.filter((item) => hasText(`${item.name} ${item.summary || ''} ${item.list_title || ''} ${item.parent_title || ''}`, q)).slice(0, 24)
        : [];
    }
    function normalizeDeepSearchPayload(payload) {
      if (Array.isArray(payload?.results)) return payload.results;
      if (Array.isArray(payload?.result?.hits)) return payload.result.hits;
      return [];
    }
    function deepSearchTitle(result) {
      return result.item_names?.[0]
        || result.product_names?.[0]
        || result.brands?.[0]
        || result.shortcode
        || 'Saved reel';
    }
    function deepSearchSummary(result) {
      const reasons = result.match_reasons || [];
      if (reasons.length) return reasons.slice(0, 2).join(' • ');
      const parts = [
        ...(result.product_names || []),
        ...(result.brands || []),
        ...(result.collection_titles || []),
        ...(result.parent_titles || []),
        ...(result.entities || []),
        ...(result.visual_entities || []),
        ...(result.visible_text || []),
        ...(result.visual_supporting_points || []),
        result.visual_summary || '',
      ].filter(Boolean);
      return parts.slice(0, 5).join(' • ') || 'Matched from your saved reel memory.';
    }
    function deepSearchItem(result) {
      const media = result.media || {};
      return {
        reel_id: result.reel_id || result.id,
        url: result.url || '',
        name: deepSearchTitle(result),
        summary: deepSearchSummary(result),
        local_video_url: media.local_video_url || '',
        thumbnail_url: media.thumbnail_url || '',
        reel_thumbnail: media.thumbnail_url || '',
        list_title: (result.collection_titles || [])[0] || (result.parent_titles || [])[0] || 'Deep Search',
      };
    }
    function scheduleDeepSearch() {
      clearTimeout(state.deepSearchTimer);
      const q = state.magicQuery.trim();
      if (!q) {
        state.deepSearch = { query: '', loading: false, error: '', results: [] };
        renderSearchResults();
        return;
      }
      state.deepSearch = { ...state.deepSearch, query: q, loading: true, error: '' };
      renderSearchResults();
      state.deepSearchTimer = setTimeout(() => runDeepSearch(q), 180);
    }
    async function runDeepSearch(query) {
      const requestId = ++state.deepSearchRequestId;
      try {
        const response = await fetch(`/deep-search?q=${encodeURIComponent(query)}&user_id=${encodeURIComponent(USER_ID)}&limit=30`);
        if (!response.ok) throw new Error('Search failed');
        const payload = await response.json();
        if (requestId !== state.deepSearchRequestId) return;
        state.deepSearch = {
          query,
          loading: false,
          error: '',
          results: normalizeDeepSearchPayload(payload),
        };
      } catch (error) {
        if (requestId !== state.deepSearchRequestId) return;
        state.deepSearch = { query, loading: false, error: 'Deep Search is unavailable right now.', results: [] };
      }
      renderSearchResults();
    }
    function renderSearchResults() {
      const q = state.magicQuery.trim();
      const deepReady = state.deepSearch.query === q;
      const deepResults = deepReady ? state.deepSearch.results.map(deepSearchItem) : [];
      const localResults = searchTabResults();
      const seen = new Set();
      const results = [...deepResults, ...localResults].filter((item) => {
        const key = item.reel_id || item.url || item.name;
        if (!key || seen.has(key)) return false;
        seen.add(key);
        return true;
      }).slice(0, 30);
      const resultList = document.getElementById('homeResults');
      if (!resultList) return;
      resultList.innerHTML = `
        ${q && state.deepSearch.loading && state.deepSearch.query === q ? '<div class="empty">Searching captions, visuals, and transcripts...</div>' : ''}
        ${q && state.deepSearch.error && !results.length ? `<div class="empty">${escapeHtml(state.deepSearch.error)}</div>` : ''}
        ${q && !state.deepSearch.loading && !results.length ? '<div class="empty">No matches yet. Try a broader word.</div>' : ''}
        ${results.length ? `<section class="masonry">${results.map(renderItemCard).join('')}</section>` : ''}
      `;
      state.lastSearchResults = results;
      resultList.querySelectorAll('[data-open-item]').forEach((button) => {
        button.addEventListener('click', (event) => {
          if (state.selecting) {
            event.preventDefault();
            toggleSelect(button.closest('.m-card')?.dataset.reel || '');
            return;
          }
          openActionSheet(results[Number(button.dataset.openItem)], Number(button.dataset.openItem), results);
        });
      });
      resultList.querySelectorAll('[data-item-menu]').forEach((el) => {
        el.addEventListener('click', (event) => {
          event.stopPropagation();
          if (state.selecting) { toggleSelect(el.closest('.m-card')?.dataset.reel || ''); return; }
          openActionSheet(results[Number(el.dataset.itemMenu)], Number(el.dataset.itemMenu), results);
        });
      });
    }

    /* ---------- SMART FOLDERS ---------- */
    function ensureFolderDom() {
      if (document.getElementById('folderSelBar')) return;
      const bar = document.createElement('div');
      bar.id = 'folderSelBar'; bar.className = 'selbar';
      bar.innerHTML = '<span id="selCount">0 selected</span>'
        + '<span><button class="newlist-btn ghost" id="selCancel2" type="button">Cancel</button> '
        + '<button class="newlist-btn" id="selContinue" type="button">Continue &rarr;</button></span>';
      document.body.appendChild(bar);
      const ov = document.createElement('div');
      ov.id = 'folderOverlay'; ov.className = 'folder-overlay';
      ov.innerHTML = '<div class="folder-modal"><h3>New list</h3><div class="sub" id="createSub"></div>'
        + '<div id="createDrafting" class="sub">✨ AI is drafting a name &amp; description…</div>'
        + '<div id="createForm" style="display:none"><label>List name</label><input id="createName" type="text" />'
        + '<label>Description (this decides what auto-joins later)</label><textarea id="createDesc"></textarea>'
        + '<div class="hint">Edit freely &mdash; the description is the rule for what belongs.</div>'
        + '<div class="row"><button class="newlist-btn ghost" id="createCancel" type="button">Cancel</button>'
        + '<button class="newlist-btn" id="createSubmit" type="button">Create list</button></div></div></div>';
      document.body.appendChild(ov);
      document.getElementById('selCancel2').addEventListener('click', exitSelect);
      document.getElementById('selContinue').addEventListener('click', openCreate);
      document.getElementById('createCancel').addEventListener('click', () => ov.classList.remove('show'));
      document.getElementById('createSubmit').addEventListener('click', submitCreate);
    }
    function enterSelect() { ensureFolderDom(); state.selecting = true; state.selectedReels = []; render(); updateSelBar(); }
    function exitSelect() { state.selecting = false; state.selectedReels = []; document.getElementById('folderSelBar')?.classList.remove('show'); render(); }
    function toggleSelect(rid) {
      if (!rid) return;
      const i = state.selectedReels.indexOf(rid);
      if (i >= 0) state.selectedReels.splice(i, 1); else state.selectedReels.push(rid);
      const card = [...document.querySelectorAll('.m-card')].find((c) => c.dataset.reel === rid);
      card?.classList.toggle('selected', state.selectedReels.includes(rid));
      updateSelBar();
    }
    function updateSelBar() {
      ensureFolderDom();
      document.getElementById('selCount').textContent = `${state.selectedReels.length} selected`;
      document.getElementById('selContinue').disabled = state.selectedReels.length === 0;
      document.getElementById('folderSelBar').classList.toggle('show', state.selecting);
    }
    async function openCreate() {
      if (!state.selectedReels.length) return;
      const ov = document.getElementById('folderOverlay');
      ov.classList.add('show');
      document.getElementById('createDrafting').style.display = 'block';
      document.getElementById('createForm').style.display = 'none';
      document.getElementById('createSub').textContent = `${state.selectedReels.length} reels · from "${state.magicQuery.trim()}"`;
      try {
        const r = await fetch('/folders/suggest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
          body: JSON.stringify({ user_id: USER_ID, query: state.magicQuery.trim(), reel_ids: state.selectedReels }) });
        const d = await r.json();
        document.getElementById('createName').value = d.name || state.magicQuery.trim();
        document.getElementById('createDesc').value = d.description || '';
      } catch (e) {
        document.getElementById('createName').value = state.magicQuery.trim();
        document.getElementById('createDesc').value = '';
      }
      document.getElementById('createDrafting').style.display = 'none';
      document.getElementById('createForm').style.display = 'block';
    }
    async function submitCreate() {
      const name = document.getElementById('createName').value.trim();
      const description = document.getElementById('createDesc').value.trim();
      if (!name || !description) return;
      await fetch('/folders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
        body: JSON.stringify({ user_id: USER_ID, query: state.magicQuery.trim(), name, description, reel_ids: state.selectedReels }) });
      document.getElementById('folderOverlay').classList.remove('show');
      exitSelect();
      state.foldersLoaded = false;
      await loadFolders();
      setNav('folders');
    }
    async function loadFolders() {
      try {
        const r = await fetch(`/folders?user_id=${encodeURIComponent(USER_ID)}`, { credentials: 'same-origin' });
        const d = await r.json();
        state.folders = d.folders || [];
      } catch (e) { state.folders = []; }
      state.foldersLoaded = true;
      if (state.screen === 'folders') renderFolders();
    }
    function renderFolders() {
      if (state.folderDetail) { renderFolderDetail(); return; }
      const fs = state.folders;
      app.innerHTML = '<div class="home-head"><h1 class="greeting">Folders</h1></div>'
        + (!state.foldersLoaded ? '<div class="empty">Loading…</div>' : '')
        + (state.foldersLoaded && !fs.length ? '<div class="empty">No folders yet. Search your reels and tap ＋ New list to make one.</div>' : '')
        + fs.map((f) => `<div class="folder-card" data-folder="${f.id}"><span class="count">${f.item_count} reels</span>`
          + `<h3>${escapeHtml(f.name)}</h3><p class="sub">${escapeHtml(f.description || '')}</p></div>`).join('');
      app.querySelectorAll('[data-folder]').forEach((el) => el.addEventListener('click', () => openFolderDetail(Number(el.dataset.folder))));
    }
    async function openFolderDetail(id) {
      try {
        const r = await fetch(`/folders/${id}?user_id=${encodeURIComponent(USER_ID)}`, { credentials: 'same-origin' });
        state.folderDetail = await r.json();
      } catch (e) { return; }
      renderFolderDetail();
    }
    function folderItemRow(m, suggested) {
      return `<article class="m-card"><button style="width:100%;text-align:left" type="button" data-open-url="${escapeHtml(m.url || '')}">`
        + `<span class="m-title-row"><p class="m-title">${escapeHtml(m.item_name || m.name || 'Saved reel')}${suggested ? '<span class="sug-chip">suggested</span>' : ''}</p></span>`
        + (m.summary ? `<p class="m-summary">${escapeHtml(m.summary)}</p>` : '') + '</button>'
        + (suggested ? '<div style="display:flex;gap:8px;padding:0 4px 10px">'
          + `<button class="newlist-btn" type="button" data-accept="${escapeHtml(m.reel_id)}">Add</button>`
          + `<button class="newlist-btn ghost" type="button" data-reject="${escapeHtml(m.reel_id)}">No</button></div>` : '')
        + '</article>';
    }
    function renderFolderDetail() {
      const f = state.folderDetail;
      app.innerHTML = '<div class="home-head"><button class="newlist-btn ghost" id="folderBack" type="button">← Folders</button></div>'
        + `<h1 class="greeting" style="margin-top:6px">${escapeHtml(f.name)}</h1>`
        + `<p style="color:var(--muted);font-size:.85rem;margin:4px 0 8px">${escapeHtml(f.description || '')}</p>`
        + ((f.suggestions || []).length ? '<div class="section-head"><h2 class="section-title">Suggested &mdash; auto-routed, needs your yes</h2></div>'
          + `<section class="masonry">${f.suggestions.map((m) => folderItemRow(m, true)).join('')}</section>` : '')
        + '<div class="section-head"><h2 class="section-title">In this folder</h2></div>'
        + ((f.members || []).length ? `<section class="masonry">${f.members.map((m) => folderItemRow(m, false)).join('')}</section>` : '<div class="empty">No reels yet.</div>');
      document.getElementById('folderBack').addEventListener('click', () => { state.folderDetail = null; renderFolders(); });
      app.querySelectorAll('[data-open-url]').forEach((b) => b.addEventListener('click', () => { const u = b.dataset.openUrl; if (u) window.open(u, '_blank'); }));
      app.querySelectorAll('[data-accept]').forEach((b) => b.addEventListener('click', () => folderDecide(f.id, b.dataset.accept, 'accept')));
      app.querySelectorAll('[data-reject]').forEach((b) => b.addEventListener('click', () => folderDecide(f.id, b.dataset.reject, 'reject')));
    }
    async function folderDecide(id, reel, action) {
      await fetch(`/folders/${id}/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
        body: JSON.stringify({ user_id: USER_ID, reel_id: reel }) });
      await openFolderDetail(id);
    }

    /* ---------- PROFILE ---------- */
    function renderProfile() {
      const totalItems = sortedCollections().reduce((sum, list) => sum + list.real_count, 0);
      const jobs = recentJobs();
      const diagnostics = recentDiagnostics();
      app.innerHTML = `
        <div class="home-head">
          <h1 class="greeting">Profile</h1>
          <div class="icon-row"><button class="icon-button" type="button" aria-label="Refresh diagnostics" id="profileRefresh">${REFRESH_SVG}</button></div>
        </div>
        ${renderSyncPill(true)}
        <section class="metric-grid">
          <div class="metric-card"><span>Library items</span><b>${totalItems}</b></div>
          <div class="metric-card"><span>Processed reels</span><b>${state.dashboard.processed_url_count || 0}</b></div>
          <div class="metric-card"><span>Queued</span><b>${state.dashboard.queued_job_count || 0}</b></div>
          <div class="metric-card"><span>Running</span><b>${state.dashboard.running_job_count || 0}</b></div>
        </section>
        <section class="set-section">
          <h2 class="set-title">Account</h2>
          <div class="set-card">
            <div class="set-row">Signed in as <span class="value">${escapeHtml(USER_ID)}</span></div>
            <div class="set-row">Instagram <span class="value">${instagramStatusLabel()}</span></div>
            ${renderInstagramRows()}
            <button class="set-row danger" type="button" id="logoutButton">Log out</button>
          </div>
        </section>
        <section class="set-section">
          <h2 class="set-title">Pipeline</h2>
          <div class="set-card">
            <div class="set-row">Sync status <span class="value">${escapeHtml(pipelineStatus().title)}</span></div>
            <div class="set-row">Pending reels <span class="value">${state.dashboard.pending_url_count || 0}</span></div>
            <div class="set-row">Failed reels <span class="value">${state.dashboard.failed_url_count || 0}</span></div>
            ${state.session?.authenticated ? '<button class="set-row action" type="button" id="retryUnsortedButton">Reprocess Unsorted &amp; failed reels</button>' : ''}
          </div>
        </section>
        <section class="set-section">
          <h2 class="set-title">Recent reel jobs</h2>
          <section class="job-list">
            ${jobs.length ? jobs.map(renderJobCard).join('') : '<div class="empty">No recent jobs found yet</div>'}
          </section>
        </section>
        <section class="set-section">
          <h2 class="set-title">Recent stored reels</h2>
          <section class="job-list">
            ${diagnostics.length ? diagnostics.map(renderReelDiagnosticCard).join('') : '<div class="empty">No stored reel diagnostics found yet</div>'}
          </section>
        </section>
      `;
      document.getElementById('profileRefresh')?.addEventListener('click', loadData);
      document.getElementById('retryUnsortedButton')?.addEventListener('click', retryUnsorted);
      document.getElementById('logoutButton')?.addEventListener('click', logout);
      document.getElementById('unlinkInstagramButton')?.addEventListener('click', unlinkInstagram);
      document.getElementById('connectInstagramButton')?.addEventListener('click', connectInstagram);
      document.getElementById('igNewCodeButton')?.addEventListener('click', connectInstagram);
      document.getElementById('igLinkDoneButton')?.addEventListener('click', loadData);
    }
    async function retryUnsorted() {
      const confirmed = window.confirm(
        'Reprocess every Unsorted or failed reel?\\n\\n' +
        'Each reel will be downloaded and categorized again. If the AI key on the server is not working, they will come back as Unsorted again — fix the key first.'
      );
      if (!confirmed) return;
      const button = document.getElementById('retryUnsortedButton');
      if (button) { button.disabled = true; button.textContent = 'Requeuing…'; }
      try {
        const response = await fetch(`/reels/retry-unsorted?user_id=${encodeURIComponent(USER_ID)}`, { method: 'POST', credentials: 'same-origin' });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Requeue failed');
        window.alert(`Requeued ${payload.requeued_count} reels for reprocessing.` + (payload.error_count ? ` ${payload.error_count} could not be requeued.` : ''));
      } catch (error) {
        window.alert(error.message || 'Could not requeue reels. Please try again.');
      }
      loadData();
    }
    function instagramStatusLabel() {
      if (!state.session || !state.session.authenticated) return '—';
      if (state.session.instagram_connected) {
        const username = state.session.user?.instagram_username;
        return username ? '@' + escapeHtml(username) : 'Connected';
      }
      return 'Not connected';
    }
    function renderInstagramRows() {
      const session = state.session;
      if (!session || !session.authenticated) return '';
      if (session.instagram_connected) {
        return `<button class="set-row" type="button" id="unlinkInstagramButton">Unlink Instagram <span class="value">Start a fresh library</span></button>`;
      }
      if (state.igLink) {
        return `
          <div class="ig-code">${escapeHtml(state.igLink.code)}</div>
          <p class="ig-help">From your Instagram app, send this code as a direct message to <b>@${escapeHtml(state.igLink.instagram_username || '')}</b>. Reels you DM will only arrive here after this step.</p>
          <button class="set-row action" type="button" id="igLinkDoneButton">I sent the code — check status</button>
          <button class="set-row" type="button" id="igNewCodeButton">Get a new code</button>
        `;
      }
      return `<button class="set-row action" type="button" id="connectInstagramButton">Connect Instagram</button>`;
    }
    async function connectInstagram() {
      const button = document.getElementById('connectInstagramButton') || document.getElementById('igNewCodeButton');
      if (button) { button.disabled = true; button.textContent = 'Getting code…'; }
      try {
        const response = await fetch('/auth/instagram/connect', { method: 'POST', credentials: 'same-origin' });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Could not start Instagram linking');
        state.igLink = payload;
      } catch (error) {
        window.alert(error.message || 'Could not start Instagram linking. Please try again.');
      }
      renderProfile();
    }
    async function unlinkInstagram() {
      const confirmed = window.confirm(
        'Unlink this Instagram account?\\n\\n' +
        'Your current library stays saved on this account, but new reels will stop arriving here. ' +
        'You can then sign in with another Google account and connect the same Instagram to build a fresh library.'
      );
      if (!confirmed) return;
      const button = document.getElementById('unlinkInstagramButton');
      if (button) { button.disabled = true; button.textContent = 'Unlinking…'; }
      try {
        const response = await fetch('/auth/instagram/disconnect', { method: 'POST', credentials: 'same-origin' });
        if (!response.ok) throw new Error('Failed to unlink');
        state.igLink = null;
        window.alert('Instagram unlinked. Log out, then sign in with your other Google account and connect Instagram there.');
      } catch (error) {
        window.alert('Could not unlink Instagram. Please try again.');
        if (button) { button.disabled = false; button.textContent = 'Unlink Instagram (start a fresh library)'; }
      }
      loadData();
    }
    async function logout() {
      const button = document.getElementById('logoutButton');
      if (button) { button.disabled = true; button.textContent = 'Logging out…'; }
      try {
        await fetch('/auth/logout', { method: 'POST', credentials: 'same-origin' });
      } catch (error) {
        // Ignore network errors — clear the session view regardless.
      }
      window.location.href = '/';
    }
    function bindChips() {
      app.querySelectorAll('[data-chip-kind]').forEach((button) => {
        button.addEventListener('click', () => {
          if (button.dataset.chipKind === 'library') {
            state.chip = state.chip === button.dataset.chip ? 'All' : button.dataset.chip;
          }
          if (button.dataset.chipKind === 'item') state.itemChip = button.dataset.chip;
          render();
        });
      });
    }
    function fmtTime(seconds) {
      if (!Number.isFinite(seconds) || seconds < 0) return '0:00';
      return `${Math.floor(seconds / 60)}:${String(Math.floor(seconds % 60)).padStart(2, '0')}`;
    }
    function openMiniPlayer(item, index, list) {
      if (!item) return;
      state.miniList = Array.isArray(list) && list.length ? list : [item];
      state.miniIndex = Math.max(0, Math.min(index || 0, state.miniList.length - 1));
      renderReel('none');
      miniPlayer.classList.add('visible');
    }
    function renderReel(direction) {
      const item = state.miniList[state.miniIndex];
      if (!item) return;
      state.miniItem = item;
      clearBufferHint();
      miniSound.hidden = true;
      miniTitle.textContent = item.name || 'Untitled item';
      miniTime.textContent = '0:00 / 0:00';
      miniProgress.style.width = '0%';
      playerCounter.hidden = state.miniList.length < 2;
      playerCounter.textContent = `${state.miniIndex + 1} / ${state.miniList.length}`;
      const thumb = thumbnailFor(item);
      const video = videoFor(item);
      miniThumb.classList.remove('enter-up', 'enter-down');
      if (direction !== 'none') {
        void miniThumb.offsetWidth; // restart the enter animation
        miniThumb.classList.add(direction === 'up' ? 'enter-up' : 'enter-down');
      }
      if (video) {
        // Poster shows instantly while the file streams in — perceived speed.
        miniThumb.innerHTML = `<video id="miniVideo" src="${escapeHtml(video)}" ${thumb ? `poster="${escapeHtml(thumb)}"` : ''} playsinline loop preload="auto"></video>`;
        const player = document.getElementById('miniVideo');
        player.addEventListener('timeupdate', updateMiniTime);
        player.addEventListener('loadedmetadata', updateMiniTime);
        player.addEventListener('error', () => showPlayerFallback(item, 'This video could not be loaded.'));
        // Buffering hint appears only after a real stall — an instant spinner
        // makes fast loads feel slower than they are.
        player.addEventListener('waiting', queueBufferHint);
        player.addEventListener('stalled', queueBufferHint);
        player.addEventListener('playing', clearBufferHint);
        player.addEventListener('canplay', clearBufferHint);
        setPausedUI(false);
        // Opened from a tap, so playing with sound is usually allowed. If the
        // browser refuses, fall back to muted playback with a tap-for-sound button.
        player.muted = !state.soundOn;
        if (player.muted) {
          miniSound.hidden = false;
          miniSound.textContent = '🔇';
        }
        player.play().catch(() => {
          if (!player.muted) {
            player.muted = true;
            miniSound.hidden = false;
            miniSound.textContent = '🔇';
            player.play().catch(() => {});
          }
        });
        preloadNextReel();
      } else {
        showPlayerFallback(item, 'No video is saved for this reel yet.');
      }
    }
    function stepReel(delta) {
      const nextIndex = state.miniIndex + delta;
      if (nextIndex < 0 || nextIndex >= state.miniList.length) return;
      state.miniIndex = nextIndex;
      renderReel(delta > 0 ? 'up' : 'down');
    }
    function preloadNextReel() {
      const next = state.miniList[state.miniIndex + 1];
      const src = next ? videoFor(next) : '';
      if (!src) return;
      if (!state.preloadEl) {
        state.preloadEl = document.createElement('video');
        state.preloadEl.preload = 'metadata';
        state.preloadEl.muted = true;
      }
      if (state.preloadEl.getAttribute('src') !== src) state.preloadEl.src = src;
    }
    function queueBufferHint() {
      clearTimeout(state.bufferTimer);
      state.bufferTimer = setTimeout(() => { playerBuffer.hidden = false; }, 450);
    }
    function clearBufferHint() {
      clearTimeout(state.bufferTimer);
      playerBuffer.hidden = true;
    }
    function setPausedUI(paused) {
      state.playing = !paused;
      miniToggle.textContent = paused ? '▶' : '⏸';
      // Persistent centered ▶ while paused: instant, unmissable status feedback.
      playerFlash.classList.toggle('showing', paused);
    }
    function showPlayerFallback(item, message) {
      const thumb = thumbnailFor(item);
      setPausedUI(true);
      playerFlash.classList.remove('showing');
      miniSound.hidden = true;
      clearBufferHint();
      miniThumb.innerHTML = `
        <div class="player-fallback">
          ${thumb ? `<img src="${escapeHtml(thumb)}" alt="" onerror="this.remove()" />` : ''}
          <p>${escapeHtml(message)}</p>
          ${item.url ? `<a href="${escapeHtml(item.url)}" target="_blank" rel="noopener">Open original reel ↗</a>` : ''}
        </div>`;
    }
    function updateMiniTime() {
      const video = document.getElementById('miniVideo');
      if (!video) return;
      const duration = Number.isFinite(video.duration) && video.duration > 0 ? video.duration : 0;
      miniTime.textContent = `${fmtTime(video.currentTime)} / ${fmtTime(duration)}`;
      miniProgress.style.width = duration ? `${Math.min(100, (video.currentTime / duration) * 100)}%` : '0%';
    }
    function toggleMini() {
      const video = document.getElementById('miniVideo');
      if (!video) return;
      if (state.playing) video.pause();
      else video.play().catch(() => {});
      setPausedUI(state.playing);
    }
    function toggleMiniSound() {
      const video = document.getElementById('miniVideo');
      if (!video) return;
      video.muted = !video.muted;
      miniSound.hidden = false;
      miniSound.textContent = video.muted ? '🔇' : '🔊';
      state.soundOn = !video.muted;
      localStorage.setItem('clipnest_sound', state.soundOn ? '1' : '0');
    }
    function seekFromEvent(event) {
      const video = document.getElementById('miniVideo');
      if (!video || !Number.isFinite(video.duration) || video.duration <= 0) return;
      const rect = playerScrub.getBoundingClientRect();
      const pct = Math.min(1, Math.max(0, (event.clientX - rect.left) / rect.width));
      video.currentTime = pct * video.duration;
      updateMiniTime();
    }
    function closeMini() {
      miniPlayer.classList.remove('visible');
      const video = document.getElementById('miniVideo');
      if (video) video.pause();
      miniThumb.innerHTML = '';
      state.miniItem = null;
      state.miniList = [];
      state.stageTouch = null;
      clearBufferHint();
      playerFlash.classList.remove('showing');
      miniProgress.style.width = '0%';
      closeActionSheet();
    }
    function openActionSheet(item, index, list) {
      const target = item || state.miniItem;
      if (!target) return;
      state.miniItem = target;
      state.sheetIndex = Number.isFinite(index) ? index : state.miniIndex;
      state.sheetList = Array.isArray(list) && list.length ? list : (state.miniList.length ? state.miniList : [target]);
      openSheetForItem(target);
    }
    function openSheetForItem(item) {
      const media = mediaFor(item);
      actionSheet.innerHTML = `
        <div id="sheetMedia" class="sheet-media">
          ${/\\.mp4($|[?#])/i.test(media) ? `<video src="${escapeHtml(media)}#t=0.1" muted playsinline preload="metadata"></video>` : `<img src="${escapeHtml(media)}" alt="" onerror="this.remove()" />`}
          <span class="sheet-play">▶</span>
          <button id="sheetClose" class="sheet-close" type="button" aria-label="Close actions">✕</button>
        </div>
        <div class="sheet-body">
          <div class="sheet-handle"></div>
          <div class="sheet-title-row"><h2 class="sheet-title">${escapeHtml(item.name)}</h2><span class="type-badge">${videoFor(item) ? 'Video' : 'Saved'}</span></div>
          <div class="quick-actions">
            <button id="shareItem" class="quick-action" type="button"><span>⇧</span>Share</button>
            <button id="copyLinkItem" class="quick-action" type="button"><span>⧉</span>Copy Link</button>
            <a class="quick-action" href="${escapeHtml(item.url || '#')}" target="_blank" rel="noopener"><span>↗</span>Open</a>
          </div>
          <div class="sheet-list">
            ${state.session?.authenticated && item.reel_id ? '<button id="retryItem" class="sheet-row action" type="button"><span>Retry Processing</span><span>›</span></button>' : ''}
            <button id="deleteItem" class="sheet-row danger" type="button"><span>Delete Item</span><span>›</span></button>
          </div>
        </div>`;
      sheetBackdrop.classList.add('visible');
      actionSheet.classList.add('visible');
      document.getElementById('sheetClose').addEventListener('click', (event) => {
        event.stopPropagation();
        closeActionSheet();
      });
      document.getElementById('sheetMedia').addEventListener('click', playFromSheet);
      document.getElementById('deleteItem').addEventListener('click', deleteCurrentItem);
      document.getElementById('retryItem')?.addEventListener('click', retryCurrentItem);
      document.getElementById('shareItem').addEventListener('click', (event) => {
        const link = item.url || window.location.href;
        if (navigator.share) { navigator.share({ title: item.name, url: link }).catch(() => {}); return; }
        // No native share sheet (e.g. desktop): fall back to copying the link.
        copyItemLink(link, event.currentTarget, 'Share');
      });
      document.getElementById('copyLinkItem').addEventListener('click', (event) => {
        copyItemLink(item.url, event.currentTarget, 'Copy Link');
      });
    }
    function setQuickActionLabel(button, text) {
      for (const node of button.childNodes) {
        if (node.nodeType === Node.TEXT_NODE) { node.textContent = text; return; }
      }
    }
    function copyItemLink(url, button, restoreLabel) {
      const flash = (text) => {
        if (!button) return;
        setQuickActionLabel(button, text);
        setTimeout(() => setQuickActionLabel(button, restoreLabel), 1200);
      };
      if (!url) { flash('No link'); return; }
      const done = () => flash('Copied');
      if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(url).then(done).catch(() => legacyCopy(url, done, () => flash('Copy failed')));
      } else {
        legacyCopy(url, done, () => flash('Copy failed'));
      }
    }
    function legacyCopy(text, onOk, onErr) {
      try {
        const ta = document.createElement('textarea');
        ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
        document.body.appendChild(ta); ta.select();
        const ok = document.execCommand('copy');
        ta.remove();
        ok ? onOk() : onErr();
      } catch (_) { onErr(); }
    }
    function playFromSheet() {
      const item = state.miniItem;
      if (!item) return;
      closeActionSheet();
      // If this reel is already open in the player behind the sheet, just reveal it.
      if (miniPlayer.classList.contains('visible') && state.miniList[state.miniIndex] === item) return;
      openMiniPlayer(item, state.sheetIndex, state.sheetList);
    }
    function closeActionSheet() {
      sheetBackdrop.classList.remove('visible');
      actionSheet.classList.remove('visible');
    }
    async function retryCurrentItem() {
      const item = state.miniItem;
      if (!item?.reel_id) {
        window.alert('This item is missing a backend reel id, so it cannot be retried.');
        return;
      }
      const button = document.getElementById('retryItem');
      if (button) { button.disabled = true; button.firstElementChild.textContent = 'Requeuing…'; }
      try {
        const response = await fetch(`/reels/${encodeURIComponent(item.reel_id)}/retry`, { method: 'POST', credentials: 'same-origin' });
        if (!response.ok) throw new Error('Retry failed');
        window.alert('Reel requeued. It will be reprocessed and refiled in the next few minutes.');
        closeMini();
        loadData();
      } catch (error) {
        window.alert('Could not requeue this reel. Please try again.');
        if (button) { button.disabled = false; button.firstElementChild.textContent = 'Retry Processing'; }
      }
    }
    async function deleteCurrentItem() {
      const item = state.miniItem;
      if (!item?.reel_id) {
        window.alert('This item is missing a backend reel id, so it cannot be deleted yet.');
        return;
      }
      const confirmed = window.confirm(`Delete "${item.name}" from your library?`);
      if (!confirmed) return;
      const response = await fetch(`/reels/${encodeURIComponent(item.reel_id)}`, { method: 'DELETE' });
      if (!response.ok) {
        window.alert('Delete failed. Please try again.');
        return;
      }
      removeReelFromState(item.reel_id);
      closeMini();
      render();
    }
    function removeReelFromState(reelId) {
      state.data = state.data.map((list) => ({ ...list, items: (list.items || []).filter((item) => item.reel_id !== reelId) }));
    }
    function setNav(screen) {
      // Tapping Home always returns to a clean browse: drop any active search
      // query and category filter so the tab acts as a "reset to top".
      if (screen === 'library') {
        state.magicQuery = '';
        state.chip = 'All';
        state.deepSearch = { query: '', loading: false, error: '', results: [] };
      }
      state.screen = screen;
      if (screen !== 'list') state.currentListId = '';
      state.notifOpen = false;
      closeActionSheet();
      render();
      if (screen === 'library') window.scrollTo({ top: 0, behavior: 'instant' });
    }
    function render() {
      libraryNav.classList.toggle('active', state.screen === 'library' || state.screen === 'list');
      profileNav.classList.toggle('active', state.screen === 'profile');
      foldersNav.classList.toggle('active', state.screen === 'folders');
      if (state.screen === 'profile') renderProfile();
      else if (state.screen === 'list') renderListScreen();
      else if (state.screen === 'folders') renderFolders();
      else renderLibrary();
    }
    async function loadData() {
      state.loading = true;
      render();
      try {
        const [libraryRes, dashboardRes, jobsRes, diagnosticsRes, sessionRes] = await Promise.all([
          fetch(`/library?user_id=${encodeURIComponent(USER_ID)}`),
          fetch(`/dashboard?user_id=${encodeURIComponent(USER_ID)}`),
          fetch(`/jobs?user_id=${encodeURIComponent(USER_ID)}&limit=50`),
          fetch(`/diagnostics/reels?user_id=${encodeURIComponent(USER_ID)}&limit=12`),
          fetch('/auth/session', { credentials: 'same-origin' })
        ]);
        const library = await libraryRes.json();
        state.data = normalizeCollections(library.personalized?.length ? library.personalized : library.standard || []);
        state.dashboard = await dashboardRes.json();
        state.jobs = await jobsRes.json();
        state.diagnostics = await diagnosticsRes.json();
        state.session = await sessionRes.json();
        if (state.session?.instagram_connected) state.igLink = null;
      } catch (error) {
        state.data = [];
        state.diagnostics = [];
      }
      state.loading = false;
      scheduleStatusPolling();
      render();
    }
    function scheduleStatusPolling() {
      clearTimeout(state.pollTimer);
      const interval = activeJobCount() > 0 || Number(state.dashboard.pending_url_count || 0) > 0 ? 8000 : 25000;
      state.pollTimer = setTimeout(loadData, interval);
    }
    function normalizeCollections(collections) {
      return (collections || []).map((list, index) => ({
        ...list,
        list_id: `${index}-${list.parent_title || ''}-${list.list_title || ''}`,
        items: (list.items || []).map((item) => ({ ...item }))
      }));
    }
    libraryNav.addEventListener('click', () => setNav('library'));
    profileNav.addEventListener('click', () => setNav('profile'));
    foldersNav.addEventListener('click', () => { state.folderDetail = null; if (!state.foldersLoaded) loadFolders(); setNav('folders'); });
    miniToggle.addEventListener('click', toggleMini);
    miniMore.addEventListener('click', () => openActionSheet());
    miniClose.addEventListener('click', closeMini);
    miniSound.addEventListener('click', toggleMiniSound);
    // Stage gestures: quick tap = pause/play, vertical swipe = next/previous reel.
    playerStage.addEventListener('pointerdown', (event) => {
      if (event.target.closest('.player-fallback a')) return;
      state.stageTouch = { x: event.clientX, y: event.clientY, t: Date.now() };
    });
    playerStage.addEventListener('pointerup', (event) => {
      const start = state.stageTouch;
      state.stageTouch = null;
      if (!start || event.target.closest('.player-fallback a')) return;
      const dx = event.clientX - start.x;
      const dy = event.clientY - start.y;
      if (Math.abs(dy) > 60 && Math.abs(dy) > Math.abs(dx)) {
        stepReel(dy < 0 ? 1 : -1);
        return;
      }
      if (Math.abs(dx) < 12 && Math.abs(dy) < 12 && Date.now() - start.t < 400) toggleMini();
    });
    playerStage.addEventListener('pointercancel', () => { state.stageTouch = null; });
    // Progress bar scrubbing (tap or drag to seek).
    playerScrub.addEventListener('pointerdown', (event) => {
      state.scrubbing = true;
      playerScrub.classList.add('active');
      playerScrub.setPointerCapture(event.pointerId);
      seekFromEvent(event);
    });
    playerScrub.addEventListener('pointermove', (event) => {
      if (state.scrubbing) seekFromEvent(event);
    });
    ['pointerup', 'pointercancel'].forEach((type) => playerScrub.addEventListener(type, () => {
      state.scrubbing = false;
      playerScrub.classList.remove('active');
    }));
    document.addEventListener('keydown', (event) => {
      if (!miniPlayer.classList.contains('visible')) return;
      if (event.key === ' ') { event.preventDefault(); toggleMini(); }
      else if (event.key === 'Escape') closeMini();
      else if (event.key === 'ArrowDown') { event.preventDefault(); stepReel(1); }
      else if (event.key === 'ArrowUp') { event.preventDefault(); stepReel(-1); }
      else if (event.key.toLowerCase() === 'm') toggleMiniSound();
    });
    sheetBackdrop.addEventListener('click', closeActionSheet);
    loadData();
  </script>
</body>
</html>"""
    return html.replace("__USER_ID__", safe_user_id)
