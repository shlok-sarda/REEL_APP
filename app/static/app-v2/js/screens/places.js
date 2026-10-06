// Places: a dark map of everywhere your reels point to, with a draggable
// sheet listing each place, its reels, and the named spots inside them.
// Leaflet is the same library prod already uses (loaded from cdnjs here).
import { el, esc, plural, clamp, haptic } from '../util.js';
import { icon } from '../icons.js';
import { S, on, reelsFor } from '../store.js';
import { back, pushScreen } from '../router.js';
import { animate, moveTo, freeze, isReduced, rise } from '../motion.js';
import { openPlayer } from '../player.js';
import { wireFades } from '../cards.js';

let leaflet = null;
function loadLeaflet() {
  if (window.L) return Promise.resolve(window.L);
  if (leaflet) return leaflet;
  leaflet = new Promise((resolve, reject) => {
    const css = document.createElement('link');
    css.rel = 'stylesheet';
    css.href = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.css';
    document.head.appendChild(css);
    const s = document.createElement('script');
    s.src = 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.9.4/leaflet.min.js';
    s.onload = () => resolve(window.L);
    s.onerror = () => { leaflet = null; reject(new Error('leaflet')); };
    document.head.appendChild(s);
  });
  return leaflet;
}

export function openPlaces(focus) { return pushScreen(createPlaces(focus)); }

function createPlaces(focus) {
  const root = el(`<section class="screen-wrap places">
    <div class="pm-map" data-map><div class="pm-loading"><span class="spinner-mark"></span><span class="xs muted">Loading map</span></div></div>
    <div class="navbar is-floating"><button class="icon-btn is-glass" type="button" data-back aria-label="Back">${icon('back')}</button><span class="pm-title">Places</span><span class="navbar-end"></span></div>
    <section class="pm-sheet" data-sheet aria-label="Places list">
      <div class="pm-grab" data-drag><i></i></div>
      <div class="pm-head" data-drag><h2 class="head" data-count></h2><p class="xs muted">From the places your reels mention or show</p></div>
      <div class="pm-list" data-list></div>
    </section>
  </section>`);
  const $ = (s) => root.querySelector(s);
  const inst = { el: root, dock: false };
  let map = null;
  const markers = {};
  let selected = null;

  root.querySelector('[data-back]').addEventListener('click', () => back());

  function paintList() {
    const ps = S.places;
    const reelCount = new Set(ps.flatMap((p) => p.reels)).size;
    $('[data-count]').textContent = ps.length ? `${plural(ps.length, 'place')} · ${plural(reelCount, 'reel')}` : 'No places yet';
    const list = $('[data-list]');
    if (!ps.length) {
      list.innerHTML = '<div class="lesson"><p class="head">No places yet.</p><p class="sm">Save reels about cafes, cities or trips and they land on this map, with every spot they name.</p></div>';
      return;
    }
    list.innerHTML = ps.map((p) => {
      const rs = reelsFor(p.reels);
      return `<article class="pm-place ${selected === p.place ? 'is-open' : ''}" data-place="${esc(p.place)}">
        <button class="pm-row pressable" type="button" data-pick>
          <span class="pm-fan">${rs.slice(0, 3).map((r) => `<i style="--c:${r.color}"><img src="${esc(r.thumb)}" alt="" decoding="async"></i>`).join('')}</span>
          <span class="pm-row-text"><b>${esc(p.place)}</b><small>${plural(p.reels.length, 'reel')}${p.named.length > 1 ? ` · ${plural(p.named.length, 'spot')} named` : ''}</small></span>
          <span class="pm-chev">${icon('down')}</span>
        </button>
        <div class="pm-detail">
          <div class="pm-reels">${rs.map((r) => `<button class="pm-reel pressable" type="button" data-rid="${esc(r.id)}"><span class="rr-thumb" style="--c:${r.color}">${r.lqip ? `<img class="lq" src="${r.lqip}" alt="">` : ''}<img class="full" src="${esc(r.thumb)}" alt="" data-fade decoding="async"></span><b class="clamp-2">${esc(r.name)}</b></button>`).join('')}</div>
          ${p.named.length > 1 ? `<p class="eyebrow is-quiet pm-named-h">Spots named in these reels</p><ol class="pm-named">${p.named.map((n, i) => `<li class="${i >= 6 ? 'is-more' : ''}"><span class="rs-n">${i + 1}</span><span><b>${esc(n.name)}</b><small class="clamp-2">${esc(n.summary)}</small></span><a class="icon-btn" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(n.name + ' ' + p.place)}" target="_blank" rel="noopener" aria-label="Open ${esc(n.name)} in Maps">${icon('ext')}</a></li>`).join('')}</ol>${p.named.length > 6 ? `<button class="link-btn" type="button" data-more>Show all ${p.named.length}</button>` : ''}` : ''}
          <a class="btn btn-secondary btn-sm pm-maps" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.place)}" target="_blank" rel="noopener">${icon('map')}Open ${esc(p.place)} in Maps</a>
        </div>
      </article>`;
    }).join('');
    wireFades(list);
    list.querySelectorAll('[data-pick]').forEach((b) => b.addEventListener('click', () => select(b.closest('[data-place]').dataset.place, true)));
    list.querySelectorAll('.pm-reel').forEach((b) => b.addEventListener('click', () => {
      const p = S.places.find((x) => x.place === b.closest('[data-place]').dataset.place);
      openPlayer(p.reels, p.reels.indexOf(b.dataset.rid), b.querySelector('.rr-thumb'));
    }));
    list.querySelectorAll('[data-more]').forEach((b) => b.addEventListener('click', () => {
      b.closest('.pm-detail').querySelectorAll('.is-more').forEach((li) => li.classList.remove('is-more'));
      b.remove();
      setDetent('full');
    }));
  }

  function select(place, fromList) {
    const was = selected;
    selected = selected === place && fromList ? null : place;
    root.querySelectorAll('[data-place]').forEach((a) => {
      const open = a.dataset.place === selected;
      a.classList.toggle('is-open', open);
      if (open && !isReduced()) rise(a.querySelectorAll('.pm-reel, .pm-named li:not(.is-more)'), { y: 8, stagger: 25, duration: 280 });
    });
    Object.keys(markers).forEach((k) => markers[k].getElement() && markers[k].getElement().classList.toggle('is-on', k === selected));
    const p = S.places.find((x) => x.place === selected);
    if (p && map) {
      map.flyTo([p.lat, p.lng], p.reels.length > 1 || p.named.length > 3 ? 9 : 8, { duration: isReduced() ? 0 : 0.9 });
      haptic(6);
    }
    if (selected && detent === 'peek') setDetent('half');
    if (!selected && was && map) fitAll();
    if (selected) {
      const node = root.querySelector(`[data-place="${CSS.escape ? CSS.escape(selected) : selected}"]`);
      if (node) setTimeout(() => node.scrollIntoView({ block: 'nearest', behavior: isReduced() ? 'auto' : 'smooth' }), 260);
    }
  }

  /* ---------- sheet detents ---------- */
  const sheet = $('[data-sheet]');
  let detent = 'peek';
  function detentY(d) {
    const H = root.clientHeight;
    const h = sheet.offsetHeight;
    if (d === 'full') return 0;
    if (d === 'half') return Math.max(0, h - H * 0.56);
    return Math.max(0, h - Math.min(310, H * 0.4));
  }
  function setDetent(d, instant) {
    detent = d;
    sheet.classList.toggle('is-full', d === 'full');
    const y = detentY(d);
    if (instant || isReduced()) { freeze(sheet); sheet.style.transform = `translateY(${y}px)`; return; }
    moveTo(sheet, `translateY(${y}px)`, { duration: 380, easing: 'snap', force: true });
  }
  let drag = null;
  sheet.addEventListener('pointerdown', (e) => {
    const onHandle = e.target.closest('[data-drag]');
    const list = $('[data-list]');
    const inList = e.target.closest('[data-list]');
    if (e.target.closest('a, button') && !onHandle) return;
    if (!onHandle && !(inList && (detent !== 'full' || list.scrollTop <= 0))) return;
    freeze(sheet);
    const m = getComputedStyle(sheet).transform;
    const cur = m && m !== 'none' ? new DOMMatrix(m).m42 : detentY(detent);
    drag = { y: e.clientY, start: cur, v: 0, ly: e.clientY, lt: performance.now(), moved: false, fromList: !onHandle, pid: e.pointerId };
  });
  sheet.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dy = e.clientY - drag.y;
    if (drag.fromList && !drag.moved) {
      if (Math.abs(dy) < 6) return;
      if (detent === 'full' && dy < 0) { drag = null; return; }
    }
    if (!drag.moved) { drag.moved = true; try { sheet.setPointerCapture(drag.pid); } catch (err) { /* ignore */ } }
    const now = performance.now();
    drag.v = (e.clientY - drag.ly) / Math.max(1, now - drag.lt); drag.ly = e.clientY; drag.lt = now;
    const y = clamp(drag.start + dy, -20, detentY('peek') + 40);
    sheet.style.transform = `translateY(${y}px)`;
  });
  const end = (e) => {
    if (!drag) return;
    const d = drag; drag = null;
    if (!d.moved) return;
    const y = d.start + (e.clientY - d.y);
    const opts = ['full', 'half', 'peek'].map((k) => [k, detentY(k)]);
    let target = opts.reduce((a, b) => (Math.abs(b[1] - y) < Math.abs(a[1] - y) ? b : a))[0];
    if (d.v < -0.5) target = detent === 'peek' ? 'half' : 'full';
    if (d.v > 0.5) target = detent === 'full' ? 'half' : 'peek';
    setDetent(target);
  };
  sheet.addEventListener('pointerup', end);
  sheet.addEventListener('pointercancel', end);

  /* ---------- map ---------- */
  function fitAll() {
    const ps = S.places;
    if (!map || !ps.length) return;
    const pad = Math.min(310, root.clientHeight * 0.4);
    if (ps.length === 1) map.setView([ps[0].lat, ps[0].lng], 9);
    else map.fitBounds(ps.map((p) => [p.lat, p.lng]), { paddingTopLeft: [48, 90], paddingBottomRight: [48, pad + 24], maxZoom: 9 });
  }

  async function initMap() {
    const box = $('[data-map]');
    if (!S.places.length) { box.innerHTML = '<div class="pm-fallback"></div>'; return; }
    try {
      if (navigator.onLine === false) throw new Error('offline');
      const L = await loadLeaflet();
      if (!root.isConnected) return;
      box.innerHTML = '<div class="pm-leaflet"></div>';
      map = L.map(box.firstElementChild, { zoomControl: false, attributionControl: true, worldCopyJump: true, minZoom: 2 });
      L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 18,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener">OpenStreetMap</a>',
      }).addTo(map);
      S.places.forEach((p, i) => {
        const icn = L.divIcon({ className: 'pm-pin-wrap', html: `<span class="pm-pin" style="--i:${i}"><b>${p.reels.length}</b></span>`, iconSize: [44, 44], iconAnchor: [22, 22] });
        const mk = L.marker([p.lat, p.lng], { icon: icn, keyboard: true, title: p.place }).addTo(map);
        mk.on('click', () => select(p.place, false));
        markers[p.place] = mk;
      });
      fitAll();
      if (focus) setTimeout(() => select(focus, false), 400);
    } catch (e) {
      box.innerHTML = `<div class="pm-fallback"><span class="icon-tile is-neutral">${icon('wifiOff')}</span><p class="sm">The map needs internet. Your places are listed below.</p></div>`;
    }
  }

  paintList();
  inst.onShow = () => { if (map) setTimeout(() => map.invalidateSize(), 60); };
  const offs = [on('library', paintList)];
  inst.destroy = () => { offs.forEach((f) => f()); if (map) map.remove(); };
  requestAnimationFrame(() => {
    setDetent('peek', true);
    if (!isReduced()) animate(sheet, [{ transform: `translateY(${detentY('peek') + 120}px)` }, { transform: `translateY(${detentY('peek')}px)` }], { duration: 520, easing: 'snap', delay: 120 });
    setTimeout(initMap, 260);
  });
  return inst;
}
