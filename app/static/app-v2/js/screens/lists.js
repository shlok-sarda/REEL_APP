// Lists tab (the Apple-style one): your smart lists as collage covers with a
// "New list" tile, then the shelves ClipNest sorted for you, then places,
// recipes and the full library.
import { esc, plural } from '../util.js';
import { icon } from '../icons.js';
import { S, on, reelsFor } from '../store.js';
import { makeScreen } from '../ui.js';
import { listCover, wireFades, coverMode, patchList } from '../cards.js';
import { openNewList } from '../newlist.js';
import { rise, isReduced, animate } from '../motion.js';

export function createLists() {
  const { el: root, scroller } = makeScreen('lists-tab');
  scroller.innerHTML = `
    <header class="lt-head"><div><p class="eyebrow">Your shelves</p><h1 class="display">Lists</h1></div>
      <button class="icon-btn is-filled lt-add" type="button" data-new aria-label="New smart list">${icon('plus')}</button></header>
    <section class="lt-sec"><div class="sec-head"><h2 class="head">My lists <small data-n></small></h2></div>
      <div class="lt-grid" data-grid></div></section>
    <section class="lt-sec" data-sorted-sec><div class="sec-head"><h2 class="head">Sorted for you</h2><span class="xs faint">ClipNest files these on its own</span></div>
      <div class="lt-sorted" data-sorted></div></section>
    <section class="lt-sec"><div class="group lt-more" data-more></div></section>`;
  const $ = (s) => scroller.querySelector(s);
  let first = true;

  function paint() {
    const mode = coverMode();
    const grid = $('[data-grid]');
    $('[data-n]').textContent = S.lists.length ? String(S.lists.length) : '';
    if (!S.extrasLoaded) {
      grid.innerHTML = '<div class="lcard"><span class="cover sk"></span><span class="sk sk-line"></span></div>'.repeat(2);
    } else {
      const items = S.lists.map((l) => ({ kind: 'list', l })).concat([{ kind: 'new' }]);
      patchList(grid, items, (it) => (it.kind === 'new' ? 'new' : 'l' + it.l.id), (it) => {
        if (it.kind === 'new') {
          return `<button class="lcard lcard-new pressable" type="button" data-newtile><span class="cover cover-new">${icon('plus')}</span><b>New list</b><small>${S.lists.length ? 'Fills itself' : 'Describe it once, it fills itself'}</small></button>`;
        }
        const l = it.l;
        return `<button class="lcard pressable" type="button" data-list="${l.id}"><span class="lcard-cover">${listCover(l, mode)}${l.suggestions.length ? `<span class="count-badge">${l.suggestions.length}</span>` : ''}</span>
          <b class="clamp-2">${l.emoji ? `<span class="lcard-e">${l.emoji}</span>` : ''}${esc(l.name)}</b><small>${plural(l.members.length, 'reel')}${l.suggestions.length ? ` · <em>${l.suggestions.length} to review</em>` : ''}</small></button>`;
      }, { sigOf: (it) => (it.kind === 'new' ? String(S.lists.length > 0) : `${it.l.name}|${it.l.members.join(',')}|${it.l.suggestions.length}|${it.l.emoji}|${mode}`) });
      grid.querySelectorAll('[data-list]').forEach((b) => {
        if (b.__w) return; b.__w = true;
        b.addEventListener('click', () => import('./listDetail.js').then((m) => m.openListDetail(Number(b.dataset.list), { origin: b.querySelector('.lcard-cover') })));
      });
      const nt = grid.querySelector('[data-newtile]');
      if (nt && !nt.__w) { nt.__w = true; nt.addEventListener('click', () => openNewList({})); }
    }
    const sorted = $('[data-sorted]');
    $('[data-sorted-sec]').hidden = !S.collections.length;
    sorted.innerHTML = S.collections.map((c) => {
      const r = S.byId.get(c.ids[0]);
      return `<button class="scard pressable" type="button" data-col="${esc(c.key)}" style="--c:${r ? r.color : '#222'}">
        ${r ? `<img class="scard-bg" src="${esc(r.thumb)}" alt="" loading="lazy" decoding="async">` : ''}
        <span class="scard-text">${c.emoji ? `<span class="scard-e">${c.emoji}</span>` : ''}<b>${esc(c.title)}</b><small>${plural(c.ids.length, 'reel')}</small></span></button>`;
    }).join('');
    sorted.querySelectorAll('[data-col]').forEach((b) => b.addEventListener('click', () => import('./collection.js').then((m) => m.openCollection(b.dataset.col))));
    const more = [];
    if (S.places.length) more.push(`<button class="row has-icon pressable" type="button" data-go="places"><span class="icon-tile">${icon('pin')}</span><span><span class="row-title">Places</span><span class="row-meta">${plural(S.places.length, 'place')} on your map</span></span>${icon('chev')}</button>`);
    if (S.recipesEnabled) more.push(`<button class="row has-icon pressable" type="button" data-go="recipes"><span class="icon-tile">🍳</span><span><span class="row-title">Recipes</span><span class="row-meta">${S.recipes.length ? plural(S.recipes.length, 'recipe') + ' you can shop' : 'Cooking reels become shopping lists'}</span></span>${icon('chev')}</button>`);
    more.push(`<button class="row has-icon pressable" type="button" data-go="all"><span class="icon-tile">${icon('grid')}</span><span><span class="row-title">All reels</span><span class="row-meta">${plural(S.reels.length, 'reel')}, newest first</span></span>${icon('chev')}</button>`);
    $('[data-more]').innerHTML = more.join('');
    $('[data-more]').querySelectorAll('[data-go]').forEach((b) => b.addEventListener('click', () => {
      const go = b.dataset.go;
      if (go === 'places') import('./places.js').then((m) => m.openPlaces());
      if (go === 'recipes') import('./recipes.js').then((m) => m.openRecipes());
      if (go === 'all') import('./allReels.js').then((m) => m.openAllReels());
    }));
    wireFades(scroller);
    if (first && S.extrasLoaded) {
      first = false;
      if (!isReduced()) rise(scroller.querySelectorAll('.lcard, .scard, .lt-more .row'), { stagger: 35, duration: 380, y: 12 });
    }
  }

  $('[data-new]').addEventListener('click', () => openNewList({}));
  const offs = ['lists', 'extras', 'library', 'recipes'].map((e) => on(e, paint));
  paint();
  return {
    el: root, scroller, dock: true,
    onShow: () => paint(),
    scrollTop: () => scroller.scrollTo({ top: 0, behavior: isReduced() ? 'auto' : 'smooth' }),
    destroy: () => offs.forEach((f) => f()),
  };
}

export { reelsFor, animate };
