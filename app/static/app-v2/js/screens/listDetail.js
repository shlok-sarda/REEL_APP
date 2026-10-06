// Smart list detail: collage hero, the rule that decides what joins, a review
// tray for suggestions (Add / Skip with an optional reason, both undoable),
// the members grid, and a menu to edit, re-check or delete.
import { el, esc, plural, haptic } from '../util.js';
import { icon } from '../icons.js';
import { S, on, emit, listById, reelsFor, reel } from '../store.js';
import * as api from '../api.js';
import { makeScreen, navBar, toast, apiToast, openSheet, confirmSheet } from '../ui.js';
import { reelCard, patchList, delegateReelGrid, wireFades, thumb } from '../cards.js';
import { pushScreen, back } from '../router.js';
import { openPlayer, warmPlayer } from '../player.js';
import { animate, rise, isReduced, slamWords, glowBeat } from '../motion.js';
import { openNewList } from '../newlist.js';

export function openListDetail(id, opts = {}) {
  const l = listById(id);
  if (!l) return null;
  return pushScreen(createListDetail(id, opts));
}

function createListDetail(id, opts) {
  const scr = makeScreen('page list-detail');
  const { el: root, scroller } = scr;
  const bar = navBar(scr, '', `<button class="icon-btn is-glass" type="button" data-menu aria-label="List options">${icon('more')}</button>`);
  scroller.innerHTML = `
    <div class="ld-hero" data-hero></div>
    <div class="ld-body">
      <div class="ld-rule" data-rule></div>
      <div class="ld-scan" data-scan hidden></div>
      <section class="ld-review" data-review hidden></section>
      <div class="sec-head"><h2 class="head">In this list <small data-n></small></h2><button class="btn btn-secondary btn-sm" type="button" data-playall>${icon('play')}Play all</button></div>
      <div class="grid" data-grid></div>
      <div data-empty></div>
    </div>`;
  const $ = (s) => scroller.querySelector(s);
  const grid = $('[data-grid]');

  function list() { return listById(id); }

  function paintHero(animateTitle) {
    const l = list();
    if (!l) return;
    bar.querySelector('.navbar-title').textContent = l.name;
    const rs = reelsFor(l.members.concat(l.suggestions)).slice(0, 4);
    $('[data-hero]').innerHTML = `
      <div class="ld-collage n${rs.length}">${rs.map((r) => `<i style="--c:${r.color}">${r.lqip ? `<img class="lq" src="${r.lqip}" alt="">` : ''}<img class="full" src="${esc(r.full)}" alt="" data-fade decoding="async"></i>`).join('') || '<i class="ld-collage-empty"></i>'}</div>
      <div class="ld-hero-shade"></div>
      <div class="ld-hero-text"><p class="eyebrow">Smart list · ${plural(l.members.length, 'reel')}</p><h1 class="display ld-title" data-title>${l.emoji ? `<span class="ld-e">${l.emoji}</span>` : ''}${esc(l.name)}</h1></div>`;
    wireFades($('[data-hero]'));
    if (animateTitle) {
      const t = $('[data-title]');
      slamWords(t, (l.emoji ? l.emoji + ' ' : '') + l.name, { delay: 120 });
      setTimeout(() => glowBeat($('[data-hero]')), 160);
    }
    $('[data-rule]').innerHTML = `<p class="ld-rule-text">${esc(l.description)}</p><button class="link-btn" type="button" data-edit>${icon('edit')}Edit</button>
      <p class="xs faint ld-rule-hint">${icon('sparkle')}New reels that match this join on their own.</p>`;
    $('[data-edit]').addEventListener('click', () => openNewList({ edit: id }));
    $('[data-n]').textContent = String(l.members.length);
    $('[data-playall]').hidden = !l.members.length;
  }

  function paintReview() {
    const l = list();
    const box = $('[data-review]');
    const sug = reelsFor(l.suggestions);
    box.hidden = !sug.length;
    if (!sug.length) { box.innerHTML = ''; return; }
    if (!box.querySelector('.ld-tray')) {
      box.innerHTML = `<div class="ld-review-head"><p class="hcard-t">${icon('sparkle')}<span data-rn></span></p><p class="xs muted">They look like they belong. Keep the ones that do.</p></div><div class="ld-tray" data-tray></div>`;
    }
    box.querySelector('[data-rn]').textContent = `${plural(sug.length, 'reel')} waiting for you`;
    const tray = box.querySelector('[data-tray]');
    patchList(tray, sug, (r) => r.id, (r) => `<article class="ld-sug" data-rid="${esc(r.id)}">
      <button class="ld-sug-media pressable" type="button" data-play aria-label="Play ${esc(r.name)}">${thumb(r, 'rc-thumb', { dur: true })}</button>
      <b class="clamp-2">${esc(r.name)}</b><small>${esc(r.creator)}</small>
      <div class="ld-sug-acts"><button class="btn btn-secondary btn-sm" type="button" data-skip>${icon('x')}Skip</button><button class="btn btn-primary btn-sm" type="button" data-add>${icon('check')}Add</button></div>
    </article>`);
    tray.querySelectorAll('.ld-sug').forEach((card) => {
      if (card.__w) return; card.__w = true;
      const rid = card.dataset.rid;
      card.querySelector('[data-play]').addEventListener('click', () => openPlayer(list().suggestions, list().suggestions.indexOf(rid), card.querySelector('.rc-thumb')));
      card.querySelector('[data-add]').addEventListener('click', () => decide(rid, 'accept', card));
      card.querySelector('[data-skip]').addEventListener('click', () => decide(rid, 'reject', card));
    });
  }

  function paintGrid(fresh) {
    const l = list();
    const rs = reelsFor(l.members);
    const added = patchList(grid, rs, (r) => r.id, (r) => reelCard(r));
    if (fresh && !isReduced()) rise(Array.from(grid.children).slice(0, 8), { stagger: 40, y: 12 });
    else if (added.length && !isReduced()) added.forEach((n) => animate(n, [{ opacity: 0, transform: 'translateY(-10px) scale(0.96)' }, { opacity: 1, transform: 'translateY(0) scale(1)' }], { duration: 380, easing: 'snap', clear: true }));
    $('[data-empty]').innerHTML = rs.length ? '' : `<div class="lesson ld-empty"><p class="head">Nothing here yet.</p><p class="sm">New reels that match the rule above land here on their own. You can also add any reel from its <b>+ List</b> button.</p></div>`;
  }

  async function decide(rid, action, card) {
    const l = list();
    const prevIndex = l.suggestions.indexOf(rid);
    haptic(action === 'accept' ? 12 : 6);
    // optimistic: the card leaves the tray straight away
    const out = action === 'accept'
      ? [{ opacity: 1, transform: 'translateY(0) scale(1)' }, { opacity: 0, transform: 'translateY(30px) scale(0.9)' }]
      : [{ opacity: 1, transform: 'translateX(0)' }, { opacity: 0, transform: 'translateX(-40px)' }];
    if (!isReduced()) await animate(card, out, { duration: 220, easing: 'in' });
    l.suggestions = l.suggestions.filter((x) => x !== rid);
    if (action === 'accept') l.members.unshift(rid);
    paintReview(); paintGrid(); paintHero(false);
    emit('lists');
    const undo = async () => {
      l.members = l.members.filter((x) => x !== rid);
      l.suggestions.splice(Math.max(0, prevIndex), 0, rid);
      paintReview(); paintGrid(); paintHero(false); emit('lists');
      try { await api.undoDecide(id, rid, prevIndex); } catch (e) { apiToast(e); }
    };
    try {
      await api.decide(id, rid, action);
      if (action === 'accept') toast({ msg: `Added to ${l.name}`, icon: 'check', action: { label: 'Undo', fn: undo } });
      else {
        toast({
          msg: 'Skipped. Why not this one?', sub: 'Optional. It teaches the list what belongs.', icon: 'x',
          why: ['Different topic', 'Related, not this', 'Just this one'], scoped: true,
          onWhy: (reason) => { api.decide(id, rid, 'reject', reason).catch(() => {}); },
          action: { label: 'Undo', fn: undo },
        });
      }
    } catch (e) {
      l.suggestions.splice(Math.max(0, prevIndex), 0, rid);
      l.members = l.members.filter((x) => x !== rid);
      paintReview(); paintGrid(); paintHero(false); emit('lists');
      apiToast(e);
    }
  }

  async function rescan() {
    const scan = $('[data-scan]');
    scan.hidden = false;
    scan.innerHTML = `<span class="pulse-dot"></span><span><b>Checking ${plural(S.reels.length, 'reel')}</b><small>against "${esc(list().name)}"</small></span><span class="ld-scan-bar"><i></i></span>`;
    if (!isReduced()) animate(scan, [{ opacity: 0, transform: 'translateY(-6px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 220, clear: true });
    const before = list().suggestions.length;
    try {
      const d = await api.rescanFolder(id);
      const l = list();
      l.suggestions = d.suggestions.map((m) => m.reel_id).filter((x) => S.byId.has(x));
      l.members = d.members.map((m) => m.reel_id).filter((x) => S.byId.has(x));
      const found = l.suggestions.length - before;
      paintReview(); paintHero(false); emit('lists');
      toast({ msg: found > 0 ? `Found ${plural(found, 'new match', 'new matches')}` : 'No new matches. You are all set.', icon: found > 0 ? 'sparkle' : 'check' });
      if (found > 0) glowBeat($('[data-review]'));
    } catch (e) { apiToast(e, rescan); }
    if (!isReduced()) await animate(scan, [{ opacity: 1 }, { opacity: 0 }], { duration: 160 });
    scan.hidden = true;
  }

  async function del() {
    const l = list();
    const ok = await confirmSheet({ title: `Delete "${l.name}"?`, body: 'Your reels stay saved. Only the list goes. You can undo for a few seconds.', confirm: 'Delete list', danger: true });
    if (!ok) return;
    const snapshot = S.lists.slice();
    const idx = S.lists.findIndex((x) => x.id === id);
    await back();
    S.lists = S.lists.filter((x) => x.id !== id);
    emit('lists');
    let undone = false;
    toast({ msg: 'List deleted', sub: l.name, icon: 'trash', action: { label: 'Undo', fn: () => { undone = true; S.lists = snapshot; emit('lists'); } }, duration: 5000 });
    setTimeout(async () => {
      if (undone) return;
      try { await api.deleteFolder(id); }
      catch (e) { S.lists = snapshot.slice(); if (idx >= 0 && !S.lists.some((x) => x.id === id)) S.lists.splice(idx, 0, l); emit('lists'); apiToast(e); }
    }, 5200);
  }

  bar.querySelector('[data-menu]').addEventListener('click', () => {
    const body = el(`<div class="menu">
      <button class="row has-icon pressable" type="button" data-m="edit"><span class="icon-tile is-neutral">${icon('edit')}</span><span><span class="row-title">Edit name and rule</span><span class="row-meta">Changes what joins from now on</span></span>${icon('chev')}</button>
      <button class="row has-icon pressable" type="button" data-m="scan"><span class="icon-tile is-neutral">${icon('refresh')}</span><span><span class="row-title">Check my library again</span><span class="row-meta">Looks for reels that fit but were missed</span></span>${icon('chev')}</button>
      <button class="row has-icon pressable is-danger" type="button" data-m="del"><span class="icon-tile is-danger">${icon('trash')}</span><span><span class="row-title">Delete list</span><span class="row-meta">Reels stay saved</span></span><span></span></button>
    </div>`);
    const s = openSheet({ title: list().name, body, className: 'sheet-menu' });
    body.querySelectorAll('[data-m]').forEach((b) => b.addEventListener('click', async () => {
      const m = b.dataset.m;
      await s.close();
      if (m === 'edit') openNewList({ edit: id });
      if (m === 'scan') rescan();
      if (m === 'del') del();
    }));
  });
  $('[data-playall]').addEventListener('click', () => { const ids = list().members; openPlayer(ids, 0, grid.querySelector('.rc-thumb')); });

  delegateReelGrid(grid, () => list().members, {
    warm: (rid) => warmPlayer(reel(rid)),
    tap: (rid, ids, card) => openPlayer(ids, ids.indexOf(rid), card.querySelector('.rc-thumb')),
    long: (rid) => import('../sheets.js').then((m) => m.openReelSheet(rid)),
  });

  paintHero(!!opts.justCreated);
  paintReview();
  paintGrid(true);
  const offs = [
    on('lists', () => { if (!list()) return; paintHero(false); paintReview(); paintGrid(); }),
    on('library', () => { if (!list()) return; paintReview(); paintGrid(); }),
  ];
  return { el: root, scroller, dock: true, destroy: () => offs.forEach((f) => f()) };
}
