from fastapi import APIRouter
from fastapi.responses import HTMLResponse


router = APIRouter(tags=["webapp"])


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
      margin: calc(-16px - var(--safe-top)) -16px 12px;
      padding: calc(16px + var(--safe-top)) 16px 14px;
      background: linear-gradient(180deg, rgba(7,9,12,0.96), rgba(7,9,12,0.8) 72%, transparent);
      backdrop-filter: blur(18px);
    }}
    .topbar {{ display:flex; gap:10px; align-items:center; margin-bottom:12px; }}
    .back, .status-btn, .refresh-btn {{
      width:42px; height:42px; border-radius:999px; border:1px solid var(--line);
      background: rgba(255,255,255,0.08); color:var(--text); display:inline-flex; align-items:center; justify-content:center;
      font-size:1rem; cursor:pointer;
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
    .kicker {{ margin:0 0 6px; color:var(--accent-2); font-size:.72rem; font-weight:900; letter-spacing:.11em; text-transform:uppercase; }}
    .title {{ margin:0; font-size: clamp(1.8rem, 7vw, 2.7rem); letter-spacing:-.05em; line-height:.96; }}
    .subtitle {{ margin:8px 0 0; color:var(--muted); font-size:.92rem; line-height:1.45; }}
    .segmented {{
      display:grid; grid-template-columns:1fr 1fr; gap:8px; margin-top:14px;
      padding:6px; border:1px solid var(--line); border-radius:18px; background:rgba(255,255,255,0.05);
    }}
    .segmented button {{
      height:42px; border:0; border-radius:12px; background:transparent; color:var(--muted); font-weight:850; cursor:pointer;
    }}
    .segmented button.active {{ background:rgba(255,255,255,0.1); color:var(--text); }}
    .search {{
      width:100%; height:48px; margin-top:14px; border-radius:18px; border:1px solid var(--line);
      background:rgba(255,255,255,0.07); color:var(--text); padding:0 16px; font-size:.96rem;
    }}
    .stats {{ display:flex; gap:8px; overflow:auto; padding:4px 0 2px; margin-bottom:12px; scrollbar-width:none; }}
    .stats::-webkit-scrollbar {{ display:none; }}
    .chip {{
      flex:0 0 auto; padding:8px 11px; border:1px solid var(--line); border-radius:999px;
      color:var(--muted); background:rgba(255,255,255,0.055); font-size:.74rem; font-weight:900;
    }}
    .sync-note {{ margin: 6px 0 0; color: var(--soft); font-size: .78rem; }}
    .content {{ display:grid; gap:12px; }}
    .card {{
      border:1px solid var(--line); border-radius:24px; background:linear-gradient(180deg, rgba(255,255,255,0.085), rgba(255,255,255,0.045));
      box-shadow: var(--shadow); padding:16px; cursor:pointer; overflow:hidden;
    }}
    .card-media {{
      position:relative; margin:-16px -16px 14px; aspect-ratio:1.8; background:#0b0d11;
      border-bottom:1px solid var(--line); overflow:hidden;
    }}
    .card-media img {{
      width:100%; height:100%; display:block; object-fit:cover;
      filter:saturate(1.02) contrast(1.04);
    }}
    .card-overlay {{
      position:absolute; inset:0;
      background:linear-gradient(180deg, rgba(6,7,10,0.0) 0%, rgba(6,7,10,0.15) 45%, rgba(6,7,10,0.72) 100%);
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
    .preview-lines {{ display:grid; gap:8px; }}
    .preview-lines div {{ color:var(--muted); font-size:.88rem; line-height:1.4; }}
    .detail {{ display:grid; gap:12px; }}
    .video-panel {{
      overflow:hidden; border:1px solid var(--line); border-radius:26px; background:var(--panel); box-shadow:var(--shadow);
    }}
    .video-wrap {{ position:relative; width:100%; aspect-ratio:.62; background:#050607; }}
    .video-wrap video, .video-wrap img {{ width:100%; height:100%; display:block; object-fit:cover; }}
    .video-empty {{
      position:absolute; inset:0; display:grid; place-items:center; padding:24px; text-align:center; color:var(--muted);
      font-size:.95rem; line-height:1.5;
    }}
    .video-meta {{ padding:16px; display:grid; gap:10px; }}
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
  </style>
</head>
<body>
  <main class="shell">
    <header class="header">
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
      <div class="segmented">
        <button id="standardTab" class="active">Standard</button>
        <button id="personalizedTab">Personalized</button>
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

    function coverForCollection(collection) {{
      return collection?.items?.find((item) => item.thumbnail_url)?.thumbnail_url || '';
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
      stats.innerHTML = `
        <span class="chip">${{collections.length}} Lists</span>
        <span class="chip">${{items}} Items</span>
        <span class="chip">${{dash.item_count || items}} Indexed</span>
        <span class="chip">${{dash.pending_url_count || 0}} Pending</span>
      `;
    }}

    function renderHome() {{
      if (state.loading) {{
        content.innerHTML = `<div class="loading"><div><h2 style="margin:0 0 8px;">Refreshing your library…</h2><p style="margin:0;">Pulling your latest reels, items, and status.</p></div></div>`;
        return;
      }}
      const collections = modeCollections().filter((c) => matchesCollection(c, state.query));
      backButton.classList.add('hidden');
      screenTitle.textContent = state.mode === 'personalized' ? 'Your Personalized Library' : 'Your Reel Library';
      screenSubtitle.textContent = state.mode === 'personalized'
        ? 'Repeated interests get separated automatically; everything else stays broad.'
        : 'Browse your saved reels by clean collection titles.';
      if (!collections.length) {{
        content.innerHTML = `<div class="empty"><div><h2 style="margin:0 0 8px;">No collections yet</h2><p style="margin:0;">Send reels to the bot and they’ll appear here.</p></div></div>`;
        return;
      }}
      content.innerHTML = collections.map((collection, index) => {{
        const preview = collection.items.filter((item) => matchesItem(item, state.query)).slice(0, 2);
        const cover = coverForCollection(collection);
        return `
          <article class="card" data-collection="${{index}}">
            <div class="card-media">
              ${{
                cover
                  ? `<img src="${{escapeHtml(cover)}}" alt="" />`
                  : `<div class="video-empty">Open this list to explore the saved reels inside.</div>`
              }}
              <div class="card-overlay"></div>
            </div>
            <div class="card-top">
              <div>
                ${{collection.parent_title ? `<p class="card-kicker">${{escapeHtml(collection.parent_title)}}</p>` : ''}}
                <h2 class="card-title">${{escapeHtml(collection.list_title)}}</h2>
              </div>
              <span class="count">${{collection.items.length}} items</span>
            </div>
            <div class="preview-lines">
              ${{preview.map((item) => `<div>${{escapeHtml(item.summary || item.name)}}</div>`).join('')}}
            </div>
            <div class="card-meta-row">
              <span class="mini-chip">${{state.mode === 'personalized' ? 'Personalized view' : 'Standard view'}}</span>
              <span class="mini-chip">${{preview.length ? `${{preview.length}} quick previews` : 'Ready to browse'}}</span>
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
      backButton.classList.remove('hidden');
      screenTitle.textContent = collection.list_title;
      screenSubtitle.textContent = `${{collection.parent_title ? `${{collection.parent_title}} · ` : ''}}${{items.length}} items`;
      content.innerHTML = `
        <section class="detail">
          <article class="video-panel">
            <div class="video-wrap">
              ${{
                item?.local_video_url
                  ? `<video src="${{escapeHtml(item.local_video_url)}}" ${{item.thumbnail_url ? `poster="${{escapeHtml(item.thumbnail_url)}}"` : ''}} controls playsinline preload="metadata"></video>`
                  : item?.thumbnail_url
                    ? `<img src="${{escapeHtml(item.thumbnail_url)}}" alt="" />`
                    : `<div class="video-empty">This reel is still waiting for local playback or media extraction.</div>`
              }}
            </div>
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
    }}

    document.getElementById('standardTab').addEventListener('click', () => {{
      state.mode = 'standard';
      state.currentList = null;
      document.getElementById('standardTab').classList.add('active');
      document.getElementById('personalizedTab').classList.remove('active');
      render();
    }});
    document.getElementById('personalizedTab').addEventListener('click', () => {{
      state.mode = 'personalized';
      state.currentList = null;
      document.getElementById('personalizedTab').classList.add('active');
      document.getElementById('standardTab').classList.remove('active');
      render();
    }});
    backButton.addEventListener('click', () => {{
      state.currentList = null;
      state.currentItem = 0;
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


@router.get("/app/{user_id}", response_class=HTMLResponse)
def user_app(user_id: str):
    return HTMLResponse(build_web_app_html(user_id))
