// A shelf ClipNest sorted on its own (Collections).
import { esc, plural } from '../util.js';
import { icon } from '../icons.js';
import { S, on, collectionByKey, reelsFor, reel } from '../store.js';
import { makeScreen, navBar } from '../ui.js';
import { reelCard, patchList, delegateReelGrid, emojiTile } from '../cards.js';
import { pushScreen } from '../router.js';
import { openPlayer, warmPlayer } from '../player.js';
import { rise, isReduced } from '../motion.js';

export function openCollection(key) {
  if (!collectionByKey(key)) return null;
  return pushScreen(createCollection(key));
}

function createCollection(key) {
  const scr = makeScreen('page collection');
  const { el: root, scroller } = scr;
  const c0 = collectionByKey(key);
  navBar(scr, c0.title);
  scroller.innerHTML = `
    <header class="page-head col-head">${emojiTile(c0.emoji, c0.title, 'col-tile')}
      <p class="eyebrow">Sorted for you</p><h1 class="display">${esc(c0.title)}</h1>
      <p class="sm muted" data-n></p>
      <button class="btn btn-primary btn-sm col-play" type="button" data-playall>${icon('play')}Play all</button></header>
    <div class="grid" data-grid></div>`;
  const grid = scroller.querySelector('[data-grid]');
  const ids = () => { const c = collectionByKey(key); return c ? c.ids : []; };
  function paint(first) {
    const rs = reelsFor(ids());
    scroller.querySelector('[data-n]').textContent = `${plural(rs.length, 'reel')}${c0.parent ? ' · ' + c0.parent : ''}`;
    patchList(grid, rs, (r) => r.id, (r) => reelCard(r));
    if (first && !isReduced()) rise(Array.from(grid.children).slice(0, 8), { stagger: 40, y: 12 });
  }
  scroller.querySelector('[data-playall]').addEventListener('click', () => openPlayer(ids(), 0, grid.querySelector('.rc-thumb')));
  delegateReelGrid(grid, ids, {
    warm: (rid) => warmPlayer(reel(rid)),
    tap: (rid, list, card) => openPlayer(list, list.indexOf(rid), card.querySelector('.rc-thumb')),
    long: (rid) => import('../sheets.js').then((m) => m.openReelSheet(rid)),
  });
  paint(true);
  const off = on('library', () => paint(false));
  return { el: root, scroller, dock: true, destroy: off };
}

export { S };
