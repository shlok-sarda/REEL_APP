// Boot. Order matters: motion + network settings first so the very first
// frame already respects reduced motion and the chosen network profile.
import * as api from './api.js';
import { S, loadAll, refresh, resetState, on } from './store.js';
import { initPress, setOffline } from './ui.js';
import { initRouter, registerListsTab, resetRouter } from './router.js';
import { initDock } from './dock.js';
import { initSearch } from './search.js';
import { createHome, setDevOpener } from './screens/home.js';
import { createLists } from './screens/lists.js';
import { loadDev, applyLive, openDevPanel } from './dev.js';
import { LAN_URL } from './config.js';

const cfg = loadDev();
applyLive(cfg);

function scenarioOpts(c) { return { stage: c.stage, recipes: c.recipes, admin: c.admin }; }

function fitFrame() {
  const wide = window.matchMedia('(min-width: 760px) and (min-height: 560px)').matches;
  const s = wide ? Math.min(1, (window.innerHeight - 48) / 844, (window.innerWidth - 40) / 410) : 1;
  document.documentElement.style.setProperty('--frame-scale', String(Math.max(0.5, s)));
}

// The page shell paints a loading mark before any module arrives; it leaves
// as soon as the library has loaded or failed to.
function hideBoot() {
  const b = document.getElementById('boot');
  if (!b || b.classList.contains('is-out')) return;
  b.classList.add('is-out');
  setTimeout(() => b.remove(), 420);
}
setTimeout(hideBoot, 15000);

let pollTimer = 0;
function schedulePoll() {
  clearTimeout(pollTimer);
  // Faster while reels are being sorted. Polls patch the UI; they never
  // rebuild it, so they are safe while the user is mid-scroll.
  const ms = S.processing.length ? (api.LIVE ? 8000 : 2500) : 25000;
  pollTimer = setTimeout(async () => {
    if (document.hidden) { schedulePoll(); return; }
    try { await refresh(); setOffline(false); } catch (e) { if (e.status === 0) setOffline(true); }
    schedulePoll();
  }, ms);
}

async function start() {
  initPress();
  fitFrame();
  window.addEventListener('resize', fitFrame);
  const lan = document.getElementById('lan-url');
  if (lan) lan.textContent = LAN_URL || location.origin;
  window.addEventListener('offline', () => setOffline(true));
  window.addEventListener('online', () => setOffline(false));

  initDock(initSearch());
  registerListsTab(createLists);
  setDevOpener(() => openDevPanel(restart));
  await api.loadFixtures();
  api.setScenario(cfg.scenario, scenarioOpts(cfg));
  initRouter(createHome());
  on('loaded', schedulePoll);
  on('loaded', hideBoot);
  on('loadError', hideBoot);
  loadAll();
  if (new URLSearchParams(location.search).get('dev') === '1') setTimeout(() => openDevPanel(restart), 900);
}

export async function restart() {
  clearTimeout(pollTimer);
  resetRouter();
  resetState();
  const c = loadDev();
  applyLive(c);
  api.setScenario(c.scenario, scenarioOpts(c));
  initRouter(createHome());
  loadAll();
}

start().catch((e) => {
  console.error(e);
  hideBoot();
  document.getElementById('stage').innerHTML = '<div class="boot-fail"><p class="head">Could not start the replica.</p><p class="sm muted">Run it from the app-v2 folder with a local server so the fixtures can load.</p></div>';
});
