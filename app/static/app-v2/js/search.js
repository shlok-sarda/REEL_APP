// Search overlay. Local matches render instantly; server results append
// without reordering anything already on screen. Suggestions come from the
// library itself, so every suggestion returns results.
import { el, esc, debounce, words, titleCase } from './util.js';
import { icon } from './icons.js';
import { S, localSearch, reel, savePref } from './store.js';
import { deepSearch } from './api.js';
import { evidenceFromServer } from './searchcore.js';
import { thumb, wireFades } from './cards.js';
import { pushLayer, closeLayer, isOpen } from './router.js';
import { setDockMode, dockInput, setDockLoading, setDockValue } from './dock.js';
import { animate, isReduced, rise } from './motion.js';
import { setOffline } from './ui.js';
import { openPlayer } from './player.js';
import { openNewList } from './newlist.js';
import { libraryQueries } from './queries.js';

let layer = null;
let panel = null;
let state = { q: '', shown: [], serverFor: '', reqId: 0, error: null };

export function initSearch() {
  return {
    focus: () => openSearch(),
    input: (v) => onQuery(v),
    submit: (v) => { rememberQuery(v); },
    clear: () => closeSearch(),
  };
}

export function openSearch(prefill) {
  const inp = dockInput();
  if (prefill != null) { setDockValue(prefill); }
  if (layer && isOpen(layer)) { if (prefill != null) onQuery(prefill); return; }
  panel = el(`<section class="search-layer" aria-label="Search">
    <div class="search-scroll">
      <div class="search-top"><p class="eyebrow">Ask your library</p><h2 class="title search-title">Describe it the way <em>you remember it.</em></h2></div>
      <div class="search-results" data-results></div>
      <div class="search-idle" data-idle></div>
    </div>
  </section>`);
  document.getElementById('overlays').appendChild(panel);
  animate(panel, [{ opacity: 0 }, { opacity: 1 }], { duration: 180 });
  setDockMode('search');
  layer = pushLayer({
    kind: 'overlay',
    hidesDock: false,
    close: ({ instant }) => {
      const p = panel;
      panel = null;
      setDockMode('idle');
      setDockLoading(false);
      runServer.cancel();
      if (inflight) { inflight.abort(); inflight = null; }
      if (document.activeElement === inp) inp.blur();
      setDockValue('');
      state = { q: '', shown: [], serverFor: '', reqId: state.reqId + 1, error: null };
      if (!p) return;
      if (instant) { p.remove(); return; }
      animate(p, [{ opacity: 1 }, { opacity: 0 }], { duration: 140 }).then(() => p.remove());
    },
  });
  renderIdle();
  if (prefill) onQuery(prefill);
  // A prefilled search (from the Ask widget) shows results with the keyboard
  // down; an empty one focuses so the user can type straight away.
  if (prefill == null && document.activeElement !== inp) { try { inp.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }
}

export function closeSearch() {
  return layer && isOpen(layer) ? closeLayer(layer) : Promise.resolve();
}

function rememberQuery(q) {
  const v = String(q || '').trim();
  if (!v) return;
  const list = [v].concat(S.prefs.recent.filter((x) => x.toLowerCase() !== v.toLowerCase())).slice(0, 6);
  savePref('recent', list);
}

/* ---------- suggestions from the library itself ---------- */
function suggestions() {
  // Real phrases from this library first ("veg food in bali"), then single
  // words if the library is too small to make phrases from.
  const out = libraryQueries(7);
  S.places.slice(0, 2).forEach((p) => out.push(p.place));
  S.collections.slice(0, 3).forEach((c) => { const w = c.title.split(' & ')[0]; if (w.length < 22) out.push(w.toLowerCase()); });
  const counts = {};
  S.reels.forEach((r) => words(r.name + ' ' + r.sub).forEach((w) => { if (w.length > 4) counts[w] = (counts[w] || 0) + 1; }));
  Object.keys(counts).sort((a, b) => counts[b] - counts[a]).slice(0, 6).forEach((w) => out.push(w));
  const seen = new Set();
  return out.filter((q) => { const k = q.toLowerCase(); if (seen.has(k) || !localSearch(q, 1).length) return false; seen.add(k); return true; }).slice(0, 7);
}

function renderIdle() {
  if (!panel) return;
  const idle = panel.querySelector('[data-idle]');
  panel.querySelector('[data-results]').innerHTML = '';
  panel.classList.remove('has-query');
  if (!S.reels.length) {
    idle.innerHTML = `<div class="search-empty"><p class="head">Nothing to search yet.</p><p class="sm muted">Send a reel to <b>@clipnest.in</b> on Instagram. Once it is sorted, you can find it here by describing it.</p></div>`;
    return;
  }
  const recent = S.prefs.recent;
  idle.innerHTML = `
    ${recent.length ? `<div class="search-sec"><p class="eyebrow is-quiet">Recent</p>${recent.map((q, i) => `<div class="recent-row"><button class="row pressable" type="button" data-q="${esc(q)}">${icon('clock')}<span class="row-title">${esc(q)}</span><span></span></button><button class="icon-btn" type="button" data-rm="${i}" aria-label="Remove ${esc(q)}">${icon('x')}</button></div>`).join('')}</div>` : ''}
    <div class="search-sec"><p class="eyebrow is-quiet">Try</p><div class="try-chips">${suggestions().map((q) => `<button class="chip" type="button" data-q="${esc(q)}">${esc(q)}</button>`).join('')}</div></div>`;
  idle.querySelectorAll('[data-q]').forEach((b) => b.addEventListener('click', () => { setDockValue(b.dataset.q); onQuery(b.dataset.q); rememberQuery(b.dataset.q); }));
  idle.querySelectorAll('[data-rm]').forEach((b) => b.addEventListener('click', () => {
    const list = S.prefs.recent.slice(); list.splice(Number(b.dataset.rm), 1); savePref('recent', list); renderIdle();
  }));
  rise(idle.querySelectorAll('.recent-row, .chip'), { y: 8, stagger: 24, duration: 300 });
}

/* ---------- querying ---------- */
const runServer = debounce((q) => serverSearch(q), 220);

function onQuery(v) {
  const q = String(v || '').trim();
  if (!panel) openSearch();
  state.q = q;
  if (!q) { runServer.cancel(); if (inflight) { inflight.abort(); inflight = null; } state.reqId += 1; setDockLoading(false); state.shown = []; renderIdle(); return; }
  panel.classList.add('has-query');
  panel.querySelector('[data-idle]').innerHTML = '';
  const local = localSearch(q, 30).map((h) => ({ id: h.id, evidence: h.evidence, src: 'local' }));
  // While typing the list may change freely (the user is not reading yet).
  state.shown = local;
  state.serverFor = '';
  renderResults(true);
  // The bar only moves while the screen is empty. Once local matches are
  // showing, smart results append quietly, so search never looks unfinished.
  setDockLoading(!local.length);
  runServer(q);
}

let inflight = null;
const SERVER_TIMEOUT_MS = 10000;

async function serverSearch(q) {
  const id = ++state.reqId;
  if (inflight) inflight.abort();
  const ctl = new AbortController();
  inflight = ctl;
  const timer = setTimeout(() => ctl.abort(), SERVER_TIMEOUT_MS);
  try {
    const res = await deepSearch(q, { signal: ctl.signal });
    if (id !== state.reqId || state.q !== q) return;
    state.error = null;
    setOffline(false);
    const have = new Set(state.shown.map((x) => x.id));
    const extra = [];
    res.results.forEach((r) => {
      const ev = evidenceFromServer(r.match_reasons, q);
      if (have.has(r.reel_id)) {
        // Local evidence already names the matched words; keep it unless it
        // had nothing to say.
        const cur = state.shown.find((x) => x.id === r.reel_id);
        if (cur && ev && !cur.evidence) cur.evidence = ev;
      } else if (reel(r.reel_id)) {
        extra.push({ id: r.reel_id, evidence: ev, src: 'server' });
      }
    });
    state.shown = state.shown.concat(extra);
    state.serverFor = q;
    renderResults(false, extra.map((x) => x.id));
  } catch (e) {
    if (id !== state.reqId) return;
    // A timeout is not an outage: keep what is on screen, say nothing.
    const timedOut = e && e.name === 'AbortError';
    state.error = timedOut ? null : e;
    if (!timedOut && e.status === 0) setOffline(true);
    state.serverFor = q;
    renderResults(false, []);
  } finally {
    clearTimeout(timer);
    if (inflight === ctl) inflight = null;
    if (id === state.reqId) setDockLoading(false);
  }
}

function usefulEvidence(r, ev) {
  if (!ev || !ev.text) return null;
  return ev.text.trim().toLowerCase() === r.name.trim().toLowerCase() ? null : ev;
}

function resultRow(item) {
  const r = reel(item.id);
  const ev = usefulEvidence(r, item.evidence);
  return `<button class="rrow" type="button" data-rid="${esc(r.id)}" data-key="${esc(r.id)}">
    ${thumb(r, 'rc-thumb')}
    <span class="rrow-text"><span class="rrow-title clamp-2">${esc(r.name)}</span><span class="rrow-sub">${esc(r.creator || r.sub)}</span>
    ${ev ? `<span class="evidence"><b>${esc(ev.label)}</b><span>${esc(ev.text)}</span></span>` : ''}</span>
  </button>`;
}

function renderResults(typing, appended = []) {
  if (!panel) return;
  const box = panel.querySelector('[data-results]');
  const q = state.q;
  const items = state.shown.filter((x) => reel(x.id));
  const settled = state.serverFor === q;
  let head = box.querySelector('.results-head');
  if (!head) {
    box.innerHTML = '<div class="results-head"></div><div class="results-list"></div><div class="results-foot"></div>';
    head = box.querySelector('.results-head');
  }
  const list = box.querySelector('.results-list');
  const foot = box.querySelector('.results-foot');
  const ids = items.map((x) => x.id);
  const match = settled && ids.length >= 2 ? S.lists.find((l) => ids.filter((id) => l.members.includes(id)).length >= Math.ceil(ids.length * 0.66)) : null;
  const listBtn = match
    ? `<button class="btn btn-secondary btn-sm make-list" type="button" data-openlist="${match.id}">${match.emoji ? match.emoji + ' ' : ''}Open your list</button>`
    : `<button class="btn btn-secondary btn-sm make-list" type="button" data-make>${icon('plus')}Make this a list</button>`;
  const reportBtn = S.flags && S.flags.showReport ? `<button class="btn btn-secondary btn-sm make-list" type="button" data-report>${icon('sparkle')}Report</button>` : '';
  head.classList.toggle('has-two', !!reportBtn);
  head.innerHTML = items.length
    ? `<p class="results-count"><b>${items.length}</b> ${items.length === 1 ? 'reel' : 'reels'} for <em>${esc(q)}</em></p>
       <span class="results-actions">${reportBtn}${listBtn}</span>`
    : '';
  const rb = head.querySelector('[data-report]');
  if (rb) rb.addEventListener('click', () => {
    rememberQuery(q);
    import('./report.js').then((m) => m.openReport(q));
  });
  const ol = head.querySelector('[data-openlist]');
  if (ol) ol.addEventListener('click', async () => {
    rememberQuery(q);
    const id = Number(ol.dataset.openlist);
    await closeSearch();
    const ld = await import('./screens/listDetail.js');
    ld.openListDetail(id);
  });
  // keyed patch: existing rows stay where they are
  const existing = new Map();
  list.querySelectorAll(':scope > [data-key]').forEach((n) => existing.set(n.dataset.key, n));
  let prev = null;
  const fresh = [];
  items.forEach((it) => {
    let n = existing.get(it.id);
    if (!n) { n = el(resultRow(it)); fresh.push(n); wireFades(n); } else {
      const ev = n.querySelector('.evidence');
      const good = usefulEvidence(reel(it.id), it.evidence);
      const html = good ? `<b>${esc(good.label)}</b><span>${esc(good.text)}</span>` : '';
      if (ev && good) ev.innerHTML = html;
      else if (!ev && good) n.querySelector('.rrow-text').insertAdjacentHTML('beforeend', `<span class="evidence">${html}</span>`);
    }
    existing.delete(it.id);
    const want = prev ? prev.nextElementSibling : list.firstElementChild;
    if (n !== want) list.insertBefore(n, prev ? prev.nextSibling : list.firstChild);
    prev = n;
  });
  existing.forEach((n) => n.remove());
  fresh.forEach((n, i) => {
    if (isReduced()) return;
    animate(n, [{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 260, delay: typing ? 0 : i * 40, clear: true });
  });
  list.querySelectorAll('[data-rid]').forEach((b) => {
    if (b.__wired) return;
    b.__wired = true;
    b.addEventListener('click', () => {
      rememberQuery(q);
      const ids = state.shown.map((x) => x.id).filter((id) => reel(id));
      openPlayer(ids, ids.indexOf(b.dataset.rid), b.querySelector('.rc-thumb'));
    });
  });
  const make = head.querySelector('[data-make]');
  if (make) make.addEventListener('click', () => {
    rememberQuery(q);
    openNewList({ query: q, reelIds: state.shown.map((x) => x.id).filter((id) => reel(id)), source: 'search' });
  });
  // states
  if (!items.length && settled) {
    const alt = suggestions().filter((s) => s.toLowerCase() !== q.toLowerCase()).slice(0, 3);
    foot.innerHTML = `<div class="no-results">
      <p class="head">Nothing for <em>"${esc(q)}"</em> yet.</p>
      <p class="sm muted">${state.error ? 'Smart search is unreachable right now, so this only checked titles and captions.' : 'Try fewer words, or what was on screen. These do have matches:'}</p>
      <div class="try-chips">${alt.map((s) => `<button class="chip" type="button" data-q="${esc(s)}">${esc(s)}</button>`).join('')}</div>
      <p class="xs faint dm-hint">${icon('ig')} Not saved yet? Send the reel to @clipnest.in and it shows up here.</p>
    </div>`;
    foot.querySelectorAll('[data-q]').forEach((b) => b.addEventListener('click', () => { setDockValue(b.dataset.q); onQuery(b.dataset.q); }));
  } else if (state.error && settled) {
    foot.innerHTML = `<p class="xs faint results-note">${icon('wifiOff')} Showing title matches only. Smart search will be back when you are online.</p>`;
  } else if (!items.length && !settled) {
    foot.innerHTML = '<div class="results-sk">' + Array.from({ length: 3 }, () => '<div class="rrow sk-row sk-delay" aria-hidden="true"><span class="rc-thumb sk"></span><span class="rrow-text"><span class="sk sk-line"></span><span class="sk sk-line is-short"></span></span></div>').join('') + '</div>';
  } else foot.innerHTML = '';
  if (appended.length === 0 && typing) panel.querySelector('.search-scroll').scrollTop = 0;
}

export function searchFor(q) { openSearch(q); }
export { titleCase };
