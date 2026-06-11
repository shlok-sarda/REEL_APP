def build_clipnest_v1_html(user_id: str) -> str:
    safe_user_id = user_id.replace("\\", "\\\\").replace("'", "\\'")
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <title>MyLife Library</title>
  <style>
    :root {
      color-scheme: light;
      --bg:#fff;
      --text:#111;
      --muted:#777;
      --border:#eee;
      --soft:#f7f7f8;
      --accent:#6c4dff;
      --danger:#ff3b30;
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
      letter-spacing:0;
    }
    body { overflow-x:hidden; }
    button, input, a { font:inherit; -webkit-tap-highlight-color:transparent; }
    button { border:0; background:none; color:inherit; cursor:pointer; }
    .phone-shell {
      width:min(430px, 100%);
      min-height:100vh;
      margin:0 auto;
      background:var(--bg);
      position:relative;
    }
    .screen {
      min-height:100vh;
      padding:calc(18px + var(--safe-top)) 16px calc(96px + var(--safe-bottom));
    }
    .screen.search-mode {
      background:
        linear-gradient(180deg, #07070b 0%, #101018 48%, #050508 100%);
      color:#fff;
      transition:background 160ms ease, color 160ms ease;
    }
    .topbar {
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      margin-bottom:20px;
    }
    .brand-mark {
      width:54px;
      height:54px;
      border-radius:50%;
      display:grid;
      place-items:center;
      background:#000;
      color:#fff;
      font-size:.68rem;
      font-weight:800;
    }
    .icon-row { display:flex; align-items:center; gap:10px; }
    .icon-button, .back-button {
      width:44px;
      height:44px;
      border:1px solid var(--border);
      border-radius:50%;
      display:grid;
      place-items:center;
      background:#fff;
      color:var(--text);
      font-size:1.05rem;
      line-height:1;
    }
    .back-button { width:42px; height:42px; font-size:1.25rem; }
    .page-title {
      margin:0;
      font-size:2rem;
      line-height:1;
      font-weight:900;
    }
    .microcopy {
      margin:8px 0 0;
      color:var(--muted);
      font-size:.88rem;
      line-height:1.35;
      font-weight:600;
    }
    .list-heading {
      display:grid;
      grid-template-columns:42px minmax(0,1fr) auto;
      align-items:center;
      gap:10px;
      margin-bottom:18px;
    }
    .list-title-block h1 {
      margin:0;
      font-size:1.28rem;
      line-height:1.05;
      font-weight:900;
    }
    .count-text {
      margin:3px 0 0;
      color:var(--accent);
      font-size:.78rem;
      font-weight:700;
    }
    .search { position:relative; margin:14px 0 12px; }
    .search input {
      width:100%;
      height:46px;
      border:0;
      border-radius:18px;
      background:var(--soft);
      color:var(--text);
      padding:0 44px;
      outline:none;
      font-size:.92rem;
      font-weight:600;
    }
    .search input::placeholder { color:#9a9a9a; }
    .search span {
      position:absolute;
      left:16px;
      top:50%;
      transform:translateY(-50%);
      color:var(--muted);
      font-size:.95rem;
      pointer-events:none;
    }
    .chips {
      display:flex;
      gap:9px;
      overflow-x:auto;
      padding:2px 0 14px;
      scrollbar-width:none;
    }
    .chips::-webkit-scrollbar { display:none; }
    .chip {
      flex:0 0 auto;
      height:36px;
      border-radius:18px;
      padding:0 17px;
      background:var(--soft);
      color:var(--text);
      font-size:.82rem;
      font-weight:750;
      white-space:nowrap;
    }
    .chip.active { background:var(--accent); color:#fff; }
    .list-grid {
      display:grid;
      grid-template-columns:1fr;
      gap:12px;
    }
    .list-card {
      position:relative;
      min-height:210px;
      overflow:hidden;
      border-radius:10px;
      background:linear-gradient(180deg, #efeff1, #bbb);
      isolation:isolate;
      text-align:left;
    }
    .list-card img, .list-card video {
      position:absolute;
      inset:0;
      width:100%;
      height:100%;
      object-fit:cover;
      transform:scale(1.02);
    }
    .list-card::after {
      content:"";
      position:absolute;
      inset:0;
      background:linear-gradient(180deg, rgba(0,0,0,.02), rgba(0,0,0,.64));
      z-index:1;
    }
    .list-card-content {
      position:absolute;
      left:12px;
      right:12px;
      bottom:12px;
      z-index:2;
      color:#fff;
      display:grid;
      gap:7px;
      text-align:left;
    }
    .list-domain {
      width:max-content;
      max-width:100%;
      min-height:25px;
      border-radius:13px;
      padding:5px 9px;
      background:rgba(255,255,255,.9);
      color:#111;
      font-size:.68rem;
      font-weight:850;
      white-space:nowrap;
      overflow:hidden;
      text-overflow:ellipsis;
    }
    .list-card-title {
      font-size:1.02rem;
      line-height:1.12;
      font-weight:850;
    }
    .list-preview {
      margin:0;
      color:rgba(255,255,255,.84);
      font-size:.78rem;
      line-height:1.32;
      font-weight:650;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .count-badge {
      position:absolute;
      top:10px;
      right:10px;
      z-index:2;
      min-width:27px;
      height:27px;
      padding:0 8px;
      border-radius:14px;
      display:inline-grid;
      place-items:center;
      background:#fff;
      color:#111;
      font-size:.78rem;
      font-weight:850;
    }
    .item-grid {
      display:grid;
      grid-template-columns:1fr;
      gap:12px;
      align-items:start;
    }
    .item-card {
      min-width:0;
      border:1px solid var(--border);
      border-radius:14px;
      background:#fff;
      padding:10px;
      text-align:left;
      box-shadow:0 10px 28px rgba(17,17,17,.05);
    }
    .item-open {
      width:100%;
      display:grid;
      grid-template-columns:96px minmax(0,1fr);
      gap:12px;
      text-align:left;
      align-items:start;
    }
    .thumb-wrap {
      position:relative;
      aspect-ratio:9 / 14;
      overflow:hidden;
      border-radius:8px;
      background:#ececef;
    }
    .thumb-wrap img, .thumb-wrap video {
      width:100%;
      height:100%;
      object-fit:cover;
      display:block;
    }
    .duration {
      position:absolute;
      top:6px;
      right:6px;
      height:20px;
      border-radius:10px;
      padding:0 6px;
      display:inline-flex;
      align-items:center;
      background:rgba(0,0,0,.74);
      color:#fff;
      font-size:.7rem;
      font-weight:800;
    }
    .play-dot {
      position:absolute;
      left:7px;
      bottom:7px;
      width:20px;
      height:20px;
      border-radius:50%;
      display:grid;
      place-items:center;
      background:rgba(0,0,0,.62);
      color:#fff;
      font-size:.64rem;
    }
    .item-title-row {
      display:grid;
      grid-template-columns:minmax(0,1fr) 18px;
      gap:4px;
      margin-top:1px;
    }
    .item-title {
      margin:0;
      min-width:0;
      font-size:.95rem;
      line-height:1.16;
      font-weight:800;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .more-dot { color:var(--muted); font-weight:900; line-height:1; }
    .item-summary {
      margin:7px 0 0;
      color:#555;
      font-size:.78rem;
      line-height:1.34;
      font-weight:600;
      display:-webkit-box;
      -webkit-line-clamp:3;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .item-meta-row {
      display:flex;
      flex-wrap:wrap;
      gap:6px;
      margin-top:9px;
    }
    .item-pill {
      min-height:24px;
      border-radius:12px;
      padding:5px 8px;
      background:var(--soft);
      color:#555;
      font-size:.68rem;
      line-height:1;
      font-weight:850;
      max-width:100%;
      overflow:hidden;
      text-overflow:ellipsis;
      white-space:nowrap;
    }
    .item-pill.product { background:#f0edff; color:#4f34d9; }
    .buy-row {
      display:flex;
      flex-wrap:wrap;
      gap:7px;
      margin:10px 0 0 108px;
    }
    .buy-link {
      min-height:30px;
      border-radius:15px;
      padding:7px 10px;
      background:#111;
      color:#fff;
      text-decoration:none;
      font-size:.72rem;
      line-height:1;
      font-weight:850;
    }
    .bottom-nav {
      position:fixed;
      left:50%;
      bottom:0;
      z-index:30;
      width:min(430px, 100%);
      transform:translateX(-50%);
      display:grid;
      grid-template-columns:repeat(3,1fr);
      border-top:1px solid var(--border);
      background:rgba(255,255,255,.96);
      padding:9px 18px calc(9px + var(--safe-bottom));
    }
    .bottom-nav.search-nav-mode {
      border-top-color:rgba(255,255,255,.12);
      background:rgba(6,6,10,.96);
    }
    .nav-button {
      display:grid;
      gap:3px;
      place-items:center;
      color:var(--muted);
      font-size:.72rem;
      font-weight:700;
    }
    .nav-icon {
      width:24px;
      height:22px;
      display:grid;
      place-items:center;
      font-size:1.08rem;
    }
    .nav-button.active { color:var(--accent); }
    .sync-banner {
      display:grid;
      grid-template-columns:10px minmax(0,1fr) auto;
      gap:11px;
      align-items:center;
      border:1px solid var(--border);
      border-radius:18px;
      background:#fff;
      padding:12px;
      margin:14px 0;
      box-shadow:0 10px 30px rgba(17,17,17,.05);
    }
    .sync-banner.idle { background:var(--soft); box-shadow:none; }
    .sync-dot {
      width:10px;
      height:10px;
      border-radius:50%;
      background:#26b36d;
      box-shadow:0 0 0 5px rgba(38,179,109,.12);
    }
    .sync-banner.active .sync-dot {
      background:var(--accent);
      box-shadow:0 0 0 5px rgba(108,77,255,.14);
      animation:pulse 1.2s ease-in-out infinite;
    }
    .sync-banner.issue .sync-dot {
      background:#d9822b;
      box-shadow:0 0 0 5px rgba(217,130,43,.14);
    }
    @keyframes pulse {
      0%, 100% { transform:scale(1); opacity:1; }
      50% { transform:scale(.72); opacity:.62; }
    }
    .sync-title { margin:0; font-size:.86rem; font-weight:850; line-height:1.2; }
    .sync-copy { margin:3px 0 0; color:var(--muted); font-size:.74rem; line-height:1.3; font-weight:650; }
    .sync-count {
      min-height:28px;
      border-radius:14px;
      padding:7px 10px;
      background:#111;
      color:#fff;
      font-size:.7rem;
      font-weight:850;
      line-height:1;
      white-space:nowrap;
    }
    .profile-panel { display:grid; gap:12px; margin-top:16px; }
    .profile-row {
      min-height:54px;
      border-bottom:1px solid var(--border);
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      font-weight:750;
    }
    .profile-row span { color:var(--muted); font-size:.82rem; font-weight:700; }
    .profile-grid {
      display:grid;
      grid-template-columns:repeat(2, minmax(0,1fr));
      gap:10px;
      margin-top:14px;
    }
    .metric-card {
      border:1px solid var(--border);
      border-radius:16px;
      background:#fff;
      padding:13px;
      box-shadow:0 10px 26px rgba(17,17,17,.04);
    }
    .metric-card span {
      display:block;
      color:var(--muted);
      font-size:.69rem;
      font-weight:800;
      text-transform:uppercase;
    }
    .metric-card b {
      display:block;
      margin-top:7px;
      font-size:1.3rem;
      line-height:1;
      font-weight:900;
    }
    .profile-section-title {
      margin:22px 0 10px;
      font-size:.82rem;
      line-height:1;
      font-weight:900;
      color:#444;
      text-transform:uppercase;
    }
    .job-list { display:grid; gap:10px; }
    .job-card {
      border:1px solid var(--border);
      border-radius:16px;
      background:#fff;
      padding:12px;
      box-shadow:0 10px 26px rgba(17,17,17,.04);
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
      font-weight:850;
      overflow:hidden;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
    }
    .status-pill {
      min-height:24px;
      border-radius:12px;
      padding:5px 8px;
      background:var(--soft);
      color:#444;
      font-size:.66rem;
      line-height:1;
      font-weight:900;
      text-transform:uppercase;
    }
    .status-pill.running, .status-pill.queued, .status-pill.pending { background:#f0edff; color:#4f34d9; }
    .status-pill.completed { background:#eaf8f0; color:#147d49; }
    .status-pill.failed { background:#fff2e5; color:#a85512; }
    .job-meta {
      margin:8px 0 0;
      color:var(--muted);
      font-size:.72rem;
      line-height:1.35;
      font-weight:650;
      word-break:break-word;
    }
    .json-box {
      margin-top:10px;
      border-radius:12px;
      background:#111;
      color:#e8e8e8;
      overflow:hidden;
    }
    .json-box summary {
      cursor:pointer;
      padding:10px 12px;
      font-size:.72rem;
      font-weight:850;
    }
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
    .search-stage {
      min-height:calc(100vh - 130px - var(--safe-bottom));
      display:grid;
      place-items:center;
      padding:24px 0 60px;
    }
    .magic-search {
      width:100%;
      display:grid;
      gap:18px;
      text-align:center;
    }
    .magic-orb {
      width:60px;
      height:60px;
      margin:0 auto;
      border-radius:20px;
      display:grid;
      place-items:center;
      color:#fff;
      background:
        linear-gradient(135deg, rgba(255,255,255,.18), rgba(255,255,255,0)),
        linear-gradient(135deg, #12121a, #6c4dff 68%, #e5dcff);
      box-shadow:0 18px 46px rgba(108,77,255,.34), inset 0 1px 0 rgba(255,255,255,.28);
      font-weight:900;
    }
    .magic-title {
      margin:0;
      font-size:1.72rem;
      line-height:1.05;
      font-weight:900;
    }
    .magic-copy {
      margin:0 auto;
      max-width:19rem;
      color:rgba(255,255,255,.64);
      font-size:.9rem;
      line-height:1.45;
      font-weight:600;
    }
    .magic-bar {
      position:relative;
      margin-top:4px;
    }
    .magic-bar::before {
      content:"";
      position:absolute;
      inset:-1px;
      border-radius:26px;
      background:linear-gradient(90deg, rgba(108,77,255,.95), rgba(255,255,255,.4), rgba(128,104,255,.82));
      opacity:.92;
      z-index:0;
    }
    .magic-bar::after {
      content:"";
      position:absolute;
      inset:2px;
      border-radius:23px;
      background:#0d0d14;
      z-index:0;
    }
    .magic-bar input {
      position:relative;
      z-index:1;
      width:100%;
      height:58px;
      border:1px solid rgba(255,255,255,.12);
      border-radius:24px;
      background:rgba(12,12,20,.94);
      color:#fff;
      outline:none;
      padding:0 54px 0 18px;
      font-size:1rem;
      font-weight:750;
      box-shadow:0 18px 42px rgba(0,0,0,.36), inset 0 1px 0 rgba(255,255,255,.08);
    }
    .magic-bar input::placeholder {
      color:rgba(255,255,255,.48);
    }
    .magic-bar input:focus {
      border-color:rgba(255,255,255,.22);
    }
    .magic-submit {
      position:absolute;
      z-index:2;
      right:8px;
      top:50%;
      transform:translateY(-50%);
      width:42px;
      height:42px;
      border-radius:18px;
      display:grid;
      place-items:center;
      background:var(--accent);
      color:#fff;
      font-weight:900;
      box-shadow:0 10px 26px rgba(108,77,255,.36);
    }
    .result-list { display:grid; gap:10px; width:100%; margin-top:18px; }
    .result-card {
      display:grid;
      grid-template-columns:58px minmax(0,1fr);
      gap:12px;
      align-items:center;
      padding:9px;
      border:1px solid rgba(255,255,255,.1);
      border-radius:16px;
      background:rgba(255,255,255,.07);
      color:#fff;
      text-align:left;
      backdrop-filter:blur(14px);
    }
    .result-thumb {
      width:58px;
      height:58px;
      border-radius:12px;
      overflow:hidden;
      background:#eee;
    }
    .result-thumb img, .result-thumb video { width:100%; height:100%; object-fit:cover; display:block; }
    .result-card h3 {
      margin:0;
      font-size:.9rem;
      line-height:1.2;
      font-weight:850;
      overflow:hidden;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
    }
    .result-card p {
      margin:4px 0 0;
      color:rgba(255,255,255,.58);
      font-size:.75rem;
      line-height:1.25;
      overflow:hidden;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
    }
    .empty {
      padding:48px 8px;
      text-align:center;
      color:var(--muted);
      font-weight:700;
    }
    .mini-player {
      position:fixed;
      left:50%;
      bottom:calc(72px + var(--safe-bottom));
      z-index:40;
      width:min(398px, calc(100% - 28px));
      transform:translate(-50%, calc(100% + 110px));
      border:1px solid var(--border);
      border-radius:18px;
      background:#fff;
      overflow:hidden;
      opacity:0;
      pointer-events:none;
      transition:transform 180ms ease, opacity 180ms ease;
    }
    .mini-player.visible {
      transform:translate(-50%, 0);
      opacity:1;
      pointer-events:auto;
    }
    .mini-body {
      display:grid;
      grid-template-columns:58px minmax(0,1fr) 44px 34px 34px;
      align-items:center;
      gap:10px;
      padding:12px;
    }
    .mini-thumb {
      width:58px;
      height:58px;
      border-radius:9px;
      overflow:hidden;
      background:#eee;
    }
    .mini-thumb img, .mini-thumb video { width:100%; height:100%; object-fit:cover; display:block; }
    .mini-title {
      margin:0;
      font-size:.9rem;
      line-height:1.2;
      font-weight:850;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .mini-time { margin-top:5px; color:var(--accent); font-size:.72rem; font-weight:800; }
    .mini-action {
      min-width:34px;
      height:34px;
      display:grid;
      place-items:center;
      border-radius:50%;
      color:var(--text);
      font-size:.88rem;
      font-weight:750;
    }
    .progress-track { height:3px; background:#e7e7e7; }
    .progress-fill { width:0%; height:100%; background:var(--accent); }
    .sheet-backdrop {
      position:fixed;
      inset:0;
      z-index:50;
      background:rgba(0,0,0,.22);
      opacity:0;
      pointer-events:none;
      transition:opacity 160ms ease;
    }
    .sheet-backdrop.visible { opacity:1; pointer-events:auto; }
    .action-sheet {
      position:fixed;
      left:50%;
      bottom:0;
      z-index:60;
      width:min(430px,100%);
      transform:translate(-50%,104%);
      border-radius:22px 22px 0 0;
      background:#fff;
      overflow:hidden;
      transition:transform 180ms ease;
    }
    .action-sheet.visible { transform:translate(-50%,0); }
    .sheet-media { position:relative; height:210px; background:#111; }
    .sheet-media img, .sheet-media video { width:100%; height:100%; object-fit:cover; display:block; opacity:.9; }
    .sheet-close {
      position:absolute;
      top:14px;
      left:14px;
      width:34px;
      height:34px;
      border-radius:50%;
      display:grid;
      place-items:center;
      background:rgba(0,0,0,.72);
      color:#fff;
    }
    .sheet-body { padding:14px 18px calc(18px + var(--safe-bottom)); }
    .sheet-handle { width:38px; height:4px; border-radius:3px; background:#d8d8d8; margin:0 auto 14px; }
    .sheet-title-row { display:flex; justify-content:space-between; gap:12px; align-items:start; margin-bottom:14px; }
    .sheet-title { margin:0; font-size:1rem; line-height:1.25; font-weight:900; }
    .type-badge {
      flex:0 0 auto;
      border-radius:12px;
      background:rgba(108,77,255,.1);
      color:var(--accent);
      padding:5px 9px;
      font-size:.72rem;
      font-weight:850;
    }
    .quick-actions { display:grid; grid-template-columns:repeat(4,1fr); gap:8px; margin-bottom:16px; }
    .quick-action { display:grid; place-items:center; gap:6px; color:var(--text); font-size:.68rem; font-weight:700; }
    .quick-action span {
      width:38px;
      height:38px;
      border:1px solid var(--border);
      border-radius:50%;
      display:grid;
      place-items:center;
      font-size:1rem;
    }
    .sheet-list { border-top:1px solid var(--border); }
    .sheet-row {
      min-height:49px;
      border-bottom:1px solid var(--border);
      display:flex;
      align-items:center;
      justify-content:space-between;
      gap:12px;
      color:var(--text);
      text-decoration:none;
      font-size:.88rem;
      font-weight:750;
      width:100%;
    }
    .sheet-row .new {
      margin-left:7px;
      border-radius:9px;
      background:rgba(108,77,255,.1);
      color:var(--accent);
      padding:2px 7px;
      font-size:.66rem;
      font-weight:850;
    }
    .sheet-row.danger { color:var(--danger); }
    .hidden { display:none !important; }
    @media (min-width:760px) {
      body { background:#fafafa; }
      .phone-shell {
        margin-top:24px;
        margin-bottom:24px;
        min-height:calc(100vh - 48px);
        border:1px solid var(--border);
        border-radius:28px;
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
        <button id="miniMore" class="mini-action" type="button" aria-label="More actions">...</button>
        <button id="miniClose" class="mini-action" type="button" aria-label="Close mini player">X</button>
      </div>
      <div class="progress-track"><div id="miniProgress" class="progress-fill"></div></div>
    </section>
    <div id="sheetBackdrop" class="sheet-backdrop"></div>
    <section id="actionSheet" class="action-sheet" aria-label="Item actions"></section>
    <nav class="bottom-nav" aria-label="Primary">
      <button id="searchNav" class="nav-button" type="button"><span class="nav-icon">⌕</span><span>Search</span></button>
      <button id="libraryNav" class="nav-button active" type="button"><span class="nav-icon">□</span><span>Library</span></button>
      <button id="profileNav" class="nav-button" type="button"><span class="nav-icon">○</span><span>Profile</span></button>
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

    function escapeHtml(value) {
      return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
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
    function renderSyncBanner(compact = false) {
      const status = pipelineStatus();
      if (compact && status.tone === 'idle') return '';
      return `<section class="sync-banner ${status.tone}">
        <span class="sync-dot" aria-hidden="true"></span>
        <div><p class="sync-title">${escapeHtml(status.title)}</p><p class="sync-copy">${escapeHtml(status.copy)}</p></div>
        <span class="sync-count">${escapeHtml(status.count)}</span>
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
    function renderSearch(placeholder, value, id) {
      return `<label class="search"><span>⌕</span><input id="${id}" type="search" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}" autocomplete="off" /></label>`;
    }
    function renderChips(values, active, kind) {
      return `<div class="chips" aria-label="${kind} filters">${values.map((chip) => `<button class="chip ${chip === active ? 'active' : ''}" type="button" data-chip-kind="${kind}" data-chip="${escapeHtml(chip)}">${escapeHtml(chip)}</button>`).join('')}</div>`;
    }
    function renderLibrary() {
      const lists = sortedCollections().filter(listMatches);
      app.innerHTML = `
        <div class="topbar">
          <div class="brand-mark">MyLife</div>
          <div class="icon-row">
            <button class="icon-button" type="button" aria-label="Filters">☷</button>
            <button class="icon-button" type="button" aria-label="Refresh" id="refreshButton">↻</button>
          </div>
        </div>
        <h1 class="page-title">All Folders</h1>
        <p class="microcopy">Sorted by most saved items first. Smaller noisy folders naturally settle lower.</p>
        ${renderSyncBanner(true)}
        ${renderSearch('Search folders...', state.query, 'librarySearch')}
        ${renderChips(chips(), state.chip, 'library')}
        ${state.loading ? '<div class="empty">Loading your library...</div>' : ''}
        ${!state.loading && lists.length ? `<section class="list-grid">${lists.map(renderListCard).join('')}</section>` : ''}
        ${!state.loading && !lists.length ? '<div class="empty">No real folders found yet</div>' : ''}
      `;
      document.getElementById('librarySearch')?.addEventListener('input', (event) => {
        state.query = event.target.value;
        render();
      });
      document.getElementById('refreshButton')?.addEventListener('click', loadData);
      bindChips();
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
    function renderListCard(list) {
      const examples = (list.items || [])
        .slice(0, 3)
        .map((item) => item.name || item.product_name)
        .filter(Boolean)
        .join(' • ');
      return `<button class="list-card" type="button" data-open-list="${escapeHtml(list.list_id)}" aria-label="Open ${escapeHtml(list.list_title)}">
        ${renderMedia(coverItem(list))}
        <span class="count-badge">${list.real_count}</span>
        <span class="list-card-content">
          <span class="list-domain">${escapeHtml(list.parent_title || 'Strong interest')}</span>
          <span class="list-card-title">${escapeHtml(list.list_title)}</span>
          ${examples ? `<span class="list-preview">${escapeHtml(examples)}</span>` : ''}
        </span>
      </button>`;
    }
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
          <button id="backToLibrary" class="back-button" type="button" aria-label="Back to library">‹</button>
          <div class="list-title-block"><h1>${escapeHtml(list.list_title)}</h1><p class="count-text">${items.length} items</p></div>
          <div class="icon-row">
            <button class="icon-button" type="button" aria-label="Filters">☷</button>
            <button id="listMore" class="icon-button" type="button" aria-label="More list options">...</button>
          </div>
        </div>
        ${renderSearch(`Search in ${list.list_title}...`, state.itemQuery, 'itemSearch')}
        ${renderChips(['All', 'Video', 'Products', 'Saved'], state.itemChip, 'item')}
        ${items.length ? `<section class="item-grid">${items.map(renderItemCard).join('')}</section>` : '<div class="empty">No items found</div>'}
      `;
      document.getElementById('backToLibrary').addEventListener('click', () => {
        state.screen = 'library';
        state.currentListId = '';
        render();
      });
      document.getElementById('itemSearch').addEventListener('input', (event) => {
        state.itemQuery = event.target.value;
        render();
      });
      bindChips();
      app.querySelectorAll('[data-open-item]').forEach((button) => {
        button.addEventListener('click', () => openMiniPlayer(items[Number(button.dataset.openItem)], Number(button.dataset.openItem)));
      });
    }
    function renderItemCard(item, index) {
      const productText = [item.product_brand, item.product_name || item.product_type].filter(Boolean).join(' ');
      return `<article class="item-card">
        <button class="item-open" type="button" data-open-item="${index}" aria-label="Preview ${escapeHtml(item.name)}">
          <div class="thumb-wrap">
            ${renderMedia(item)}
            <span class="duration">${escapeHtml(durationFor(item, index))}</span>
            <span class="play-dot">▶</span>
          </div>
          <div>
            <div class="item-title-row"><p class="item-title">${escapeHtml(item.name)}</p><span class="more-dot">...</span></div>
            ${item.summary ? `<p class="item-summary">${escapeHtml(item.summary)}</p>` : ''}
            <div class="item-meta-row">
              ${hasProduct(item) ? '<span class="item-pill product">Product</span>' : ''}
              ${productText ? `<span class="item-pill">${escapeHtml(productText)}</span>` : ''}
            </div>
          </div>
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
    function searchTabResults() {
      const q = state.magicQuery.trim();
      const allItems = sortedCollections().flatMap((list) => list.items.map((item) => ({ ...item, list_title: list.list_title, parent_title: list.parent_title })));
      return q
        ? allItems.filter((item) => hasText(`${item.name} ${item.summary || ''} ${item.product_name || ''} ${item.product_brand || ''} ${item.list_title || ''}`, q)).slice(0, 24)
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
        list_title: 'Deep Search',
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
        ${q && state.deepSearch.error ? `<div class="empty">${escapeHtml(state.deepSearch.error)}</div>` : ''}
        ${q && !state.deepSearch.loading && !results.length ? '<div class="empty">No matches yet. Try a broader word.</div>' : ''}
        ${results.map((item, index) => `<button class="result-card" type="button" data-search-item="${index}">
          <div class="result-thumb">${renderMedia(item)}</div>
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
          <div class="magic-search">
            <div class="magic-orb">⌕</div>
            <div>
              <h1 class="magic-title">Find anything you saved.</h1>
              <p class="magic-copy">Search products, places, ideas, captions, and folder names from your reel memory.</p>
            </div>
            <label class="magic-bar">
              <input id="magicInput" value="${escapeHtml(state.magicQuery)}" placeholder="What are you trying to remember?" autocomplete="off" />
              <button id="magicSubmit" class="magic-submit" type="button" aria-label="Search">↗</button>
            </label>
            <div id="magicResults" class="result-list"></div>
          </div>
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
    function renderProfile() {
      const totalItems = sortedCollections().reduce((sum, list) => sum + list.real_count, 0);
      const jobs = recentJobs();
      const diagnostics = recentDiagnostics();
      const dashboardJson = JSON.stringify(state.dashboard || {}, null, 2);
      app.innerHTML = `
        <div class="topbar">
          <div class="brand-mark">MyLife</div>
          <div class="icon-row"><button class="icon-button" type="button" aria-label="Refresh diagnostics" id="profileRefresh">↻</button></div>
        </div>
        <h1 class="page-title">Profile</h1>
        ${renderSyncBanner(false)}
        <section class="profile-grid">
          <div class="metric-card"><span>Library Items</span><b>${totalItems}</b></div>
          <div class="metric-card"><span>Processed Reels</span><b>${state.dashboard.processed_url_count || 0}</b></div>
          <div class="metric-card"><span>Queued</span><b>${state.dashboard.queued_job_count || 0}</b></div>
          <div class="metric-card"><span>Running</span><b>${state.dashboard.running_job_count || 0}</b></div>
        </section>
        <section class="profile-panel">
          <div class="profile-row">Connected Instagram <span>${USER_ID}</span></div>
          <div class="profile-row">Sync Status <span>${escapeHtml(pipelineStatus().title)}</span></div>
          <div class="profile-row">Pending Reels <span>${state.dashboard.pending_url_count || 0}</span></div>
          <div class="profile-row">Failed Reels <span>${state.dashboard.failed_url_count || 0}</span></div>
          <div class="profile-row">Storage Usage <span>${totalItems} items</span></div>
        </section>
        <h2 class="profile-section-title">Recent Reel Jobs</h2>
        <section class="job-list">
          ${jobs.length ? jobs.map(renderJobCard).join('') : '<div class="empty">No recent jobs found yet</div>'}
        </section>
        <h2 class="profile-section-title">Recent Stored Reels</h2>
        <section class="job-list">
          ${diagnostics.length ? diagnostics.map(renderReelDiagnosticCard).join('') : '<div class="empty">No stored reel diagnostics found yet</div>'}
        </section>
        <h2 class="profile-section-title">Dashboard JSON</h2>
        <details class="json-box"><summary>View dashboard JSON</summary><pre>${escapeHtml(dashboardJson)}</pre></details>
      `;
      document.getElementById('profileRefresh')?.addEventListener('click', loadData);
    }
    function bindChips() {
      app.querySelectorAll('[data-chip-kind]').forEach((button) => {
        button.addEventListener('click', () => {
          if (button.dataset.chipKind === 'library') state.chip = button.dataset.chip;
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
          <button id="sheetClose" class="sheet-close" type="button" aria-label="Close actions">X</button>
        </div>
        <div class="sheet-body">
          <div class="sheet-handle"></div>
          <div class="sheet-title-row"><h2 class="sheet-title">${escapeHtml(item.name)}</h2><span class="type-badge">${hasProduct(item) ? 'Product' : 'Video'}</span></div>
          <div class="quick-actions">
            <button class="quick-action" type="button"><span>♡</span>Save</button>
            <button id="shareItem" class="quick-action" type="button"><span>⇧</span>Share</button>
            <button class="quick-action" type="button"><span>☷</span>Add To List</button>
            <button class="quick-action" type="button"><span>...</span>More</button>
          </div>
          <div class="sheet-list">
            <a class="sheet-row" href="${escapeHtml(item.url || '#')}" target="_blank" rel="noopener"><span>Open Original Reel</span><span>›</span></a>
            ${productAction}
            <button class="sheet-row" type="button"><span>Notes</span><span>›</span></button>
            <button class="sheet-row" type="button"><span>Related Items</span><span>›</span></button>
            <button id="deleteItem" class="sheet-row danger" type="button"><span>Delete Item</span><span>›</span></button>
          </div>
        </div>`;
      sheetBackdrop.classList.add('visible');
      actionSheet.classList.add('visible');
      document.getElementById('sheetClose').addEventListener('click', closeActionSheet);
      document.getElementById('deleteItem').addEventListener('click', deleteCurrentItem);
      document.getElementById('shareItem').addEventListener('click', () => {
        if (navigator.share) navigator.share({ title: item.name, url: item.url || window.location.href }).catch(() => {});
      });
    }
    function closeActionSheet() {
      sheetBackdrop.classList.remove('visible');
      actionSheet.classList.remove('visible');
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
      for (const bucket of ['standard', 'personalized']) {
        state.data = state.data.map((list) => ({ ...list, items: (list.items || []).filter((item) => item.reel_id !== reelId) }));
      }
    }
    function setNav(screen) {
      state.screen = screen;
      if (screen !== 'list') state.currentListId = '';
      closeActionSheet();
      searchNav.classList.toggle('active', screen === 'search');
      libraryNav.classList.toggle('active', screen === 'library' || screen === 'list');
      profileNav.classList.toggle('active', screen === 'profile');
      render();
    }
    function render() {
      app.classList.toggle('search-mode', state.screen === 'search');
      document.querySelector('.bottom-nav')?.classList.toggle('search-nav-mode', state.screen === 'search');
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
        const [libraryRes, dashboardRes, jobsRes, diagnosticsRes] = await Promise.all([
          fetch(`/library?user_id=${encodeURIComponent(USER_ID)}`),
          fetch(`/dashboard?user_id=${encodeURIComponent(USER_ID)}`),
          fetch(`/jobs?user_id=${encodeURIComponent(USER_ID)}&limit=50`),
          fetch(`/diagnostics/reels?user_id=${encodeURIComponent(USER_ID)}&limit=12`)
        ]);
        const library = await libraryRes.json();
        state.data = normalizeCollections(library.personalized?.length ? library.personalized : library.standard || []);
        state.dashboard = await dashboardRes.json();
        state.jobs = await jobsRes.json();
        state.diagnostics = await diagnosticsRes.json();
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
