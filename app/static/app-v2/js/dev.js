// Dev panel: hidden by default so the demo looks real. Opens with ?dev=1 or
// a long-press on the logo. Switch library state, network, motion, A/B
// variants, and watch the frame meter.
import { el, esc, store } from './util.js';
import { icon } from './icons.js';
import { S, emit } from './store.js';
import { net, LIVE } from './api.js';
import { setMotionMode } from './motion.js';
import { openSheet, toast } from './ui.js';
import { startHud, stopHud } from './perf.js';

const DEFAULTS = {
  scenario: 'populated', stage: 'signin', inInsta: false, network: 'fast4g', fail: 'off', motion: 'auto',
  ab: { dock: 'glass', entry: 'morph', covers: 'collage' }, hud: false, recipes: true, admin: false,
};

export function loadDev() {
  const saved = store.get('dev', {});
  return { ...DEFAULTS, ...saved, ab: { ...DEFAULTS.ab, ...(saved.ab || {}) } };
}
export function saveDev(cfg) { store.set('dev', cfg); }

export function applyLive(cfg) {
  net.profile = LIVE ? 'live' : cfg.network;
  net.fail = LIVE ? 'off' : cfg.fail;
  setMotionMode(cfg.motion);
  S.ab = cfg.ab;
  S.dev = cfg;
  document.getElementById('device').classList.toggle('is-solid-dock', cfg.ab.dock === 'solid');
  if (cfg.hud) startHud(); else stopHud();
}

const SCENARIOS = [
  ['populated', 'Populated', 'The demo library with 3 smart lists and recipes on'],
  ['empty', 'New user', 'Signed in, Instagram linked, zero reels'],
  ['processing', 'Processing', '3 reels land over the next ~20 seconds'],
  ['failed', 'Failed', '2 reels could not be sorted'],
  ['guest', 'Guest', 'No Google account yet, claim card on Home'],
  ['noig', 'No Instagram', 'Google account, Instagram not linked'],
  ['big', '300 reels', 'Stress test: scrolling and search'],
  ['demo', 'Read-only demo', 'Exactly like clipnest.in/try: 0 lists, writes refused'],
];

const NEEDS_BACKEND = [
  ['Creator name on cards', 'add creator to /library items (already in deep-search documents)'],
  ['"In this reel" spots list', 'per-reel items on /library or a /reels/{id} endpoint'],
  ['Duration on cards', 'store video duration at ingest'],
  ['Colour + blur placeholders', 'compute at thumbnail time'],
  ['Edit list name and rule', 'PATCH /folders/{id}'],
  ['Auto-add switch on new lists', 'a per-folder auto vs review flag'],
  ['List icon you pick', 'store an emoji on user_folders'],
  ['Map drops non-place pins', 'pin quality filter (client heuristic ships now)'],
];

export function openDevPanel(restart) {
  const cfg = loadDev();
  const seg = (key, opts, sub) => `<div class="seg dev-seg" data-seg="${key}" ${sub ? `data-sub="${sub}"` : ''}>${opts.map(([v, l]) => `<button type="button" data-v="${v}" class="${(sub ? cfg[sub][key] : cfg[key]) === v ? 'is-on' : ''}">${esc(l)}</button>`).join('')}</div>`;
  const body = el(`<div class="dev">
    <p class="xs faint">${LIVE ? 'Your real library. These settings only change how the app looks and moves on this device.' : 'Hidden from the real demo. Settings persist on this device.'}</p>
    <div ${LIVE ? 'hidden' : ''}>
    <h3 class="dev-h">Library state</h3>
    <div class="dev-scen">${SCENARIOS.map(([v, l, d]) => `<button type="button" class="dev-card pressable ${cfg.scenario === v ? 'is-on' : ''}" data-scen="${v}"><b>${esc(l)}</b><small>${esc(d)}</small></button>`).join('')}</div>
    <div class="dev-sub" ${cfg.scenario === 'guest' ? '' : 'hidden'} data-guest>
      <p class="xs muted">Guest stage</p>${seg('stage', [['home', 'Home screen (5)'], ['signin', 'Sign in (17)'], ['locked', 'Locked (20)']])}
      <label class="dev-check"><input type="checkbox" data-insta ${cfg.inInsta ? 'checked' : ''}> Inside Instagram's browser</label>
    </div>
    <label class="dev-check"><input type="checkbox" data-recipes ${cfg.recipes ? 'checked' : ''}> Recipes feature on (SHOW_RECIPES)</label>
    <label class="dev-check"><input type="checkbox" data-admin ${cfg.admin ? 'checked' : ''}> Admin account</label>
    <h3 class="dev-h">Network</h3>
    ${seg('network', [['instant', 'Instant'], ['fast4g', 'Fast 4G'], ['slow3g', 'Slow 3G'], ['offline', 'Offline']])}
    <p class="xs muted dev-l">Server errors</p>
    ${seg('fail', [['off', 'None'], ['writes', 'On writes'], ['all', 'On everything']])}
    </div>
    <h3 class="dev-h">Motion</h3>
    ${seg('motion', [['auto', 'Normal'], ['reduced', 'Reduced'], ['slow', 'Slow-mo 5x']])}
    <label class="dev-check"><input type="checkbox" data-hud ${cfg.hud ? 'checked' : ''}> Frame meter (fps, worst frame, long tasks, INP)</label>
    <h3 class="dev-h">A/B: feel both</h3>
    <p class="xs muted dev-l">Player entry</p>${seg('entry', [['morph', 'Card grows into player'], ['rise', 'Player slides up']], 'ab')}
    <p class="xs muted dev-l">List covers</p>${seg('covers', [['collage', 'Reel collage'], ['icon', 'Emoji icon']], 'ab')}
    <p class="xs muted dev-l">Search dock</p>${seg('dock', [['glass', 'Frosted glass'], ['solid', 'Solid (cheaper to draw)']], 'ab')}
    ${LIVE ? `<a class="btn btn-secondary btn-block dev-classic" href="/app?ui=classic">Switch to the classic app</a>` : `<h3 class="dev-h">Needs backend</h3>
    <ul class="dev-nb">${NEEDS_BACKEND.map(([a, b]) => `<li><b>${esc(a)}</b><small>${esc(b)}</small></li>`).join('')}</ul>`}
    <button class="btn btn-danger btn-block dev-reset" type="button" data-reset>${icon('refresh')}Reset all state</button>
  </div>`);
  const s = openSheet({ title: LIVE ? 'Display settings' : 'Dev panel', eyebrow: LIVE ? 'Admin' : 'Replica only', body, className: 'sheet-dev', full: true });
  const commit = (needsRestart) => {
    saveDev(cfg);
    applyLive(cfg);
    emit('ab');
    if (needsRestart) { s.close().then(() => restart()); }
  };
  body.querySelectorAll('[data-scen]').forEach((b) => b.addEventListener('click', () => {
    cfg.scenario = b.dataset.scen;
    body.querySelectorAll('[data-scen]').forEach((x) => x.classList.toggle('is-on', x === b));
    body.querySelector('[data-guest]').hidden = cfg.scenario !== 'guest';
    commit(true);
  }));
  body.querySelectorAll('[data-seg]').forEach((g) => g.querySelectorAll('[data-v]').forEach((b) => b.addEventListener('click', () => {
    const key = g.dataset.seg;
    const sub = g.dataset.sub;
    if (sub) cfg[sub][key] = b.dataset.v; else cfg[key] = b.dataset.v;
    g.querySelectorAll('[data-v]').forEach((x) => x.classList.toggle('is-on', x === b));
    const restartKeys = ['stage', 'covers'];
    commit(restartKeys.includes(key) && !(LIVE && key === 'covers'));
    if (LIVE && key === 'covers') emit('lists');
    if (key === 'network') toast({ msg: `Network: ${b.textContent}`, icon: key === 'network' && b.dataset.v === 'offline' ? 'wifiOff' : 'check' });
  })));
  body.querySelector('[data-insta]').addEventListener('change', (e) => { cfg.inInsta = e.target.checked; commit(true); });
  body.querySelector('[data-recipes]').addEventListener('change', (e) => { cfg.recipes = e.target.checked; commit(true); });
  body.querySelector('[data-admin]').addEventListener('change', (e) => { cfg.admin = e.target.checked; commit(true); });
  body.querySelector('[data-hud]').addEventListener('change', (e) => { cfg.hud = e.target.checked; commit(false); });
  body.querySelector('[data-reset]').addEventListener('click', () => {
    try { Object.keys(localStorage).filter((k) => k.startsWith('cn2_')).forEach((k) => localStorage.removeItem(k)); } catch (e) { /* storage unavailable */ }
    location.replace(location.pathname);
  });
  return s;
}
