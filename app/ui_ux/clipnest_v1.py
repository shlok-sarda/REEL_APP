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
    .ph-emoji {
      display:grid;
      place-items:center;
      width:100%;
      height:100%;
      font-size:1.6em;
      opacity:.9;
    }
    .m-thumb .ph-emoji, .recent-thumb .ph-emoji { font-size:2.6em; }
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
    .mini-player {
      position:fixed;
      left:50%;
      bottom:calc(76px + var(--safe-bottom));
      z-index:40;
      width:min(398px, calc(100% - 28px));
      transform:translate(-50%, calc(100% + 120px));
      border:1px solid var(--line);
      border-radius:20px;
      background:#141417;
      overflow:hidden;
      opacity:0;
      pointer-events:none;
      transition:transform 200ms cubic-bezier(.32,.72,.35,1), opacity 200ms ease;
      box-shadow:0 18px 50px rgba(0,0,0,.55);
    }
    .mini-player.visible {
      transform:translate(-50%, 0);
      opacity:1;
      pointer-events:auto;
    }
    .mini-body {
      display:grid;
      grid-template-columns:54px minmax(0,1fr) 44px 34px 34px;
      align-items:center;
      gap:10px;
      padding:11px;
    }
    .mini-thumb {
      width:54px;
      height:54px;
      border-radius:12px;
      overflow:hidden;
      background:var(--soft);
    }
    .mini-thumb img, .mini-thumb video { width:100%; height:100%; object-fit:cover; display:block; }
    .mini-title {
      margin:0;
      font-size:.88rem;
      line-height:1.2;
      font-weight:700;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .mini-time { margin-top:4px; color:var(--muted); font-size:.7rem; font-weight:650; }
    .mini-action {
      min-width:34px;
      height:34px;
      display:grid;
      place-items:center;
      border-radius:50%;
      color:var(--text);
      font-size:.82rem;
      font-weight:650;
    }
    .progress-track { height:3px; background:#232327; }
    .progress-fill { width:0%; height:100%; background:#fff; }

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
    .sheet-media { position:relative; height:200px; background:#0f0f11; }
    .sheet-media img, .sheet-media video { width:100%; height:100%; object-fit:cover; display:block; opacity:.92; }
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
    .quick-actions { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-bottom:16px; }
    .quick-action { display:grid; place-items:center; gap:6px; color:var(--muted); font-size:.68rem; font-weight:650; }
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
    <section id="miniPlayer" class="mini-player" aria-label="Mini player">
      <div class="mini-body">
        <div id="miniThumb" class="mini-thumb"></div>
        <div>
          <p id="miniTitle" class="mini-title"></p>
          <div id="miniTime" class="mini-time">0:00 / 0:12</div>
        </div>
        <button id="miniToggle" class="mini-action" type="button" aria-label="Play or pause">Pause</button>
        <button id="miniMore" class="mini-action" type="button" aria-label="More actions">···</button>
        <button id="miniClose" class="mini-action" type="button" aria-label="Close mini player">✕</button>
      </div>
      <div class="progress-track"><div id="miniProgress" class="progress-fill"></div></div>
    </section>
    <div id="sheetBackdrop" class="sheet-backdrop"></div>
    <section id="actionSheet" class="action-sheet" aria-label="Item actions"></section>
    <nav class="bottom-nav" aria-label="Primary">
      <button id="libraryNav" class="nav-button active" type="button">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10.5 12 3l9 7.5"/><path d="M5 9.5V21h14V9.5"/></svg>
        <span>Home</span>
      </button>
      <button id="searchNav" class="nav-button" type="button">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
        <span>Search</span>
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
      miniItem: null,
      miniIndex: 0,
      playing: false,
      progressTimer: null,
      pollTimer: null,
      progress: 0,
      session: null,
      igLink: null,
      loading: true
    };
    const app = document.getElementById('app');
    const searchNav = document.getElementById('searchNav');
    const libraryNav = document.getElementById('libraryNav');
    const profileNav = document.getElementById('profileNav');
    const miniPlayer = document.getElementById('miniPlayer');
    const miniThumb = document.getElementById('miniThumb');
    const miniTitle = document.getElementById('miniTitle');
    const miniTime = document.getElementById('miniTime');
    const miniProgress = document.getElementById('miniProgress');
    const miniToggle = document.getElementById('miniToggle');
    const miniMore = document.getElementById('miniMore');
    const miniClose = document.getElementById('miniClose');
    const actionSheet = document.getElementById('actionSheet');
    const sheetBackdrop = document.getElementById('sheetBackdrop');

    const SEARCH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>';
    const CHEV_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>';
    const BACK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 6-6 6 6 6"/></svg>';
    const ARROW_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>';
    const REFRESH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 1 0-2.3 6.3"/><path d="M20 5v6h-6"/></svg>';

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
      const json = JSON.stringify(job, null, 2);
      return `<article class="job-card">
        <div class="job-head">
          <h3 class="job-title">${escapeHtml(jobTitle(job))}</h3>
          <span class="status-pill ${escapeHtml(status)}">${escapeHtml(status)}</span>
        </div>
        <p class="job-meta">${escapeHtml(job.job_type || 'processing')} · ${escapeHtml(formatTime(time) || 'time unavailable')} · attempts ${escapeHtml(job.attempts ?? 0)}</p>
        ${url ? `<p class="job-meta">${escapeHtml(url)}</p>` : ''}
        ${job.error_message ? `<p class="job-meta">${escapeHtml(job.error_message)}</p>` : ''}
        <details class="json-box"><summary>View job JSON</summary><pre>${escapeHtml(json)}</pre></details>
      </article>`;
    }
    function recentDiagnostics() {
      return Array.isArray(state.diagnostics) ? state.diagnostics.slice(0, 8) : [];
    }
    function renderReelDiagnosticCard(reel) {
      const status = String(reel.status || 'unknown').toLowerCase();
      const json = JSON.stringify(reel, null, 2);
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
        <details class="json-box"><summary>View stored extraction JSON</summary><pre>${escapeHtml(json)}</pre></details>
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
        || (state.itemChip === 'Products' && hasProduct(item))
        || (state.itemChip === 'Saved')
        || (state.itemChip === 'Video' && videoFor(item));
      if (!chipOk) return false;
      if (!q) return true;
      return hasText(`${item.name} ${item.product_name || ''} ${item.summary || ''}`, q);
    }
    function hasProduct(item) {
      return String(item.contains_product || '').toLowerCase() === 'yes' || Boolean(item.best_buy_link || item.product_name);
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
    function mediaBox(item, className, loading = 'lazy', inner = '') {
      const src = mediaFor(item);
      const label = item.name || item.list_title || 'reel';
      const emoji = emojiFor(`${item.parent_title || ''} ${item.list_title || ''} ${label}`);
      const fallback = `<span class="ph-emoji">${emoji}</span>`;
      const media = src ? renderMedia(item, loading) : fallback;
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
    function durationFor(item, index) {
      const seconds = 7 + ((index * 5 + String(item.name || '').length) % 16);
      return `0:${String(seconds).padStart(2, '0')}`;
    }
    function chips() {
      return ['All', ...Array.from(new Set(sortedCollections().map((list) => list.parent_title || list.list_title))).filter(Boolean)];
    }
    function categoryTiles() {
      const groups = new Map();
      for (const list of sortedCollections()) {
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
    function recentItems(limit = 10) {
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
      const lists = sortedCollections().filter(listMatches);
      const tiles = categoryTiles();
      const recents = recentItems(10);
      app.innerHTML = `
        <div class="home-head">
          <h1 class="greeting">${escapeHtml(greeting())}</h1>
          <div class="icon-row">
            <button class="icon-button" type="button" aria-label="Refresh" id="refreshButton">${REFRESH_SVG}</button>
          </div>
        </div>
        ${renderSearchBox('Search saves...', state.query, 'librarySearch')}
        ${renderSyncPill(true)}
        ${tiles.length ? `<div class="cat-rail" aria-label="Categories">${tiles.map(([name, count]) => `
          <button class="cat-tile ${state.chip === name ? 'active' : ''}" type="button" data-chip-kind="library" data-chip="${escapeHtml(name)}">
            <span class="cat-icon">${emojiFor(name)}<span class="cat-count">${count}</span></span>
            <span class="cat-label">${escapeHtml(prettyTitle(name))}</span>
          </button>`).join('')}</div>` : ''}
        ${recents.length && !state.query.trim() && state.chip === 'All' ? `
          <div class="section-head"><h2 class="section-title">Recently saved <span class="chev">›</span></h2></div>
          <div class="recent-rail">${recents.map((item, index) => `
            <button class="recent-card" type="button" data-recent-item="${index}">
              ${mediaBox(item, 'recent-thumb', index < 4 ? 'eager' : 'lazy', `<span class="mini-badge">${hasProduct(item) ? '<span class="badge-dot">🛒</span>' : ''}</span>`)}
              <p class="recent-source">${escapeHtml(sourceFor(item))}</p>
              <p class="recent-title">${escapeHtml(item.name)}</p>
            </button>`).join('')}</div>` : ''}
        <div class="section-head">
          <h2 class="section-title">Library <span class="chev">›</span></h2>
          <span class="section-side">${lists.length} folders</span>
        </div>
        ${state.loading ? '<div class="empty">Loading your library...</div>' : ''}
        ${!state.loading && lists.length ? `<section class="lib-list">${lists.map(renderLibRow).join('')}</section>` : ''}
        ${!state.loading && !lists.length ? '<div class="empty">Nothing here yet. Save a reel to get started.</div>' : ''}
      `;
      document.getElementById('librarySearch')?.addEventListener('input', (event) => {
        state.query = event.target.value;
        render();
        const input = document.getElementById('librarySearch');
        if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
      });
      document.getElementById('refreshButton')?.addEventListener('click', loadData);
      bindChips();
      const recentsData = recentItems(10);
      app.querySelectorAll('[data-recent-item]').forEach((button) => {
        button.addEventListener('click', () => openMiniPlayer(recentsData[Number(button.dataset.recentItem)], Number(button.dataset.recentItem)));
      });
      app.querySelectorAll('[data-open-list]').forEach((button) => {
        button.addEventListener('click', () => {
          state.currentListId = button.dataset.openList;
          state.itemQuery = '';
          state.itemChip = 'All';
          state.screen = 'list';
          window.scrollTo({ top: 0, behavior: 'instant' });
          render();
        });
      });
    }
    function renderLibRow(list) {
      const cover = coverItem(list);
      return `<button class="lib-row" type="button" data-open-list="${escapeHtml(list.list_id)}" aria-label="Open ${escapeHtml(list.list_title)}">
        ${mediaBox({ ...cover, name: cover.name || list.list_title, parent_title: list.parent_title, list_title: list.list_title }, 'lib-icon')}
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
      const items = list.items.filter(itemMatches);
      app.innerHTML = `
        <div class="list-heading">
          <button id="backToLibrary" class="back-button" type="button" aria-label="Back to library">${BACK_SVG}</button>
          <div class="list-title-block"><h1>${escapeHtml(prettyTitle(list.list_title))}</h1><p class="count-text">${items.length} ${items.length === 1 ? 'item' : 'items'}</p></div>
          <div class="icon-row"></div>
        </div>
        ${renderSearchBox(`Search in ${prettyTitle(list.list_title)}...`, state.itemQuery, 'itemSearch')}
        ${renderChips(['All', 'Video', 'Products', 'Saved'], state.itemChip, 'item')}
        ${items.length ? `<section class="masonry">${items.map(renderItemCard).join('')}</section>` : '<div class="empty">No items found</div>'}
      `;
      document.getElementById('backToLibrary').addEventListener('click', () => {
        state.screen = 'library';
        state.currentListId = '';
        render();
      });
      document.getElementById('itemSearch').addEventListener('input', (event) => {
        state.itemQuery = event.target.value;
        render();
        const input = document.getElementById('itemSearch');
        if (input) { input.focus(); input.setSelectionRange(input.value.length, input.value.length); }
      });
      bindChips();
      app.querySelectorAll('[data-open-item]').forEach((button) => {
        button.addEventListener('click', () => openMiniPlayer(items[Number(button.dataset.openItem)], Number(button.dataset.openItem)));
      });
      app.querySelectorAll('[data-item-menu]').forEach((el) => {
        el.addEventListener('click', (event) => {
          event.stopPropagation();
          state.miniItem = items[Number(el.dataset.itemMenu)];
          openActionSheet();
        });
      });
    }
    function renderItemCard(item, index) {
      const productText = [item.product_brand, item.product_name || item.product_type].filter(Boolean).join(' ');
      return `<article class="m-card">
        <button style="width:100%;text-align:left" type="button" data-open-item="${index}" aria-label="Preview ${escapeHtml(item.name)}">
          ${mediaBox(item, 'm-thumb', 'lazy', `<span class="m-badges">${videoFor(item) ? '<span class="badge-dot">▶</span>' : ''}${hasProduct(item) ? '<span class="badge-dot">🛒</span>' : ''}</span>`)}
          <span class="m-title-row"><p class="m-title">${escapeHtml(item.name)}</p><span class="m-kebab" data-item-menu="${index}">···</span></span>
          ${item.summary ? `<p class="m-summary">${escapeHtml(item.summary)}</p>` : ''}
          ${productText ? `<p class="m-summary">🛒 ${escapeHtml(productText)}</p>` : ''}
        </button>
        ${renderBuyLinks(item)}
      </article>`;
    }
    function renderBuyLinks(item) {
      const links = [
        ['Best', item.best_buy_link],
        ['Amazon', item.amazon_link],
        ['Flipkart', item.flipkart_link],
        ['Nykaa', item.nykaa_link],
      ].filter((entry) => entry[1]);
      if (!links.length) return '';
      return `<div class="buy-row">${links.map(([label, href]) => `<a class="buy-link" href="${escapeHtml(href)}" target="_blank" rel="noopener">${escapeHtml(label)}</a>`).join('')}</div>`;
    }

    /* ---------- SEARCH ---------- */
    function searchTabResults() {
      const q = state.magicQuery.trim();
      const allItems = flatItems();
      return q
        ? allItems.filter((item) => hasText(`${item.name} ${item.summary || ''} ${item.product_name || ''} ${item.product_brand || ''} ${item.list_title || ''} ${item.parent_title || ''}`, q)).slice(0, 24)
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
        product_name: (result.product_names || [])[0] || '',
        product_brand: (result.brands || [])[0] || '',
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
      const resultList = document.getElementById('magicResults');
      if (!resultList) return;
      resultList.innerHTML = `
        ${q && state.deepSearch.loading && state.deepSearch.query === q ? '<div class="empty">Searching captions, products, visuals, and transcripts...</div>' : ''}
        ${q && state.deepSearch.error && !results.length ? `<div class="empty">${escapeHtml(state.deepSearch.error)}</div>` : ''}
        ${q && !state.deepSearch.loading && !results.length ? '<div class="empty">No matches yet. Try a broader word.</div>' : ''}
        ${results.map((item, index) => `<button class="result-card" type="button" data-search-item="${index}">
          ${mediaBox(item, 'result-thumb')}
          <div><h3>${escapeHtml(item.name)}</h3><p>${escapeHtml(item.summary || item.list_title || '')}</p></div>
        </button>`).join('')}
      `;
      resultList.querySelectorAll('[data-search-item]').forEach((button) => {
        button.addEventListener('click', () => openMiniPlayer(results[Number(button.dataset.searchItem)], Number(button.dataset.searchItem)));
      });
    }
    function renderSearchTab() {
      app.innerHTML = `
        <section class="search-stage">
          <div class="magic-head">
            <h1 class="magic-title">Find anything<br/>you saved.</h1>
            <p class="magic-copy">Search what was said, shown, or written in your reels — products, places, ideas, captions.</p>
          </div>
          <label class="magic-bar">
            <input id="magicInput" value="${escapeHtml(state.magicQuery)}" placeholder="What are you trying to remember?" autocomplete="off" />
            <button id="magicSubmit" class="magic-submit" type="button" aria-label="Search">${ARROW_SVG}</button>
          </label>
          <div id="magicResults" class="result-list"></div>
        </section>
      `;
      const input = document.getElementById('magicInput');
      input?.focus();
      if (input) input.setSelectionRange(input.value.length, input.value.length);
      input?.addEventListener('input', (event) => {
        state.magicQuery = event.target.value;
        scheduleDeepSearch();
      });
      document.getElementById('magicSubmit')?.addEventListener('click', scheduleDeepSearch);
      if (state.magicQuery.trim() && state.deepSearch.query !== state.magicQuery.trim()) scheduleDeepSearch();
      else renderSearchResults();
    }

    /* ---------- PROFILE ---------- */
    function renderProfile() {
      const totalItems = sortedCollections().reduce((sum, list) => sum + list.real_count, 0);
      const jobs = recentJobs();
      const diagnostics = recentDiagnostics();
      const dashboardJson = JSON.stringify(state.dashboard || {}, null, 2);
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
        <section class="set-section">
          <h2 class="set-title">Dashboard</h2>
          <details class="json-box"><summary>View dashboard JSON</summary><pre>${escapeHtml(dashboardJson)}</pre></details>
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
    function openMiniPlayer(item, index) {
      if (!item) return;
      state.miniItem = item;
      state.miniIndex = index || 0;
      state.playing = true;
      state.progress = 0;
      const thumb = thumbnailFor(item);
      const video = videoFor(item);
      miniThumb.innerHTML = video
        ? `<video id="miniVideo" src="${escapeHtml(video)}" ${thumb ? `poster="${escapeHtml(thumb)}"` : ''} muted playsinline autoplay loop></video>`
        : `<img src="${escapeHtml(thumb)}" alt="" onerror="this.remove()" />`;
      miniTitle.textContent = item.name || 'Untitled item';
      miniTime.textContent = `0:00 / ${durationFor(item, state.miniIndex)}`;
      miniToggle.textContent = 'Pause';
      miniPlayer.classList.add('visible');
      startProgress();
    }
    function startProgress() {
      clearInterval(state.progressTimer);
      state.progressTimer = setInterval(() => {
        if (!state.playing) return;
        const video = document.getElementById('miniVideo');
        if (video && Number.isFinite(video.duration) && video.duration > 0) {
          state.progress = Math.min(100, (video.currentTime / video.duration) * 100);
        } else {
          state.progress = (state.progress + 1.8) % 100;
        }
        miniProgress.style.width = `${state.progress}%`;
      }, 350);
    }
    function toggleMini() {
      const video = document.getElementById('miniVideo');
      state.playing = !state.playing;
      if (video) {
        if (state.playing) video.play().catch(() => {});
        else video.pause();
      }
      miniToggle.textContent = state.playing ? 'Pause' : 'Play';
    }
    function closeMini() {
      miniPlayer.classList.remove('visible');
      clearInterval(state.progressTimer);
      const video = document.getElementById('miniVideo');
      if (video) video.pause();
      state.miniItem = null;
      state.progress = 0;
      miniProgress.style.width = '0%';
      closeActionSheet();
    }
    function openActionSheet() {
      const item = state.miniItem;
      if (!item) return;
      const media = mediaFor(item);
      const productAction = hasProduct(item)
        ? `<a class="sheet-row" href="${escapeHtml(item.best_buy_link || item.amazon_link || '#')}" target="_blank" rel="noopener"><span>Buy Link <span class="new">New</span></span><span>›</span></a>`
        : '';
      actionSheet.innerHTML = `
        <div class="sheet-media">
          ${/\\.mp4($|[?#])/i.test(media) ? `<video src="${escapeHtml(media)}#t=0.1" muted playsinline preload="metadata"></video>` : `<img src="${escapeHtml(media)}" alt="" onerror="this.remove()" />`}
          <button id="sheetClose" class="sheet-close" type="button" aria-label="Close actions">✕</button>
        </div>
        <div class="sheet-body">
          <div class="sheet-handle"></div>
          <div class="sheet-title-row"><h2 class="sheet-title">${escapeHtml(item.name)}</h2><span class="type-badge">${hasProduct(item) ? 'Product' : 'Video'}</span></div>
          <div class="quick-actions">
            <button class="quick-action" type="button"><span>♡</span>Save</button>
            <button id="shareItem" class="quick-action" type="button"><span>⇧</span>Share</button>
            <button class="quick-action" type="button"><span>☷</span>Add To List</button>
            <button class="quick-action" type="button"><span>···</span>More</button>
          </div>
          <div class="sheet-list">
            <a class="sheet-row" href="${escapeHtml(item.url || '#')}" target="_blank" rel="noopener"><span>Open Original Reel</span><span>›</span></a>
            ${productAction}
            ${state.session?.authenticated && item.reel_id ? '<button id="retryItem" class="sheet-row action" type="button"><span>Retry Processing</span><span>›</span></button>' : ''}
            <button class="sheet-row" type="button"><span>Notes</span><span>›</span></button>
            <button id="deleteItem" class="sheet-row danger" type="button"><span>Delete Item</span><span>›</span></button>
          </div>
        </div>`;
      sheetBackdrop.classList.add('visible');
      actionSheet.classList.add('visible');
      document.getElementById('sheetClose').addEventListener('click', closeActionSheet);
      document.getElementById('deleteItem').addEventListener('click', deleteCurrentItem);
      document.getElementById('retryItem')?.addEventListener('click', retryCurrentItem);
      document.getElementById('shareItem').addEventListener('click', () => {
        if (navigator.share) navigator.share({ title: item.name, url: item.url || window.location.href }).catch(() => {});
      });
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
      state.screen = screen;
      if (screen !== 'list') state.currentListId = '';
      closeActionSheet();
      render();
    }
    function render() {
      searchNav.classList.toggle('active', state.screen === 'search');
      libraryNav.classList.toggle('active', state.screen === 'library' || state.screen === 'list');
      profileNav.classList.toggle('active', state.screen === 'profile');
      if (state.screen === 'search') renderSearchTab();
      else if (state.screen === 'profile') renderProfile();
      else if (state.screen === 'list') renderListScreen();
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
    searchNav.addEventListener('click', () => setNav('search'));
    libraryNav.addEventListener('click', () => setNav('library'));
    profileNav.addEventListener('click', () => setNav('profile'));
    miniToggle.addEventListener('click', toggleMini);
    miniMore.addEventListener('click', openActionSheet);
    miniClose.addEventListener('click', closeMini);
    miniPlayer.addEventListener('click', (event) => {
      if (event.target.closest('.mini-action')) return;
      openActionSheet();
    });
    sheetBackdrop.addEventListener('click', closeActionSheet);
    loadData();
  </script>
</body>
</html>"""
    return html.replace("__USER_ID__", safe_user_id)
