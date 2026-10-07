// Search report (admin): one AI read across the reels a search returned.
// It streams: searching -> judging (which reels count) -> writing (rows
// appear as they are written) -> done.
//
// Layout is summary first, details on demand (measured: the old full-card
// layout ran 3.6 to 8.8 phone screens, showed 1 or 2 cards on screen 1, and
// 46% of cards carried no fact at all):
//   your reels (strip) -> Quick take -> section tabs -> compact rows
//   (thumb, name, the one key fact, primary action; tap to open the rest)
//   -> fact-less items folded into one "Also mentioned" line -> steps
//   collapsed per method -> tips capped at 3 -> Edit reels in a sheet.
// Usage beacons (api.reportEvent) say which parts get used.
import { el, esc, plural, haptic, NL } from './util.js';
import { icon } from './icons.js';
import { S, reel } from './store.js';
import * as api from './api.js';
import { pushLayer, closeLayer, isOpen } from './router.js';
import { animate, isReduced, rise } from './motion.js';
import { toast, copyText, errorMessage, openSheet } from './ui.js';
import { wireFades } from './cards.js';
import { openPlayer } from './player.js';

const KIND = { place: 'Place', activity: 'Activity', stay: 'Stay', dish: 'Dish', website: 'Website', app: 'App', product: 'Product', title: 'Watch', person: 'Person' };
const ACTION_ICON = { Map: 'map', Open: 'ext', Search: 'search' };
const ALSO_MIN = 3;   // this many fact-less items in a section fold into one line
const TIPS_SHOWN = 3;
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
  const r = {
    node, query, include: [], exclude: [], data: null, live: null,
    pendingInclude: new Set(), pendingExclude: new Set(), run: 0, shown: 0,
    open: new Set(), steps: new Set(), closedSteps: new Set(), more: new Set(), all: false, viewed: false,
  };
  R = r;
  if (isReduced()) animate(node, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 });
  else animate(node, [{ opacity: 0, transform: 'translateY(24px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 380, easing: 'snap', clear: true });
  r.layer = pushLayer({
    kind: 'overlay',
    hidesDock: true,
    close: ({ instant }) => {
      r.run += 1;
      if (r.ctl) r.ctl.abort();
      if (r.sheet) r.sheet.close();
      if (R === r) R = null;
      if (instant || isReduced()) { node.remove(); return; }
      animate(node, [{ opacity: 1, transform: 'translateY(0)' }, { opacity: 0, transform: 'translateY(18px)' }], { duration: 200, easing: 'in' }).then(() => node.remove());
    },
  });
  node.querySelector('[data-back]').addEventListener('click', () => closeLayer(r.layer));
  node.querySelector('[data-share]').addEventListener('click', () => share(r));
  node.querySelector('[data-update] button').addEventListener('click', () => applyEdits(r));
  const scroll = node.querySelector('[data-scroll]');
  const nav = node.querySelector('.report-nav');
  scroll.addEventListener('scroll', () => {
    nav.classList.toggle('is-solid', scroll.scrollTop > 64);
    markJump(r);
  }, { passive: true });
  load(r);
  return r;
}

function track(r, event, detail) {
  if (api.reportEvent) api.reportEvent(event, detail || '', r.query);
}

/* ---------- loading ---------- */
async function load(r) {
  const run = ++r.run;
  if (r.ctl) r.ctl.abort();
  r.ctl = typeof AbortController === 'function' ? new AbortController() : null;
  r.data = null;
  r.error = '';
  r.shown = 0;
  r.viewed = false;
  r.open = new Set(); r.steps = new Set(); r.closedSteps = new Set(); r.more = new Set(); r.all = false;
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
  return `<span class="${cls}" style="--c:${it ? it.color : '#1c1c20'}">${it && it.src ? `<img class="full" src="${esc(it.src)}" alt="" loading="lazy" decoding="async" data-fade>` : ''}${inner}</span>`;
}

function refs(list, watch) {
  return (list || []).map((n) => `<button class="rp-ref ${watch ? 'is-watch' : ''}" type="button" data-ref="${Number(n)}" aria-label="Watch reel ${Number(n)}">${watch ? icon('play') : ''}${Number(n)}</button>`).join('');
}

function safeHref(href) { return /^https?:[/][/]/i.test(href || '') ? href : ''; }

function actionsOf(c) { return (c.actions || []).filter((a) => safeHref(a.href)); }

function strip(items, reading) {
  return `<div class="rp-strip ${reading ? 'is-reading' : ''}">${items.map((it, i) => reading
    ? `<span class="rp-strip-item" style="--d:${(i % 8) * 90}ms">${thumbHtml(it, 'rp-thumb')}</span>`
    : `<button class="rp-strip-item pressable" type="button" data-ref="${i + 1}" data-src="strip" aria-label="Watch reel ${i + 1}">${thumbHtml(it, 'rp-thumb', `<span class="rp-num">${i + 1}</span>`)}</button>`).join('')}</div>`;
}

function quickTake(highlights) {
  if (!highlights || !highlights.length) return '';
  return `<section class="rp-qt" aria-label="Quick take"><p class="eyebrow">Quick take</p>
    <ul>${highlights.map((h) => `<li><span>${esc(h.text)}</span><span class="rp-refs">${refs(h.refs, true)}</span></li>`).join('')}</ul></section>`;
}

// One compact row: thumbnail (plays the source reel), name + the one key
// fact, the primary action. Tap the row for everything else.
function row(c, key, used, opts) {
  const open = opts.open;
  const acts = actionsOf(c);
  const primary = acts[0];
  const first = (c.refs || [])[0];
  const it = first ? used[first - 1] : null;
  const kind = KIND[c.kind] || '';
  const line = c.key || (c.thin ? (c.what || c.location) : '');
  const sub = [kind, c.location].filter(Boolean).join(' · ');
  return `<article class="rp-row ${open ? 'is-open' : ''} ${opts.fresh ? 'is-new' : ''}" data-row="${key}">
    ${first ? `<button class="rp-row-thumb pressable" type="button" data-ref="${first}" data-src="row" aria-label="Watch reel ${first}">${thumbHtml(it, 'rp-row-img', `<span class="rp-num">${first}</span>`)}</button>` : '<span class="rp-row-thumb"></span>'}
    <button class="rp-row-main" type="button" data-toggle-row="${key}" aria-expanded="${open ? 'true' : 'false'}">
      <b class="rp-row-name">${esc(c.name)}</b>
      ${line ? `<span class="rp-row-key ${c.key ? '' : 'is-plain'}">${esc(line)}</span>` : ''}
    </button>
    ${primary ? `<a class="rp-row-act pressable" href="${esc(primary.href)}" target="_blank" rel="noopener noreferrer" data-act="${esc(primary.label)}" data-src="row" aria-label="${esc(primary.label)}: ${esc(c.name)}">${icon(ACTION_ICON[primary.label] || 'ext')}</a>` : '<span></span>'}
    ${open ? `<div class="rp-row-more">
      ${sub ? `<p class="rp-row-sub">${esc(sub)}</p>` : ''}
      ${c.what && c.what !== line ? `<p class="rp-what">${esc(c.what)}</p>` : ''}
      ${c.details && c.details.length ? `<dl class="rp-details">${c.details.map((d) => `<div><dt>${esc(d[0])}</dt><dd>${esc(d[1])}</dd></div>`).join('')}</dl>` : ''}
      <div class="rp-actions">${acts.map((a) => `<a class="rp-act ${a.label === 'Open' ? 'is-primary' : ''}" href="${esc(a.href)}" target="_blank" rel="noopener noreferrer" data-act="${esc(a.label)}" data-src="pill">${icon(ACTION_ICON[a.label] || 'ext')}<span>${esc(a.label)}</span></a>`).join('')}<span class="rp-refs">${refs(c.refs, true)}</span></div>
    </div>` : ''}
  </article>`;
}

function also(items) {
  return `<div class="rp-also"><p class="rp-also-h">Also mentioned</p><div class="rp-also-list">${items.map((c) => {
    const a = actionsOf(c)[0];
    const label = `${icon(a ? (ACTION_ICON[a.label] || 'ext') : 'pin')}<span>${esc(c.name)}</span>`;
    return a
      ? `<a class="rp-also-chip pressable" href="${esc(a.href)}" target="_blank" rel="noopener noreferrer" data-act="${esc(a.label)}" data-src="also">${label}</a>`
      : `<span class="rp-also-chip">${label}</span>`;
  }).join('')}</div></div>`;
}

// final: true once the report is done (folding and collapsing only then, so
// streamed rows never jump between layouts mid-write).
function blocksHtml(r, blocks, used, final) {
  let fresh = 0;
  return (blocks || []).map((b, bi) => {
    const items = b.items || [];
    const id = `rp-b${bi}`;
    const count = items.length;
    if (b.type === 'cards') {
      const thin = final ? items.filter((c) => c.thin) : [];
      const folded = thin.length >= ALSO_MIN;
      const rows = folded ? items.filter((c) => !c.thin) : items;
      const head = b.heading ? `<div class="rp-bhead"><h3 class="head rp-h">${esc(b.heading)}</h3><span class="rp-count">${count}</span></div>` : '';
      const rowsHtml = rows.map((c, ci) => {
        const key = `${bi}:${items.indexOf(c)}`;
        const isNew = !final && fresh++ >= r.shown;
        return row(c, key, used, { open: final && (r.all || r.open.has(key)), fresh: isNew });
      }).join('');
      return `<section class="rp-block" id="${id}" data-block="${bi}">${head}${rowsHtml ? `<div class="rp-rows">${rowsHtml}</div>` : ''}${folded ? also(thin) : ''}</section>`;
    }
    if (b.type === 'steps') {
      const open = !final || r.all || r.steps.has(bi) || (bi === 0 && !r.closedSteps.has(bi));
      const key = (p) => (p.refs || []).join(',');
      const shared = items.length > 0 && items.every((p) => key(p) === key(items[0]));
      return `<section class="rp-block" id="${id}" data-block="${bi}">
        <div class="rp-steps ${open ? 'is-open' : ''}">
          <button class="rp-steps-head" type="button" data-steps="${bi}" aria-expanded="${open ? 'true' : 'false'}">
            <span class="rp-steps-ico">${icon('steps')}</span>
            <span class="rp-steps-t"><b>${esc(b.heading || 'Steps')}</b><small>${plural(count, 'step')}</small></span>
            <span class="rp-steps-chev">${icon('chev')}</span>
          </button>
          ${open ? `<ol class="rp-points is-steps">${items.map((p) => `<li><span>${esc(p.text)}</span>${shared ? '' : `<span class="rp-refs">${refs(p.refs)}</span>`}</li>`).join('')}</ol>
          ${shared && items[0].refs && items[0].refs.length ? `<div class="rp-steps-src"><span class="sm muted">From</span>${refs(items[0].refs, true)}</div>` : ''}` : ''}
        </div></section>`;
    }
    const showAll = !final || r.all || r.more.has(bi) || items.length <= TIPS_SHOWN + 1;
    const shownItems = showAll ? items : items.slice(0, TIPS_SHOWN);
    return `<section class="rp-block" id="${id}" data-block="${bi}">
      ${b.heading ? `<div class="rp-bhead"><h3 class="head rp-h">${esc(b.heading)}</h3><span class="rp-count">${count}</span></div>` : ''}
      <ul class="rp-points">${shownItems.map((p) => `<li><span>${esc(p.text)}</span><span class="rp-refs">${refs(p.refs)}</span></li>`).join('')}</ul>
      ${showAll ? '' : `<button class="link-btn rp-more" type="button" data-more="${bi}">${icon('chev')}Show ${plural(items.length - TIPS_SHOWN, 'more tip')}</button>`}
    </section>`;
  }).join('');
}

function jumpNav(blocks) {
  if (!blocks || blocks.length < 2) return '';
  return `<nav class="rp-jump" data-jumpnav aria-label="Report sections"><div class="chips">
    ${blocks.map((b, bi) => `<button class="chip" type="button" data-jump="${bi}">${esc(b.label || b.heading || 'Section')}${b.type === 'cards' ? `<span class="chip-n">${(b.items || []).length}</span>` : ''}</button>`).join('')}
    <button class="chip rp-expall" type="button" data-expand-all>${icon('stack')}<span data-expall-t>Expand all</span></button>
  </div></nav>`;
}

function reelRow(it, i, kind, why, st) {
  const label = kind === 'used' ? (st === 'off' ? 'Put this reel back' : 'Leave this reel out') : (st === 'picked' ? 'Undo adding this reel' : 'Add this reel to the report');
  const ic = kind === 'used' ? (st === 'off' ? 'undo' : 'x') : (st === 'picked' ? 'check' : 'plus');
  return `<div class="rp-reel ${st ? 'is-' + st : ''}">
    <button class="rp-open pressable" type="button" data-open="${kind}:${i}">${thumbHtml(it, 'rp-row-img', kind === 'used' ? `<span class="rp-num">${i + 1}</span>` : '')}
      <span class="rp-meta"><b class="clamp-2">${esc(it.name)}</b>${why ? `<small>${esc(why)}</small>` : (it.creator ? `<small>${esc(it.creator)}</small>` : '')}</span></button>
    <button class="icon-btn is-filled rp-toggle" type="button" data-toggle="${kind}:${i}" aria-label="${label}">${icon(ic)}</button>
  </div>`;
}

function reelLists(r, used, skipped) {
  const d = r.data;
  const usedRaw = d.used || [];
  const skippedRaw = d.skipped || [];
  return `${used.length ? `<p class="eyebrow is-quiet rp-label">In this report</p><div class="rp-reels">${used.map((it, i) => reelRow(it, i, 'used', '', r.pendingExclude.has(usedRaw[i].reel_id) ? 'off' : '')).join('')}</div>` : ''}
    ${skipped.length ? `<p class="eyebrow is-quiet rp-label">Left out <span class="rp-label-n">Reels the search found but the report skipped</span></p><div class="rp-reels">${skipped.map((it, i) => reelRow(it, i, 'skipped', skippedRaw[i].why || '', r.pendingInclude.has(skippedRaw[i].reel_id) ? 'picked' : '')).join('')}</div>` : ''}`;
}

function dirty(r) {
  const same = (set, list) => set.size === list.length && list.every((id) => set.has(id));
  return !same(r.pendingInclude, r.include) || !same(r.pendingExclude, r.exclude);
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
        html += quickTake(L.partial.highlights);
        html += blocksHtml(r, L.partial.blocks, used, false);
        r.shown = (L.partial.blocks || []).filter((b) => b.type === 'cards').reduce((n, b) => n + (b.items || []).length, 0);
      }
      if (used.length) html += '<div class="rp-writing"><span class="pulse-dot"></span>Writing your report</div>';
    }
  } else if (r.data) {
    const d = r.data;
    title = d.title || r.query;
    used = (d.used || []).map(itemOf);
    skipped = (d.skipped || []).map(itemOf);
    shareBtn.hidden = d.status !== 'ok';
    if (d.status === 'ok') {
      html = `<p class="eyebrow">Report</p><h1 class="title rp-title">${esc(title)}</h1>
        <p class="sm muted rp-sub">From ${plural(used.length, 'of your reels', 'of your reels')}. Tap one to watch.</p>
        ${strip(used, false)}
        ${quickTake(d.highlights) || (d.intro ? `<p class="rp-intro">${esc(d.intro)}</p>` : '')}
        ${jumpNav(d.blocks)}
        ${blocksHtml(r, d.blocks, used, true)}
        ${d.gaps ? `<p class="rp-gaps">${icon('info')}<span>${esc(d.gaps)}</span></p>` : ''}
        <button class="rp-edit pressable" type="button" data-edit>
          <span class="rp-edit-ico">${icon('edit')}</span>
          <span class="rp-edit-t"><b>Edit reels</b><small>${plural(used.length, 'reel')} in${skipped.length ? `, ${skipped.length} left out` : ''}</small></span>
          ${icon('chev')}
        </button>`;
      if (!r.viewed) { r.viewed = true; track(r, 'view', `${used.length} reels`); }
    } else {
      // Nothing to show: the reels to add back are the whole screen.
      html = `<p class="eyebrow">Report</p><h1 class="title rp-title">${esc(r.query)}</h1>
        ${d.status === 'empty'
          ? `<div class="lesson rp-empty"><p class="head">Nothing matches <em>"${q}"</em> yet.</p><p class="sm">Save a few reels about it and run the report again.</p></div>`
          : `<div class="lesson rp-empty"><p class="head">Nothing specific to say yet.</p><p class="sm">None of these reels talk about "${q}" in detail. Add any that should count below.</p></div>`}
        ${reelLists(r, used, skipped)}`;
      if (!r.viewed) { r.viewed = true; track(r, 'view', d.status); }
      const upd = node.querySelector('[data-update]');
      const isDirty = dirty(r);
      if (isDirty && upd.hidden && !isReduced()) animate(upd, [{ opacity: 0, transform: 'translateY(20px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 300, easing: 'snap', clear: true });
      upd.hidden = !isDirty;
    }
  }
  node.querySelector('[data-navtitle]').textContent = title;
  body.innerHTML = html;
  scroll.scrollTop = keep;
  wireFades(body);
  if (!isReduced()) body.querySelectorAll('.rp-row.is-new').forEach((c, i) => animate(c, [{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 320, delay: i * 60, clear: true }));
  wire(r, used, skipped);
  markJump(r);
}

function playable(list) { return list.filter((it) => it.inLib).map((it) => it.id); }

function play(r, used, n, from, src) {
  const it = used[n - 1];
  if (!it) return;
  if (!it.inLib) { toast({ msg: 'That reel is not in your library any more.', tone: 'error' }); return; }
  track(r, 'watch', src || 'ref');
  const ids = playable(used);
  openPlayer(ids, ids.indexOf(it.id), from);
}

function wire(r, used, skipped) {
  const body = r.node.querySelector('[data-body]');
  const retry = body.querySelector('[data-retry]');
  if (retry) retry.addEventListener('click', () => { r.failed = null; load(r); });
  body.querySelectorAll('[data-ref]').forEach((b) => b.addEventListener('click', () => {
    play(r, used, Number(b.dataset.ref), b.querySelector('.rp-thumb, .rp-row-img'), b.dataset.src);
  }));
  body.querySelectorAll('[data-act]').forEach((a) => a.addEventListener('click', () => {
    track(r, 'action', `${a.dataset.act}:${a.dataset.src || ''}`);
  }));
  body.querySelectorAll('[data-toggle-row]').forEach((b) => b.addEventListener('click', () => {
    const key = b.dataset.toggleRow;
    if (!r.data) return;
    const opening = !(r.all || r.open.has(key));
    if (r.all) {
      // Closing one row while everything is open: switch to per-row state.
      r.all = false;
      r.open = new Set(allRowKeys(r.data.blocks));
    }
    if (opening) r.open.add(key); else r.open.delete(key);
    if (opening) {
      const [bi, ci] = key.split(':').map(Number);
      const c = ((r.data.blocks[bi] || {}).items || [])[ci];
      track(r, 'expand', c ? c.kind : '');
    }
    haptic(6);
    paint(r);
    if (opening && !isReduced()) {
      const more = r.node.querySelector(`[data-row="${key}"] .rp-row-more`);
      if (more) animate(more, [{ opacity: 0, transform: 'translateY(-4px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 220, clear: true });
    }
  }));
  body.querySelectorAll('[data-steps]').forEach((b) => b.addEventListener('click', () => {
    const bi = Number(b.dataset.steps);
    const open = b.getAttribute('aria-expanded') === 'true';
    if (r.all) { r.all = false; r.open = new Set(allRowKeys(r.data.blocks)); allStepKeys(r.data.blocks).forEach((k) => r.steps.add(k)); }
    // A report that opens with a method shows it open; every other method
    // starts as one line ("Crop a shirt · 4 steps") until tapped.
    if (open) { r.steps.delete(bi); r.closedSteps.add(bi); } else { r.steps.add(bi); r.closedSteps.delete(bi); track(r, 'steps', String(bi)); }
    haptic(6);
    paint(r);
  }));
  body.querySelectorAll('[data-more]').forEach((b) => b.addEventListener('click', () => {
    r.more.add(Number(b.dataset.more));
    track(r, 'more', b.dataset.more);
    paint(r);
  }));
  body.querySelectorAll('[data-jump]').forEach((b) => b.addEventListener('click', () => {
    const bi = Number(b.dataset.jump);
    const blocks = (r.data || {}).blocks || [];
    track(r, 'jump', (blocks[bi] || {}).label || '');
    jumpTo(r, bi);
  }));
  const all = body.querySelector('[data-expand-all]');
  if (all) {
    all.classList.toggle('is-on', r.all);
    all.querySelector('[data-expall-t]').textContent = r.all ? 'Collapse all' : 'Expand all';
    all.addEventListener('click', () => {
      r.all = !r.all;
      r.open = new Set();
      r.steps = new Set();
      r.closedSteps = new Set();
      if (r.all) track(r, 'expand_all');
      haptic(8);
      paint(r);
    });
  }
  const edit = body.querySelector('[data-edit]');
  if (edit) edit.addEventListener('click', () => openEdit(r));
  wireReelLists(r, body, used, skipped);
  if (r.live && r.live.stage === 'judging' && !isReduced()) rise(body.querySelectorAll('.rp-strip-item'), { y: 6, stagger: 40, duration: 300 });
}

function allRowKeys(blocks) {
  const keys = [];
  (blocks || []).forEach((b, bi) => { if (b.type === 'cards') (b.items || []).forEach((c, ci) => keys.push(`${bi}:${ci}`)); });
  return keys;
}

function allStepKeys(blocks) {
  return (blocks || []).map((b, bi) => (b.type === 'steps' ? bi : -1)).filter((bi) => bi >= 0);
}

/* ---------- section tabs ---------- */
function stickyOffset(r) {
  const scroll = r.node.querySelector('[data-scroll]');
  const nav = r.node.querySelector('.report-nav');
  const jump = r.node.querySelector('[data-jumpnav]');
  const top = scroll.getBoundingClientRect().top;
  return (nav.getBoundingClientRect().bottom - top) + (jump ? jump.offsetHeight : 0) + 8;
}

function jumpTo(r, bi) {
  const scroll = r.node.querySelector('[data-scroll]');
  const sec = r.node.querySelector(`#rp-b${bi}`);
  if (!sec) return;
  const y = scroll.scrollTop + (sec.getBoundingClientRect().top - scroll.getBoundingClientRect().top) - stickyOffset(r);
  // Sections near the end can't scroll up to the tabs; the tapped tab stays
  // lit until the person scrolls on their own.
  r.jumped = { bi, at: Date.now() };
  scroll.scrollTo({ top: Math.max(0, y), behavior: isReduced() ? 'auto' : 'smooth' });
  markJump(r);
}

// Light up the tab of the section under the tabs, and keep it in view.
function markJump(r) {
  const nav = r.node.querySelector('[data-jumpnav]');
  if (!nav) return;
  const scroll = r.node.querySelector('[data-scroll]');
  const line = scroll.getBoundingClientRect().top + stickyOffset(r) + 4;
  let current = 0;
  const secs = Array.from(r.node.querySelectorAll('.rp-block[data-block]'));
  secs.forEach((sec) => {
    if (sec.getBoundingClientRect().top <= line) current = Number(sec.dataset.block);
  });
  const atEnd = scroll.scrollTop + scroll.clientHeight >= scroll.scrollHeight - 4;
  if (r.jumped && Date.now() - r.jumped.at < 1500) current = r.jumped.bi;
  else if (atEnd && secs.length) current = Number(secs[secs.length - 1].dataset.block);
  const atStart = scroll.scrollTop < 40 && !(r.jumped && Date.now() - r.jumped.at < 1500);
  nav.querySelectorAll('[data-jump]').forEach((chip) => {
    const on = !atStart && Number(chip.dataset.jump) === current;
    if (on && !chip.classList.contains('is-on')) {
      const row = chip.parentElement;
      const left = chip.offsetLeft - row.clientWidth / 2 + chip.offsetWidth / 2;
      row.scrollTo({ left: Math.max(0, left), behavior: isReduced() ? 'auto' : 'smooth' });
    }
    chip.classList.toggle('is-on', on);
  });
}

/* ---------- editing which reels count ---------- */
function wireReelLists(r, root, used, skipped) {
  root.querySelectorAll('[data-open]').forEach((b) => b.addEventListener('click', () => {
    const [kind, i] = b.dataset.open.split(':');
    const list = kind === 'used' ? used : skipped;
    const it = list[Number(i)];
    if (!it || !it.inLib) return;
    const ids = playable(list);
    openPlayer(ids, ids.indexOf(it.id), b.querySelector('.rp-row-img'));
  }));
  root.querySelectorAll('[data-toggle]').forEach((b) => b.addEventListener('click', () => {
    const [kind, i] = b.dataset.toggle.split(':');
    const d = r.data;
    const id = (kind === 'used' ? d.used : d.skipped)[Number(i)].reel_id;
    if (kind === 'used') {
      if (r.pendingExclude.has(id)) { r.pendingExclude.delete(id); if (r.include.includes(id)) r.pendingInclude.add(id); }
      else { r.pendingExclude.add(id); r.pendingInclude.delete(id); }
    } else if (r.pendingInclude.has(id)) { r.pendingInclude.delete(id); if (r.exclude.includes(id)) r.pendingExclude.add(id); }
    else { r.pendingInclude.add(id); r.pendingExclude.delete(id); }
    haptic(6);
    if (r.sheet) paintEdit(r); else paint(r);
  }));
}

function openEdit(r) {
  if (!r.data) return;
  track(r, 'edit');
  const foot = el(`<div class="rp-edit-foot"><button class="btn btn-primary btn-block" type="button" data-apply disabled>${icon('refresh')}Update report</button></div>`);
  r.sheet = openSheet({
    title: 'Reels in this report',
    sub: 'Leave one out or add a skipped one back, then update.',
    body: '<div class="rp-edit-body"></div>',
    foot,
    className: 'rp-edit-sheet',
    expandable: true,
    onClose: () => { r.sheet = null; },
  });
  foot.querySelector('[data-apply]').addEventListener('click', () => {
    const s = r.sheet;
    r.sheet = null;
    if (s) s.close();
    applyEdits(r);
  });
  paintEdit(r);
}

function paintEdit(r) {
  if (!r.sheet || !r.data) return;
  const host = r.sheet.body.querySelector('.rp-edit-body');
  const used = (r.data.used || []).map(itemOf);
  const skipped = (r.data.skipped || []).map(itemOf);
  const keep = r.sheet.body.scrollTop;
  host.innerHTML = reelLists(r, used, skipped);
  r.sheet.body.scrollTop = keep;
  wireFades(host);
  wireReelLists(r, host, used, skipped);
  const apply = r.sheet.el.querySelector('[data-apply]');
  if (apply) apply.disabled = !dirty(r);
}

function applyEdits(r) {
  r.include = Array.from(r.pendingInclude);
  r.exclude = Array.from(r.pendingExclude);
  track(r, 'update', `+${r.include.length} -${r.exclude.length}`);
  r.node.querySelector('[data-scroll]').scrollTop = 0;
  load(r);
}

/* ---------- share as plain text (sent as the user's own message: no dashes) ---------- */
function plainText(d) {
  const clean = (t) => String(t || '').replace(/ +[—–] +/g, ', ').replace(/[—–]/g, '-');
  const lines = [clean(d.title)];
  if (d.highlights && d.highlights.length) {
    lines.push('');
    d.highlights.forEach((h) => lines.push('★ ' + clean(h.text)));
  } else if (d.intro) lines.push(clean(d.intro));
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
  track(r, 'share');
  const text = plainText(d);
  if (navigator.share) { navigator.share({ title: d.title, text }).catch(() => {}); return; }
  copyText(text).then((ok) => toast(ok ? { msg: 'Report copied', icon: 'copy' } : { msg: 'Could not copy the report', tone: 'error' }));
}

export { S };
