import os


def _token_safe(value: str) -> str:
    """Only characters that can sit inside a single-quoted JS string and an
    HTML attribute untouched. Tokens, client ids and stage names all fit."""
    return "".join(c for c in (value or "") if c.isalnum() or c in "._-")


def build_clipnest_v1_html(
    user_id: str,
    library_token: str = "",
    claim_stage: str = "",
    login_csrf: str = "",
    google_client_id: str = "",
) -> str:
    safe_user_id = user_id.replace("\\", "\\\\").replace("'", "\\'")
    # Collections shelves are visible to the demo showcase account plus any
    # account listed in COLLECTIONS_ACCOUNTS, so the engine can be polished
    # against a real library. Return "1" unconditionally to roll out to all.
    from app.services.discover import recipes_enabled
    from app.services.library import collections_enabled

    show_collections = "1" if collections_enabled(user_id) else "0"
    # Recipes hub + ingredient buy links: admin/RECIPES_ACCOUNTS only while
    # the founder bakes the feature in his own library.
    show_recipes = "1" if recipes_enabled(user_id) else "0"
    # Search reports: admin-only while the founder tries them on his library.
    from app.services.search_report import search_report_enabled

    show_report = "1" if search_report_enabled(user_id) else "0"
    # Render exposes the deployed commit; locally this shows "dev". Surfaced in
    # Profile so a stale cached build can be spotted from the phone instantly.
    build_sha = (os.getenv("RENDER_GIT_COMMIT") or "dev")[:7]
    html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0, viewport-fit=cover" />
  <meta name="theme-color" content="#0a0a0b" />
  <link rel="apple-touch-icon" sizes="180x180" href="/static/apple-touch-icon.png" />
  <link rel="icon" type="image/png" href="/static/favicon.png" />
  <link rel="manifest" href="__MANIFEST_HREF__" />
  <meta name="apple-mobile-web-app-title" content="ClipNest" />
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
      /* Brand palette from the ClipNest logo: charcoal mascot on warm cream,
         orange sparks. Dark app shell + warm orange accents. */
      --accent:#f2a866;
      --brand-hi:#f9a660;
      --brand-deep:#ee7f2f;
      --brand-grad:linear-gradient(135deg, #f9a660 0%, #ee7f2f 100%);
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
      /* shrinks on narrow phones so the four header icons never overlap it */
      font-size:clamp(1.55rem, 7.5vw, 2.1rem);
      line-height:1.05;
      font-weight:600;
      letter-spacing:.2px;
      white-space:nowrap;
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
    .icon-button.spinning svg { animation: cn-spin .7s linear infinite; }
    @keyframes cn-spin { to { transform: rotate(360deg); } }
    /* Claim card: home screen at 5 reels, sign in from 17, the wall at 20.
       Sits outside #app because render() rewrites #app wholesale. */
    .claim-card { margin:calc(12px + var(--safe-top)) 18px -4px; background:var(--card); border:1px solid var(--line); border-radius:16px; padding:14px 16px;
      box-shadow:0 1px 0 rgba(255,255,255,.03) inset, 0 10px 28px -18px rgba(0,0,0,.9); opacity:0; transform:translateY(-4px); transition:opacity .25s ease, transform .25s ease; }
    .claim-card.show { opacity:1; transform:none; }
    .claim-card.locked { border-color:rgba(242,168,102,.45); box-shadow:0 1px 0 rgba(255,255,255,.04) inset, 0 12px 32px -16px rgba(238,127,47,.45); }
    .claim-title { margin:0; font-family:var(--serif); font-size:1.05rem; font-weight:600; letter-spacing:-.01em; color:var(--text); }
    .claim-sub { margin:3px 0 12px; font-size:.78rem; line-height:1.45; color:var(--muted); }
    .claim-btn { display:inline-flex; align-items:center; justify-content:center; background:var(--brand-grad); color:#1a0f06; border-radius:999px; padding:10px 18px; font-weight:700; font-size:.88rem; text-decoration:none;
      box-shadow:0 6px 18px -8px rgba(238,127,47,.6); transition:transform .15s ease, opacity .15s ease; }
    .claim-btn:hover { opacity:.92; }
    .claim-btn:active { transform:scale(.97); }
    .claim-btn:focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
    .claim-hint { margin:10px 0 0; font-size:.72rem; line-height:1.4; color:var(--faint); }
    .claim-err { margin:10px 0 0; font-size:.75rem; color:var(--danger); }
    /* No display rule here on purpose: setting one overrides the [hidden]
       attribute, which is how the locked card hides this button. */
    .claim-skip { margin-top:10px; color:var(--muted); font-size:.75rem; transition:opacity .15s ease; }
    .claim-skip:hover { opacity:.75; }
    .claim-skip:active { opacity:.55; }
    .claim-skip:focus-visible { outline:2px solid var(--accent); outline-offset:2px; border-radius:4px; }

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
      padding:0 54px 0 48px;
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
    .search-plus {
      position:absolute; right:7px; top:50%; transform:translateY(-50%);
      width:36px; height:36px; border-radius:50%; border:0; padding:0;
      background:var(--brand-grad); color:#fff; font-size:1.5rem; line-height:1;
      display:grid; place-items:center; cursor:pointer;
    }
    .search-plus:active { filter:brightness(1.1); }
    .search-plus { transition:transform .18s ease, background .18s ease; }
    /* Selecting mode: the + rotates into an x and hollows out = "cancel". */
    .search-plus.active { background:var(--soft); border:1.5px solid var(--brand-hi); color:var(--brand-hi); transform:translateY(-50%) rotate(45deg); }
    /* Admin-only report button, just left of the +. Hollow so the + stays the
       primary action. */
    .search.has-report input { padding-right:96px; }
    .search-report { position:absolute; right:49px; top:50%; transform:translateY(-50%);
      width:36px; height:36px; border-radius:50%; padding:0; display:grid; place-items:center; cursor:pointer;
      background:var(--card); border:1.5px solid rgba(238,127,47,.55); color:var(--brand-hi);
      box-shadow:0 6px 16px -10px rgba(238,127,47,.7); transition:transform .14s ease; }
    .search-report svg { width:18px; height:18px; }
    .search-report:hover { border-color:var(--brand-hi); }
    .search-report:focus-visible { outline:2px solid var(--brand-hi); outline-offset:2px; }
    .search-report:active { transform:translateY(-50%) scale(.9); }
    /* Brand loader, square one: the simple bookmark silhouette in the brand
       gradient, gently pulsing. */
    .load-wrap { display:flex; justify-content:center; padding:44px 0; }
    .spinner {
      width:30px; height:38px; border:0; display:block;
      background:var(--brand-grad);
      -webkit-mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6 2h12a2 2 0 0 1 2 2v18l-8-5.2L4 22V4a2 2 0 0 1 2-2z'/%3E%3C/svg%3E") center/contain no-repeat;
      mask:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath d='M6 2h12a2 2 0 0 1 2 2v18l-8-5.2L4 22V4a2 2 0 0 1 2-2z'/%3E%3C/svg%3E") center/contain no-repeat;
      animation:bookmarkPulse 1.1s ease-in-out infinite;
    }
    @keyframes bookmarkPulse {
      0%, 100% { transform:scale(1); opacity:.6; }
      50% { transform:scale(1.12); opacity:1; }
    }
    .brand-mark {
      width:34px; height:34px; border-radius:9px; flex:0 0 auto;
      background:url('/static/icon-192.png') center/contain no-repeat;
    }
    .greeting-row { display:flex; align-items:center; gap:11px; min-width:0; }
    /* tappable section header (Recently saved) */
    .section-head-btn { width:100%; background:none; border:0; padding:0; cursor:pointer;
      text-align:left; color:inherit; }

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
    .lib-logo { width: 76%; height: 76%; object-fit: contain; display: block; }
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
    .lib-text { min-width:0; }
    .lib-meta {
      margin:4px 0 0;
      color:var(--muted);
      font-size:.8rem;
      font-weight:500;
      display:-webkit-box;
      -webkit-line-clamp:2;
      -webkit-box-orient:vertical;
      overflow:hidden;
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
    .chip.active { background:var(--brand-grad); color:#fff; }

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
    /* Two independent packed columns: card heights never couple across the
       row, so no stretched cells or dead vertical gaps — each column stacks
       tight with its own rhythm. */
    .masonry {
      display:flex;
      gap:12px;
      align-items:flex-start;
    }
    .mas-col {
      flex:1;
      min-width:0;
      display:flex;
      flex-direction:column;
      gap:16px;
    }
    .m-card {
      margin:0;
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
    /* Image cards flow at their natural height for a dense Pinterest-style
       pack; capped so one panorama can't eat the column. Video/empty cells
       keep the fixed 9/13 aspect above so they never collapse. */
    .m-thumb.natural { aspect-ratio:auto; min-height:110px; }
    .m-thumb.natural img { height:auto; min-height:110px; max-height:64vh; }
    .m-thumb.broken::after, .recent-thumb.broken::after {
      content:'▶';
      position:absolute;
      inset:0;
      display:grid;
      place-items:center;
      color:rgba(255,255,255,.55);
      font-size:1.7em;
    }
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
      /* Overlay-centered so it stays visible on top of a <video> that hasn't
         painted a frame yet (iOS shows those as solid black). */
      position:absolute;
      inset:0;
      display:grid;
      place-items:center;
      color:rgba(255,255,255,.55);
      font-size:1.1em;
      pointer-events:none;
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
      display:flex;
      border-top:1px solid var(--line);
      background:rgba(10,10,11,.86);
      -webkit-backdrop-filter:blur(18px);
      backdrop-filter:blur(18px);
      padding:10px 26px calc(10px + var(--safe-bottom));
    }
    .nav-button {
      flex:1;
      display:grid;
      gap:4px;
      place-items:center;
      color:var(--faint);
      font-size:.68rem;
      font-weight:650;
    }
    .nav-button svg { width:23px; height:23px; }
    .nav-button.active { color:#f5b878; }

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
      color:#fff; background:var(--brand-grad); border:none; border-radius:20px; padding:7px 15px; cursor:pointer; }
    .newlist-btn.ghost { background:none; color:var(--accent); border:1px solid rgba(238,127,47,.5); }
    .newlist-btn:disabled { opacity:.45; }
    .m-card.selectable { cursor:pointer; position:relative; }
    .m-card.selected { outline:2px solid var(--brand-deep); outline-offset:-2px; border-radius:16px; }
    .m-card .selring { position:absolute; top:10px; right:10px; width:22px; height:22px; border-radius:50%;
      border:2px solid rgba(255,255,255,.7); background:rgba(0,0,0,.35); z-index:3; display:none; }
    .m-card.selectable .selring { display:block; }
    .m-card.selected .selring { background:var(--brand-deep); border-color:var(--brand-deep); }
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
    .sug-chip { font-size:.66rem; color:#fff; background:var(--brand-grad); border-radius:20px; padding:2px 8px; margin-left:6px; }
    .skip-chips { display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; }
    .list-pick-wrap { max-height:46vh; overflow-y:auto; margin-top:10px; }
    .list-pick-row { display:flex; justify-content:space-between; align-items:center; gap:10px;
      padding:11px 2px; border-bottom:1px solid var(--line); }
    .list-pick-row:last-child { border-bottom:none; }
    .list-pick-name { font-size:.92rem; display:flex; flex-direction:column; gap:2px; min-width:0; }
    .list-pick-name em { font-style:normal; color:var(--muted); font-size:.72rem; }
    .in-chip { color:var(--accent); font-size:.8rem; font-weight:650; white-space:nowrap; }
    /* ---------- reel map overlay (ClipNest dark) ---------- */
    .map-overlay { position:fixed; inset:0; z-index:80; display:none; background:var(--bg); }
    .map-overlay.show { display:block; }
    #reelMap { position:absolute; inset:0; }
    /* Dark cartography: invert OSM's light tiles into the app's night palette.
       Tuned for tile.openstreetmap.org, which runs hotter than the old CARTO
       basemap: heavier desaturation and a lower brightness floor keep land near
       --bg while water holds just enough cool tint to read as sea. */
    #reelMap .leaflet-tile-pane { filter:invert(1) hue-rotate(185deg) saturate(.22) brightness(.76) contrast(1.08); }
    .map-hud { position:absolute; z-index:600; top:calc(14px + var(--safe-top)); left:14px; background:var(--card);
      border:1px solid var(--line); border-radius:16px; padding:12px 16px; max-width:74vw; }
    .map-hud h2 { margin:0; font-family:var(--serif); font-size:1.25rem; font-weight:600; color:var(--text); }
    .map-hud p { margin:3px 0 0; font-size:.75rem; color:var(--muted); font-weight:600; }
    .map-close { position:absolute; z-index:600; top:calc(14px + var(--safe-top)); right:14px; width:44px; height:44px;
      background:var(--card); color:var(--text); border:1px solid var(--line); border-radius:50%;
      font-size:18px; cursor:pointer; }
    .map-close:active { background:var(--soft); }
    .map-doodle { display:none; }
    .map-empty { position:absolute; z-index:600; left:50%; top:50%; transform:translate(-50%,-50%);
      background:var(--card); border:1px solid var(--line); border-radius:18px; padding:18px 22px;
      font-weight:650; color:var(--text); text-align:center; max-width:82vw; }
    .map-empty span { font-weight:500; font-size:.8rem; color:var(--muted); }
    .pin-wrap { position:relative; width:48px; height:54px; }
    .pin-blob { position:absolute; left:2px; top:0; width:44px; height:44px; background:var(--card);
      border:2px solid var(--brand-deep); border-radius:50%;
      display:flex; align-items:center; justify-content:center;
      font-size:22px; box-shadow:0 6px 18px rgba(238,127,47,.35);
      animation:pinplop .5s cubic-bezier(.34,1.65,.6,1) both; }
    .pin-shadow { position:absolute; left:13px; bottom:0; width:22px; height:7px;
      background:rgba(0,0,0,.45); border-radius:50%; }
    .pin-badge { position:absolute; right:-6px; top:-7px; min-width:22px; height:22px;
      background:var(--brand-grad); color:#fff; border:2px solid var(--bg); border-radius:999px;
      font-size:12px; font-weight:800; line-height:18px; text-align:center; padding:0 5px; }
    @keyframes pinplop { from { transform:scale(0) translateY(-26px); } to { transform:scale(1) translateY(0); } }
    .map-overlay .leaflet-popup-content-wrapper { background:var(--card); color:var(--text);
      border:1px solid var(--line); border-radius:16px; box-shadow:0 18px 44px rgba(0,0,0,.5); }
    .map-overlay .leaflet-popup-tip { background:var(--card); border:1px solid var(--line); }
    /* OSM's tile policy requires visible licence attribution -- keep it readable. */
    .map-overlay .leaflet-control-attribution { background:rgba(22,22,25,.82); color:var(--muted);
      border:1px solid var(--line); border-right:none; border-bottom:none; border-radius:10px 0 0 0;
      padding:3px 8px; font-size:.62rem; backdrop-filter:blur(4px); }
    .map-overlay .leaflet-control-attribution a { color:var(--accent); text-decoration:none; font-weight:650;
      transition:opacity .15s ease; }
    .map-overlay .leaflet-control-attribution a:hover { opacity:.72; }
    .map-overlay .leaflet-control-attribution a:focus-visible { outline:2px solid var(--accent);
      outline-offset:2px; border-radius:4px; }
    .map-overlay .leaflet-control-attribution a:active { opacity:.55; }
    .map-pop-place { font-weight:700; font-size:1rem; font-family:var(--serif); }
    .map-pop-sub { font-size:.72rem; color:var(--muted); font-weight:600; margin-bottom:8px; }
    .map-pop-item { margin:7px 0; padding:8px 10px; background:var(--soft); border:1px solid var(--line); border-radius:12px; }
    .map-pop-name { font-weight:650; font-size:.82rem; color:var(--text); }
    .map-pop-link { font-size:.78rem; color:var(--accent); text-decoration:none; font-weight:700; }
    /* ---------- recipe card overlay (ClipNest dark) ---------- */
    .recipe-overlay { position:fixed; inset:0; z-index:90; display:none; background:rgba(10,10,11,.7);
      backdrop-filter:blur(6px); align-items:flex-end; justify-content:center; }
    .recipe-overlay.show { display:flex; }
    .recipe-card { background:var(--card); color:var(--text); border:1px solid var(--line); border-bottom:none;
      border-radius:22px 22px 0 0; width:min(560px,100%); max-height:88vh; overflow-y:auto;
      padding:20px 18px calc(26px + var(--safe-bottom)); }
    .recipe-card h2 { margin:0 0 6px; font-family:var(--serif); font-size:1.4rem; font-weight:600; padding-right:50px; }
    .recipe-close { position:sticky; top:0; float:right; width:40px; height:40px; background:var(--soft);
      color:var(--text); border:1px solid var(--line); border-radius:50%; font-size:16px; cursor:pointer; }
    .recipe-meta { display:flex; gap:8px; flex-wrap:wrap; margin:8px 0 4px; }
    .recipe-chip { background:var(--soft); border:1px solid var(--line); border-radius:999px;
      font-size:.75rem; font-weight:650; color:var(--muted); padding:5px 13px; }
    .recipe-card h3 { font-size:.7rem; margin:18px 0 8px; color:var(--accent); text-transform:uppercase; letter-spacing:.8px; }
    .recipe-ing { list-style:none; margin:0; padding:0; }
    .recipe-ing li { padding:9px 12px; margin:6px 0; background:var(--soft); border:1px solid var(--line);
      border-radius:12px; font-size:.88rem; font-weight:550; cursor:pointer; user-select:none; }
    .recipe-ing li.done { text-decoration:line-through; opacity:.38; }
    .recipe-steps { margin:0; padding:0; counter-reset:rstep; list-style:none; }
    .recipe-steps li { counter-increment:rstep; position:relative; padding:9px 12px 9px 46px; margin:8px 0;
      background:var(--soft); border:1px solid var(--line); border-radius:12px; font-size:.88rem; line-height:1.5; }
    .recipe-steps li::before { content:counter(rstep); position:absolute; left:9px; top:9px; width:26px; height:26px;
      background:var(--brand-grad); color:#fff; border-radius:999px; font-weight:800;
      font-size:12.5px; display:flex; align-items:center; justify-content:center; }
    .recipe-watch { display:inline-block; margin-top:14px; background:var(--brand-grad); color:#fff;
      border:0; border-radius:22px; font-weight:700; font-size:.9rem; padding:11px 20px; text-decoration:none; }
    .recipe-watch:active { filter:brightness(1.1); }

    /* ---------- ingredient buy links + shop-the-recipe ---------- */
    .recipe-ing li { display:flex; flex-wrap:wrap; align-items:center; gap:6px; }
    .recipe-ing li .ing-name { flex:1 1 auto; min-width:0; }
    .recipe-ing li .ing-buy { flex:0 0 auto; color:var(--accent); font-size:.72rem; font-weight:700; }
    .recipe-ing li .ing-buy.exact { color:#f5b878; }
    .ing-links { flex-basis:100%; display:none; flex-wrap:wrap; gap:6px; padding-top:7px; }
    .recipe-ing li.shopping-open .ing-links { display:flex; }
    .qc-btn { display:inline-flex; align-items:center; gap:5px; min-height:28px; border-radius:14px;
      padding:5px 11px; background:var(--bg); border:1px solid var(--line); color:var(--text);
      text-decoration:none; font-size:.72rem; font-weight:650; }
    .qc-btn .qc-dot { width:7px; height:7px; border-radius:999px; flex:none; }
    .qc-btn .qc-exact { color:var(--accent); font-size:.6rem; font-weight:800; letter-spacing:.4px; }
    .qc-btn.has-exact { border-color:rgba(238,127,47,.5); }
    .qc-exact-line { flex-basis:100%; display:flex; align-items:center; gap:7px; padding-top:6px;
      font-size:.75rem; color:var(--accent); }
    .qc-exact-line a { color:var(--accent); text-decoration:none; border-bottom:1px dotted rgba(242,168,102,.5); min-width:0;
      overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .qc-badge { flex:none; background:var(--brand-grad); color:#fff; border-radius:6px;
      font-size:.56rem; font-weight:800; letter-spacing:.5px; padding:3px 6px; }
    .shop-city-row { display:flex; align-items:center; gap:8px; margin:2px 0 10px; }
    .shop-city-row label { color:var(--muted); font-size:.75rem; font-weight:650; }
    .shop-city-row select { background:var(--soft); color:var(--text); border:1px solid var(--line);
      border-radius:10px; padding:7px 10px; font-size:.8rem; font-weight:600; }
    .shop-all-row { display:flex; flex-wrap:wrap; gap:7px; margin:0 0 4px; }
    .shop-all-btn { display:inline-flex; align-items:center; gap:6px; border-radius:18px; padding:9px 14px;
      background:var(--soft); border:1px solid var(--line); color:var(--text); font-size:.78rem; font-weight:700; }
    .shop-all-btn .qc-cnt { color:var(--muted); font-weight:600; }
    .shop-all-btn.has-exact { border-color:rgba(238,127,47,.5); }
    .shop-copy-btn { width:100%; margin:10px 0 2px; background:var(--brand-grad); color:#fff; border:0;
      border-radius:14px; padding:12px; font-size:.82rem; font-weight:750; }
    .shop-copy-btn.copied { background:none; border:1px solid rgba(238,127,47,.5); color:var(--accent); }
    .shop-list { list-style:none; margin:0; padding:0; }
    .shop-list a { display:flex; align-items:center; gap:11px; padding:11px 10px; margin:5px 0;
      background:var(--soft); border:1px solid var(--line); border-radius:12px;
      color:var(--text); text-decoration:none; font-size:.86rem; font-weight:550; }
    .shop-list .shop-tick { width:23px; height:23px; border-radius:999px; border:2px solid var(--line);
      flex:none; display:flex; align-items:center; justify-content:center; font-size:12px; color:transparent; }
    .shop-list a.done .shop-tick { background:var(--brand-grad); border-color:transparent; color:#fff; }
    .shop-list a.done .shop-nm { color:var(--faint); text-decoration:line-through; }
    .shop-list .shop-nm { flex:1; min-width:0; }
    .shop-list .shop-go { color:var(--muted); font-size:.72rem; font-weight:650; }
    .shop-head { display:flex; align-items:center; gap:10px; margin:2px 0 8px; }
    .shop-head .shop-back { width:36px; height:36px; border-radius:50%; background:var(--soft);
      border:1px solid var(--line); color:var(--text); font-size:15px; }
    .shop-head .shop-prog { margin-left:auto; color:var(--accent); font-size:.78rem; font-weight:700; }

    /* ---------- recipes hub overlay ---------- */
    .recipes-overlay { position:fixed; inset:0; z-index:85; display:none; flex-direction:column;
      background:var(--bg); overflow-y:auto; }
    .recipes-overlay.show { display:flex; }
    .recipes-shell { width:min(430px,100%); margin:0 auto; padding:calc(16px + var(--safe-top)) 18px calc(40px + var(--safe-bottom)); }
    .recipes-head { display:flex; align-items:center; gap:12px; margin:6px 0 4px; }
    .recipes-head h1 { margin:0; font-family:var(--serif); font-size:1.7rem; font-weight:600; flex:1; }
    .recipes-sub { color:var(--muted); font-size:.8rem; margin:0 0 14px; }
    .rx-card { width:100%; text-align:left; background:var(--card); border:1px solid var(--line);
      border-radius:18px; padding:16px 16px 14px; margin:0 0 12px; color:var(--text); }
    .rx-card:active { background:var(--soft); }
    .rx-card h2 { margin:0 0 6px; font-family:var(--serif); font-size:1.15rem; font-weight:600; }
    .rx-meta { display:flex; flex-wrap:wrap; gap:6px; }
    .rx-meta span { background:var(--soft); border:1px solid var(--line); border-radius:999px;
      font-size:.68rem; font-weight:650; color:var(--muted); padding:4px 10px; }
    .rx-meta .rx-exact { color:var(--accent); border-color:rgba(238,127,47,.5); }

    /* ---------- search report ---------- */
    /* Sits BELOW the player (40) and the reel sheet (50/60): tapping a cited
       reel opens it on top of the report, and closing it lands back here. */
    .recipes-overlay.report-overlay { z-index:35; }
    .report-overlay .recipes-head { align-items:flex-start; gap:10px; }
    .report-overlay .recipes-head h1 { font-size:1.42rem; line-height:1.2; letter-spacing:-.02em; padding-top:6px; }
    .rp-summary { font-size:.95rem; line-height:1.62; color:var(--text); margin:4px 2px 18px; }
    .rp-section { background:var(--card); border:1px solid var(--line); border-radius:18px; padding:14px 16px 6px; margin:0 0 12px;
      box-shadow:0 1px 0 rgba(255,255,255,.03) inset, 0 14px 32px -24px rgba(0,0,0,.95), 0 2px 8px -6px rgba(238,127,47,.18); }
    .rp-section h2 { margin:0 0 10px; font-family:var(--serif); font-size:1.14rem; font-weight:600; letter-spacing:-.015em; }
    .rp-points { list-style:none; margin:0; padding:0; }
    .rp-points li { position:relative; padding:0 0 11px 15px; font-size:.88rem; line-height:1.58; }
    .rp-points li::before { content:''; position:absolute; left:0; top:.66em; width:5px; height:5px; border-radius:50%; background:var(--accent); }
    .rp-ref { display:inline-grid; place-items:center; min-width:22px; height:20px; padding:0 6px; margin-left:5px; border-radius:7px;
      background:rgba(238,127,47,.14); color:var(--accent); font-size:.68rem; font-weight:750; vertical-align:1px;
      transition:transform 120ms ease; }
    .rp-ref:hover { background:rgba(238,127,47,.26); }
    .rp-ref:focus-visible { outline:2px solid var(--accent); outline-offset:1px; }
    .rp-ref:active { transform:scale(.9); }
    .rp-gaps { color:var(--muted); font-size:.8rem; line-height:1.5; margin:2px 2px 4px; }
    .rp-label { color:var(--muted); font-size:.7rem; font-weight:750; letter-spacing:.07em; text-transform:uppercase; margin:20px 2px 8px; }
    .rp-skipped > summary { list-style:none; cursor:pointer; display:flex; align-items:center; gap:6px; }
    .rp-skipped > summary::-webkit-details-marker { display:none; }
    .rp-skipped > summary:focus-visible { outline:2px solid var(--accent); outline-offset:2px; border-radius:6px; }
    .rp-skipped > summary .chev { display:inline-block; transition:transform 160ms ease; }
    .rp-skipped[open] > summary .chev { transform:rotate(90deg); }
    .rp-reels { display:flex; flex-direction:column; gap:8px; }
    .rp-reel { display:flex; align-items:center; gap:8px; background:var(--soft); border:1px solid var(--line); border-radius:14px; padding:7px 8px 7px 7px;
      transition:opacity 160ms ease; }
    .rp-reel.off { opacity:.45; }
    .rp-reel.picked { border-color:rgba(238,127,47,.55); }
    .rp-open { flex:1; min-width:0; display:flex; align-items:center; gap:10px; text-align:left; color:var(--text); border-radius:10px;
      transition:transform 120ms ease; }
    .rp-open:hover .rp-name { color:var(--accent); }
    .rp-open:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    .rp-open:active { transform:scale(.985); }
    .rp-thumb { position:relative; width:42px; height:54px; border-radius:9px; overflow:hidden; flex:none; display:block; }
    .rp-thumb img, .rp-thumb video { width:100%; height:100%; object-fit:cover; display:block; }
    .rp-num { position:absolute; left:3px; top:3px; z-index:2; min-width:17px; height:17px; padding:0 4px; border-radius:6px;
      display:grid; place-items:center; background:var(--brand-grad); color:#fff; font-size:.62rem; font-weight:800; }
    .rp-meta { flex:1; min-width:0; display:flex; flex-direction:column; gap:2px; }
    .rp-name { font-size:.82rem; font-weight:620; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
    .rp-why { color:var(--faint); font-size:.72rem; line-height:1.3; }
    .rp-toggle { width:34px; height:34px; border-radius:50%; flex:none; display:grid; place-items:center;
      background:var(--card); border:1px solid var(--line); color:var(--muted); font-size:14px; font-weight:700;
      transition:transform 120ms ease; }
    .rp-toggle:hover { color:var(--text); border-color:rgba(238,127,47,.5); }
    .rp-toggle:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    .rp-toggle:active { transform:scale(.9); }
    .rp-reel.picked .rp-toggle { background:var(--brand-grad); color:#fff; border-color:transparent; }
    .rp-update { position:sticky; bottom:calc(14px + var(--safe-bottom)); width:100%; margin-top:18px; padding:13px;
      background:var(--brand-grad); color:#fff; border:0; border-radius:14px; font-size:.86rem; font-weight:750;
      box-shadow:0 14px 30px -14px rgba(238,127,47,.85), 0 4px 10px -6px rgba(0,0,0,.8); transition:transform 120ms ease; }
    .rp-update:focus-visible { outline:2px solid #fff; outline-offset:2px; }
    .rp-update:active { transform:scale(.985); }
    .rp-share { width:40px; height:40px; border-radius:50%; flex:none; display:grid; place-items:center; color:var(--text);
      background:var(--soft); border:1px solid var(--line); margin-top:2px; transition:transform 120ms ease; }
    .rp-share svg { width:18px; height:18px; }
    .rp-share:hover { border-color:rgba(238,127,47,.55); }
    .rp-share:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    .rp-share:active { transform:scale(.92); }
    .rp-share.done { background:var(--brand-grad); border-color:transparent; color:#fff; }
    .rp-strip { display:flex; gap:7px; overflow-x:auto; padding:2px 2px 10px; margin:0 -2px 6px; scrollbar-width:none; }
    .rp-strip::-webkit-scrollbar { display:none; }
    .rp-strip-item { flex:none; border-radius:10px; transition:transform 120ms ease; }
    .rp-strip.reading { flex-wrap:wrap; overflow:visible; }
    .rp-strip.reading .rp-strip-item { animation:rpRead 1.4s ease-in-out infinite both; }
    @keyframes rpRead { 0%, 100% { opacity:.28; transform:scale(.96); } 50% { opacity:.8; transform:none; } }
    .rp-strip-item:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    .rp-strip-item:active { transform:scale(.94); }
    .rp-writing { display:flex; align-items:center; gap:9px; color:var(--muted); font-size:.8rem; font-weight:600; padding:6px 4px 18px; }
    .rp-dot { width:8px; height:8px; border-radius:50%; background:var(--brand-grad); animation:bookmarkPulse 1s ease-in-out infinite; }
    .rp-block { margin:0 0 18px; }
    .rp-block > h2 { margin:6px 2px 10px; font-family:var(--serif); font-size:1.16rem; font-weight:600; letter-spacing:-.015em; }
    .rp-cards { display:flex; flex-direction:column; gap:10px; }
    .rp-card { background:var(--card); border:1px solid var(--line); border-radius:16px; padding:13px 14px 11px;
      box-shadow:0 1px 0 rgba(255,255,255,.03) inset, 0 12px 28px -22px rgba(0,0,0,.95), 0 2px 8px -6px rgba(238,127,47,.16); }
    .rp-card.rp-new { animation:rpIn 260ms cubic-bezier(.2,.7,.3,1) both; }
    @keyframes rpIn { from { opacity:0; transform:translateY(6px); } to { opacity:1; transform:none; } }
    .rp-card-top { display:flex; align-items:baseline; gap:8px; }
    .rp-card h3 { flex:1; min-width:0; margin:0; font-family:var(--serif); font-size:1.02rem; font-weight:600; line-height:1.28; letter-spacing:-.01em; }
    .rp-kind { flex:none; font-size:.62rem; font-weight:750; letter-spacing:.06em; text-transform:uppercase; color:var(--faint); }
    .rp-loc { margin:3px 0 0; color:var(--accent); font-size:.74rem; font-weight:600; }
    .rp-what { margin:6px 0 0; font-size:.86rem; line-height:1.52; color:var(--text); }
    .rp-details { margin:8px 0 0; display:grid; gap:4px; }
    .rp-details div { display:flex; gap:8px; font-size:.78rem; line-height:1.4; }
    .rp-details dt { flex:none; min-width:68px; max-width:42%; color:var(--muted); font-weight:600; }
    .rp-details dd { margin:0; color:var(--text); }
    .rp-actions { display:flex; flex-wrap:wrap; align-items:center; gap:6px; margin-top:10px; }
    .rp-act { display:inline-flex; align-items:center; gap:5px; height:30px; padding:0 11px; border-radius:999px; text-decoration:none;
      background:var(--soft); border:1px solid var(--line); color:var(--text); font-size:.74rem; font-weight:650; transition:transform 120ms ease; }
    .rp-act svg { width:13px; height:13px; color:var(--accent); }
    .rp-act.primary { background:var(--brand-grad); border-color:transparent; color:#fff; }
    .rp-act.primary svg { color:#fff; }
    .rp-act:hover { border-color:rgba(238,127,47,.55); }
    .rp-act:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
    .rp-act:active { transform:scale(.95); }
    .rp-card-refs { margin-left:auto; display:flex; gap:4px; }
    .rp-ref.rp-watch { height:26px; margin-left:0; padding:0 8px; border-radius:999px; }
    .rp-sec-head { display:flex; align-items:flex-start; gap:10px; margin:0 0 10px; }
    .rp-sec-head h2 { flex:1; margin:0; }
    .rp-steps { counter-reset:rpstep; }
    .rp-steps li { padding-left:28px; counter-increment:rpstep; }
    .rp-steps li::before { content:counter(rpstep); width:19px; height:19px; top:.15em; display:grid; place-items:center;
      background:rgba(238,127,47,.16); color:var(--accent); font-size:.66rem; font-weight:800; }
    .folder-desc {
      color:var(--muted);
      font-size:.85rem;
      line-height:1.45;
      margin:2px 2px 14px;
      display:-webkit-box;
      -webkit-line-clamp:3;
      -webkit-box-orient:vertical;
      overflow:hidden;
    }
    .section-title.sm { font-size:1.05rem; }
    .sug-actions { display:flex; gap:8px; padding:8px 2px 2px; }
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
    .quick-actions { display:flex; gap:8px; margin-bottom:16px; }
    .quick-action { flex:1; display:grid; place-items:center; gap:6px; color:var(--muted); font-size:.68rem; font-weight:650; text-decoration:none; }
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
    /* Tactile press feedback on every tappable card/row — subtle scale-down. */
    .m-card button, .recent-card, .lib-row, .quick-action, .cat-tile {
      transition:transform .12s ease;
    }
    .m-card button:active, .recent-card:active, .lib-row:active, .quick-action:active {
      transform:scale(.97);
    }
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
    <section id="claimCard" class="claim-card" hidden aria-live="polite">
      <p id="claimTitle" class="claim-title"></p>
      <p id="claimSub" class="claim-sub"></p>
      <div id="claimAction"></div>
      <p id="claimHint" class="claim-hint" hidden></p>
      <p id="claimErr" class="claim-err" hidden></p>
      <button id="claimSkip" class="claim-skip" type="button" hidden>Not now</button>
    </section>
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
      <button id="profileNav" class="nav-button" type="button">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><circle cx="12" cy="8" r="4"/><path d="M4 20c1.8-3.4 4.5-5 8-5s6.2 1.6 8 5"/></svg>
        <span>Profile</span>
      </button>
    </nav>
  </div>
  <script>
    const USER_ID = '__USER_ID__';
    const SHOW_COLLECTIONS = '__SHOW_COLLECTIONS__' === '1';
    const SHOW_RECIPES = '__SHOW_RECIPES__' === '1';
    const SHOW_REPORT = '__SHOW_REPORT__' === '1';
    const state = {
      data: [],
      recents: [],
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
    // Loader: the actual 3D mascot from the logo (transparent cutout), pulsing.
    const REPORT_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z"/><path d="M14 3v5h5"/><path d="M9 13h6M9 17h4"/></svg>';
    const LOADER_HTML = '<div class="load-wrap"><span class="spinner" aria-label="Loading"></span></div>';
    const CHEV_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m9 6 6 6-6 6"/></svg>';
    const BACK_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 6-6 6 6 6"/></svg>';
    const ARROW_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="m13 6 6 6-6 6"/></svg>';
    const REFRESH_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 1 0-2.3 6.3"/><path d="M20 5v6h-6"/></svg>';
    const MAP_PIN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0z"/><circle cx="12" cy="10" r="3"/></svg>';
    const RECIPES_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 11a8 8 0 0 1 16 0"/><path d="M2 11h20"/><path d="M4 11v3a8 4 0 0 0 16 0v-3"/><path d="M12 3v2"/></svg>';
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
      [/groom|beauty|skin|makeup|hair|personal care/i, '✨'],
      [/software|code|app|ai |artificial|computer|tech/i, '💻'],
      [/product|shop|buy|gadget/i, '🛍️'],
      [/recipe|food|cook|craving|snack|street/i, '🍲'],
      [/place|travel|trip|city|location/i, '🗺️'],
      [/fitness|workout|gym|sport|swim|exercise/i, '💪'],
      [/meme|funny|laugh|humor|comedy/i, '😂'],
      [/fashion|outfit|style|wear/i, '👕'],
      [/film|movie|tv|show|series/i, '🎬'],
      [/music|song|album/i, '🎵'],
      [/book|read|learn|tutorial|study/i, '📘'],
      [/(^|[^a-z])(car|cars|bike|bikes|auto|driving)([^a-z]|$)/i, '🏎️'],
      [/game|gaming|play/i, '🎮'],
      [/finance|money|invest|business/i, '💸'],
      [/hobby|diy|craft|build/i, '🧩'],
    ];
    // A generated logo wins over the keyword guess. The guess only ever ran on
    // hand-written folder names; with names the model invents it misfires —
    // "Grooming & Personal Care" matched /car/ and drew a racing car.
    function iconMarkup(list) {
      const url = list && list.icon_url;
      if (url) return '<img class="lib-logo" src="' + url + '" alt="" />';
      return emojiFor(list && (list.parent_title || list.list_title));
    }
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
    // Placeholder gradients stay inside the brand family (purples, violets,
    // magentas on near-black) so empty cards still look like ClipNest.
    const PH_PALETTES = [
      ['#2b2018', '#5c4327'], ['#33241a', '#6e4a2b'], ['#241d18', '#4d3a2a'],
      ['#2e1e12', '#63401f'], ['#26211c', '#514436'], ['#301c10', '#6b4a24'],
      ['#221a14', '#48362a'], ['#2c2216', '#5d4426'],
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
      const isVideo = Boolean(src) && /\\.mp4($|[?#])/i.test(src);
      const isImage = Boolean(src) && !isVideo;
      const label = item.name || item.list_title || 'reel';
      // Images flow at natural height (dense masonry). Video-only and empty
      // cells keep a fixed aspect AND a visible ▶ glyph — an unloaded <video>
      // paints as a solid black rectangle on iOS, which reads as dead space.
      const media = src ? renderMedia(item, loading) : '';
      const glyph = isImage ? '' : '<span class="ph-glyph">▶</span>';
      return `<span class="${className}${isImage ? ' natural' : ''}" style="background:${gradFor(label)}">${media}${glyph}${inner}</span>`;
    }
    function renderMedia(item, loading = 'lazy') {
      const src = mediaFor(item);
      if (!src) return '<div aria-hidden="true"></div>';
      if (/\\.mp4($|[?#])/i.test(src)) return `<video src="${escapeHtml(src)}#t=0.1" muted playsinline preload="metadata"></video>`;
      // On failure, fall back to the fixed-aspect gradient WITH a glyph — a
      // silently removed image left a dark block that read as dead space.
      return `<img src="${escapeHtml(src)}" alt="" loading="${loading}" onerror="this.parentNode.classList.remove('natural');this.parentNode.classList.add('broken');this.remove()" />`;
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
    // Recents are always ordered by when the reel was SAVED (received_at),
    // newest first — the rail and the full view must agree.
    function recentItems(limit = 24) {
      return allRecentsSorted().slice(0, limit);
    }
    function renderSearchBox(placeholder, value, id) {
      return `<label class="search"><span class="glyph">${SEARCH_SVG}</span><input id="${id}" type="search" value="${escapeHtml(value)}" placeholder="${escapeHtml(placeholder)}" autocomplete="off" /></label>`;
    }
    function renderChips(values, active, kind) {
      return `<div class="chips" aria-label="${kind} filters">${values.map((chip) => `<button class="chip ${chip === active ? 'active' : ''}" type="button" data-chip-kind="${kind}" data-chip="${escapeHtml(chip)}">${escapeHtml(prettyTitle(chip))}</button>`).join('')}</div>`;
    }

    /* ---------- HOME ---------- */
    function renderLibrary() {
      const folders = state.folders || [];
      const recents = recentItems(24);
      const searching = state.magicQuery.trim().length > 0;
      const status = pipelineStatus();
      app.innerHTML = `
        <div class="home-head">
          <div class="greeting-row"><span class="brand-mark" aria-hidden="true"></span><h1 class="greeting">${escapeHtml(greeting())}</h1></div>
          <div class="icon-row">
            ${SHOW_RECIPES ? `<button class="icon-button" type="button" aria-label="Your recipes" id="recipesButton">${RECIPES_SVG}</button>` : ''}
            <button class="icon-button" type="button" aria-label="Your reel map" id="mapButton">${MAP_PIN_SVG}</button>
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
        <label class="search${SHOW_REPORT && !state.selecting ? ' has-report' : ''}"><span class="glyph">${SEARCH_SVG}</span><input id="deepSearchInput" type="search" value="${escapeHtml(state.magicQuery)}" placeholder="${SHOW_REPORT && !state.selecting ? 'Search anything...' : 'Search anything you saved...'}" autocomplete="off" />${SHOW_REPORT && !state.selecting ? `<button id="reportBtn" class="search-report" type="button" aria-label="Report on these search results">${REPORT_SVG}</button>` : ''}<button id="newListBtn" class="search-plus${state.selecting ? ' active' : ''}" type="button" aria-label="New list from search">+</button></label>
        <section id="homeResults" ${searching ? '' : 'hidden'}></section>
        <div id="homeBrowse" ${searching ? 'hidden' : ''}>
          ${recents.length ? `
            <button class="section-head section-head-btn" id="openRecents" type="button"><h2 class="section-title">Recently saved <span class="chev">›</span></h2></button>
            <div class="recent-rail">${recents.map((item, index) => `
              <button class="recent-card" type="button" data-recent-item="${index}">
                ${reelThumb(item, 'recent-thumb', index < 4 ? 'eager' : 'lazy')}
                <p class="recent-source">${escapeHtml(sourceFor(item))}</p>
                <p class="recent-title">${escapeHtml(item.name)}</p>
              </button>`).join('')}</div>` : ''}
          <div class="section-head">
            <h2 class="section-title">Library</h2>
            <span class="section-side">${folders.length} ${folders.length === 1 ? 'list' : 'lists'}</span>
          </div>
          ${!state.foldersLoaded ? '<div class="empty">Loading your lists…</div>' : ''}
          ${state.foldersLoaded && folders.length ? `<section class="lib-list">${folders.map(renderFolderLibRow).join('')}</section>` : ''}
          ${state.foldersLoaded && !folders.length ? '<div class="empty">No lists yet. Search your reels and tap the ＋ in the search bar to make one.</div>' : ''}
          ${SHOW_COLLECTIONS && realFolders().length ? `
          <div class="section-head">
            <h2 class="section-title">Collections</h2>
            <span class="section-side">sorted for you</span>
          </div>
          <section class="lib-list">${realFolders().map(renderLibRow).join('')}</section>` : ''}
        </div>
      `;
      const deepInput = document.getElementById('deepSearchInput');
      deepInput?.addEventListener('input', (event) => {
        state.magicQuery = event.target.value;
        const active = state.magicQuery.trim().length > 0;
        document.getElementById('homeResults')?.toggleAttribute('hidden', !active);
        document.getElementById('homeBrowse')?.toggleAttribute('hidden', active);
        scheduleDeepSearch();
      });
      document.getElementById('reportBtn')?.addEventListener('click', () => {
        const q = state.magicQuery.trim();
        if (!q) { document.getElementById('deepSearchInput')?.focus(); return; }
        openSearchReport(q);
      });
      document.getElementById('newListBtn')?.addEventListener('click', () => {
        if (state.selecting) { exitSelect(); return; }
        if (!state.magicQuery.trim()) { document.getElementById('deepSearchInput')?.focus(); return; }
        enterSelect();
      });
      document.getElementById('openRecents')?.addEventListener('click', () => {
        state.screen = 'recents';
        window.scrollTo({ top: 0, behavior: 'instant' });
        render();
      });
      document.getElementById('mapButton')?.addEventListener('click', openReelMap);
      document.getElementById('recipesButton')?.addEventListener('click', openRecipesHub);
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
      document.getElementById('refreshButton')?.addEventListener('click', manualRefresh);
      bindChips();
      const recentsData = recentItems(24);
      app.querySelectorAll('[data-recent-item]').forEach((button) => {
        button.addEventListener('click', () => openActionSheet(recentsData[Number(button.dataset.recentItem)], Number(button.dataset.recentItem), recentsData));
      });
      app.querySelectorAll('[data-open-folder]').forEach((button) => {
        button.addEventListener('click', () => {
          state.notifOpen = false;
          window.scrollTo({ top: 0, behavior: 'instant' });
          openFolderDetail(Number(button.dataset.openFolder));
        });
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
      if (searching) {
        if (state.deepSearch.query !== state.magicQuery.trim()) scheduleDeepSearch();
        else renderSearchResults();
        if (deepInput) { deepInput.focus(); deepInput.setSelectionRange(deepInput.value.length, deepInput.value.length); }
      }
    }
    function renderLibRow(list) {
      // Folders are represented by a clean logo (emoji), never a random reel frame.
      return `<button class="lib-row" type="button" data-open-list="${escapeHtml(list.list_id)}" aria-label="Open ${escapeHtml(list.list_title)}">
        <span class="lib-icon" style="background:${gradFor(list.parent_title || list.list_title)}">${iconMarkup(list)}</span>
        <span>
          <p class="lib-name">${escapeHtml(prettyTitle(list.list_title))}</p>
          <p class="lib-meta">${list.icon_url ? '' : emojiFor(list.parent_title || list.list_title) + ' '}${list.real_count} ${list.real_count === 1 ? 'item' : 'items'}${list.parent_title ? `<span class="dot-sep">·</span>${escapeHtml(prettyTitle(list.parent_title))}` : ''}</p>
        </span>
        <span class="row-chev">${CHEV_SVG}</span>
      </button>`;
    }
    // Library rows are now the user's created smart-folders (lists).
    function renderFolderLibRow(folder) {
      const count = folder.item_count || 0;
      return `<button class="lib-row" type="button" data-open-folder="${escapeHtml(String(folder.id))}" aria-label="Open ${escapeHtml(folder.name)}">
        <span class="lib-icon" style="background:${gradFor(folder.name)}">${emojiFor(folder.name)}</span>
        <span class="lib-text">
          <p class="lib-name">${escapeHtml(folder.name)}</p>
          <p class="lib-meta">${count} ${count === 1 ? 'reel' : 'reels'}${folder.description ? `<span class="dot-sep">·</span>${escapeHtml(folder.description)}` : ''}</p>
        </span>
        <span class="row-chev">${CHEV_SVG}</span>
      </button>`;
    }

    /* ---------- RECENTLY SAVED (full view) ---------- */
    // The server sends an authoritative, already-ordered recents list (reels
    // table, newest-saved first, deterministic). We trust it verbatim — no
    // client re-sorting, so the order can't drift between refreshes.
    function allRecentsSorted() {
      if (Array.isArray(state.recents) && state.recents.length) return state.recents;
      // Fallback only if the server list is unavailable: dedupe library items.
      const seen = new Set();
      const items = [];
      for (const item of flatItems()) {
        const key = item.reel_id || item.url || item.name;
        if (!key || seen.has(key)) continue;
        seen.add(key);
        items.push(item);
      }
      const savedAt = (v) => {
        const t = Date.parse(String(v || '').trim().replace(' ', 'T'));
        return Number.isFinite(t) ? t : 0;
      };
      items.sort((a, b) => savedAt(b.received_at) - savedAt(a.received_at));
      return items;
    }
    function renderRecents() {
      const items = allRecentsSorted();
      app.innerHTML = `
        <div class="list-heading">
          <button id="recentsBack" class="back-button" type="button" aria-label="Back to home">${BACK_SVG}</button>
          <div class="list-title-block"><h1>Recently saved</h1><p class="count-text">${items.length} ${items.length === 1 ? 'reel' : 'reels'}</p></div>
          <div class="icon-row"></div>
        </div>
        ${items.length ? renderMasonry(items, renderItemCard) : '<div class="empty">Nothing saved yet.</div>'}
      `;
      document.getElementById('recentsBack').addEventListener('click', () => { state.screen = 'library'; render(); });
      app.querySelectorAll('[data-open-item]').forEach((button) => {
        button.addEventListener('click', () => openActionSheet(items[Number(button.dataset.openItem)], Number(button.dataset.openItem), items));
      });
      app.querySelectorAll('[data-item-menu]').forEach((el) => {
        el.addEventListener('click', (event) => {
          event.stopPropagation();
          openActionSheet(items[Number(el.dataset.itemMenu)], Number(el.dataset.itemMenu), items);
        });
      });
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
          ? renderMasonry(items, renderItemCard)
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
    // Split items across two columns (left/right alternating so save order
    // still reads left-to-right). cardFn receives the ORIGINAL index so tap
    // handlers keep resolving into the source array.
    function renderMasonry(items, cardFn) {
      const cols = [[], []];
      items.forEach((item, index) => { cols[index % 2].push(cardFn(item, index)); });
      return `<section class="masonry"><div class="mas-col">${cols[0].join('')}</div><div class="mas-col">${cols[1].join('')}</div></section>`;
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
    // A search result was opened: fire and forget, never throws.
    function logSearchClick(q, item, position) {
      try {
        if (!q || !item || !item.reel_id) return;
        fetch('/deep-search/click', {
          method: 'POST', credentials: 'same-origin', keepalive: true,
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            user_id: USER_ID,
            query_id: state.deepSearch.query === q ? (state.deepSearch.queryId || null) : null,
            query: q, reel_id: item.reel_id, position,
          }),
        }).catch(() => {});
      } catch (e) {}
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
          queryId: payload.query_id || null,
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
        ${q && state.deepSearch.loading && state.deepSearch.query === q ? LOADER_HTML : ''}
        ${q && state.deepSearch.error && !results.length ? `<div class="empty">${escapeHtml(state.deepSearch.error)}</div>` : ''}
        ${q && !state.deepSearch.loading && !results.length ? '<div class="empty">No matches yet. Try a broader word.</div>' : ''}
        ${results.length ? renderMasonry(results, renderItemCard) : ''}
      `;
      state.lastSearchResults = results;
      resultList.querySelectorAll('[data-open-item]').forEach((button) => {
        button.addEventListener('click', (event) => {
          if (state.selecting) {
            event.preventDefault();
            toggleSelect(button.closest('.m-card')?.dataset.reel || '');
            return;
          }
          logSearchClick(q, results[Number(button.dataset.openItem)], Number(button.dataset.openItem));
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

    /* ---------- SEARCH REPORT (admin) ---------- */
    // The report streams in: search -> judge (which reels count) -> writer
    // (cards appear as they're written). Event frames are server-sent events
    // read off a POST, so EventSource can't be used.
    const NL = String.fromCharCode(10);
    const FRAME_END = NL + NL;
    const REPORT_KIND = { place: 'Place', activity: 'Activity', stay: 'Stay', dish: 'Dish', website: 'Website', app: 'App', product: 'Product', title: 'Watch', person: 'Person' };
    const OPEN_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M7 17 17 7"/><path d="M8 7h9v9"/></svg>';
    const SHARE_SVG = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v12"/><path d="m7 8 5-5 5 5"/><path d="M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/></svg>';
    const ACTION_ICON = { Map: MAP_PIN_SVG, Open: OPEN_SVG, Search: SEARCH_SVG };
    function openSearchReport(query) {
      let ov = document.getElementById('reportOverlay');
      if (!ov) {
        ov = document.createElement('div');
        ov.id = 'reportOverlay'; ov.className = 'recipes-overlay report-overlay';
        document.body.appendChild(ov);
      }
      state.report = { query, include: [], exclude: [], data: null, live: null, skippedOpen: false };
      ov.classList.add('show');
      ov.scrollTop = 0;
      loadSearchReport();
    }
    function closeSearchReport() {
      document.getElementById('reportOverlay')?.classList.remove('show');
      state.report = null;
    }
    function reportHead(title, canShare) {
      return '<div class="recipes-head"><button class="back-button" type="button" data-report-close aria-label="Close report">‹</button>'
        + '<h1>' + escapeHtml(title) + '</h1>'
        + (canShare ? '<button class="rp-share" type="button" data-report-share aria-label="Share this report">' + SHARE_SVG + '</button>' : '')
        + '</div>';
    }
    function splitFrames(text) {
      return text.split(FRAME_END).map((f) => f.trim()).filter((f) => f.indexOf('data:') === 0)
        .map((f) => { try { return JSON.parse(f.slice(5)); } catch (_) { return null; } })
        .filter(Boolean);
    }
    async function loadSearchReport() {
      const ov = document.getElementById('reportOverlay');
      const r = state.report;
      if (!ov || !r) return;
      r.data = null; r.error = ''; r.live = { stage: 'searching', shown: 0 };
      renderReportProgress();
      try {
        const res = await fetch('/api/search-report/stream', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
          body: JSON.stringify({ user_id: USER_ID, query: r.query, include: r.include, exclude: r.exclude }) });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || 'Could not make the report.');
        }
        if (res.body && res.body.getReader) {
          const reader = res.body.getReader();
          const decoder = new TextDecoder();
          let buf = '';
          for (;;) {
            const { value, done } = await reader.read();
            if (state.report !== r) { reader.cancel().catch(() => {}); return; }
            if (done) break;
            buf += decoder.decode(value, { stream: true });
            const cut = buf.lastIndexOf(FRAME_END);
            if (cut < 0) continue;
            splitFrames(buf.slice(0, cut)).forEach((ev) => handleReportEvent(r, ev));
            buf = buf.slice(cut + FRAME_END.length);
          }
          if (buf.trim()) splitFrames(buf).forEach((ev) => handleReportEvent(r, ev));
        } else {
          splitFrames(await res.text()).forEach((ev) => handleReportEvent(r, ev));
        }
        if (state.report === r && !r.data) throw new Error(r.error || 'Could not make the report.');
      } catch (e) {
        if (state.report !== r) return;
        r.live = null;
        ov.innerHTML = '<div class="recipes-shell">' + reportHead('Report', false)
          + '<div class="empty">' + escapeHtml(e.message || 'Could not make the report.') + '</div>'
          + '<button class="rp-update" type="button" id="reportRetry">Try again</button></div>';
        ov.querySelector('[data-report-close]').addEventListener('click', closeSearchReport);
        ov.querySelector('#reportRetry').addEventListener('click', loadSearchReport);
      }
    }
    function handleReportEvent(r, ev) {
      if (state.report !== r) return;
      if (ev.event === 'judging') {
        r.live = { ...r.live, stage: 'judging', candidates: ev.candidates, reading: ev.reels || [] };
        renderReportProgress();
      } else if (ev.event === 'judged') {
        r.live = { ...r.live, stage: 'writing', used: ev.used || [] };
        renderReportProgress();
      } else if (ev.event === 'partial') {
        r.live = { ...r.live, stage: 'writing', partial: ev.report };
        renderReportProgress();
      } else if (ev.event === 'done') {
        r.live = null;
        r.data = ev.report;
        if (ev.report.status !== 'ok') r.skippedOpen = true;
        r.pendingInclude = new Set(r.include);
        r.pendingExclude = new Set(r.exclude);
        renderSearchReport();
      } else if (ev.event === 'error') {
        r.error = ev.detail || '';
      }
    }
    function safeHref(href) {
      return /^https?:[/][/]/i.test(href || '') ? href : '';
    }
    function refButtons(refs, cls) {
      return (refs || []).map((n) => '<button class="rp-ref' + (cls || '') + '" type="button" data-rp-ref="' + n + '" aria-label="Watch reel ' + n + '">' + (cls ? '▶ ' : '') + n + '</button>').join('');
    }
    // `fresh` = index from which cards are new this render, so only newly
    // streamed cards animate in (re-rendering never replays old ones).
    function reportBlocksHtml(blocks, fresh) {
      let idx = 0;
      const html = (blocks || []).map((b) => {
        const head = b.heading ? '<h2>' + escapeHtml(b.heading) + '</h2>' : '';
        if (b.type === 'cards') {
          return '<section class="rp-block">' + head + '<div class="rp-cards">'
            + b.items.map((c) => reportCardHtml(c, fresh !== undefined && idx++ >= fresh)).join('') + '</div></section>';
        }
        const tag = b.type === 'steps' ? 'ol' : 'ul';
        // Every item from the same reel(s): cite once by the heading, not per line.
        const key = (p) => (p.refs || []).join(',');
        const shared = b.items.length > 1 && b.items.every((p) => key(p) === key(b.items[0]));
        const top = shared
          ? '<div class="rp-sec-head">' + (b.heading ? '<h2>' + escapeHtml(b.heading) + '</h2>' : '<span></span>') + '<span class="rp-card-refs">' + refButtons(b.items[0].refs, ' rp-watch') + '</span></div>'
          : head;
        return '<section class="rp-section">' + top + '<' + tag + ' class="rp-points' + (b.type === 'steps' ? ' rp-steps' : '') + '">'
          + b.items.map((p) => '<li>' + escapeHtml(p.text) + (shared ? '' : refButtons(p.refs)) + '</li>').join('')
          + '</' + tag + '></section>';
      }).join('');
      return { html, cards: idx };
    }
    function reportCardHtml(c, isNew) {
      const kind = REPORT_KIND[c.kind] || '';
      const actions = (c.actions || []).filter((a) => safeHref(a.href));
      return '<article class="rp-card' + (isNew ? ' rp-new' : '') + '">'
        + '<div class="rp-card-top"><h3>' + escapeHtml(c.name) + '</h3>' + (kind ? '<span class="rp-kind">' + kind + '</span>' : '') + '</div>'
        + (c.location ? '<p class="rp-loc">' + escapeHtml(c.location) + '</p>' : '')
        + (c.what ? '<p class="rp-what">' + escapeHtml(c.what) + '</p>' : '')
        + (c.details && c.details.length ? '<dl class="rp-details">' + c.details.map((d) => '<div><dt>' + escapeHtml(d[0]) + '</dt><dd>' + escapeHtml(d[1]) + '</dd></div>').join('') + '</dl>' : '')
        + '<div class="rp-actions">'
        + actions.map((a) => '<a class="rp-act' + (a.label === 'Open' ? ' primary' : '') + '" href="' + escapeHtml(a.href) + '" target="_blank" rel="noopener noreferrer">' + (ACTION_ICON[a.label] || '') + '<span>' + escapeHtml(a.label) + '</span></a>').join('')
        + '<span class="rp-card-refs">' + refButtons(c.refs, ' rp-watch') + '</span>'
        + '</div></article>';
    }
    function bindReportRefs(ov, items) {
      ov.querySelectorAll('[data-rp-ref]').forEach((b) => b.addEventListener('click', () => {
        const n = Number(b.dataset.rpRef);
        if (items[n - 1]) openMiniPlayer(items[n - 1], n - 1, items);
      }));
    }
    function renderReportProgress() {
      const ov = document.getElementById('reportOverlay');
      const r = state.report;
      if (!ov || !r || !r.live) return;
      const L = r.live;
      const used = (L.used || []).map(deepSearchItem);
      let html = '<div class="recipes-shell">' + reportHead((L.partial && L.partial.title) || 'Report', false);
      if (L.stage === 'searching') {
        html += '<p class="recipes-sub">Searching your reels for “' + escapeHtml(r.query) + '”…</p>' + LOADER_HTML;
      } else if (L.stage === 'judging') {
        html += '<p class="recipes-sub">Reading ' + L.candidates + ' reels to find the ones about “' + escapeHtml(r.query) + '”…</p>';
        const reading = (L.reading || []).map(deepSearchItem);
        html += reading.length
          ? '<div class="rp-strip reading">' + reading.map((it, i) => '<span class="rp-strip-item" style="animation-delay:' + ((i % 8) * 90) + 'ms">' + reelThumb(it, 'rp-thumb') + '</span>').join('') + '</div>'
          : LOADER_HTML;
      } else {
        html += '<p class="recipes-sub">' + (used.length
          ? 'Found ' + used.length + ' reel' + (used.length === 1 ? '' : 's') + ' about “' + escapeHtml(r.query) + '”'
          : 'None of your reels answer this') + '</p>';
        if (used.length) {
          html += '<div class="rp-strip">' + used.map((it, i) => '<button class="rp-strip-item" type="button" data-rp-ref="' + (i + 1) + '" aria-label="Watch reel ' + (i + 1) + '">'
            + reelThumb(it, 'rp-thumb', 'lazy', '<span class="rp-num">' + (i + 1) + '</span>') + '</button>').join('') + '</div>';
        }
        if (L.partial) {
          if (L.partial.intro) html += '<p class="rp-summary">' + escapeHtml(L.partial.intro) + '</p>';
          const built = reportBlocksHtml(L.partial.blocks, L.shown || 0);
          html += built.html;
          L.shown = built.cards;
        }
        if (used.length) html += '<div class="rp-writing"><span class="rp-dot" aria-hidden="true"></span>Writing your report…</div>';
      }
      html += '</div>';
      const keep = ov.scrollTop;
      ov.innerHTML = html;
      ov.scrollTop = keep;
      ov.querySelector('[data-report-close]').addEventListener('click', closeSearchReport);
      bindReportRefs(ov, used);
    }
    function reportPlainText(d) {
      // Shared as the user's own message: no dashes (they read as AI-written).
      const clean = (t) => String(t || '').replace(/ +[—–] +/g, ', ').replace(/[—–]/g, '-');
      const lines = [clean(d.title)];
      if (d.intro) lines.push(clean(d.intro));
      (d.blocks || []).forEach((b) => {
        lines.push('');
        if (b.heading) lines.push(clean(b.heading).toUpperCase());
        b.items.forEach((it, i) => {
          if (b.type === 'cards') {
            const facts = (it.details || []).map((x) => clean(x[0]) + ': ' + clean(x[1])).join(', ');
            const link = (it.actions || []).find((a) => safeHref(a.href));
            lines.push('• ' + clean(it.name) + (it.location ? ' (' + clean(it.location) + ')' : '') + (it.what ? ': ' + clean(it.what) : '')
              + (facts ? '. ' + facts : '') + (link ? NL + '  ' + link.href : ''));
          } else {
            lines.push((b.type === 'steps' ? (i + 1) + '. ' : '• ') + clean(it.text));
          }
        });
      });
      lines.push('', 'Made with ClipNest from my saved reels');
      return lines.join(NL);
    }
    function shareReport(button) {
      const d = state.report && state.report.data;
      if (!d) return;
      const text = reportPlainText(d);
      if (navigator.share) { navigator.share({ title: d.title, text }).catch(() => {}); return; }
      const done = () => { button.classList.add('done'); setTimeout(() => button.classList.remove('done'), 1400); };
      if (navigator.clipboard?.writeText) navigator.clipboard.writeText(text).then(done).catch(() => legacyCopy(text, done, () => {}));
      else legacyCopy(text, done, () => {});
    }
    function reportDirty(r) {
      const same = (set, list) => set.size === list.length && list.every((id) => set.has(id));
      return !same(r.pendingInclude, r.include) || !same(r.pendingExclude, r.exclude);
    }
    function reportReelRow(item, i, kind, why, state_) {
      const num = kind === 'used' ? '<span class="rp-num">' + (i + 1) + '</span>' : '';
      const label = kind === 'used'
        ? (state_ === 'off' ? 'Put this reel back' : 'Leave this reel out')
        : (state_ === 'picked' ? 'Undo adding this reel' : 'Add this reel to the report');
      const glyph = kind === 'used' ? (state_ === 'off' ? '↺' : '✕') : (state_ === 'picked' ? '✓' : '+');
      return '<div class="rp-reel ' + state_ + '">'
        + '<button class="rp-open" type="button" data-rp-open="' + kind + ':' + i + '">'
        + reelThumb(item, 'rp-thumb', 'lazy', num)
        + '<span class="rp-meta"><span class="rp-name">' + escapeHtml(item.name) + '</span>'
        + (why ? '<span class="rp-why">' + escapeHtml(why) + '</span>' : '') + '</span></button>'
        + '<button class="rp-toggle" type="button" data-rp-toggle="' + kind + ':' + i + '" aria-label="' + label + '">' + glyph + '</button></div>';
    }
    function renderSearchReport() {
      const ov = document.getElementById('reportOverlay');
      const r = state.report;
      if (!ov || !r || !r.data) return;
      const d = r.data;
      const usedRaw = d.used || [];
      const skippedRaw = d.skipped || [];
      const used = usedRaw.map(deepSearchItem);
      const skipped = skippedRaw.map(deepSearchItem);
      const total = used.length + skippedRaw.filter((s) => s.why !== 'Removed by you').length;
      let html = '<div class="recipes-shell">' + reportHead(d.title || r.query, d.status === 'ok')
        + '<p class="recipes-sub">From ' + used.length + ' of ' + total + ' reels for “' + escapeHtml(r.query) + '”</p>';
      if (d.status === 'empty') {
        html += '<div class="empty">Nothing in your library matches “' + escapeHtml(r.query) + '” yet.</div>';
      } else if (d.status !== 'ok') {
        html += '<div class="empty">None of these reels say anything specific about “' + escapeHtml(r.query) + '”. Add any that should count from the list below.</div>';
      }
      if (d.intro) html += '<p class="rp-summary">' + escapeHtml(d.intro) + '</p>';
      html += reportBlocksHtml(d.blocks).html;
      if (d.gaps) html += '<p class="rp-gaps">' + escapeHtml(d.gaps) + '</p>';
      if (used.length) {
        html += '<p class="rp-label">Reels in this report</p><div class="rp-reels">'
          + used.map((it, i) => reportReelRow(it, i, 'used', '', r.pendingExclude.has(usedRaw[i].reel_id) ? 'off' : '')).join('')
          + '</div>';
      }
      if (skipped.length) {
        html += '<details class="rp-skipped"' + (r.skippedOpen ? ' open' : '') + '><summary class="rp-label"><span class="chev">›</span> Skipped ' + skipped.length + '</summary><div class="rp-reels">'
          + skipped.map((it, i) => reportReelRow(it, i, 'skipped', skippedRaw[i].why || '', r.pendingInclude.has(skippedRaw[i].reel_id) ? 'picked' : '')).join('')
          + '</div></details>';
      }
      if (reportDirty(r)) html += '<button class="rp-update" type="button" id="reportUpdate">Update report</button>';
      html += '</div>';
      const keep = ov.scrollTop;
      ov.innerHTML = html;
      ov.scrollTop = keep;
      ov.querySelector('[data-report-close]').addEventListener('click', closeSearchReport);
      ov.querySelector('[data-report-share]')?.addEventListener('click', (e) => shareReport(e.currentTarget));
      ov.querySelector('.rp-skipped')?.addEventListener('toggle', (e) => { r.skippedOpen = e.target.open; });
      bindReportRefs(ov, used);
      ov.querySelectorAll('[data-rp-open]').forEach((b) => b.addEventListener('click', () => {
        const [kind, i] = b.dataset.rpOpen.split(':');
        const list = kind === 'used' ? used : skipped;
        openMiniPlayer(list[Number(i)], Number(i), list);
      }));
      ov.querySelectorAll('[data-rp-toggle]').forEach((b) => b.addEventListener('click', () => {
        const [kind, i] = b.dataset.rpToggle.split(':');
        const id = (kind === 'used' ? usedRaw : skippedRaw)[Number(i)].reel_id;
        if (kind === 'used') {
          if (r.pendingExclude.has(id)) {
            r.pendingExclude.delete(id);
            if (r.include.includes(id)) r.pendingInclude.add(id);
          } else {
            r.pendingExclude.add(id);
            r.pendingInclude.delete(id);
          }
        } else if (r.pendingInclude.has(id)) {
          r.pendingInclude.delete(id);
          if (r.exclude.includes(id)) r.pendingExclude.add(id);
        } else {
          r.pendingInclude.add(id);
          r.pendingExclude.delete(id);
        }
        renderSearchReport();
      }));
      ov.querySelector('#reportUpdate')?.addEventListener('click', () => {
        r.include = [...r.pendingInclude];
        r.exclude = [...r.pendingExclude];
        ov.scrollTop = 0;
        loadSearchReport();
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
      const q = state.magicQuery.trim();
      document.getElementById('createSub').textContent = `${state.selectedReels.length} reels · from "${q}"`;
      let name = q, desc = '', drafted = false;
      try {
        const r = await fetch('/folders/suggest', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
          body: JSON.stringify({ user_id: USER_ID, query: q, reel_ids: state.selectedReels }) });
        if (r.ok) {
          const d = await r.json();
          if (d.name) name = d.name;
          if (d.description) { desc = d.description; drafted = true; }
        }
      } catch (e) {}
      if (!desc) desc = 'Reels about ' + q + '.';
      document.getElementById('createName').value = name;
      document.getElementById('createDesc').value = desc;
      const hintEl = document.querySelector('#folderOverlay .hint');
      if (hintEl) hintEl.textContent = drafted
        ? 'AI draft — edit freely. The description is the rule for what auto-joins later.'
        : 'Could not reach the AI just now, so we added starter text. Edit it to describe what belongs.';
      document.getElementById('createDrafting').style.display = 'none';
      document.getElementById('createForm').style.display = 'block';
    }
    async function submitCreate() {
      const name = document.getElementById('createName').value.trim();
      const description = document.getElementById('createDesc').value.trim();
      if (!name || !description) return;
      const btn = document.getElementById('createSubmit');
      btn.disabled = true; btn.textContent = 'Creating…';
      const hintEl = document.querySelector('#folderOverlay .hint');
      try {
        const r = await fetch('/folders', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
          body: JSON.stringify({ user_id: USER_ID, query: state.magicQuery.trim(), name, description, reel_ids: state.selectedReels }) });
        if (!r.ok) throw new Error('server ' + r.status);
        document.getElementById('folderOverlay').classList.remove('show');
        exitSelect();
        state.foldersLoaded = false;
        await loadFolders();
        setNav('library');
      } catch (e) {
        if (hintEl) hintEl.textContent = 'Could not create the list (' + (e.message || 'error') + '). Try again.';
      } finally {
        btn.disabled = false; btn.textContent = 'Create list';
      }
    }
    async function loadFolders() {
      const before = state.foldersLoaded ? JSON.stringify(state.folders) : null;
      try {
        const r = await fetch(`/folders?user_id=${encodeURIComponent(USER_ID)}`, { credentials: 'same-origin' });
        const d = await r.json();
        state.folders = d.folders || [];
      } catch (e) { state.folders = []; }
      state.foldersLoaded = true;
      // Only repaint Home when the list content actually changed — background
      // polls must not rebuild the screen mid-interaction.
      const changed = before === null || before !== JSON.stringify(state.folders);
      if (changed && state.screen === 'library' && !state.selecting) render();
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
      state.screen = 'folderDetail';
      state.folderDetail = null;
      render();
      try {
        const r = await fetch(`/folders/${id}?user_id=${encodeURIComponent(USER_ID)}`, { credentials: 'same-origin' });
        state.folderDetail = await r.json();
      } catch (e) { state.folderDetail = null; }
      renderFolderDetail();
    }
    // Folder reels render as real thumbnail cards (same look as search/recents).
    function folderItemRow(m, suggested, index) {
      return `<article class="m-card" data-reel="${escapeHtml(m.reel_id || '')}">`
        + `<button style="width:100%;text-align:left" type="button" data-fitem="${suggested ? 's' : 'm'}-${index}" aria-label="Preview ${escapeHtml(m.name || 'reel')}">`
        + reelThumb(m, 'm-thumb', 'lazy', `<span class="m-badges">${videoFor(m) ? '<span class="badge-dot">▶</span>' : ''}</span>`)
        + `<span class="m-title-row"><p class="m-title">${escapeHtml(m.name || 'Saved reel')}${suggested ? '<span class="sug-chip">suggested</span>' : ''}</p></span>`
        + (m.summary ? `<p class="m-summary">${escapeHtml(m.summary)}</p>` : '') + '</button>'
        + (suggested ? '<div class="sug-actions">'
          + `<button class="newlist-btn" type="button" data-accept="${escapeHtml(m.reel_id)}">Add</button>`
          + `<button class="newlist-btn ghost" type="button" data-reject="${escapeHtml(m.reel_id)}">Skip</button></div>` : '')
        + '</article>';
    }
    function renderFolderDetail() {
      const f = state.folderDetail;
      const backTo = () => { state.folderDetail = null; state.screen = 'library'; render(); window.scrollTo({ top: 0, behavior: 'instant' }); };
      if (!f) {
        app.innerHTML = '<div class="list-heading"><button id="folderBack" class="back-button" type="button" aria-label="Back to library">' + BACK_SVG
          + '</button><div class="list-title-block"></div><div class="icon-row"></div></div>'
          + LOADER_HTML;
        document.getElementById('folderBack').addEventListener('click', backTo);
        return;
      }
      const norm = (m) => ({ ...m, name: m.name || m.item_name || 'Saved reel' });
      const members = (f.members || []).map(norm);
      const suggestions = (f.suggestions || []).map(norm);
      const memberCount = members.length;
      app.innerHTML = '<div class="list-heading">'
        + '<button id="folderBack" class="back-button" type="button" aria-label="Back to library">' + BACK_SVG + '</button>'
        + `<div class="list-title-block"><h1>${escapeHtml(f.name)}</h1><p class="count-text">${memberCount} ${memberCount === 1 ? 'reel' : 'reels'}</p></div>`
        + '<span style="display:flex;gap:8px">'
        + '<button class="newlist-btn ghost" id="folderRescan" type="button" title="Re-check your saved reels against this list">↻</button>'
        + '<button class="newlist-btn ghost" id="folderDelete" type="button" style="color:#e0736b;border-color:rgba(224,115,107,.5)">Delete</button></span></div>'
        + (f.description ? `<p class="folder-desc">${escapeHtml(f.description)}</p>` : '')
        + (suggestions.length ? '<div class="section-head"><h2 class="section-title sm">Suggested for this list</h2></div>'
          + renderMasonry(suggestions, (m, i) => folderItemRow(m, true, i)) : '')
        + `<div class="section-head"><h2 class="section-title sm">In this list</h2><span class="section-side">${memberCount} ${memberCount === 1 ? 'reel' : 'reels'}</span></div>`
        + (memberCount ? renderMasonry(members, (m, i) => folderItemRow(m, false, i)) : '<div class="empty">No reels yet.</div>');
      document.getElementById('folderBack').addEventListener('click', backTo);
      document.getElementById('folderRescan').addEventListener('click', async () => {
        const b = document.getElementById('folderRescan');
        b.disabled = true; b.textContent = '…';
        try {
          const r = await fetch(`/folders/${f.id}/rescan`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
            body: JSON.stringify({ user_id: USER_ID }) });
          if (r.ok) { state.folderDetail = await r.json(); renderFolderDetail(); return; }
        } catch (e) {}
        b.disabled = false; b.textContent = '↻';
      });
      document.getElementById('folderDelete').addEventListener('click', async () => {
        if (!confirm('Delete "' + f.name + '"? Your reels stay saved — only the folder is removed.')) return;
        try { await fetch(`/folders/${f.id}?user_id=${encodeURIComponent(USER_ID)}`, { method: 'DELETE', credentials: 'same-origin' }); } catch (e) {}
        state.folderDetail = null; state.foldersLoaded = false; state.screen = 'library'; await loadFolders(); render();
      });
      app.querySelectorAll('[data-fitem]').forEach((b) => b.addEventListener('click', () => {
        const [kind, idx] = b.dataset.fitem.split('-');
        const arr = kind === 's' ? suggestions : members;
        openActionSheet(arr[Number(idx)], Number(idx), arr);
      }));
      app.querySelectorAll('[data-accept]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); folderDecide(f.id, b.dataset.accept, 'accept'); }));
      app.querySelectorAll('[data-reject]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); folderDecide(f.id, b.dataset.reject, 'reject'); }));
    }
    async function folderDecide(id, reel, action) {
      await fetch(`/folders/${id}/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
        body: JSON.stringify({ user_id: USER_ID, reel_id: reel }) });
      // The skip itself is already saved; the why-prompt is optional and
      // non-blocking — answering it teaches the list (negative example for
      // the router), dismissing it costs nothing.
      if (action === 'reject') openSkipWhy(id, reel);
      await openFolderDetail(id);
    }
    function openSkipWhy(folderId, reelId) {
      document.getElementById('skipWhy')?.remove();
      const ov = document.createElement('div');
      ov.id = 'skipWhy'; ov.className = 'folder-overlay show';
      ov.innerHTML = '<div class="folder-modal"><h3>Skipped</h3>'
        + '<div class="sub">Why not this one? Your answer teaches this list what belongs.</div>'
        + '<div class="skip-chips">'
        + '<button class="newlist-btn ghost" type="button" data-why="Different topic">Different topic</button>'
        + '<button class="newlist-btn ghost" type="button" data-why="Related, but not what this list is about">Related, not this</button>'
        + '<button class="newlist-btn ghost" type="button" data-why="Just do not want this one here">Just this one</button></div>'
        + '<label>Or say it in your own words</label>'
        + '<input id="skipWhyText" type="text" placeholder="e.g. remedies are not restaurants" />'
        + '<div class="row"><button class="newlist-btn ghost" id="skipWhyClose" type="button">No reason</button>'
        + '<button class="newlist-btn" id="skipWhySave" type="button">Save</button></div></div>';
      document.body.appendChild(ov);
      const send = async (reason) => {
        ov.remove();
        if (!reason) return;
        try {
          await fetch(`/folders/${folderId}/reject`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
            body: JSON.stringify({ user_id: USER_ID, reel_id: reelId, reason }) });
        } catch (e) {}
      };
      ov.querySelectorAll('[data-why]').forEach((b) => b.addEventListener('click', () => send(b.dataset.why)));
      document.getElementById('skipWhySave').addEventListener('click', () => send(document.getElementById('skipWhyText').value.trim()));
      document.getElementById('skipWhyClose').addEventListener('click', () => send(''));
    }

    /* ---------- REEL MAP (in-app overlay) ---------- */
    let leafletPromise = null;
    function loadLeaflet() {
      if (window.L) return Promise.resolve();
      if (leafletPromise) return leafletPromise;
      leafletPromise = new Promise((resolve, reject) => {
        const css = document.createElement('link');
        css.rel = 'stylesheet'; css.href = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css';
        document.head.appendChild(css);
        const s = document.createElement('script');
        s.src = 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js';
        s.onload = resolve; s.onerror = reject;
        document.head.appendChild(s);
      });
      return leafletPromise;
    }
    function ensureMapDom() {
      if (document.getElementById('mapOverlay')) return;
      const ov = document.createElement('div');
      ov.id = 'mapOverlay'; ov.className = 'map-overlay';
      ov.innerHTML = '<div id="reelMap"></div>'
        + '<span class="map-doodle" style="top:84px;right:70px;animation-delay:0s">☁️</span>'
        + '<span class="map-doodle" style="bottom:120px;left:26px;animation-delay:1.6s;font-size:28px">☁️</span>'
        + '<span class="map-doodle" style="bottom:60px;right:30px;animation-delay:.8s">🎈</span>'
        + '<span class="map-doodle" style="top:90px;left:50%;animation-delay:2.2s;font-size:30px">✈️</span>'
        + '<div class="map-hud"><h2>🌍 Your Reel World</h2><p id="mapStat">finding your places…</p></div>'
        + '<button id="mapClose" class="map-close" type="button" aria-label="Close map">✕</button>'
        + '<div id="mapEmpty" class="map-empty" hidden>No places yet! 🧭<br><span>Save reels about cities, food spots or trips and they pop up here.</span></div>';
      document.body.appendChild(ov);
      document.getElementById('mapClose').addEventListener('click', closeReelMap);
    }
    function closeReelMap() { document.getElementById('mapOverlay')?.classList.remove('show'); }
    function mapEmojiFor(cats) {
      if (/food|recipe|restaurant|cafe|street/i.test(cats)) return '🍜';
      if (/stay|hotel|accommodation|rental|resort/i.test(cats)) return '🛏️';
      if (/travel|destination|place|beach/i.test(cats)) return '🏖️';
      return '📍';
    }
    async function openReelMap() {
      ensureMapDom();
      document.getElementById('mapOverlay').classList.add('show');
      try { await loadLeaflet(); } catch (e) {
        document.getElementById('mapStat').textContent = 'map could not load 😢 — check internet'; return;
      }
      if (state.reelMap) { setTimeout(() => state.reelMap.invalidateSize(), 120); return; }
      const map = L.map('reelMap', { zoomControl: false, minZoom: 3, worldCopyJump: true }).setView([21, 78], 4);
      state.reelMap = map;
      // CARTO key-gated its raster basemaps: keyless requests still return 200 OK,
      // but every tile is an "API KEY REQUIRED" placeholder, so nothing errors and
      // the map silently renders as grey watermarks. OSM standard tiles are keyless
      // and permitted for a website basemap; the CSS filter above darkens them.
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a> contributors',
        maxZoom: 19,
      }).addTo(map);
      try {
        const res = await fetch('/api/map-data?user_id=' + encodeURIComponent(USER_ID), { credentials: 'same-origin' });
        const data = await res.json();
        const pins = data.pins || [];
        const groups = {};
        for (const p of pins) {
          (groups[p.place] ||= { lat: p.lat, lng: p.lng, place: p.place, cats: '', reels: [] }).reels.push(p);
          groups[p.place].cats += ' ' + (p.category || '');
        }
        const keys = Object.keys(groups);
        document.getElementById('mapStat').textContent = keys.length
          ? pins.length + ' reels · ' + keys.length + ' places 🎉'
          : 'no pins yet';
        if (!keys.length) { document.getElementById('mapEmpty').hidden = false; return; }
        document.getElementById('mapEmpty').hidden = true;
        const bounds = [];
        const routePts = [];
        let delay = 0;
        for (const key of keys.sort((a, b) => groups[a].lng - groups[b].lng)) {
          const g = groups[key];
          bounds.push([g.lat, g.lng]);
          routePts.push([g.lat, g.lng]);
          const badge = g.reels.length > 1 ? '<div class="pin-badge">' + g.reels.length + '</div>' : '';
          const icon = L.divIcon({ className: '',
            html: '<div class="pin-wrap"><div class="pin-shadow"></div><div class="pin-blob">' + mapEmojiFor(g.cats) + '</div>' + badge + '</div>',
            iconSize: [54, 60], iconAnchor: [27, 54], popupAnchor: [0, -46] });
          const list = g.reels.map(r =>
            '<div class="map-pop-item"><div class="map-pop-name">' + escapeHtml(r.item_name || r.reel_id) + '</div>'
            + (r.url ? '<a class="map-pop-link" href="' + escapeHtml(r.url) + '" target="_blank" rel="noopener">▶ watch reel</a>' : '')
            + '</div>').join('');
          const marker = L.marker([g.lat, g.lng], { icon, opacity: 0 });
          marker.addTo(map).bindPopup(
            '<div class="map-pop-place">' + escapeHtml(g.place) + '</div>'
            + '<div class="map-pop-sub">you saved ' + g.reels.length + ' reel' + (g.reels.length > 1 ? 's' : '') + ' here! 🎒</div>' + list,
            { maxWidth: 250 });
          setTimeout(() => marker.setOpacity(1), delay += 110);
        }
        if (routePts.length > 1) {
          L.polyline(routePts, { color: '#ef476f', weight: 4, dashArray: '2 12', lineCap: 'round', opacity: .85 }).addTo(map);
        }
        map.fitBounds(bounds, { padding: [70, 70], maxZoom: 6, minZoom: 3 });
        setTimeout(() => map.invalidateSize(), 150);
      } catch (e) {
        document.getElementById('mapStat').textContent = 'could not load your places 😢';
      }
    }

    /* ---------- RECIPE CARD (per-reel, in-app overlay) ---------- */
    let qGeo = { apps: {}, cities: {}, default_apps: [] };
    function captureGeo(payload) {
      if (payload && payload.apps && Object.keys(payload.apps).length) {
        qGeo = { apps: payload.apps, cities: payload.cities || {}, default_apps: payload.default_apps || [] };
      }
    }
    function cityApps() {
      const saved = localStorage.getItem('clipnest_city') || '';
      return qGeo.cities[saved] || qGeo.default_apps || [];
    }
    function appLabel(a) { return (qGeo.apps[a] || {}).label || a; }
    function appDot(a) {
      return '<span class="qc-dot" style="background:' + escapeHtml((qGeo.apps[a] || {}).color || '#888') + '"></span>';
    }
    function shopDoneKey(reelKey, appKey) { return 'cn_shop_' + reelKey + '_' + appKey; }
    function shopDoneSet(reelKey, appKey) {
      try { return new Set(JSON.parse(localStorage.getItem(shopDoneKey(reelKey, appKey)) || '[]')); }
      catch (e) { return new Set(); }
    }
    function cityPickerHtml() {
      const saved = localStorage.getItem('clipnest_city') || '';
      const names = Object.keys(qGeo.cities || {});
      if (!names.length) return '';
      const placeholder = saved ? '' : '<option value="" selected>Choose your city…</option>';
      const opts = names.map(c =>
        '<option value="' + escapeHtml(c) + '"' + (c === saved ? ' selected' : '') + '>' + escapeHtml(c) + '</option>').join('');
      return '<div class="shop-city-row"><label for="cnCity">Deliver in</label><select id="cnCity">' + placeholder + opts + '</select></div>';
    }

    function showRecipeCard(card, reelUrl, reelKey, geoPayload) {
      captureGeo(geoPayload);
      let ov = document.getElementById('recipeOverlay');
      if (!ov) {
        ov = document.createElement('div');
        ov.id = 'recipeOverlay'; ov.className = 'recipe-overlay';
        document.body.appendChild(ov);
        ov.addEventListener('click', (e) => { if (e.target === ov) ov.classList.remove('show'); });
      }
      const rid = reelKey || card.reel_id || (card.title || 'recipe').replaceAll(' ', '-');
      const shopping = card.shopping || [];
      const shoppable = shopping.filter(s => s && s.links);

      function ingredientLi(text, index) {
        const row = shopping[index] && shopping[index].links ? shopping[index] : null;
        if (!row) return '<li><span class="ing-name">' + escapeHtml(text) + '</span></li>';
        const apps = cityApps().filter(a => row.links[a]);
        const exactApps = apps.filter(a => row.exact && row.exact[a]);
        const cue = exactApps.length
          ? '<span class="ing-buy exact">exact ›</span>'
          : '<span class="ing-buy">buy ›</span>';
        const cleanName = [row.brand, row.query].filter(Boolean).join(' ');
        const exactLines = exactApps.map(a =>
          '<span class="qc-exact-line"><span class="qc-badge">EXACT</span>'
          + '<a href="' + escapeHtml(row.exact[a].url) + '" target="_blank" rel="noopener noreferrer">'
          + escapeHtml(cleanName) + ' on ' + escapeHtml(appLabel(a)) + ' ↗</a></span>').join('');
        const btns = apps.map(a =>
          '<a class="qc-btn' + (row.exact && row.exact[a] ? ' has-exact' : '') + '" target="_blank" rel="noopener noreferrer" href="'
          + escapeHtml(row.exact && row.exact[a] ? row.exact[a].url : row.links[a]) + '">'
          + appDot(a) + escapeHtml(appLabel(a))
          + (row.exact && row.exact[a] ? '<span class="qc-exact">exact</span>' : '') + '</a>').join('');
        return '<li data-shoppable="1"><span class="ing-name">' + escapeHtml(text) + '</span>' + cue
          + '<span class="ing-links">' + exactLines + btns + '</span></li>';
      }

      function shopAllHtml() {
        const items = shoppable.filter(s => !s.pantry);
        if (items.length < 2) return '';
        const btns = cityApps().filter(a => items.some(s => s.links[a])).map(a => {
          const n = items.filter(s => s.links[a]).length;
          const ex = items.filter(s => s.exact && s.exact[a]).length;
          return '<button class="shop-all-btn' + (ex ? ' has-exact' : '') + '" type="button" data-shop-app="' + a + '">'
            + appDot(a) + escapeHtml(appLabel(a)) + '<span class="qc-cnt">buy all ' + n + '</span>'
            + (ex ? '<span class="qc-exact">' + ex + ' exact</span>' : '') + '</button>';
        }).join('');
        if (!btns) return '';
        return '<h3>Shop the recipe</h3>' + cityPickerHtml() + '<div class="shop-all-row">' + btns + '</div>';
      }

      function renderCardView() {
        const ing = (card.ingredients || []).map((i, idx) => ingredientLi(i, idx)).join('');
        const steps = (card.steps || []).map(s => '<li>' + escapeHtml(s) + '</li>').join('');
        ov.innerHTML = '<div class="recipe-card">'
          + '<button class="recipe-close" type="button" aria-label="Close recipe">✕</button>'
          + '<h2>🍳 ' + escapeHtml(card.title || 'Recipe') + '</h2>'
          + '<div class="recipe-meta">'
          + (card.total_time ? '<span class="recipe-chip">⏱ ' + escapeHtml(card.total_time) + '</span>' : '')
          + (card.servings ? '<span class="recipe-chip">🍽 serves ' + escapeHtml(card.servings) + '</span>' : '')
          + '<span class="recipe-chip">🥘 ' + (card.ingredients || []).length + ' ingredients</span>'
          + '</div>'
          + shopAllHtml()
          + '<h3>Ingredients — tap to tick off' + (shoppable.length ? ', tap buy › to order' : '') + '</h3>'
          + '<ul class="recipe-ing">' + ing + '</ul>'
          + '<h3>Steps</h3><ol class="recipe-steps">' + steps + '</ol>'
          + (reelUrl ? '<a class="recipe-watch" href="' + escapeHtml(reelUrl) + '" target="_blank" rel="noopener">▶ watch the reel</a>' : '')
          + '</div>';
        ov.querySelector('.recipe-close').addEventListener('click', () => ov.classList.remove('show'));
        ov.querySelectorAll('.recipe-ing li').forEach(li => {
          const buyCue = li.querySelector('.ing-buy');
          buyCue?.addEventListener('click', (e) => { e.stopPropagation(); li.classList.toggle('shopping-open'); });
          li.addEventListener('click', (e) => {
            if (e.target.closest('.ing-links')) return;
            if (li.dataset.shoppable) { li.classList.toggle('shopping-open'); return; }
            li.classList.toggle('done');
          });
        });
        ov.querySelector('#cnCity')?.addEventListener('change', (e) => {
          localStorage.setItem('clipnest_city', e.target.value);
          renderCardView();
        });
        ov.querySelectorAll('[data-shop-app]').forEach(btn =>
          btn.addEventListener('click', () => renderShopView(btn.dataset.shopApp)));
      }

      function renderShopView(appKey) {
        const items = shoppable.filter(s => !s.pantry && s.links[appKey]);
        const done = shopDoneSet(rid, appKey);
        const rows = items.map((s, i) => {
          const exact = s.exact && s.exact[appKey];
          return '<li><a class="' + (done.has(i) ? 'done' : '') + '" data-shop-idx="' + i + '" target="_blank" rel="noopener noreferrer" href="'
            + escapeHtml(exact ? exact.url : s.links[appKey]) + '">'
            + '<span class="shop-tick">✓</span><span class="shop-nm">' + escapeHtml(s.display) + '</span>'
            + (exact ? '<span class="qc-badge">EXACT</span>' : '')
            + '<span class="shop-go">open ↗</span></a></li>';
        }).join('');
        const copyBtn = appKey === 'instamart'
          ? '<button class="shop-copy-btn" type="button" id="shopCopyBtn">📋 Copy list — paste in Instamart › Shopping List › “Write it” to fill the whole cart</button>'
          : '';
        ov.innerHTML = '<div class="recipe-card">'
          + '<div class="shop-head">'
          + '<button class="shop-back" type="button" aria-label="Back">‹</button>'
          + '<h2 style="margin:0; padding:0; font-size:1.15rem;">' + escapeHtml(appLabel(appKey)) + '</h2>'
          + '<span class="shop-prog" id="shopProg">' + done.size + '/' + items.length + ' added</span>'
          + '</div>'
          + '<p class="recipes-sub" style="margin:0 0 8px;">Tap each item — ' + escapeHtml(appLabel(appKey))
          + ' opens, hit ADD, come back. Ticks track your progress.</p>'
          + copyBtn
          + '<ul class="shop-list">' + rows + '</ul>'
          + '</div>';
        ov.querySelector('.shop-back').addEventListener('click', renderCardView);
        ov.querySelectorAll('[data-shop-idx]').forEach(a =>
          a.addEventListener('click', () => {
            const i = Number(a.dataset.shopIdx);
            const set = shopDoneSet(rid, appKey);
            set.add(i);
            localStorage.setItem(shopDoneKey(rid, appKey), JSON.stringify([...set]));
            a.classList.add('done');
            const prog = ov.querySelector('#shopProg');
            if (prog) prog.textContent = set.size + '/' + items.length + ' added';
          }));
        ov.querySelector('#shopCopyBtn')?.addEventListener('click', () => {
          const text = items.map(s => s.branded_query || s.query || s.display).join(String.fromCharCode(10));
          navigator.clipboard.writeText(text).then(() => {
            const b = ov.querySelector('#shopCopyBtn');
            b.classList.add('copied');
            b.textContent = '✓ Copied — open Instamart › Shopping List › “Write it” and paste';
          }).catch(() => {});
        });
      }

      renderCardView();
      ov.classList.add('show');
    }

    /* ---------- RECIPES HUB (all recipe cards, full-screen overlay) ---------- */
    function openRecipesHub() {
      let hub = document.getElementById('recipesHub');
      if (!hub) {
        hub = document.createElement('div');
        hub.id = 'recipesHub'; hub.className = 'recipes-overlay';
        document.body.appendChild(hub);
      }
      hub.innerHTML = '<div class="recipes-shell">'
        + '<div class="recipes-head"><button class="back-button" type="button" id="recipesBack">‹</button>'
        + '<h1>Recipes</h1></div>'
        + '<p class="recipes-sub">Cook-along reels, turned into cards you can shop</p>'
        + LOADER_HTML + '</div>';
      hub.classList.add('show');
      hub.querySelector('#recipesBack').addEventListener('click', () => hub.classList.remove('show'));
      fetch('/api/recipes?user_id=' + encodeURIComponent(USER_ID), { credentials: 'same-origin' })
        .then(r => r.json())
        .then(d => {
          captureGeo(d);
          const recipes = d.recipes || [];
          const shell = hub.querySelector('.recipes-shell');
          if (!recipes.length) {
            shell.querySelector('.load-wrap')?.remove();
            const empty = document.createElement('div');
            empty.className = 'empty';
            empty.textContent = 'No recipes yet — save a few cooking reels and they will show up here.';
            shell.appendChild(empty);
            return;
          }
          const cards = recipes.map((r, i) => {
            const exact = (r.shopping || []).filter(s => s.exact && Object.keys(s.exact).length).length;
            return '<button class="rx-card" type="button" data-rx="' + i + '">'
              + '<h2>' + escapeHtml(r.title || 'Recipe') + '</h2>'
              + '<div class="rx-meta">'
              + (r.total_time ? '<span>⏱ ' + escapeHtml(r.total_time) + '</span>' : '')
              + '<span>🥘 ' + (r.ingredients || []).length + ' ingredients</span>'
              + ((r.shopping || []).length ? '<span>🛒 shoppable</span>' : '')
              + (exact ? '<span class="rx-exact">' + exact + ' exact match' + (exact === 1 ? '' : 'es') + '</span>' : '')
              + '</div></button>';
          }).join('');
          shell.innerHTML = '<div class="recipes-head"><button class="back-button" type="button" id="recipesBack">‹</button>'
            + '<h1>Recipes</h1></div>'
            + '<p class="recipes-sub">' + recipes.length + ' cook-along reel' + (recipes.length === 1 ? '' : 's')
            + ', turned into cards you can shop</p>'
            + cityPickerHtml()
            + cards;
          shell.querySelector('#recipesBack').addEventListener('click', () => hub.classList.remove('show'));
          shell.querySelector('#cnCity')?.addEventListener('change', (e) => {
            localStorage.setItem('clipnest_city', e.target.value);
          });
          shell.querySelectorAll('[data-rx]').forEach(btn =>
            btn.addEventListener('click', () => {
              const r = recipes[Number(btn.dataset.rx)];
              showRecipeCard(r, r.url, r.reel_id, d);
            }));
        })
        .catch(() => {
          const shell = hub.querySelector('.recipes-shell');
          if (shell) shell.innerHTML += '<div class="empty">Could not load recipes. Pull to retry.</div>';
        });
    }
    function attachRecipeAction(item) {
      if (!state.session?.authenticated || !item.reel_id) return;
      fetch('/api/reel-recipe?reel_id=' + encodeURIComponent(item.reel_id) + '&user_id=' + encodeURIComponent(USER_ID), { credentials: 'same-origin' })
        .then(r => r.json())
        .then(d => {
          if (!d || d.status === 'none') return;
          const listEl = actionSheet.querySelector('.sheet-list');
          if (!listEl || document.getElementById('recipeItem')) return;
          const b = document.createElement('button');
          b.id = 'recipeItem'; b.className = 'sheet-row action'; b.type = 'button';
          b.innerHTML = '<span>🍳 ' + (d.status === 'recipe' ? 'View Recipe' : 'Get Recipe') + '</span><span>›</span>';
          listEl.insertBefore(b, listEl.firstChild);
          b.addEventListener('click', async () => {
            if (d.status === 'recipe') { showRecipeCard(d.card, item.url, item.reel_id, d); return; }
            b.disabled = true; b.firstElementChild.textContent = '🍳 Reading the reel…';
            try {
              const r = await fetch('/api/reel-recipe/extract', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
                body: JSON.stringify({ user_id: USER_ID, reel_id: item.reel_id }) });
              const out = await r.json();
              if (out.status === 'recipe') {
                d.status = 'recipe'; d.card = out.card;
                b.disabled = false; b.firstElementChild.textContent = '🍳 View Recipe';
                showRecipeCard(out.card, item.url, item.reel_id, out);
              } else if (out.error) {
                b.disabled = false; b.firstElementChild.textContent = '🍳 Could not read it right now, tap to retry';
              } else {
                b.firstElementChild.textContent = '🙅 No step-by-step recipe in this reel';
                setTimeout(() => b.remove(), 2000);
              }
            } catch (e) {
              b.disabled = false; b.firstElementChild.textContent = '🍳 Get Recipe';
            }
          });
        })
        .catch(() => {});
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
            <div class="set-row">Signed in as <span class="value">${escapeHtml(accountLabel())}</span></div>
            <div class="set-row">Email <span class="value">${escapeHtml(state.session?.user?.email || '—')}</span></div>
            <div class="set-row">App build <span class="value">__BUILD_SHA__</span></div>
            <div class="set-row">Instagram <span class="value">${instagramStatusLabel()}</span></div>
            ${renderInstagramRows()}
            <button class="set-row danger" type="button" id="logoutButton">Log out</button>
          </div>
        </section>
        ${renderAdminUsers()}
        <section class="set-section">
          <h2 class="set-title">Pipeline</h2>
          <div class="set-card">
            <div class="set-row">Sync status <span class="value">${escapeHtml(pipelineStatus().title)}</span></div>
            <div class="set-row">Pending reels <span class="value">${state.dashboard.pending_url_count || 0}</span></div>
            <div class="set-row">Failed reels <span class="value">${state.dashboard.failed_url_count || 0}</span></div>
            ${state.session?.authenticated ? '<button class="set-row action" type="button" id="retryUnsortedButton">Repair broken &amp; unsorted reels</button>' : ''}
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
      document.getElementById('profileRefresh')?.addEventListener('click', manualRefresh);
      document.getElementById('retryUnsortedButton')?.addEventListener('click', retryUnsorted);
      document.getElementById('logoutButton')?.addEventListener('click', logout);
      document.getElementById('connectInstagramButton')?.addEventListener('click', connectInstagram);
      document.getElementById('igNewCodeButton')?.addEventListener('click', connectInstagram);
      document.getElementById('igLinkDoneButton')?.addEventListener('click', loadData);
      loadAdminUsers();
    }
    async function retryUnsorted() {
      const button = document.getElementById('retryUnsortedButton');
      if (button) { button.disabled = true; button.textContent = 'Checking your library…'; }
      let broken = -1;
      try {
        const probe = await fetch(`/reels/retry-unsorted?user_id=${encodeURIComponent(USER_ID)}&dry_run=1`, { method: 'POST', credentials: 'same-origin' });
        const found = await probe.json();
        if (probe.ok) broken = Number(found.broken_count || 0);
      } catch (e) {}
      if (broken === 0) {
        window.alert('All reels look fully extracted — nothing to repair. ✓');
        if (button) { button.disabled = false; button.textContent = 'Repair broken & unsorted reels'; }
        return;
      }
      const countLine = broken > 0 ? `${broken} reel${broken === 1 ? '' : 's'} with broken or incomplete extraction found.\\n\\n` : '';
      const confirmed = window.confirm(
        countLine +
        'Reprocess them now? Each reel is downloaded and categorized again (costs a little per reel). ' +
        'If the AI key on the server is not working, they will come back broken — fix the key first.'
      );
      if (!confirmed) {
        if (button) { button.disabled = false; button.textContent = 'Repair broken & unsorted reels'; }
        return;
      }
      if (button) { button.textContent = 'Requeuing…'; }
      try {
        const response = await fetch(`/reels/retry-unsorted?user_id=${encodeURIComponent(USER_ID)}`, { method: 'POST', credentials: 'same-origin' });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.detail || 'Requeue failed');
        window.alert(`Requeued ${payload.requeued_count} reels for reprocessing. Watch progress in Activity (bell icon).` + (payload.error_count ? ` ${payload.error_count} could not be requeued.` : ''));
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
        return '';
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
    function accountLabel() {
      const user = state.session && state.session.user;
      if (!user) return USER_ID;
      return user.preferred_name || user.display_name || user.email || USER_ID;
    }
    function loginAgo(iso) {
      if (!iso) return 'never';
      const then = new Date(iso);
      if (Number.isNaN(then.getTime())) return iso;
      const mins = Math.max(0, Math.round((Date.now() - then.getTime()) / 60000));
      if (mins < 2) return 'just now';
      if (mins < 60) return mins + ' min ago';
      const hours = Math.round(mins / 60);
      if (hours < 24) return hours + 'h ago';
      const days = Math.round(hours / 24);
      return days + 'd ago';
    }
    function renderAdminUsers() {
      if (!state.session?.user?.is_admin) return '';
      const users = state.adminUsers;
      const body = !users
        ? '<div class="set-row">Loading users…</div>'
        : (users.length ? users.map((u) => {
            const name = u.name || (u.email ? u.email.split('@')[0] : u.id);
            const ig = u.instagram_connected ? (u.instagram_username ? '@' + u.instagram_username : 'IG linked') : 'no IG';
            return '<div class="set-row"><span>' + escapeHtml(name)
              + '<br><small style="color:var(--muted)">' + escapeHtml(u.email || '—') + '</small></span>'
              + '<span class="value" style="text-align:right">' + u.reel_count + ' reels · ' + escapeHtml(ig)
              + '<br><small>seen ' + escapeHtml(loginAgo(u.last_login_at)) + '</small></span></div>';
          }).join('') : '<div class="set-row">No signups yet</div>');
      const count = users ? ' · ' + users.length : '';
      return '<section class="set-section"><h2 class="set-title">People (admin' + count + ')</h2><div class="set-card">' + body + '</div></section>';
    }
    function loadAdminUsers() {
      if (!state.session?.user?.is_admin || state.adminUsers || state.adminUsersLoading) return;
      state.adminUsersLoading = true;
      fetch('/admin/users', { credentials: 'same-origin' })
        .then((response) => (response.ok ? response.json() : { users: [] }))
        .then((payload) => {
          state.adminUsers = payload.users || [];
          state.adminUsersLoading = false;
          render();
        })
        .catch(() => { state.adminUsers = []; state.adminUsersLoading = false; });
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
      const isAdmin = !!(state.session && state.session.user && state.session.user.is_admin);
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
            ${isAdmin ? '<button id="copyLinkItem" class="quick-action" type="button"><span>⧉</span>Copy Link</button>' : ''}
            <a class="quick-action" href="${escapeHtml(item.url || '#')}" target="_blank" rel="noopener"><span>↗</span>Open</a>
          </div>
          <div class="sheet-list">
            ${item.reel_id ? '<button id="addToListBtn" class="sheet-row action" type="button"><span>＋ Add to List</span><span>›</span></button>' : ''}
            ${isAdmin && item.reel_id ? '<button id="retryItem" class="sheet-row action" type="button"><span>Retry Processing</span><span>›</span></button>' : ''}
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
      document.getElementById('addToListBtn')?.addEventListener('click', () => openAddToList(item));
      attachRecipeAction(item);
      document.getElementById('shareItem').addEventListener('click', (event) => {
        const link = item.url || window.location.href;
        if (navigator.share) { navigator.share({ title: item.name, url: link }).catch(() => {}); return; }
        // No native share sheet (e.g. desktop): fall back to copying the link.
        copyItemLink(link, event.currentTarget, 'Share');
      });
      document.getElementById('copyLinkItem')?.addEventListener('click', (event) => {
        copyItemLink(item.url, event.currentTarget, 'Copy Link');
      });
    }
    async function openAddToList(item) {
      // Manual add = the user correcting the router. Deliberately NO "why"
      // prompt here (unlike Skip): the add itself is the signal, and asking
      // would punish the user for fixing our mistake.
      document.getElementById('listPick')?.remove();
      const ov = document.createElement('div');
      ov.id = 'listPick'; ov.className = 'folder-overlay show';
      ov.style.zIndex = '95';
      ov.innerHTML = '<div class="folder-modal"><h3>Add to a list</h3>'
        + '<div class="sub">' + escapeHtml(item.name || 'This reel') + '</div>'
        + '<div id="listPickRows" class="list-pick-wrap"><div class="empty">Loading your lists…</div></div>'
        + '<div class="row"><button class="newlist-btn" id="listPickDone" type="button">Done</button></div></div>';
      document.body.appendChild(ov);
      const close = () => ov.remove();
      document.getElementById('listPickDone').addEventListener('click', close);
      ov.addEventListener('click', (e) => { if (e.target === ov) close(); });
      let folders = [];
      try {
        const r = await fetch('/folders/for-reel?reel_id=' + encodeURIComponent(item.reel_id) + '&user_id=' + encodeURIComponent(USER_ID), { credentials: 'same-origin' });
        folders = (await r.json()).folders || [];
      } catch (e) {}
      const wrap = document.getElementById('listPickRows');
      if (!wrap) return;
      if (!folders.length) {
        wrap.innerHTML = '<div class="empty">No lists yet. Search your reels and tap the ＋ in the search bar to make one.</div>';
        return;
      }
      wrap.innerHTML = folders.map((f, i) =>
        '<div class="list-pick-row"><span class="list-pick-name">' + escapeHtml(f.name)
        + '<em>' + f.item_count + (f.item_count === 1 ? ' reel' : ' reels') + '</em></span>'
        + (f.state === 'member'
          ? '<span class="in-chip">✓ In</span>'
          : '<button class="newlist-btn ghost" type="button" data-addlist="' + i + '">Add</button>')
        + '</div>').join('');
      wrap.querySelectorAll('[data-addlist]').forEach((b) => b.addEventListener('click', async () => {
        const f = folders[Number(b.dataset.addlist)];
        b.disabled = true; b.textContent = '…';
        try {
          const r = await fetch('/folders/' + f.id + '/add-reel', { method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
            body: JSON.stringify({ user_id: USER_ID, reel_id: item.reel_id }) });
          if (!r.ok) throw new Error('add failed');
          b.outerHTML = '<span class="in-chip">✓ In</span>';
          state.foldersLoaded = false; loadFolders();
        } catch (e) {
          b.disabled = false; b.textContent = 'Add';
        }
      }));
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
      const response = await fetch(`/reels/${encodeURIComponent(item.reel_id)}`, { method: 'DELETE', credentials: 'same-origin' });
      if (!response.ok) {
        const body = await response.json().catch(() => ({}));
        // A library-link session is refused until a real sign-in; offer the
        // way out instead of a dead end.
        if (response.status === 403 && String(body.detail || '').includes('Sign in with Google')) {
          if (window.confirm(body.detail + ' Sign in now?')) logout();
          return;
        }
        window.alert(body.detail || 'Delete failed. Please try again.');
        return;
      }
      removeReelFromState(item.reel_id);
      closeMini();
      render();
    }
    function removeReelFromState(reelId) {
      // Every client-side copy of the library, not just the shelves: missing
      // one left the reel sitting in Recently saved or search after a
      // successful delete, which reads as the delete not working.
      const keep = (item) => item.reel_id !== reelId;
      state.data = state.data.map((list) => ({ ...list, items: (list.items || []).filter(keep) }));
      if (Array.isArray(state.recents)) state.recents = state.recents.filter(keep);
      if (state.deepSearch && Array.isArray(state.deepSearch.results)) state.deepSearch.results = state.deepSearch.results.filter(keep);
      if (Array.isArray(state.miniList)) state.miniList = state.miniList.filter(keep);
      const fd = state.folderDetail;
      if (fd) {
        if (Array.isArray(fd.members)) fd.members = fd.members.filter(keep);
        if (Array.isArray(fd.suggestions)) fd.suggestions = fd.suggestions.filter(keep);
      }
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
      libraryNav.classList.toggle('active', state.screen === 'library' || state.screen === 'list' || state.screen === 'folderDetail' || state.screen === 'recents');
      profileNav.classList.toggle('active', state.screen === 'profile');
      if (state.screen === 'profile') renderProfile();
      else if (state.screen === 'list') renderListScreen();
      else if (state.screen === 'folderDetail') renderFolderDetail();
      else if (state.screen === 'recents') renderRecents();
      else renderLibrary();
    }
    async function loadData(force = false) {
      const firstLoad = state.loading;
      if (firstLoad) render();
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
        state.recents = Array.isArray(library.recents) ? library.recents : [];
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
      // Background refreshes must never yank the UI out from under the user:
      // skip the re-render while they are typing, selecting, or in a sheet/player.
      const active = document.activeElement;
      const typing = active && active.id === 'deepSearchInput' && state.magicQuery.trim();
      const busy = !force && !firstLoad && (state.selecting || typing
        || actionSheet.classList.contains('visible')
        || miniPlayer.classList.contains('visible'));
      if (!busy) render();
      loadFolders();
    }
    function manualRefresh(event) {
      // User-initiated refresh: show a spinner and always re-render when done.
      const button = event.currentTarget;
      if (button) button.classList.add('spinning');
      loadData(true).finally(() => { if (button) button.classList.remove('spinning'); });
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
  <script>
    // Claim card. Separate block on purpose: an error in here must never take
    // the library down with it. No backslashes anywhere in this block - the
    // page is built from a non-raw Python string and would eat them.
    (function () {
      const STAGE = '__CLAIM_STAGE__';
      const LIB_TOKEN = '__LIB_TOKEN__';
      const LOGIN_CSRF = '__LOGIN_CSRF__';
      const GOOGLE_CLIENT_ID = '__GOOGLE_CLIENT_ID__';
      if (!STAGE || !LIB_TOKEN) return;

      const ua = navigator.userAgent || '';
      const inInstagram = /Instagram/i.test(ua);
      const isIOS = /iPhone|iPad|iPod/i.test(ua);
      const isAndroid = /Android/i.test(ua);
      const card = document.getElementById('claimCard');
      const title = document.getElementById('claimTitle');
      const sub = document.getElementById('claimSub');
      const action = document.getElementById('claimAction');
      const hint = document.getElementById('claimHint');
      const err = document.getElementById('claimErr');
      const skip = document.getElementById('claimSkip');
      const skipKey = 'cn_claim_skip_' + STAGE;

      try { if (STAGE !== 'locked' && localStorage.getItem(skipKey)) return; } catch (e) {}

      const fullUrl = location.origin + '/g/' + LIB_TOKEN;

      // Instagram opens every link in its own browser, and that browser can
      // neither add to the home screen nor sign in with Google (Google refuses
      // embedded browsers outright). These are Meta's own escape hatch on
      // iPhone and Android's documented intent for Chrome. Both are
      // undocumented in Instagram and can break, hence the manual hint.
      function escapeHref() {
        if (isAndroid) {
          return 'intent://' + location.host + '/g/' + LIB_TOKEN +
            '#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=' +
            encodeURIComponent(fullUrl) + ';end';
        }
        return 'instagram://extbrowser/?url=' + encodeURIComponent(fullUrl);
      }
      function escapeButton(label) {
        const a = document.createElement('a');
        a.className = 'claim-btn';
        a.href = escapeHref();
        a.textContent = label;
        action.appendChild(a);
        hint.textContent = 'If nothing happens, tap ··· at the top right and choose Open in external browser.';
        hint.hidden = false;
      }

      if (STAGE === 'home') {
        title.textContent = 'Add ClipNest to your Home Screen';
        sub.textContent = 'It works just like an app. Open your library in one tap, without going through Instagram.';
        if (inInstagram) {
          escapeButton('Continue in browser');
          hint.textContent = 'Adding to your Home Screen works from your browser. ' + hint.textContent;
        } else if (isIOS) {
          sub.textContent += ' Tap Share, then Add to Home Screen.';
        } else if (isAndroid) {
          sub.textContent += ' Tap ⋮, then Add to Home screen.';
        } else {
          return;
        }
      } else {
        title.textContent = STAGE === 'locked' ? 'You’ve reached 20 saved reels' : 'Secure your library';
        sub.textContent = STAGE === 'locked'
          ? 'Sign in with Google to continue saving. Your library stays exactly as it is, and any reels you’ve sent since will be added automatically.'
          : 'Sign in with Google to keep your saved reels safe and accessible on any device.';
        if (STAGE === 'locked') card.classList.add('locked');
        if (inInstagram) {
          escapeButton('Continue in browser to sign in');
          hint.textContent = 'Google sign-in isn’t available inside Instagram. ' + hint.textContent;
        } else if (GOOGLE_CLIENT_ID && LOGIN_CSRF) {
          const slot = document.createElement('div');
          action.appendChild(slot);
          const s = document.createElement('script');
          s.src = 'https://accounts.google.com/gsi/client';
          s.async = true;
          s.onload = function () {
            window.google.accounts.id.initialize({
              client_id: GOOGLE_CLIENT_ID,
              callback: async function (response) {
                err.hidden = true;
                try {
                  const r = await fetch('/auth/google', {
                    method: 'POST',
                    credentials: 'same-origin',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ credential: response.credential, csrf_token: LOGIN_CSRF, visitor: '' })
                  });
                  if (!r.ok) {
                    const body = await r.json().catch(function () { return {}; });
                    throw new Error(body.detail || 'Sign in failed. Please try again.');
                  }
                  location.reload();
                } catch (e) {
                  err.textContent = e.message;
                  err.hidden = false;
                }
              }
            });
            window.google.accounts.id.renderButton(slot, { theme: 'filled_black', size: 'large', shape: 'pill', text: 'continue_with' });
          };
          document.head.appendChild(s);
        }
      }

      if (STAGE !== 'locked') {
        skip.hidden = false;
        skip.addEventListener('click', function () {
          try { localStorage.setItem(skipKey, '1'); } catch (e) {}
          card.classList.remove('show');
          setTimeout(function () { card.hidden = true; }, 250);
        });
      }
      card.hidden = false;
      requestAnimationFrame(function () { card.classList.add('show'); });
    })();
  </script>
</body>
</html>"""
    token = _token_safe(library_token)
    manifest_href = f"/g/{token}/manifest.webmanifest" if token else "/static/manifest.json"
    stage = claim_stage if claim_stage in ("home", "signin", "locked") else ""
    return (
        html.replace("__USER_ID__", safe_user_id)
        .replace("__BUILD_SHA__", build_sha)
        .replace("__SHOW_COLLECTIONS__", show_collections)
        .replace("__SHOW_RECIPES__", show_recipes)
        .replace("__SHOW_REPORT__", show_report)
        .replace("__MANIFEST_HREF__", manifest_href)
        .replace("__CLAIM_STAGE__", stage)
        .replace("__LIB_TOKEN__", token)
        .replace("__LOGIN_CSRF__", _token_safe(login_csrf))
        .replace("__GOOGLE_CLIENT_ID__", _token_safe(google_client_id))
    )
