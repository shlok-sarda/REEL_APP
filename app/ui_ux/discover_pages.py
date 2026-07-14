"""Discover pages: the cartoonish reel map and the recipes page.

Both are standalone server-rendered pages (like the rest of the app shell)
that fetch their JSON from /api/map-data and /api/recipes-data. Styling is
deliberately playful — bouncy emoji pins, speech-bubble popups, pastel cards —
per Shlok's ask: "cartoonish, not so serious, more fun".
"""

from __future__ import annotations


def build_map_html(user_id: str) -> str:
    safe = user_id.replace("'", "&#39;")
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<title>ClipNest — Your Reel World</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<style>
  * { box-sizing: border-box; }
  html, body { margin: 0; height: 100%; font-family: 'Fredoka', system-ui, sans-serif; }
  #map { position: absolute; inset: 0; background: #aad3df; }
  .hud { position: absolute; z-index: 500; top: 14px; left: 14px; right: auto;
    background: #fff7e6; border: 3px solid #2d2a26; border-radius: 22px;
    padding: 12px 18px; box-shadow: 4px 6px 0 rgba(45,42,38,.35); max-width: 78vw; }
  .hud h1 { margin: 0; font-size: 20px; font-weight: 700; color: #2d2a26; letter-spacing: .3px; }
  .hud p { margin: 2px 0 0; font-size: 13px; color: #7a6f5d; font-weight: 500; }
  .backbtn { position: absolute; z-index: 500; bottom: 22px; left: 14px;
    background: #ffd166; color: #2d2a26; border: 3px solid #2d2a26; border-radius: 999px;
    font: 600 15px 'Fredoka', sans-serif; padding: 10px 20px; cursor: pointer;
    box-shadow: 3px 4px 0 rgba(45,42,38,.35); text-decoration: none; display: inline-block; }
  .backbtn:active { transform: translate(2px,2px); box-shadow: 1px 1px 0 rgba(45,42,38,.35); }
  .pin-wrap { position: relative; width: 46px; height: 52px; }
  .pin-emoji { position: absolute; left: 0; top: 0; width: 44px; height: 44px;
    background: #fff; border: 3px solid #2d2a26; border-radius: 50% 50% 50% 12%;
    transform: rotate(-8deg); display: flex; align-items: center; justify-content: center;
    font-size: 22px; box-shadow: 3px 4px 0 rgba(45,42,38,.3);
    animation: plop .45s cubic-bezier(.34,1.56,.64,1) both; }
  .pin-wrap:hover .pin-emoji { animation: wiggle .5s ease-in-out infinite; }
  .pin-count { position: absolute; right: -4px; top: -6px; min-width: 22px; height: 22px;
    background: #ef476f; color: #fff; border: 2.5px solid #2d2a26; border-radius: 999px;
    font: 700 12px/17px 'Fredoka', sans-serif; text-align: center; padding: 0 4px; }
  @keyframes plop { from { transform: scale(0) rotate(-8deg); } to { transform: scale(1) rotate(-8deg); } }
  @keyframes wiggle { 0%,100% { transform: rotate(-12deg); } 50% { transform: rotate(4deg); } }
  .leaflet-popup-content-wrapper { background: #fff7e6; color: #2d2a26; border: 3px solid #2d2a26;
    border-radius: 18px; box-shadow: 4px 5px 0 rgba(45,42,38,.3); font-family: 'Fredoka', sans-serif; }
  .leaflet-popup-tip { background: #fff7e6; border: 2px solid #2d2a26; }
  .pop-place { font-weight: 700; font-size: 17px; margin-bottom: 2px; }
  .pop-sub { font-size: 12px; color: #7a6f5d; margin-bottom: 8px; font-weight: 500; }
  .pop-item { margin: 7px 0; padding: 8px 10px; background: #fff; border: 2px solid #2d2a26;
    border-radius: 12px; }
  .pop-name { font-weight: 600; font-size: 13.5px; }
  .pop-link { font-size: 12.5px; color: #e07a2f; text-decoration: none; font-weight: 600; }
  .empty-hint { position: absolute; z-index: 500; left: 50%; top: 50%; transform: translate(-50%,-50%);
    background: #fff7e6; border: 3px solid #2d2a26; border-radius: 20px; padding: 18px 22px;
    font-weight: 600; color: #2d2a26; box-shadow: 4px 6px 0 rgba(45,42,38,.35); display: none;
    text-align: center; max-width: 82vw; }
</style>
</head>
<body>
<div class="hud">
  <h1>🗺️ Your Reel World</h1>
  <p id="stat">finding your places…</p>
</div>
<a class="backbtn" href="/app">← back to app</a>
<div class="empty-hint" id="emptyHint">No places found yet! 🧭<br>
  <span style="font-weight:500;font-size:13px">Save reels about cities, restaurants or trips and they will pop up here.</span></div>
<div id="map"></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const USER_ID = '__USER_ID__';
const EMOJI_RULES = [
  [/food|recipe|restaurant|cafe|street/i, '🍜'],
  [/stay|hotel|accommodation|rental|resort/i, '🛏️'],
  [/travel|destination|place|beach/i, '🏖️'],
];
function emojiFor(cats) {
  for (const [re, e] of EMOJI_RULES) if (re.test(cats)) return e;
  return '📍';
}
const map = L.map('map', { zoomControl: true, minZoom: 3, worldCopyJump: true }).setView([21, 78], 4);
L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png', {
  attribution: '&copy; OpenStreetMap &copy; CARTO', maxZoom: 19,
}).addTo(map);

function pinIcon(emoji, count) {
  const badge = count > 1 ? '<div class="pin-count">' + count + '</div>' : '';
  return L.divIcon({ className: '',
    html: '<div class="pin-wrap"><div class="pin-emoji">' + emoji + '</div>' + badge + '</div>',
    iconSize: [46, 52], iconAnchor: [22, 46], popupAnchor: [0, -40] });
}
function esc(s) { return String(s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }

fetch('/api/map-data?user_id=' + encodeURIComponent(USER_ID), { credentials: 'same-origin' })
  .then(r => r.json())
  .then(({ pins, pending_places }) => {
    const groups = {};
    for (const p of (pins || [])) {
      (groups[p.place] ||= { lat: p.lat, lng: p.lng, place: p.place, cats: '', reels: [] }).reels.push(p);
      groups[p.place].cats += ' ' + (p.category || '');
    }
    const keys = Object.keys(groups);
    document.getElementById('stat').textContent = keys.length
      ? (pins.length + ' reels · ' + keys.length + ' places' + (pending_places ? ' · more loading on next visit…' : ' 🎉'))
      : 'no pins yet';
    if (!keys.length) { document.getElementById('emptyHint').style.display = 'block'; return; }
    const bounds = [];
    let delay = 0;
    for (const key of keys) {
      const g = groups[key];
      bounds.push([g.lat, g.lng]);
      const list = g.reels.map(r =>
        '<div class="pop-item"><div class="pop-name">' + esc(r.item_name || r.reel_id) + '</div>' +
        (r.url ? '<a class="pop-link" href="' + esc(r.url) + '" target="_blank" rel="noopener">▶ watch reel</a>' : '') +
        '</div>').join('');
      const marker = L.marker([g.lat, g.lng], { icon: pinIcon(emojiFor(g.cats), g.reels.length), opacity: 0 });
      marker.addTo(map).bindPopup(
        '<div class="pop-place">' + esc(g.place) + '</div>' +
        '<div class="pop-sub">you saved ' + g.reels.length + ' reel' + (g.reels.length > 1 ? 's' : '') + ' here! 🎒</div>' + list,
        { maxWidth: 260 });
      setTimeout(() => marker.setOpacity(1), delay += 90);
    }
    if (bounds.length) map.fitBounds(bounds, { padding: [70, 70], maxZoom: 6, minZoom: 3 });
    setTimeout(() => map.invalidateSize(), 200);
  })
  .catch(() => { document.getElementById('stat').textContent = 'could not load the map data 😢'; });
window.addEventListener('resize', () => map.invalidateSize());
</script>
</body>
</html>""".replace("__USER_ID__", safe)


def build_recipes_html(user_id: str) -> str:
    safe = user_id.replace("'", "&#39;")
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
<title>ClipNest — Recipes</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Fredoka:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
  * { box-sizing: border-box; }
  body { margin: 0; min-height: 100vh; background: #fdf6ec; color: #2d2a26;
    font-family: 'Fredoka', system-ui, sans-serif; padding: 22px 16px 70px; }
  .wrap { max-width: 720px; margin: 0 auto; }
  h1 { font-size: 26px; margin: 6px 0 2px; }
  .sub { color: #8a7d68; font-size: 14px; font-weight: 500; margin-bottom: 18px; }
  .backbtn { display: inline-block; background: #ffd166; color: #2d2a26; border: 3px solid #2d2a26;
    border-radius: 999px; font: 600 14px 'Fredoka'; padding: 8px 18px; text-decoration: none;
    box-shadow: 3px 4px 0 rgba(45,42,38,.3); margin-bottom: 14px; }
  .card { background: #fff; border: 3px solid #2d2a26; border-radius: 22px; padding: 18px;
    margin: 0 0 18px; box-shadow: 5px 6px 0 rgba(45,42,38,.22); }
  .card:nth-child(3n+1) { background: #fff; }
  .card:nth-child(3n+2) { background: #f0f9f4; }
  .card:nth-child(3n)   { background: #fdf1f5; }
  .card h2 { margin: 0 0 4px; font-size: 21px; }
  .meta { display: flex; gap: 10px; flex-wrap: wrap; margin: 6px 0 12px; }
  .chip { background: #ffe8c2; border: 2px solid #2d2a26; border-radius: 999px;
    font-size: 12.5px; font-weight: 600; padding: 3px 12px; }
  h3 { font-size: 14px; margin: 12px 0 6px; color: #8a7d68; text-transform: uppercase;
    letter-spacing: .6px; }
  ul.ing { list-style: none; margin: 0; padding: 0; }
  ul.ing li { padding: 7px 10px; margin: 5px 0; background: rgba(255,255,255,.75);
    border: 2px solid #2d2a26; border-radius: 12px; font-size: 14.5px; font-weight: 500;
    cursor: pointer; user-select: none; }
  ul.ing li.done { text-decoration: line-through; opacity: .45; }
  ol.steps { margin: 0; padding-left: 0; counter-reset: step; list-style: none; }
  ol.steps li { counter-increment: step; position: relative; padding: 8px 10px 8px 44px;
    margin: 7px 0; background: rgba(255,255,255,.75); border: 2px solid #2d2a26;
    border-radius: 12px; font-size: 14.5px; line-height: 1.45; }
  ol.steps li::before { content: counter(step); position: absolute; left: 8px; top: 8px;
    width: 26px; height: 26px; background: #ef476f; color: #fff; border: 2px solid #2d2a26;
    border-radius: 999px; font-weight: 700; font-size: 13px; display: flex;
    align-items: center; justify-content: center; }
  .watch { display: inline-block; margin-top: 12px; background: #ffd166; color: #2d2a26;
    border: 3px solid #2d2a26; border-radius: 999px; font: 600 14px 'Fredoka';
    padding: 8px 18px; text-decoration: none; box-shadow: 3px 4px 0 rgba(45,42,38,.3); }
  .watch:active { transform: translate(2px,2px); box-shadow: 1px 1px 0 rgba(45,42,38,.3); }
  .empty { text-align: center; padding: 60px 10px; color: #8a7d68; font-weight: 500; }
  .loading { text-align: center; padding: 40px 10px; color: #8a7d68; font-weight: 600; }
</style>
</head>
<body><div class="wrap">
  <a class="backbtn" href="/app">← back to app</a>
  <h1>👨‍🍳 Recipes from your reels</h1>
  <div class="sub" id="stat">reading your cooking reels… first visit can take a little while 🍳</div>
  <div id="list"><div class="loading">Whisking things together… 🥣</div></div>
</div>
<script>
const USER_ID = '__USER_ID__';
function esc(s) { return String(s || '').replace(/[&<>"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c])); }
fetch('/api/recipes-data?user_id=' + encodeURIComponent(USER_ID), { credentials: 'same-origin' })
  .then(r => r.json())
  .then(({ recipes }) => {
    const list = document.getElementById('list');
    recipes = recipes || [];
    document.getElementById('stat').textContent = recipes.length
      ? recipes.length + ' recipe' + (recipes.length === 1 ? '' : 's') + ' cooked up from your saved reels 🎉'
      : '';
    if (!recipes.length) {
      list.innerHTML = '<div class="empty">No cook-along recipes found yet! 🍽️<br>Save some cooking reels (with a voiceover) and they will turn into recipe cards here.</div>';
      return;
    }
    list.innerHTML = recipes.map(r =>
      '<article class="card">' +
      '<h2>' + esc(r.title) + '</h2>' +
      '<div class="meta">' +
      (r.total_time ? '<span class="chip">⏱ ' + esc(r.total_time) + '</span>' : '') +
      (r.servings ? '<span class="chip">🍽 serves ' + esc(r.servings) + '</span>' : '') +
      '<span class="chip">🥘 ' + (r.ingredients || []).length + ' ingredients</span>' +
      '</div>' +
      '<h3>Ingredients — tap to tick off</h3>' +
      '<ul class="ing">' + (r.ingredients || []).map(i => '<li>' + esc(i) + '</li>').join('') + '</ul>' +
      '<h3>Steps</h3>' +
      '<ol class="steps">' + (r.steps || []).map(s => '<li>' + esc(s) + '</li>').join('') + '</ol>' +
      (r.url ? '<a class="watch" href="' + esc(r.url) + '" target="_blank" rel="noopener">▶ watch the reel</a>' : '') +
      '</article>').join('');
    list.querySelectorAll('ul.ing li').forEach(li =>
      li.addEventListener('click', () => li.classList.toggle('done')));
  })
  .catch(() => { document.getElementById('list').innerHTML = '<div class="empty">Could not load recipes 😢 — try again in a minute.</div>'; });
</script>
</body>
</html>""".replace("__USER_ID__", safe)
