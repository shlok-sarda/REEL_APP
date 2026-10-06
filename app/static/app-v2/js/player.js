// Reel player. Native scroll-snap paging (momentum and finger-tracking come
// from the platform), the tapped card grows into the player, swipe right to
// dismiss with velocity, scrub with a 44px hit area, mute is remembered.
import { el, esc, fmtDuration, clamp, haptic } from './util.js';
import { icon } from './icons.js';
import { S, reelsFor, reel, savePref, recipeFor, collectionByKey } from './store.js';
import { pushLayer, closeLayer, isOpen } from './router.js';
import { animate, moveTo, freeze, isReduced, fadeTo } from './motion.js';
import { shareOrCopy, toast } from './ui.js';

let P = null;
const pool = [];
let warmEl = null;

function videoEl() {
  const v = document.createElement('video');
  v.playsInline = true;
  v.setAttribute('playsinline', '');
  v.setAttribute('webkit-playsinline', '');
  v.loop = true;
  v.preload = 'metadata';
  v.className = 'pl-video';
  return v;
}

const saveData = () => !!(navigator.connection && navigator.connection.saveData);

// Called on pointerdown on a card: buys the ~100ms between press and release.
export function warmPlayer(r) {
  if (!r || !r.video || saveData()) return;
  if (!warmEl) warmEl = videoEl();
  if (warmEl.dataset.src !== r.video) {
    warmEl.dataset.src = r.video;
    warmEl.preload = 'auto';
    warmEl.src = r.video;
  }
  const img = new Image();
  img.decoding = 'async';
  img.src = r.full;
}

function contained(r, W, H) {
  const ratio = (r.w || 9) / (r.h || 16);
  let w = W; let h = W / ratio;
  if (h > H) { h = H; w = H * ratio; }
  return { w, h, x: (W - w) / 2, y: (H - h) / 2 };
}

export function openPlayer(ids, index = 0, originEl = null) {
  const list = reelsFor(ids);
  if (!list.length) return;
  if (P) closePlayerNow();
  const idx = clamp(index, 0, list.length - 1);
  const node = el(`<section class="player" role="dialog" aria-modal="true" aria-label="Reel player">
    <div class="pl-bg"></div>
    <div class="pl-pager" data-pager tabindex="-1">${list.map((r, i) => `<div class="pl-page" data-i="${i}">
      <div class="pl-media">${r.lqip ? `<img class="pl-backdrop" src="${r.lqip}" alt="">` : ''}<img class="pl-poster" alt="" decoding="async" ${Math.abs(i - idx) <= 2 ? `src="${esc(r.full)}"` : `data-src="${esc(r.full)}" loading="lazy"`}></div>
    </div>`).join('')}</div>
    <div class="pl-shade" aria-hidden="true"></div>
    <div class="pl-chrome">
      <div class="pl-top">
        <button class="icon-btn is-glass" type="button" data-close aria-label="Close player">${icon('down')}</button>
        <span class="pl-pos" aria-live="polite"></span>
        <button class="icon-btn is-glass" type="button" data-mute aria-label="Sound">${icon('vol')}</button>
      </div>
      <div class="pl-rail">
        <button class="pl-act" type="button" data-addlist aria-label="Add to list"><span>${icon('plus')}</span><b>List</b></button>
        <button class="pl-act" type="button" data-details aria-label="Details"><span>${icon('info')}</span><b>Details</b></button>
        <button class="pl-act" type="button" data-share aria-label="Share"><span>${icon('share')}</span><b>Share</b></button>
      </div>
      <div class="pl-info" data-info></div>
      <div class="pl-scrub" data-scrub role="slider" aria-label="Seek" tabindex="0" aria-valuemin="0" aria-valuemax="100">
        <div class="pl-track"><i class="pl-fill"></i><i class="pl-knob"></i></div>
        <span class="pl-bubble"></span>
      </div>
      <div class="pl-times"><span data-cur>0:00</span><span data-dur>0:00</span></div>
      <button class="pl-soundhint" type="button" data-soundhint hidden>${icon('mute')}Tap for sound</button>
      <span class="pl-buffer" hidden><span class="spinner-mark"></span></span>
      <span class="pl-flash" aria-hidden="true"></span>
    </div>
  </section>`);
  document.getElementById('overlays').appendChild(node);
  P = { node, list, idx: -1, origin: originEl, playing: false, raf: 0, scrubbing: false, closing: false, active: null, preload: null };
  const pager = node.querySelector('[data-pager]');
  const H = node.clientHeight;
  pager.scrollTop = idx * H;

  // ---------- entry ----------
  const chrome = node.querySelector('.pl-chrome');
  const bg = node.querySelector('.pl-bg');
  const entry = (S.ab && S.ab.entry) || 'morph';
  const originRect = originEl && originEl.isConnected ? originEl.getBoundingClientRect() : null;
  const deviceRect = node.getBoundingClientRect();
  if (isReduced()) {
    animate(node, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 });
  } else if (entry === 'morph' && originRect && originRect.width > 20) {
    morphIn(list[idx], originRect, deviceRect, node, pager, chrome, bg);
  } else {
    node.style.transform = 'translateY(100%)';
    moveTo(node, 'translateY(0%)', { duration: 420, easing: 'snap' });
  }

  P.layer = pushLayer({ kind: 'overlay', hidesDock: true, close: ({ instant }) => closeAnim(instant) });
  activate(idx, true);
  wire(node, pager);
  haptic(6);
}

function morphIn(r, from, dev, node, pager, chrome, bg) {
  const scale = from.width / dev.width;
  const W = dev.width; const H = dev.height;
  const target = contained(r, W, H);
  const clone = el(`<div class="pl-clone" style="--c:${r.color}"><img src="${esc(r.thumb)}" alt=""></div>`);
  // Clone keeps the card's 3:4 crop and grows uniformly (no squish).
  const cw = target.w;
  const ch = target.w * (from.height / from.width);
  clone.style.width = `${cw}px`;
  clone.style.height = `${ch}px`;
  clone.style.left = '0px';
  clone.style.top = '0px';
  node.parentNode.appendChild(clone);
  const s0 = from.width / cw;
  const fx = from.left - dev.left;
  const fy = from.top - dev.top;
  const tx = target.x;
  const ty = target.y + (target.h - ch) / 2;
  animate(clone, [
    { transform: `translate(${fx}px, ${fy}px) scale(${s0})`, opacity: 1 },
    { transform: `translate(${tx}px, ${ty}px) scale(1)`, opacity: 1, offset: 0.78 },
    { transform: `translate(${tx}px, ${ty}px) scale(1)`, opacity: 0 },
  ], { duration: 520, easing: 'soft' }).then(() => clone.remove());
  pager.style.opacity = '0';
  animate(pager, [{ opacity: 0 }, { opacity: 0, offset: 0.45 }, { opacity: 1 }], { duration: 520, easing: 'out' }).then(() => { pager.style.opacity = ''; });
  animate(bg, [{ opacity: 0 }, { opacity: 1 }], { duration: 300, easing: 'out' });
  animate(chrome, [{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 0, transform: 'translateY(10px)', offset: 0.5 }, { opacity: 1, transform: 'translateY(0)' }], { duration: 560, easing: 'out' });
  if (from && scale) { /* reserved */ }
}

function closeAnim(instant) {
  if (!P) return;
  const cur = P;
  P = null;
  cur.closing = true;
  stopLoop(cur);
  if (cur.active) { cur.active.pause(); }
  document.removeEventListener('keydown', cur.onKey);
  document.removeEventListener('visibilitychange', cur.onVis);
  const node = cur.node;
  const done = () => {
    node.remove();
    pool.forEach((v) => { v.pause(); v.removeAttribute('src'); try { v.load(); } catch (e) { /* ignore */ } v.remove(); });
    pool.length = 0;
  };
  if (instant) { done(); return; }
  if (isReduced()) { animate(node, [{ opacity: 1 }, { opacity: 0 }], { duration: 140 }).then(done); return; }
  // Shrink back into the card of the reel now playing, if it's on screen.
  const r = cur.list[cur.idx];
  const card = r ? findCard(r.id) : null;
  if (card && (S.ab && S.ab.entry) !== 'rise') {
    const to = card.getBoundingClientRect();
    const dev = node.getBoundingClientRect();
    if (to.bottom > dev.top + 40 && to.top < dev.bottom - 40) {
      const target = contained(r, dev.width, dev.height);
      const cw = target.w;
      const ch = target.w * (to.height / to.width);
      const clone = el(`<div class="pl-clone" style="--c:${r.color}"><img src="${esc(r.thumb)}" alt=""></div>`);
      clone.style.width = `${cw}px`; clone.style.height = `${ch}px`;
      node.parentNode.appendChild(clone);
      const cx = parseFloat(getComputedStyle(node).getPropertyValue('--drag-x')) || 0;
      const sx = target.x + cx;
      const sy = target.y + (target.h - ch) / 2;
      animate(clone, [
        { transform: `translate(${sx}px, ${sy}px) scale(1)`, opacity: 0.4 },
        { transform: `translate(${sx}px, ${sy}px) scale(1)`, opacity: 1, offset: 0.15 },
        { transform: `translate(${to.left - dev.left}px, ${to.top - dev.top}px) scale(${to.width / cw})`, opacity: 1 },
      ], { duration: 380, easing: 'snap' }).then(() => clone.remove());
      animate(node, [{ opacity: Number(getComputedStyle(node).opacity) || 1 }, { opacity: 0 }], { duration: 220, easing: 'out' }).then(done);
      return;
    }
  }
  freeze(node);
  const t = getComputedStyle(node).transform;
  animate(node, [{ transform: t === 'none' ? 'translateY(0)' : t, opacity: 1 }, { transform: 'translateY(16%)', opacity: 0 }], { duration: 240, easing: 'in' }).then(done);
}

function findCard(rid) {
  const cands = Array.from(document.querySelectorAll(`[data-rid="${rid}"] .rc-thumb, [data-rid="${rid}"].w-latest, [data-rid="${rid}"] .rr-thumb`));
  return cands.find((n) => n.offsetParent !== null && !n.closest('.player')) || null;
}

export function closePlayer() { if (P && isOpen(P.layer)) closeLayer(P.layer); }
function closePlayerNow() { if (P && isOpen(P.layer)) closeLayer(P.layer); }
export const playerOpen = () => !!P;

/* ---------- activation: one playing video, one preloading ---------- */
function activate(i, first) {
  if (!P || i === P.idx || i < 0 || i >= P.list.length) return;
  const prev = P.idx;
  P.idx = i;
  const r = P.list[i];
  const page = P.node.querySelector(`.pl-page[data-i="${i}"]`);
  // eager posters around the new index
  for (let k = i - 1; k <= i + 2; k += 1) {
    const img = P.node.querySelector(`.pl-page[data-i="${k}"] .pl-poster[data-src]`);
    if (img) { img.src = img.dataset.src; img.removeAttribute('data-src'); }
  }
  if (P.active) { P.active.pause(); P.active.classList.remove('is-playing'); }
  let v = null;
  if (P.preload && P.preload.dataset.src === r.video) { v = P.preload; P.preload = null; }
  else if (warmEl && warmEl.dataset.src === r.video) { v = warmEl; warmEl = null; }
  else {
    v = pool.find((x) => x !== P.active && x !== P.preload) || null;
    if (!v) { v = videoEl(); pool.push(v); }
    if (r.video) { v.dataset.src = r.video; v.src = r.video; }
  }
  if (!pool.includes(v)) pool.push(v);
  if (pool.length > 3) { const old = pool.find((x) => x !== v && x !== P.preload); if (old) { old.pause(); old.removeAttribute('src'); old.remove(); pool.splice(pool.indexOf(old), 1); } }
  P.active = v;
  v.preload = 'auto';
  v.poster = r.full;
  v.classList.remove('is-playing');
  v.onplaying = () => { v.classList.add('is-playing'); hideBuffer(); };
  v.onwaiting = () => queueBuffer();
  v.oncanplay = () => hideBuffer();
  v.onerror = () => showFallback(page, r);
  v.onloadedmetadata = () => updateTimes();
  page.querySelector('.pl-media').appendChild(v);
  if (!r.video) { showFallback(page, r); }
  v.muted = !S.prefs.soundOn;
  try { v.currentTime = 0; } catch (e) { /* not ready */ }
  setMuteUI(v.muted);
  const p = v.play();
  P.playing = true;
  if (p && p.catch) {
    p.catch(() => {
      if (!P || P.active !== v) return;
      if (!v.muted) { v.muted = true; setMuteUI(true, true); v.play().catch(() => { P.playing = false; setPlayUI(); }); }
      else { P.playing = false; setPlayUI(); }
    });
  }
  renderInfo(r, !first && prev >= 0 ? (i > prev ? 1 : -1) : 0);
  startLoop();
  preloadNext();
}

function preloadNext() {
  if (!P || saveData()) return;
  const n = P.list[P.idx + 1];
  if (!n || !n.video) return;
  if (P.preload && P.preload.dataset.src === n.video) return;
  let v = pool.find((x) => x !== P.active);
  if (!v) { v = videoEl(); pool.push(v); }
  v.preload = 'auto';
  v.muted = true;
  v.dataset.src = n.video;
  v.src = n.video;
  P.preload = v;
}

function showFallback(page, r) {
  if (page.querySelector('.pl-fallback')) return;
  page.querySelector('.pl-media').insertAdjacentHTML('beforeend', `<div class="pl-fallback"><p class="sm">This video could not load.</p>${r.url ? `<a class="btn btn-secondary btn-sm" href="${esc(r.url)}" target="_blank" rel="noopener">${icon('ig')}Open on Instagram</a>` : ''}</div>`);
}

let bufferTimer = 0;
function queueBuffer() { clearTimeout(bufferTimer); bufferTimer = setTimeout(() => { if (P) P.node.querySelector('.pl-buffer').hidden = false; }, 450); }
function hideBuffer() { clearTimeout(bufferTimer); if (P) P.node.querySelector('.pl-buffer').hidden = true; }

function renderInfo(r, dir) {
  const info = P.node.querySelector('[data-info]');
  const recipe = recipeFor(r.id);
  const col = r.collections[0] ? collectionByKey(r.collections[0]) : null;
  const placeItems = (r.items || []).filter((it) => it.item_type === 'place' || it.location);
  const chips = [];
  if (recipe) chips.push(`<button class="pl-chip is-hot" type="button" data-recipe>${icon('chef')}Recipe · ${recipe.ingredients.length} ingredients</button>`);
  else if (S.recipesEnabled && (r.sub || '').toLowerCase().includes('recipe')) chips.push(`<button class="pl-chip is-hot" type="button" data-recipe>${icon('chef')}Get the recipe</button>`);
  if (placeItems.length > 1) chips.push(`<button class="pl-chip" type="button" data-places>${icon('pin')}${placeItems.length} places</button>`);
  else if (r.locations.length) chips.push(`<button class="pl-chip" type="button" data-places>${icon('pin')}${esc(r.locations[0])}</button>`);
  if (col) chips.push(`<button class="pl-chip" type="button" data-col="${esc(col.key)}">${col.emoji ? `<span class="pl-emoji">${col.emoji}</span>` : ''}${esc(col.title)}</button>`);
  info.innerHTML = `<p class="pl-creator">${esc(r.creator || 'Saved reel')}</p>
    <h2 class="pl-title clamp-2" data-details>${esc(r.name)}</h2>
    ${chips.length ? `<div class="pl-chips">${chips.join('')}</div>` : ''}`;
  P.node.querySelector('.pl-pos').textContent = P.list.length > 1 ? `${P.idx + 1} of ${P.list.length}` : '';
  if (dir && !isReduced()) animate(info, [{ opacity: 0, transform: `translateY(${dir * 10}px)` }, { opacity: 1, transform: 'translateY(0)' }], { duration: 260, easing: 'out' });
  info.querySelector('[data-details]').addEventListener('click', () => openDetailsFor(r));
  const rb = info.querySelector('[data-recipe]');
  if (rb) rb.addEventListener('click', () => import('./recipe.js').then((m) => m.openRecipe(r.id)));
  const pb = info.querySelector('[data-places]');
  if (pb) pb.addEventListener('click', () => openDetailsFor(r, 'items'));
  const cb = info.querySelector('[data-col]');
  if (cb) cb.addEventListener('click', () => { const key = cb.dataset.col; closePlayer(); setTimeout(() => import('./screens/collection.js').then((m) => m.openCollection(key)), 60); });
  updateTimes();
}

function openDetailsFor(r, focus) {
  import('./sheets.js').then((m) => m.openReelSheet(r.id, { fromPlayer: true, focus }));
}

/* ---------- progress loop + controls ---------- */
function startLoop() {
  stopLoop(P);
  const tick = () => {
    if (!P) return;
    if (!P.scrubbing) updateTimes();
    P.raf = requestAnimationFrame(tick);
  };
  P.raf = requestAnimationFrame(tick);
}
function stopLoop(p) { if (p && p.raf) cancelAnimationFrame(p.raf); }

function updateTimes() {
  if (!P || !P.active) return;
  const v = P.active;
  const d = Number.isFinite(v.duration) && v.duration > 0 ? v.duration : (P.list[P.idx].duration || 0);
  const t = v.currentTime || 0;
  const f = d ? clamp(t / d, 0, 1) : 0;
  const node = P.node;
  node.querySelector('.pl-fill').style.transform = `scaleX(${f})`;
  node.querySelector('.pl-knob').style.transform = `translateX(${f * node.querySelector('.pl-track').clientWidth}px)`;
  node.querySelector('[data-cur]').textContent = fmtDuration(t);
  node.querySelector('[data-dur]').textContent = fmtDuration(d);
  node.querySelector('[data-scrub]').setAttribute('aria-valuenow', String(Math.round(f * 100)));
}

function setMuteUI(muted, forced) {
  if (!P) return;
  const b = P.node.querySelector('[data-mute]');
  b.innerHTML = icon(muted ? 'mute' : 'vol');
  b.setAttribute('aria-label', muted ? 'Turn sound on' : 'Mute');
  P.node.querySelector('[data-soundhint]').hidden = !(muted && forced);
}

function setPlayUI() {
  if (!P) return;
  P.node.classList.toggle('is-paused', !P.playing);
}

function togglePlay() {
  if (!P || !P.active) return;
  const v = P.active;
  if (v.paused) { v.play().catch(() => {}); P.playing = true; flash('play'); }
  else { v.pause(); P.playing = false; flash('pause'); }
  setPlayUI();
}

function toggleMute() {
  if (!P || !P.active) return;
  const v = P.active;
  v.muted = !v.muted;
  savePref('soundOn', !v.muted);
  setMuteUI(v.muted);
  if (!v.muted && v.paused) v.play().catch(() => {});
}

function flash(kind) {
  const f = P.node.querySelector('.pl-flash');
  f.innerHTML = icon(kind);
  if (isReduced()) { animate(f, [{ opacity: 0.9 }, { opacity: 0 }], { duration: 500 }); return; }
  animate(f, [
    { opacity: 0, transform: 'translate(-50%, -50%) scale(0.7)' },
    { opacity: 1, transform: 'translate(-50%, -50%) scale(1)', offset: 0.35 },
    { opacity: 0, transform: 'translate(-50%, -50%) scale(1.08)' },
  ], { duration: 560, easing: 'out' });
}

function step(delta) {
  if (!P) return;
  const pager = P.node.querySelector('[data-pager]');
  const i = clamp(P.idx + delta, 0, P.list.length - 1);
  pager.scrollTo({ top: i * pager.clientHeight, behavior: isReduced() ? 'auto' : 'smooth' });
}

function wire(node, pager) {
  node.querySelector('[data-close]').addEventListener('click', closePlayer);
  node.querySelector('[data-mute]').addEventListener('click', toggleMute);
  node.querySelector('[data-soundhint]').addEventListener('click', toggleMute);
  node.querySelector('[data-share]').addEventListener('click', () => { const r = P.list[P.idx]; shareOrCopy(r.name, r.url); });
  node.querySelector('[data-details]').addEventListener('click', () => openDetailsFor(P.list[P.idx]));
  node.querySelector('[data-addlist]').addEventListener('click', () => import('./sheets.js').then((m) => m.openAddToList(P.list[P.idx].id)));

  // page changes
  let settleTimer = 0;
  const settle = () => {
    if (!P) return;
    const i = Math.round(pager.scrollTop / pager.clientHeight);
    activate(i);
  };
  pager.addEventListener('scroll', () => {
    clearTimeout(settleTimer);
    settleTimer = setTimeout(settle, 90);
    // swap the caption early, as soon as the next page dominates
    if (!P) return;
    const i = Math.round(pager.scrollTop / pager.clientHeight);
    if (i !== P.idx && Math.abs(pager.scrollTop - i * pager.clientHeight) < pager.clientHeight * 0.18) activate(i);
  }, { passive: true });
  if ('onscrollend' in window) pager.addEventListener('scrollend', settle);

  // tap to pause, horizontal drag to dismiss
  let g = null;
  pager.addEventListener('pointerdown', (e) => {
    if (e.target.closest('a, button')) return;
    g = { x: e.clientX, y: e.clientY, t: performance.now(), lx: e.clientX, lt: performance.now(), v: 0, mode: null };
  });
  pager.addEventListener('pointermove', (e) => {
    if (!g) return;
    const dx = e.clientX - g.x; const dy = e.clientY - g.y;
    if (!g.mode) {
      if (Math.abs(dx) > 10 && dx > 0 && Math.abs(dx) > Math.abs(dy) * 1.3) { g.mode = 'dismiss'; freeze(node); try { pager.setPointerCapture(e.pointerId); } catch (err) { /* ignore */ } }
      else if (Math.abs(dy) > 10) g.mode = 'scroll';
    }
    if (g.mode === 'dismiss') {
      const now = performance.now();
      g.v = (e.clientX - g.lx) / Math.max(1, now - g.lt);
      g.lx = e.clientX; g.lt = now;
      const x = Math.max(0, dx);
      const s = 1 - Math.min(0.14, x / node.clientWidth * 0.3);
      node.style.transform = `translateX(${x}px) scale(${s})`;
      node.style.setProperty('--drag-x', `${x}px`);
      node.querySelector('.pl-bg').style.opacity = String(1 - Math.min(0.7, x / node.clientWidth));
    }
  });
  const end = (e) => {
    if (!g) return;
    const d = g; g = null;
    const dx = e.clientX - d.x; const dy = e.clientY - d.y;
    if (d.mode === 'dismiss') {
      if (dx > 110 || d.v > 0.55) { closePlayer(); return; }
      moveTo(node, 'translateX(0px) scale(1)', { duration: 300, easing: 'snap', force: true });
      node.querySelector('.pl-bg').style.opacity = '';
      return;
    }
    if (!d.mode && Math.abs(dx) < 10 && Math.abs(dy) < 10 && performance.now() - d.t < 350 && e.type === 'pointerup') togglePlay();
  };
  pager.addEventListener('pointerup', end);
  pager.addEventListener('pointercancel', end);

  // scrub
  const scrub = node.querySelector('[data-scrub]');
  const bubble = node.querySelector('.pl-bubble');
  const seek = (e) => {
    if (!P || !P.active) return;
    const rect = scrub.querySelector('.pl-track').getBoundingClientRect();
    const f = clamp((e.clientX - rect.left) / rect.width, 0, 1);
    const v = P.active;
    const d = Number.isFinite(v.duration) && v.duration > 0 ? v.duration : P.list[P.idx].duration;
    if (d) { try { v.currentTime = f * d; } catch (err) { /* ignore */ } }
    node.querySelector('.pl-fill').style.transform = `scaleX(${f})`;
    node.querySelector('.pl-knob').style.transform = `translateX(${f * rect.width}px)`;
    bubble.textContent = fmtDuration(f * (d || 0));
    bubble.style.transform = `translateX(${clamp(f * rect.width, 18, rect.width - 18)}px) translateX(-50%)`;
    node.querySelector('[data-cur]').textContent = fmtDuration(f * (d || 0));
  };
  scrub.addEventListener('pointerdown', (e) => { P.scrubbing = true; node.classList.add('is-scrubbing'); scrub.setPointerCapture(e.pointerId); seek(e); });
  scrub.addEventListener('pointermove', (e) => { if (P && P.scrubbing) seek(e); });
  const stopScrub = () => { if (!P) return; P.scrubbing = false; node.classList.remove('is-scrubbing'); };
  scrub.addEventListener('pointerup', stopScrub);
  scrub.addEventListener('pointercancel', stopScrub);
  scrub.addEventListener('keydown', (e) => {
    if (!P || !P.active) return;
    if (e.key === 'ArrowRight') { P.active.currentTime += 5; e.preventDefault(); }
    if (e.key === 'ArrowLeft') { P.active.currentTime -= 5; e.preventDefault(); }
  });

  P.onKey = (e) => {
    if (!P || document.querySelector('#overlays .sheet:not(.is-closing)')) return;
    if (e.target.closest && e.target.closest('input, textarea')) return;
    if (e.key === ' ') { e.preventDefault(); togglePlay(); }
    else if (e.key === 'Escape') closePlayer();
    else if (e.key === 'ArrowDown') { e.preventDefault(); step(1); }
    else if (e.key === 'ArrowUp') { e.preventDefault(); step(-1); }
    else if (e.key === 'm' || e.key === 'M') toggleMute();
  };
  document.addEventListener('keydown', P.onKey);
  P.onVis = () => { if (document.hidden && P && P.active) { P.active.pause(); P.playing = false; setPlayUI(); } };
  document.addEventListener('visibilitychange', P.onVis);
  setTimeout(() => { try { pager.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }, 50);
}

export function currentReelId() { return P ? P.list[P.idx].id : null; }
export function pausePlayer() { if (P && P.active) { P.active.pause(); P.playing = false; setPlayUI(); } }
export { toast };
