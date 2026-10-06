// Navigation: one history entry per screen, sheet and overlay, so Android
// back and iOS swipe-back always do the expected thing. Screens push with an
// interruptible slide; tabs cross-fade.
import { animate, moveTo, freeze, isReduced } from './motion.js';

const stage = () => document.getElementById('stage');
const layers = [];
let ignorePops = 0;
const popWaiters = [];
let lastEdgeTouch = 0;
let rootInst = null;
const listeners = new Set();

export function onNav(fn) { listeners.add(fn); return () => listeners.delete(fn); }
function changed() { const s = navState(); listeners.forEach((fn) => fn(s)); }

export function navState() {
  const tab = layers.some((l) => l.kind === 'tab') ? 'lists' : 'home';
  let dock = true;
  for (let i = layers.length - 1; i >= 0; i -= 1) {
    const l = layers[i];
    if (l.kind === 'overlay') { if (l.hidesDock !== false) { dock = false; } break; }
    if (l.kind === 'screen' || l.kind === 'tab') { dock = l.inst.dock !== false; break; }
  }
  if (!layers.length && rootInst) dock = rootInst.dock !== false;
  return { tab, dock, depth: layers.length, top: layers[layers.length - 1] || null };
}

export function initRouter(root) {
  rootInst = root;
  root.el.classList.add('screen-wrap', 'is-root');
  root.el.style.zIndex = '1';
  stage().appendChild(root.el);
  try { history.replaceState({ cn: 0 }, ''); } catch (e) { /* sandboxed */ }
  window.addEventListener('popstate', onPop);
  document.addEventListener('touchstart', (e) => {
    const t = e.touches && e.touches[0];
    if (t && (t.clientX < 28 || t.clientX > window.innerWidth - 28)) lastEdgeTouch = Date.now();
  }, { passive: true });
  if (root.onShow) root.onShow();
  changed();
}

function onPop() {
  if (ignorePops > 0) {
    ignorePops -= 1;
    const w = popWaiters.shift();
    if (w) w();
    flush();
    return;
  }
  const top = layers.pop();
  if (!top) return;
  // Safari's own edge-swipe already animated a screenshot; don't animate twice.
  const instant = Date.now() - lastEdgeTouch < 700;
  top.close({ fromPop: true, instant });
  changed();
}

// A programmatic back is async in the browser. Anything pushed while it is in
// flight waits, otherwise the pending back would eat the new entry.
const deferred = [];
function flush() {
  if (ignorePops === 0) while (deferred.length) deferred.shift()();
}
function expectPop() {
  ignorePops += 1;
  return new Promise((resolve) => {
    let done = false;
    const finish = () => { if (!done) { done = true; resolve(); } };
    popWaiters.push(finish);
    setTimeout(() => {
      if (done) return;
      const i = popWaiters.indexOf(finish);
      if (i >= 0) { popWaiters.splice(i, 1); ignorePops = Math.max(0, ignorePops - 1); }
      finish();
      flush();
    }, 500);
  });
}
function pushHistory() {
  const fn = () => { try { history.pushState({ cn: layers.length }, ''); } catch (e) { /* sandboxed */ } };
  if (ignorePops > 0) deferred.push(fn); else fn();
}

export function pushLayer(layer) {
  layers.push(layer);
  pushHistory();
  changed();
  return layer;
}

export function back() {
  const top = layers.pop();
  if (!top) return Promise.resolve();
  top.close({ fromPop: false });
  const p = expectPop();
  try { history.back(); } catch (e) { /* sandboxed */ }
  changed();
  return p;
}

export function closeLayer(layer) {
  if (layers[layers.length - 1] === layer) return back();
  const i = layers.indexOf(layer);
  if (i >= 0) return unwindTo(i);
  return Promise.resolve();
}

export function isOpen(layer) { return layers.includes(layer); }

export function unwindTo(count) {
  const n = layers.length - count;
  if (n <= 0) return Promise.resolve();
  const closing = layers.splice(count).reverse();
  closing.forEach((l, i) => l.close({ fromPop: false, instant: i > 0 }));
  const p = expectPop();
  try { history.go(-n); } catch (e) { /* sandboxed */ }
  changed();
  return p;
}

export function topScreen() {
  for (let i = layers.length - 1; i >= 0; i -= 1) {
    if (layers[i].kind === 'screen' || layers[i].kind === 'tab') return layers[i].inst;
  }
  return rootInst;
}

function shadeOf(inst) {
  let s = inst.el.querySelector(':scope > .screen-shade');
  if (!s) { s = document.createElement('div'); s.className = 'screen-shade'; inst.el.appendChild(s); }
  return s;
}

/* ---------- screen push / pop ---------- */
export function pushScreen(inst) {
  const under = topScreen();
  inst.el.classList.add('screen-wrap');
  inst.el.style.zIndex = String(10 + layers.length);
  stage().appendChild(inst.el);
  const shade = shadeOf(under);
  if (isReduced()) {
    animate(inst.el, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 });
  } else {
    inst.el.style.transform = 'translateX(100%)';
    moveTo(inst.el, 'translateX(0%)', { duration: 380, easing: 'snap' });
    moveTo(under.el, 'translateX(-24%)', { duration: 380, easing: 'snap' });
    animate(shade, [{ opacity: 0 }, { opacity: 0.42 }], { duration: 380, easing: 'out' });
  }
  under.el.classList.add('is-under');
  if (under.onHide) under.onHide();
  if (inst.onShow) inst.onShow();
  const layer = {
    kind: 'screen',
    inst,
    close: ({ instant }) => {
      under.el.classList.remove('is-under');
      if (under.onShow) under.onShow();
      if (inst.onHide) inst.onHide();
      const done = () => { if (inst.destroy) inst.destroy(); inst.el.remove(); };
      if (instant || isReduced()) {
        freeze(inst.el); freeze(under.el); freeze(shade);
        under.el.style.transform = '';
        shade.style.opacity = '0';
        if (instant) done();
        else animate(inst.el, [{ opacity: 1 }, { opacity: 0 }], { duration: 140 }).then(done);
        return;
      }
      moveTo(inst.el, 'translateX(100%)', { duration: 280, easing: 'out' }).then(done);
      moveTo(under.el, 'translateX(0%)', { duration: 280, easing: 'out' }).then(() => { under.el.style.transform = ''; });
      freeze(shade);
      animate(shade, [{ opacity: getComputedStyle(shade).opacity }, { opacity: 0 }], { duration: 240 });
    },
  };
  return pushLayer(layer);
}

/* ---------- tabs (Home root + cached Lists root) ---------- */
let listsInst = null;
let listsFactory = null;
export function registerListsTab(factory) { listsFactory = factory; }

export async function switchTab(tab) {
  const idx = layers.findIndex((l) => l.kind === 'tab');
  if (tab === 'home') {
    if (!layers.length) { if (rootInst.scrollTop) rootInst.scrollTop(); return; }
    await unwindTo(0);
    return;
  }
  if (idx >= 0) {
    if (idx === layers.length - 1) { if (listsInst.scrollTop) listsInst.scrollTop(); return; }
    await unwindTo(idx + 1);
    return;
  }
  if (layers.length) await unwindTo(0);
  if (!listsInst) {
    listsInst = listsFactory();
    listsInst.el.classList.add('screen-wrap', 'is-root');
  }
  const inst = listsInst;
  inst.el.style.zIndex = '5';
  inst.el.style.transform = '';
  stage().appendChild(inst.el);
  animate(inst.el, isReduced() ? [{ opacity: 0 }, { opacity: 1 }] : [{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 200 });
  if (rootInst.onHide) rootInst.onHide();
  if (inst.onShow) inst.onShow();
  pushLayer({
    kind: 'tab',
    inst,
    close: ({ instant }) => {
      if (inst.onHide) inst.onHide();
      if (rootInst.onShow) rootInst.onShow();
      if (instant) { inst.el.remove(); return; }
      animate(inst.el, [{ opacity: 1 }, { opacity: 0 }], { duration: 150 }).then(() => { inst.el.remove(); inst.el.style.opacity = ''; });
    },
  });
}

export function resetRouter() {
  const n = layers.length;
  if (n) { expectPop(); try { history.go(-n); } catch (e) { /* sandboxed */ } }
  while (layers.length) {
    const l = layers.pop();
    try { l.close({ fromPop: false, instant: true }); } catch (e) { /* ignore */ }
  }
  if (listsInst) { if (listsInst.destroy) listsInst.destroy(); listsInst.el.remove(); listsInst = null; }
  if (rootInst) { if (rootInst.destroy) rootInst.destroy(); rootInst.el.remove(); rootInst = null; }
  changed();
}
