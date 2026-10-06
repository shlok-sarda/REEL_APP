// All reels: every save, newest first, filterable by shelf.
import { esc, plural } from '../util.js';
import { S, on } from '../store.js';
import { makeScreen, navBar } from '../ui.js';
import { reelCard, processingCard, failedCard, patchList, delegateReelGrid } from '../cards.js';
import { pushScreen } from '../router.js';
import { openPlayer, warmPlayer } from '../player.js';
import { animate, isReduced, rise } from '../motion.js';
import * as api from '../api.js';
import { refresh } from '../store.js';
import { toast, apiToast, btnLoading } from '../ui.js';

export function openAllReels(opts = {}) {
  return pushScreen(createAllReels(opts));
}

function createAllReels(opts) {
  const scr = makeScreen('page all-reels');
  const { el: root, scroller } = scr;
  let filter = opts.filter || 'all';
  scroller.innerHTML = `
    <header class="page-head"><p class="eyebrow">Your library</p><h1 class="display">All <em>reels</em></h1><p class="sm muted" data-count></p></header>
    <div class="chips page-chips" data-chips role="tablist" aria-label="Filter by shelf"></div>
    <div class="grid" data-grid></div>
    <div data-empty></div>`;
  navBar(scr, 'All reels');
  const grid = scroller.querySelector('[data-grid]');

  function filtered() {
    if (filter === 'all') return S.reels;
    if (filter === 'unsorted') return S.unsorted.map((id) => S.byId.get(id)).filter(Boolean);
    const c = S.collections.find((x) => x.key === filter);
    return c ? c.ids.map((id) => S.byId.get(id)).filter(Boolean) : [];
  }

  function paintChips() {
    const chips = [['all', 'All', S.reels.length, '']].concat(S.collections.map((c) => [c.key, c.title, c.ids.length, c.emoji]));
    if (S.unsorted.length) chips.push(['unsorted', 'Unsorted', S.unsorted.length, '']);
    const box = scroller.querySelector('[data-chips]');
    box.innerHTML = chips.map(([k, t, n, e]) => `<button class="chip ${k === filter ? 'is-on' : ''}" type="button" role="tab" aria-selected="${k === filter}" data-f="${esc(k)}">${e ? `<span class="chip-ico">${e}</span>` : ''}${esc(t)}<span class="chip-n">${n}</span></button>`).join('');
    box.querySelectorAll('[data-f]').forEach((b) => b.addEventListener('click', () => {
      if (filter === b.dataset.f) return;
      filter = b.dataset.f;
      paintChips();
      paint(true);
      b.scrollIntoView({ inline: 'center', block: 'nearest', behavior: isReduced() ? 'auto' : 'smooth' });
    }));
  }

  function paint(changedFilter) {
    const list = filtered();
    scroller.querySelector('[data-count]').textContent = plural(list.length, 'reel') + (filter === 'all' ? ', newest first' : '');
    const items = (filter === 'all' ? S.processing.map((p) => ({ kind: 'proc', p })).concat(S.failed.map((f) => ({ kind: 'fail', f }))) : [])
      .concat(list.map((r) => ({ kind: 'reel', r })));
    const fresh = patchList(grid, items,
      (it) => (it.kind === 'reel' ? it.r.id : it.kind === 'proc' ? 'job' + it.p.jobId + ':' + it.p.step : 'fail' + it.f.rid),
      (it) => (it.kind === 'reel' ? reelCard(it.r) : it.kind === 'proc' ? processingCard(it.p) : failedCard(it.f)));
    if (changedFilter) {
      if (!isReduced()) rise(Array.from(grid.children).slice(0, 8), { y: 10, stagger: 25, duration: 300 });
    } else if (fresh.length && !isReduced()) {
      fresh.forEach((n) => animate(n, [{ opacity: 0, transform: 'scale(0.96)' }, { opacity: 1, transform: 'scale(1)' }], { duration: 300, easing: 'snap', clear: true }));
    }
    grid.querySelectorAll('[data-retry]').forEach((b) => {
      if (b.__w) return; b.__w = true;
      b.addEventListener('click', async () => {
        btnLoading(b, true);
        try { await api.retryFailed([b.dataset.retry]); await refresh(); toast({ msg: 'Back in the queue' }); } catch (e) { btnLoading(b, false); apiToast(e); }
      });
    });
    scroller.querySelector('[data-empty]').innerHTML = list.length || filter === 'all' ? '' : '<p class="sm muted page-empty">Nothing on this shelf any more.</p>';
  }

  delegateReelGrid(grid, () => filtered().map((r) => r.id), {
    warm: (rid) => warmPlayer(S.byId.get(rid)),
    tap: (rid, ids, card) => openPlayer(ids, ids.indexOf(rid), card.querySelector('.rc-thumb')),
    long: (rid) => import('../sheets.js').then((m) => m.openReelSheet(rid)),
  });

  paintChips();
  paint(false);
  const offs = [on('library', () => { paintChips(); paint(false); })];
  return { el: root, scroller, dock: true, destroy: () => offs.forEach((f) => f()), scrollTop: () => scroller.scrollTo({ top: 0, behavior: 'smooth' }) };
}
