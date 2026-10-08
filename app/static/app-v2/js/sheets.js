// Sheets: reel details, add to list, activity, city picker.
import { el, esc, savedLabel, haptic, plural } from './util.js';
import { icon } from './icons.js';
import { S, reel, recipeFor, emit, on, savePref, refresh, listById, cityApps, appLabel, isGuest, isDemo, isLinkSession, refreshRecipes } from './store.js';
import * as api from './api.js';
import { openSheet, toast, apiToast, confirmSheet, shareOrCopy, copyText, errorMessage, btnLoading } from './ui.js';
import { thumb, listCover, wireFades, coverMode } from './cards.js';
import { animate, isReduced } from './motion.js';
import { openNewList } from './newlist.js';

/* =====================================================================
   Reel details
   ===================================================================== */
export function openReelSheet(rid, opts = {}) {
  const r = reel(rid);
  if (!r) return;
  const recipe = recipeFor(rid);
  const places = (r.items || []).filter((it) => it.item_type === 'place' || it.location);
  const inLists = S.lists.filter((l) => l.members.includes(rid));
  const isAdmin = !!(S.session && S.session.user && S.session.user.is_admin);
  const maybeRecipe = !recipe && S.recipesEnabled && (r.sub || '').toLowerCase().includes('recipe');
  const body = el(`<div class="rs">
    <div class="rs-top">
      ${thumb(r, 'rs-thumb', { full: false })}
      <div class="rs-top-text">
        <h2 class="head rs-title clamp-3">${esc(r.name)}</h2>
        <p class="sm muted">${esc(r.creator || 'Saved reel')}</p>
        <p class="xs faint">${esc(savedLabel(r.receivedAt))}${r.collections[0] ? ` · ${esc(r.collections[0])}` : ''}</p>
      </div>
    </div>
    <div class="rs-actions">
      ${opts.fromPlayer ? '' : `<button class="rs-act pressable" type="button" data-play><span>${icon('play')}</span>Play</button>`}
      <button class="rs-act pressable" type="button" data-add><span>${icon('plus')}</span>Add to list</button>
      <button class="rs-act pressable" type="button" data-share><span>${icon('share')}</span>Share</button>
      ${r.url ? `<a class="rs-act pressable" href="${esc(r.url)}" target="_blank" rel="noopener"><span>${icon('ig')}</span>Instagram</a>` : ''}
    </div>
    ${recipe ? `<button class="rs-feature pressable" type="button" data-recipe><span class="icon-tile">🍳</span><span><b>Recipe</b><small>${recipe.ingredients.length} ingredients · shop on ${esc(appLabel(cityApps()[0] || 'blinkit'))}</small></span>${icon('chev')}</button>` : ''}
    ${maybeRecipe ? `<button class="rs-feature pressable" type="button" data-extract><span class="icon-tile">🍳</span><span><b>Get the recipe</b><small>Turns this reel into ingredients and steps</small></span>${icon('chev')}</button>` : ''}
    ${places.length > 1 ? `<section class="rs-sec" data-items><div class="rs-sec-head"><h3 class="eyebrow is-quiet">In this reel</h3><span class="xs faint">${plural(places.length, 'place')}</span></div>
      <ol class="rs-items">${places.map((p, i) => `<li class="${i >= 5 ? 'is-more' : ''}"><span class="rs-n">${i + 1}</span><span class="rs-item-text"><b>${esc(p.item_name)}</b><small class="clamp-2">${esc(p.summary)}</small></span>
        <a class="icon-btn" href="https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(p.item_name + ' ' + (p.location || ''))}" target="_blank" rel="noopener" aria-label="Open ${esc(p.item_name)} in Maps">${icon('pin')}</a></li>`).join('')}</ol>
      ${places.length > 5 ? `<button class="link-btn" type="button" data-more>Show all ${places.length}</button>` : ''}</section>` : ''}
    ${r.summary ? `<section class="rs-sec"><h3 class="eyebrow is-quiet">About</h3><p class="sm rs-about">${esc(r.summary)}</p></section>` : ''}
    ${r.visible.length ? `<section class="rs-sec"><h3 class="eyebrow is-quiet">On screen</h3><div class="rs-chips">${r.visible.slice(0, 4).map((t) => `<span class="evidence"><span>${esc(t)}</span></span>`).join('')}</div></section>` : ''}
    <section class="rs-sec"><h3 class="eyebrow is-quiet">In your lists</h3><div class="rs-chips" data-inlists>${inLists.map((l) => `<span class="chip is-on">${l.emoji ? l.emoji + ' ' : ''}${esc(l.name)}</span>`).join('')}<button class="chip" type="button" data-add2>${icon('plus')}Add to list</button></div></section>
    <section class="rs-sec rs-danger">
      ${isAdmin ? `<button class="row pressable" type="button" data-copy>${icon('link')}<span class="row-title">Copy link</span><span></span></button>
      <button class="row pressable" type="button" data-retry>${icon('refresh')}<span class="row-title">Retry processing</span><span></span></button>` : ''}
      <button class="row pressable is-danger" type="button" data-delete>${icon('trash')}<span class="row-title">Delete from ClipNest</span><span></span></button>
    </section>
  </div>`);
  wireFades(body);
  const s = openSheet({ body, label: r.name, className: 'sheet-reel', expandable: true });
  const q = (sel) => body.querySelector(sel);
  if (q('[data-play]')) q('[data-play]').addEventListener('click', async () => {
    await s.close();
    const { openPlayer } = await import('./player.js');
    openPlayer(S.reels.map((x) => x.id), S.reels.findIndex((x) => x.id === rid), null);
  });
  const add = () => openAddToList(rid);
  q('[data-add]').addEventListener('click', add);
  q('[data-add2]').addEventListener('click', add);
  q('[data-share]').addEventListener('click', () => shareOrCopy(r.name, r.url));
  if (q('[data-recipe]')) q('[data-recipe]').addEventListener('click', () => import('./recipe.js').then((m) => m.openRecipe(rid)));
  if (q('[data-extract]')) q('[data-extract]').addEventListener('click', () => extractRecipe(rid, q('[data-extract]'), s));
  if (q('[data-more]')) q('[data-more]').addEventListener('click', (e) => {
    body.querySelectorAll('.rs-items .is-more').forEach((li, i) => { li.classList.remove('is-more'); if (!isReduced()) animate(li, [{ opacity: 0 }, { opacity: 1 }], { duration: 200, delay: i * 15 }); });
    e.currentTarget.remove();
    s.setFull(true);
  });
  if (q('[data-copy]')) q('[data-copy]').addEventListener('click', () => copyText(r.url).then((ok) => toast(ok ? { msg: 'Link copied', icon: 'link' } : { msg: 'Could not copy', tone: 'error' })));
  if (q('[data-retry]')) q('[data-retry]').addEventListener('click', async (e) => {
    btnLoading(e.currentTarget, true);
    try { await api.retryFailed([rid]); toast({ msg: 'Requeued. It will be sorted again in a minute.' }); } catch (err) { apiToast(err); }
    btnLoading(e.currentTarget, false);
  });
  q('[data-delete]').addEventListener('click', () => deleteReelFlow(rid, s));
  if (opts.focus === 'items' && q('[data-items]')) {
    s.setFull(true);
    setTimeout(() => q('[data-items]').scrollIntoView({ block: 'start', behavior: isReduced() ? 'auto' : 'smooth' }), 380);
  }
  return s;
}

async function extractRecipe(rid, btn, sheet) {
  const label = btn.querySelector('b');
  const small = btn.querySelector('small');
  btn.classList.add('is-working');
  label.textContent = 'Reading the reel';
  small.textContent = 'Pulling out ingredients and steps';
  try {
    const res = await api.extractRecipe(rid);
    if (res.status !== 'recipe') {
      btn.classList.remove('is-working');
      if (res.error) {
        label.textContent = 'Could not read this reel right now';
        small.textContent = 'Nothing was saved. Tap to try again in a bit.';
        return;
      }
      label.textContent = 'No step by step recipe here';
      small.textContent = 'This reel shows food but not how to make it.';
      return;
    }
    await refreshRecipes();
    emit('recipes');
    haptic(12);
    btn.classList.remove('is-working');
    label.textContent = 'Recipe';
    small.textContent = `${res.card.ingredients.length} ingredients · tap to open`;
    btn.replaceWith(btn.cloneNode(true));
    const fresh = sheet.body.querySelector('.rs-feature');
    fresh.addEventListener('click', () => import('./recipe.js').then((m) => m.openRecipe(rid)));
    import('./recipe.js').then((m) => m.openRecipe(rid));
  } catch (e) {
    btn.classList.remove('is-working');
    label.textContent = 'Get the recipe';
    small.textContent = e.status === 403 ? 'Recipes are switched off in the demo library.' : errorMessage(e);
  }
}

/* ---------- delete with undo: nothing is sent until the undo window closes ---------- */
export async function deleteReelFlow(rid, sheet) {
  const r = reel(rid);
  if (!r) return;
  // A link session cannot delete. Say so now, not after the reel has
  // vanished and come back.
  if (isDemo()) { toast({ msg: 'This is the demo library, so reels cannot be deleted.' }); return; }
  if (isGuest()) {
    const go = await confirmSheet({ title: 'Sign in to delete reels', body: 'Deleting needs a Google sign in, so nobody else holding your link can remove your reels. Everything you saved stays right here.', confirm: 'Sign in with Google' });
    if (go) import('./screens/home.js').then((m) => m.openSignIn());
    return;
  }
  const ok = await confirmSheet({ title: 'Delete this reel?', body: 'It disappears from your library, your lists and search. You can undo for a few seconds.', confirm: 'Delete reel', danger: true });
  if (!ok) return;
  if (sheet) await sheet.close();
  try {
    const { closePlayer, currentReelId } = await import('./player.js');
    if (currentReelId() === rid) closePlayer();
  } catch (e) { /* player not loaded */ }
  const snap = { reels: S.reels.slice(), byId: new Map(S.byId), collections: S.collections.map((c) => ({ ...c, ids: c.ids.slice() })), lists: S.lists.map((l) => ({ ...l, members: l.members.slice(), suggestions: l.suggestions.slice() })), unsorted: S.unsorted.slice() };
  S.reels = S.reels.filter((x) => x.id !== rid);
  S.byId.delete(rid);
  S.collections.forEach((c) => { c.ids = c.ids.filter((x) => x !== rid); });
  S.collections = S.collections.filter((c) => c.ids.length);
  S.lists.forEach((l) => { l.members = l.members.filter((x) => x !== rid); l.suggestions = l.suggestions.filter((x) => x !== rid); });
  S.unsorted = S.unsorted.filter((x) => x !== rid);
  emit('library', { removed: [rid] });
  emit('lists');
  let undone = false;
  const restore = () => {
    Object.assign(S, snap);
    emit('library', { restored: [rid] });
    emit('lists');
  };
  toast({ msg: 'Reel deleted', sub: r.name, icon: 'trash', action: { label: 'Undo', fn: () => { undone = true; restore(); } }, duration: 5000 });
  setTimeout(async () => {
    if (undone) return;
    try {
      await api.deleteReel(rid);
      refresh().catch(() => {});
    } catch (e) {
      restore();
      if (e.status === 403 && e.detail !== 'demo') {
        toast({ msg: e.detail, tone: 'error', action: isGuest() ? { label: 'Sign in', fn: () => import('./screens/home.js').then((m) => m.openSignIn()) } : null });
      } else apiToast(e);
    }
  }, 5200);
}

/* =====================================================================
   Add to list
   ===================================================================== */
export function openAddToList(rid) {
  const r = reel(rid);
  if (!r) return;
  const body = el(`<div class="atl">
    <button class="row has-icon pressable atl-new" type="button" data-new><span class="icon-tile">${icon('plus')}</span><span><span class="row-title">New smart list</span><span class="row-meta">Starts with this reel, fills itself</span></span>${icon('chev')}</button>
    <div class="atl-rows" data-rows>${S.lists.length ? '' : '<p class="sm muted atl-empty">No lists yet. Make one above and this reel goes in first.</p>'}</div>
  </div>`);
  const s = openSheet({ title: 'Add to a list', sub: r.name, body, className: 'sheet-atl' });
  body.querySelector('[data-new]').addEventListener('click', async () => {
    await s.close();
    const inPlayer = !!document.querySelector('#overlays .player');
    openNewList({ reelId: rid, source: inPlayer ? 'player' : 'sheet' });
  });
  const rows = body.querySelector('[data-rows]');
  S.lists.forEach((l) => {
    const state = l.members.includes(rid) ? 'member' : l.suggestions.includes(rid) ? 'suggested' : null;
    const row = el(`<div class="atl-row"><span class="atl-cover">${listCover(l, coverMode())}</span>
      <span class="atl-text"><b class="clamp-1">${esc(l.name)}</b><small>${plural(l.members.length, 'reel')}${state === 'suggested' ? ' · <em>suggested</em>' : ''}</small></span>
      <span class="atl-state"></span></div>`);
    wireFades(row);
    const slot = row.querySelector('.atl-state');
    const paint = (st) => {
      if (st === 'member') slot.innerHTML = `<span class="in-chip">${icon('check')}In</span>`;
      else slot.innerHTML = `<button class="btn btn-secondary btn-sm" type="button">${st === 'suggested' ? 'Add' : 'Add'}</button>`;
      const b = slot.querySelector('button');
      if (b) b.addEventListener('click', async () => {
        paint('member');
        if (!isReduced()) animate(slot.firstElementChild, [{ transform: 'scale(0.6)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }], { duration: 420, easing: 'pop' });
        haptic(8);
        const before = { members: l.members.slice(), suggestions: l.suggestions.slice() };
        l.members.unshift(rid);
        l.suggestions = l.suggestions.filter((x) => x !== rid);
        row.querySelector('small').textContent = plural(l.members.length, 'reel');
        emit('lists');
        try { await api.addReelToFolder(l.id, rid); }
        catch (e) {
          l.members = before.members; l.suggestions = before.suggestions;
          emit('lists');
          paint(st);
          row.querySelector('small').textContent = plural(l.members.length, 'reel');
          apiToast(e);
        }
      });
    };
    paint(state);
    rows.appendChild(row);
  });
  return s;
}

/* =====================================================================
   Activity
   ===================================================================== */
export function openActivity() {
  const body = el('<div class="act" data-act></div>');
  const s = openSheet({ title: 'Activity', body, className: 'sheet-activity' });
  const paint = () => {
    const proc = S.processing;
    const failed = S.failed;
    const steps = ['Waiting in line', 'Downloading', 'Watching the video', 'Sorting it'];
    body.innerHTML = `
      ${!proc.length && !failed.length ? `<div class="act-idle"><span class="icon-tile">${icon('check')}</span><p class="head">All caught up.</p><p class="sm muted">${plural(S.reels.length, 'reel')} sorted. New ones show up here while they are being sorted.</p></div>` : ''}
      ${proc.length ? `<h3 class="eyebrow is-quiet act-h">Sorting now</h3>${proc.map((p) => `<div class="act-row"><span class="act-spin"><span class="pulse-dot"></span></span><span><b>New reel</b><small>${esc(steps[p.status === 'queued' ? 0 : p.step] || 'Starting')}</small></span><span class="act-steps">${[1, 2, 3].map((i) => `<i class="${i < p.step ? 'is-done' : i === p.step ? 'is-now' : ''}"></i>`).join('')}</span></div>`).join('')}` : ''}
      ${failed.length ? `<h3 class="eyebrow is-quiet act-h">Needs a retry</h3>${failed.map((f) => `<div class="act-row is-failed"><span class="icon-tile is-danger">${icon('alert')}</span><span><b>Could not sort this one</b><small>${esc(f.why)}</small></span></div>`).join('')}
      ${isLinkSession() ? '<p class="sm muted">Send the reel again in the DM and it should go through.</p>' : '<button class="btn btn-primary btn-block act-retry" type="button" data-retry>Try again</button>'}` : ''}`;
    const rb = body.querySelector('[data-retry]');
    if (rb) rb.addEventListener('click', async () => {
      btnLoading(rb, true);
      try { const res = await api.retryFailed(); await refresh(); toast({ msg: `${plural(res.requeued_count, 'reel')} back in the queue` }); }
      catch (e) { apiToast(e); }
      btnLoading(rb, false);
    });
  };
  paint();
  const off = on('library', paint);
  s.onClose = off;
  return s;
}

/* =====================================================================
   City picker (decides which delivery apps show up)
   ===================================================================== */
export function openCitySheet() {
  if (!S.geo) return null;
  const cities = Object.keys(S.geo.cities);
  const body = el(`<div class="city">${cities.map((c) => `<button class="row pressable ${c === S.prefs.city ? 'is-current' : ''}" type="button" data-c="${esc(c)}"><span class="row-title">${esc(c)}</span><span class="row-meta">${S.geo.cities[c].map((a) => appLabel(a)).slice(0, 4).join(', ')}</span>${c === S.prefs.city ? icon('check') : '<span></span>'}</button>`).join('')}</div>`);
  const s = openSheet({ title: 'Where should we deliver?', sub: 'We only show apps that deliver in your city.', body, className: 'sheet-city', expandable: true });
  body.querySelectorAll('[data-c]').forEach((b) => b.addEventListener('click', () => {
    savePref('city', b.dataset.c);
    emit('city');
    haptic(6);
    s.close();
  }));
  return s;
}

export { listById };
