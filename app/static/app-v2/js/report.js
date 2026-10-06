// Search report (admin): one AI read across the reels a search returned.
// It streams: searching -> judging (which reels count) -> writing (cards
// appear as they are written) -> done. The user can leave reels out or add
// skipped ones back and regenerate. Same server contract as the classic UI.
import { el, esc, plural, haptic, NL } from './util.js';
import { icon } from './icons.js';
import { S, reel } from './store.js';
import * as api from './api.js';
import { pushLayer, closeLayer, isOpen } from './router.js';
import { animate, isReduced, rise } from './motion.js';
import { toast, copyText, errorMessage } from './ui.js';
import { wireFades } from './cards.js';
import { openPlayer } from './player.js';

const KIND = { place: 'Place', activity: 'Activity', stay: 'Stay', dish: 'Dish', website: 'Website', app: 'App', product: 'Product', title: 'Watch', person: 'Person' };
const ACTION_ICON = { Map: 'map', Open: 'ext', Search: 'search' };
let R = null;

export function openReport(query) {
  if (R && isOpen(R.layer)) closeLayer(R.layer);
  const node = el(`<section class="report" role="dialog" aria-modal="true" aria-label="Report">
    <div class="navbar report-nav">
      <button class="icon-btn is-glass" type="button" data-back aria-label="Close report">${icon('back')}</button>
      <span class="navbar-title" data-navtitle></span>
      <span class="navbar-end"><button class="icon-btn is-glass" type="button" data-share aria-label="Share this report" hidden>${icon('share')}</button></span>
    </div>
    <div class="report-scroll" data-scroll><div class="report-body" data-body></div></div>
    <div class="report-update" data-update hidden><button class="btn btn-primary btn-block" type="button">${icon('refresh')}Update report</button></div>
  </section>`);
  document.getElementById('overlays').appendChild(node);
  const r = { node, query, include: [], exclude: [], data: null, live: null, skippedOpen: false, pendingInclude: new Set(), pendingExclude: new Set(), run: 0, shown: 0 };
  R = r;
  if (isReduced()) animate(node, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 });
  else animate(node, [{ opacity: 0, transform: 'translateY(24px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 380, easing: 'snap', clear: true });
  r.layer = pushLayer({
    kind: 'overlay',
    hidesDock: true,
    close: ({ instant }) => {
      r.run += 1;
      if (r.ctl) r.ctl.abort();
      if (R === r) R = null;
      if (instant || isReduced()) { node.remove(); return; }
      animate(node, [{ opacity: 1, transform: 'translateY(0)' }, { opacity: 0, transform: 'translateY(18px)' }], { duration: 200, easing: 'in' }).then(() => node.remove());
    },
  });
  node.querySelector('[data-back]').addEventListener('click', () => closeLayer(r.layer));
  node.querySelector('[data-share]').addEventListener('click', () => share(r));
  node.querySelector('[data-update] button').addEventListener('click', () => {
    r.include = Array.from(r.pendingInclude);
    r.exclude = Array.from(r.pendingExclude);
    node.querySelector('[data-scroll]').scrollTop = 0;
    load(r);
  });
  const scroll = node.querySelector('[data-scroll]');
  const nav = node.querySelector('.report-nav');
  scroll.addEventListener('scroll', () => nav.classList.toggle('is-solid', scroll.scrollTop > 64), { passive: true });
  load(r);
  return r;
}

/* ---------- loading ---------- */
async function load(r) {
  const run = ++r.run;
  if (r.ctl) r.ctl.abort();
  r.ctl = typeof AbortController === 'function' ? new AbortController() : null;
  r.data = null;
  r.error = '';
  r.shown = 0;
  r.live = { stage: 'searching' };
  paint(r);
  try {
    await api.searchReportStream({
      query: r.query, include: r.include, exclude: r.exclude, signal: r.ctl ? r.ctl.signal : undefined,
      onEvent: (ev) => { if (run === r.run) handle(r, ev); },
    });
    if (run !== r.run) return;
    if (!r.data) throw new api.ApiError(500, r.error || 'Could not make the report.');
  } catch (e) {
    if (run !== r.run || (e && e.name === 'AbortError')) return;
    r.live = null;
    r.failed = e;
    paint(r);
  }
}

function handle(r, ev) {
  if (ev.event === 'judging') r.live = { ...r.live, stage: 'judging', candidates: ev.candidates, reading: ev.reels || [] };
  else if (ev.event === 'judged') r.live = { ...r.live, stage: 'writing', used: ev.used || [] };
  else if (ev.event === 'partial') r.live = { ...r.live, stage: 'writing', partial: ev.report };
  else if (ev.event === 'done') {
    r.live = null;
    r.failed = null;
    r.data = ev.report;
    if (ev.report.status !== 'ok') r.skippedOpen = true;
    r.pendingInclude = new Set(r.include);
    r.pendingExclude = new Set(r.exclude);
    haptic(10);
  } else if (ev.event === 'error') {
    r.error = ev.detail || '';
    return;
  } else return;
  paint(r);
}

/* ---------- pieces ---------- */
function itemOf(res) {
  const lib = reel(res.reel_id);
  const name = lib ? lib.name : ((res.item_names || [])[0] || res.main_subject || 'Saved reel');
  const src = lib ? lib.thumb : ((res.media || {}).thumbnail_url || '');
  return { id: res.reel_id, name, src, color: lib ? lib.color : '#1c1c20', creator: lib ? lib.creator : '', inLib: !!lib };
}

function thumbHtml(it, cls, inner = '') {
  return `<span class="${cls}" style="--c:${it.color}">${it.src ? `<img class="full" src="${esc(it.src)}" alt="" loading="lazy" decoding="async" data-fade>` : ''}${inner}</span>`;
}

function refs(list, watch) {
  return (list || []).map((n) => `<button class="rp-ref ${watch ? 'is-watch' : ''}" type="button" data-ref="${Number(n)}" aria-label="Watch reel ${Number(n)}">${watch ? icon('play') : ''}${Number(n)}</button>`).join('');
}

function safeHref(href) { return /^https?:[/][/]/i.test(href || '') ? href : ''; }

function blocksHtml(blocks, freshFrom) {
  let idx = 0;
  const html = (blocks || []).map((b) => {
    const head = b.heading ? `<h3 class="head rp-h">${esc(b.heading)}</h3>` : '';
    if (b.type === 'cards') {
      return `<section class="rp-block">${head}<div class="rp-cards">${(b.items || []).map((c) => card(c, freshFrom !== undefined && idx++ >= freshFrom)).join('')}</div></section>`;
    }
    const tag = b.type === 'steps' ? 'ol' : 'ul';
    const key = (p) => (p.refs || []).join(',');
    const items = b.items || [];
    const shared = items.length > 1 && items.every((p) => key(p) === key(items[0]));
    const top = shared ? `<div class="rp-sec-head">${head || '<span></span>'}<span class="rp-refs">${refs(items[0].refs, true)}</span></div>` : head;
    return `<section class="rp-block">${top}<${tag} class="rp-points ${b.type === 'steps' ? 'is-steps' : ''}">${items.map((p) => `<li><span>${esc(p.text)}</span>${shared ? '' : `<span class="rp-refs">${refs(p.refs)}</span>`}</li>`).join('')}</${tag}></section>`;
  }).join('');
  return { html, cards: idx };
}

function card(c, isNew) {
  const kind = KIND[c.kind] || '';
  const actions = (c.actions || []).filter((a) => safeHref(a.href));
  return `<article class="rp-card ${isNew ? 'is-new' : ''}">
    <div class="rp-card-top"><h4>${esc(c.name)}</h4>${kind ? `<span class="rp-kind">${kind}</span>` : ''}</div>
    ${c.location ? `<p class="rp-loc">${icon('pin')}${esc(c.location)}</p>` : ''}
    ${c.what ? `<p class="rp-what">${esc(c.what)}</p>` : ''}
    ${c.details && c.details.length ? `<dl class="rp-details">${c.details.map((d) => `<div><dt>${esc(d[0])}</dt><dd>${esc(d[1])}</dd></div>`).join('')}</dl>` : ''}
    <div class="rp-actions">${actions.map((a) => `<a class="rp-act ${a.label === 'Open' ? 'is-primary' : ''}" href="${esc(a.href)}" target="_blank" rel="noopener noreferrer">${icon(ACTION_ICON[a.label] || 'ext')}<span>${esc(a.label)}</span></a>`).join('')}<span class="rp-refs">${refs(c.refs, true)}</span></div>
  </article>`;
}

function strip(items, reading) {
  return `<div class="rp-strip ${reading ? 'is-reading' : ''}">${items.map((it, i) => reading
    ? `<span class="rp-strip-item" style="--d:${(i % 8) * 90}ms">${thumbHtml(it, 'rp-thumb')}</span>`
    : `<button class="rp-strip-item pressable" type="button" data-ref="${i + 1}" aria-label="Watch reel ${i + 1}">${thumbHtml(it, 'rp-thumb', `<span class="rp-num">${i + 1}</span>`)}</button>`).join('')}</div>`;
}

function reelRow(it, i, kind, why, st) {
  const label = kind === 'used' ? (st === 'off' ? 'Put this reel back' : 'Leave this reel out') : (st === 'picked' ? 'Undo adding this reel' : 'Add this reel to the report');
  const ic = kind === 'used' ? (st === 'off' ? 'undo' : 'x') : (st === 'picked' ? 'check' : 'plus');
  return `<div class="rp-reel ${st ? 'is-' + st : ''}">
    <button class="rp-open pressable" type="button" data-open="${kind}:${i}">${thumbHtml(it, 'rp-row-thumb', kind === 'used' ? `<span class="rp-num">${i + 1}</span>` : '')}
      <span class="rp-meta"><b class="clamp-2">${esc(it.name)}</b>${why ? `<small>${esc(why)}</small>` : (it.creator ? `<small>${esc(it.creator)}</small>` : '')}</span></button>
    <button class="icon-btn is-filled rp-toggle" type="button" data-toggle="${kind}:${i}" aria-label="${label}">${icon(ic)}</button>
  </div>`;
}

/* ---------- paint ---------- */
function paint(r) {
  const node = r.node;
  const body = node.querySelector('[data-body]');
  const scroll = node.querySelector('[data-scroll]');
  const keep = scroll.scrollTop;
  const q = esc(r.query);
  const shareBtn = node.querySelector('[data-share]');
  let html = '';
  let title = 'Report';
  shareBtn.hidden = true;
  node.querySelector('[data-update]').hidden = true;
  let used = [];
  let skipped = [];

  if (r.failed) {
    html = `<p class="eyebrow">Report</p><h1 class="title rp-title">Could not make <em>this report.</em></h1>
      <p class="sm muted rp-sub">${esc(r.failed.status === 0 ? errorMessage(r.failed) : (r.failed.detail || r.failed.message || 'Something went wrong. Try again.'))}</p>
      <button class="btn btn-primary btn-block rp-retry" type="button" data-retry>Try again</button>`;
  } else if (r.live) {
    const L = r.live;
    title = (L.partial && L.partial.title) || 'Report';
    if (L.stage === 'searching') {
      html = `<p class="eyebrow">Report</p><h1 class="title rp-title">Reading your reels for <em>"${q}"</em></h1>
        <div class="rp-loading"><span class="spinner-mark"></span><span class="sm muted">Searching your library</span></div>
        ${'<div class="rp-sk"><span class="sk sk-line"></span><span class="sk sk-line"></span><span class="sk sk-line is-short"></span></div>'.repeat(2)}`;
    } else if (L.stage === 'judging') {
      const reading = (L.reading || []).map(itemOf);
      html = `<p class="eyebrow">Report</p><h1 class="title rp-title">Reading ${plural(L.candidates || reading.length, 'reel')}</h1>
        <p class="sm muted rp-sub">Finding the ones that are really about "${q}".</p>
        ${reading.length ? strip(reading, true) : '<div class="rp-loading"><span class="spinner-mark"></span></div>'}`;
    } else {
      used = (L.used || []).map(itemOf);
      html = `<p class="eyebrow">Report</p><h1 class="title rp-title">${L.partial && L.partial.title ? esc(L.partial.title) : `Writing about <em>"${q}"</em>`}</h1>
        <p class="sm muted rp-sub">${used.length ? `From ${plural(used.length, 'reel')} about "${q}"` : 'None of your reels answer this'}</p>
        ${used.length ? strip(used, false) : ''}`;
      if (L.partial) {
        if (L.partial.intro) html += `<p class="rp-intro">${esc(L.partial.intro)}</p>`;
        const built = blocksHtml(L.partial.blocks, r.shown);
        html += built.html;
        r.shown = built.cards;
      }
      if (used.length) html += '<div class="rp-writing"><span class="pulse-dot"></span>Writing your report</div>';
    }
  } else if (r.data) {
    const d = r.data;
    title = d.title || r.query;
    const usedRaw = d.used || [];
    const skippedRaw = d.skipped || [];
    used = usedRaw.map(itemOf);
    skipped = skippedRaw.map(itemOf);
    const total = used.length + skippedRaw.filter((s) => s.why !== 'Removed by you').length;
    shareBtn.hidden = d.status !== 'ok';
    html = `<p class="eyebrow">Report</p><h1 class="title rp-title">${esc(d.title || r.query)}</h1>
      <p class="sm muted rp-sub">From ${used.length} of ${plural(total, 'reel')} for "${q}"</p>
      ${used.length ? strip(used, false) : ''}`;
    if (d.status === 'empty') html += `<div class="lesson rp-empty"><p class="head">Nothing matches <em>"${q}"</em> yet.</p><p class="sm">Save a few reels about it and run the report again.</p></div>`;
    else if (d.status !== 'ok') html += `<div class="lesson rp-empty"><p class="head">Nothing specific to say yet.</p><p class="sm">None of these reels talk about "${q}" in detail. Add any that should count from Skipped below.</p></div>`;
    if (d.intro) html += `<p class="rp-intro">${esc(d.intro)}</p>`;
    html += blocksHtml(d.blocks).html;
    if (d.gaps) html += `<p class="rp-gaps">${icon('info')}<span>${esc(d.gaps)}</span></p>`;
    if (used.length) {
      html += `<p class="eyebrow is-quiet rp-label">Reels in this report</p><div class="rp-reels">${used.map((it, i) => reelRow(it, i, 'used', '', r.pendingExclude.has(usedRaw[i].reel_id) ? 'off' : '')).join('')}</div>`;
    }
    if (skipped.length) {
      html += `<details class="rp-skipped" ${r.skippedOpen ? 'open' : ''}><summary class="rp-label-sum">${icon('chev')}<span>Skipped ${skipped.length}</span><small>Reels the search found but the report left out</small></summary>
        <div class="rp-reels">${skipped.map((it, i) => reelRow(it, i, 'skipped', skippedRaw[i].why || '', r.pendingInclude.has(skippedRaw[i].reel_id) ? 'picked' : '')).join('')}</div></details>`;
    }
    const same = (set, list) => set.size === list.length && list.every((id) => set.has(id));
    const dirty = !same(r.pendingInclude, r.include) || !same(r.pendingExclude, r.exclude);
    const upd = node.querySelector('[data-update]');
    if (dirty && upd.hidden) {
      upd.hidden = false;
      if (!isReduced()) animate(upd, [{ opacity: 0, transform: 'translateY(20px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 300, easing: 'snap', clear: true });
    }
    upd.hidden = !dirty;
    r.usedRaw = usedRaw;
    r.skippedRaw = skippedRaw;
  }
  node.querySelector('[data-navtitle]').textContent = title;
  body.innerHTML = html;
  scroll.scrollTop = keep;
  wireFades(body);
  if (!isReduced()) body.querySelectorAll('.rp-card.is-new').forEach((c, i) => animate(c, [{ opacity: 0, transform: 'translateY(14px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 380, delay: i * 70, clear: true }));
  wire(r, used, skipped);
}

function playable(list) { return list.filter((it) => it.inLib).map((it) => it.id); }

function wire(r, used, skipped) {
  const body = r.node.querySelector('[data-body]');
  const retry = body.querySelector('[data-retry]');
  if (retry) retry.addEventListener('click', () => { r.failed = null; load(r); });
  body.querySelectorAll('[data-ref]').forEach((b) => b.addEventListener('click', () => {
    const n = Number(b.dataset.ref);
    const it = used[n - 1];
    if (!it) return;
    if (!it.inLib) { toast({ msg: 'That reel is not in your library any more.', tone: 'error' }); return; }
    const ids = playable(used);
    openPlayer(ids, ids.indexOf(it.id), b.querySelector('.rp-thumb'));
  }));
  body.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => {
    const [kind, i] = b.dataset.open.split(':');
    const list = kind === 'used' ? used : skipped;
    const it = list[Number(i)];
    if (!it || !it.inLib) return;
    const ids = playable(list);
    openPlayer(ids, ids.indexOf(it.id), b.querySelector('.rp-row-thumb'));
  }));
  const det = body.querySelector('.rp-skipped');
  if (det) det.addEventListener('toggle', () => { r.skippedOpen = det.open; });
  body.querySelectorAll('[data-toggle]').forEach((b) => b.addEventListener('click', () => {
    const [kind, i] = b.dataset.toggle.split(':');
    const id = (kind === 'used' ? r.usedRaw : r.skippedRaw)[Number(i)].reel_id;
    if (kind === 'used') {
      if (r.pendingExclude.has(id)) { r.pendingExclude.delete(id); if (r.include.includes(id)) r.pendingInclude.add(id); }
      else { r.pendingExclude.add(id); r.pendingInclude.delete(id); }
    } else if (r.pendingInclude.has(id)) { r.pendingInclude.delete(id); if (r.exclude.includes(id)) r.pendingExclude.add(id); }
    else { r.pendingInclude.add(id); r.pendingExclude.delete(id); }
    haptic(6);
    paint(r);
  }));
  if (r.live && r.live.stage === 'judging' && !isReduced()) rise(body.querySelectorAll('.rp-strip-item'), { y: 6, stagger: 40, duration: 300 });
}

/* ---------- share as plain text (sent as the user's own message: no dashes) ---------- */
function plainText(d) {
  const clean = (t) => String(t || '').replace(/ +[—–] +/g, ', ').replace(/[—–]/g, '-');
  const lines = [clean(d.title)];
  if (d.intro) lines.push(clean(d.intro));
  (d.blocks || []).forEach((b) => {
    lines.push('');
    if (b.heading) lines.push(clean(b.heading).toUpperCase());
    (b.items || []).forEach((it, i) => {
      if (b.type === 'cards') {
        const facts = (it.details || []).map((x) => clean(x[0]) + ': ' + clean(x[1])).join(', ');
        const link = (it.actions || []).find((a) => safeHref(a.href));
        lines.push('• ' + clean(it.name) + (it.location ? ' (' + clean(it.location) + ')' : '') + (it.what ? ': ' + clean(it.what) : '') + (facts ? '. ' + facts : '') + (link ? NL + '  ' + link.href : ''));
      } else lines.push((b.type === 'steps' ? (i + 1) + '. ' : '• ') + clean(it.text));
    });
  });
  lines.push('', 'Made with ClipNest from my saved reels');
  return lines.join(NL);
}

function share(r) {
  const d = r.data;
  if (!d) return;
  const text = plainText(d);
  if (navigator.share) { navigator.share({ title: d.title, text }).catch(() => {}); return; }
  copyText(text).then((ok) => toast(ok ? { msg: 'Report copied', icon: 'copy' } : { msg: 'Could not copy the report', tone: 'error' }));
}

export { S };
