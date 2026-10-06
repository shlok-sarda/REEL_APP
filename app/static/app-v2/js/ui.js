// Shared UI primitives: press feedback, sheets, toasts, confirm, errors.
import { el, esc, clamp, haptic } from './util.js';
import { icon } from './icons.js';
import { animate, moveTo, freeze, isReduced, fadeTo } from './motion.js';
import { pushLayer, closeLayer, isOpen } from './router.js';

const overlays = () => document.getElementById('overlays');

/* ---------- press feedback: same frame as pointerdown, cancels on scroll ---------- */
const PRESSABLE = '[data-press], .btn, .icon-btn, .chip, .rc, .row, .rrow, .pressable, .link-btn, .seg button, .search-entry, .pill-status, .w-tile, .lcard, .dock-btn, .scard';
let pressed = null;
let pressStart = null;
export function initPress() {
  document.addEventListener('touchstart', () => {}, { passive: true });
  document.addEventListener('pointerdown', (e) => {
    const t = e.target.closest(PRESSABLE);
    if (!t || t.disabled || t.getAttribute('aria-disabled') === 'true') return;
    pressed = t;
    pressStart = { x: e.clientX, y: e.clientY };
    t.classList.add('is-pressed');
  }, { passive: true });
  const clear = () => { if (pressed) { pressed.classList.remove('is-pressed'); pressed = null; } };
  document.addEventListener('pointermove', (e) => {
    if (!pressed || !pressStart) return;
    if (Math.abs(e.clientX - pressStart.x) > 8 || Math.abs(e.clientY - pressStart.y) > 8) clear();
  }, { passive: true });
  document.addEventListener('pointerup', clear, { passive: true });
  document.addEventListener('pointercancel', clear, { passive: true });
  document.addEventListener('scroll', clear, { passive: true, capture: true });
}

export function onLongPress(node, fn, ms = 460) {
  let timer = 0;
  let start = null;
  let fired = false;
  node.addEventListener('pointerdown', (e) => {
    fired = false;
    start = { x: e.clientX, y: e.clientY };
    clearTimeout(timer);
    timer = setTimeout(() => { fired = true; haptic(12); fn(e); }, ms);
  });
  const cancel = () => clearTimeout(timer);
  node.addEventListener('pointermove', (e) => { if (start && (Math.abs(e.clientX - start.x) > 8 || Math.abs(e.clientY - start.y) > 8)) cancel(); });
  node.addEventListener('pointerup', cancel);
  node.addEventListener('pointercancel', cancel);
  node.addEventListener('contextmenu', (e) => e.preventDefault());
  node.addEventListener('click', (e) => { if (fired) { e.stopPropagation(); e.preventDefault(); fired = false; } }, true);
}

export function makeScreen(cls = '') {
  const wrap = document.createElement('section');
  wrap.className = 'screen-wrap ' + cls;
  const scroller = document.createElement('div');
  scroller.className = 'screen';
  wrap.appendChild(scroller);
  return { el: wrap, scroller };
}

/* ---------- errors ---------- */
export function errorMessage(e) {
  if (!e) return 'Something went wrong. Try again.';
  if (e.status === 0) return 'You are offline. Try again when you are back online.';
  if (e.status === 403 && e.detail === 'demo') return 'This is the demo library, so changes are switched off.';
  if (e.status === 403) return e.detail || 'You cannot do that from this link.';
  if (e.status === 404) return 'That is not there any more.';
  return 'Something went wrong on our side. Try again.';
}

let offlineTimer = 0;
export function setOffline(on) {
  const b = document.getElementById('offline-banner');
  if (!b) return;
  if (!b.innerHTML) b.innerHTML = `${icon('wifiOff')}<span>Offline. Showing what you have already loaded.</span>`;
  clearTimeout(offlineTimer);
  b.classList.toggle('is-on', !!on);
  if (on) offlineTimer = setTimeout(() => b.classList.remove('is-on'), 4200);
}

/* ---------- toast: one at a time ---------- */
let currentToast = null;
let toastTimer = 0;
let scopedToast = null;
import('./router.js').then((r) => r.onNav(() => { if (scopedToast && scopedToast.isConnected) dismissToast(scopedToast); scopedToast = null; }));

export function toast(opts) {
  const host = document.getElementById('toast-host');
  const o = typeof opts === 'string' ? { msg: opts } : opts;
  if (currentToast) dismissToast(currentToast, true);
  const why = o.why ? `<div class="toast-why">${o.why.map((w, i) => `<button class="chip" type="button" data-why="${i}">${esc(w)}</button>`).join('')}</div>` : '';
  const t = el(`<div class="toast ${o.tone === 'error' ? 'is-error' : ''} ${o.why ? 'is-stacked' : ''}" role="status">
    <span class="toast-ico ${['x', 'trash'].includes(o.icon) ? 'is-quiet' : ''}">${icon(o.tone === 'error' ? 'alert' : (o.icon || 'check'))}</span>
    <div class="toast-msg">${esc(o.msg)}${o.sub ? `<small>${esc(o.sub)}</small>` : ''}${why}</div>
    ${o.action ? `<button class="btn btn-ghost btn-sm" type="button" data-act>${esc(o.action.label)}</button>` : ''}
  </div>`);
  host.appendChild(t);
  host.classList.toggle('is-raised', !!o.raised);
  currentToast = t;
  scopedToast = o.scoped ? t : null;
  animate(t, isReduced() ? [{ opacity: 0 }, { opacity: 1 }] : [{ opacity: 0, transform: 'translateY(16px) scale(0.98)' }, { opacity: 1, transform: 'translateY(0) scale(1)' }], { duration: 300, easing: 'snap', clear: true });
  const act = t.querySelector('[data-act]');
  if (act) act.addEventListener('click', () => { o.action.fn(); dismissToast(t); });
  t.querySelectorAll('[data-why]').forEach((b) => b.addEventListener('click', () => {
    t.querySelectorAll('[data-why]').forEach((x) => x.classList.remove('is-on'));
    b.classList.add('is-on');
    if (o.onWhy) o.onWhy(o.why[Number(b.dataset.why)]);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => dismissToast(t), 1400);
  }));
  // swipe down or sideways to dismiss
  let sx = 0; let sy = 0; let dragging = false;
  t.addEventListener('pointerdown', (e) => { if (e.target.closest('button')) return; sx = e.clientX; sy = e.clientY; dragging = true; t.setPointerCapture(e.pointerId); });
  t.addEventListener('pointermove', (e) => {
    if (!dragging) return;
    const dx = e.clientX - sx; const dy = Math.max(0, e.clientY - sy);
    t.style.transform = `translate(${dx}px, ${dy}px)`;
    t.style.opacity = String(1 - Math.min(0.8, (Math.abs(dx) + dy) / 220));
  });
  t.addEventListener('pointerup', (e) => {
    if (!dragging) return;
    dragging = false;
    const dx = e.clientX - sx; const dy = e.clientY - sy;
    if (Math.abs(dx) > 70 || dy > 40) dismissToast(t);
    else { moveTo(t, 'translate(0px, 0px)', { duration: 220, easing: 'snap', force: true }); t.style.opacity = '1'; }
  });
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => dismissToast(t), o.duration || (o.action || o.why ? 5200 : 3200));
  if (o.tone === 'error') haptic(18);
  return t;
}

export function dismissToast(t, instant) {
  if (!t || !t.isConnected) return;
  if (currentToast === t) currentToast = null;
  if (instant) { t.remove(); return; }
  freeze(t);
  animate(t, [{ opacity: getComputedStyle(t).opacity, transform: getComputedStyle(t).transform === 'none' ? 'translateY(0)' : getComputedStyle(t).transform }, { opacity: 0, transform: 'translateY(12px)' }], { duration: 180, easing: 'in' }).then(() => t.remove());
}

export function apiToast(e, retry) {
  if (e && e.status === 0) setOffline(true);
  return toast({ msg: errorMessage(e), tone: 'error', action: retry ? { label: 'Retry', fn: retry } : null, raised: false });
}

/* ---------- bottom sheet with drag, velocity and detents ---------- */
export function openSheet(opts) {
  const scrim = el('<div class="scrim" aria-hidden="true"></div>');
  const sheet = el(`<section class="sheet ${opts.className || ''}" role="dialog" aria-modal="true" aria-label="${esc(opts.label || opts.title || 'Sheet')}">
    <div class="sheet-grab" data-drag><i></i></div>
    ${opts.title || opts.eyebrow ? `<div class="sheet-head" data-drag><div class="grow">${opts.eyebrow ? `<p class="eyebrow">${esc(opts.eyebrow)}</p>` : ''}${opts.title ? `<h2 class="head sheet-title">${esc(opts.title)}</h2>` : ''}${opts.sub ? `<p class="sm muted sheet-sub">${esc(opts.sub)}</p>` : ''}</div><button class="icon-btn is-filled" type="button" data-close aria-label="Close">${icon('x')}</button></div>` : ''}
    <div class="sheet-body"></div>
    ${opts.foot ? '<div class="sheet-foot"></div>' : ''}
  </section>`);
  const body = sheet.querySelector('.sheet-body');
  if (typeof opts.body === 'string') body.innerHTML = opts.body;
  else if (opts.body) body.appendChild(opts.body);
  if (opts.foot) { const f = sheet.querySelector('.sheet-foot'); if (typeof opts.foot === 'string') f.innerHTML = opts.foot; else f.appendChild(opts.foot); }
  if (opts.full) sheet.classList.add('is-full');
  // Later sheets stack above earlier ones and above the list modal.
  const z = 66 + document.querySelectorAll('#overlays .sheet').length * 2;
  scrim.style.zIndex = String(z);
  sheet.style.zIndex = String(z + 1);
  overlays().appendChild(scrim);
  overlays().appendChild(sheet);
  const prevFocus = document.activeElement;
  document.getElementById('stage').setAttribute('inert', '');
  requestAnimationFrame(() => scrim.classList.add('is-on'));
  if (isReduced()) { sheet.style.transform = 'translateY(0%)'; animate(sheet, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 }); }
  else moveTo(sheet, 'translateY(0%)', { duration: 400, easing: 'snap' });

  let closed = false;
  const api = { el: sheet, body, scrim, layer: null, onClose: opts.onClose };
  api.layer = pushLayer({
    kind: 'overlay',
    hidesDock: opts.hidesDock !== false,
    close: ({ instant }) => {
      if (closed) return;
      closed = true;
      if (!document.querySelector('#overlays .sheet:not(.is-closing)') || document.querySelectorAll('#overlays .sheet').length <= 1) document.getElementById('stage').removeAttribute('inert');
      sheet.classList.add('is-closing');
      scrim.classList.remove('is-on');
      const done = () => { sheet.remove(); scrim.remove(); if (prevFocus && prevFocus.focus && prevFocus.isConnected) { try { prevFocus.focus({ preventScroll: true }); } catch (e) { /* ignore */ } } if (api.onClose) api.onClose(); };
      if (instant) { done(); return; }
      if (isReduced()) { animate(sheet, [{ opacity: 1 }, { opacity: 0 }], { duration: 140 }).then(done); return; }
      moveTo(sheet, 'translateY(105%)', { duration: 260, easing: 'in', force: true }).then(done);
    },
  });
  api.close = () => (isOpen(api.layer) ? closeLayer(api.layer) : Promise.resolve());
  api.setFull = (on) => sheet.classList.toggle('is-full', on);
  scrim.addEventListener('click', api.close);
  sheet.querySelectorAll('[data-close]').forEach((b) => b.addEventListener('click', api.close));
  sheet.addEventListener('keydown', (e) => { if (e.key === 'Escape') api.close(); });

  // drag to dismiss / expand
  let drag = null;
  const startDrag = (e) => {
    drag = { y: e.clientY, t: performance.now(), lastY: e.clientY, lastT: performance.now(), v: 0, h: sheet.offsetHeight };
    freeze(sheet);
  };
  sheet.addEventListener('pointerdown', (e) => {
    if (e.button && e.button !== 0) return;
    const onHandle = e.target.closest('[data-drag]');
    const inBody = e.target.closest('.sheet-body');
    if (e.target.closest('input, textarea, select, button, a') && !onHandle) return;
    if (onHandle || (inBody && body.scrollTop <= 0)) {
      startDrag(e);
      drag.fromBody = !onHandle;
      drag.pid = e.pointerId;
    }
  });
  sheet.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dy = e.clientY - drag.y;
    if (drag.fromBody && !drag.active) {
      if (dy < 6) { if (dy < -4) drag = null; return; }
      drag.active = true;
      try { sheet.setPointerCapture(drag.pid); } catch (err) { /* ignore */ }
    }
    drag.active = true;
    const now = performance.now();
    drag.v = (e.clientY - drag.lastY) / Math.max(1, now - drag.lastT);
    drag.lastY = e.clientY; drag.lastT = now;
    const y = dy > 0 ? dy : dy * 0.18;
    sheet.style.transform = `translateY(${y}px)`;
    scrim.style.opacity = String(clamp(1 - dy / (drag.h * 1.1), 0, 1));
  });
  const endDrag = (e) => {
    if (!drag) return;
    const d = drag;
    drag = null;
    if (!d.active) return;
    const dy = e.clientY - d.y;
    scrim.style.opacity = '';
    if (dy > d.h * 0.28 || d.v > 0.65) { api.close(); return; }
    if (dy < -50 && opts.expandable) api.setFull(true);
    moveTo(sheet, 'translateY(0px)', { duration: 320, easing: 'snap', force: true });
  };
  sheet.addEventListener('pointerup', endDrag);
  sheet.addEventListener('pointercancel', endDrag);

  sheet.setAttribute('tabindex', '-1');
  setTimeout(() => {
    const f = sheet.querySelector('[data-autofocus]') || sheet;
    try { f.focus({ preventScroll: true }); } catch (e) { /* ignore */ }
  }, 60);
  return api;
}

/* ---------- confirm ---------- */
export function confirmSheet({ title, body, confirm = 'Confirm', danger = false, cancel = 'Cancel' }) {
  return new Promise((resolve) => {
    let answered = false;
    const content = el(`<div class="confirm">
      <p class="sm muted">${esc(body || '')}</p>
      <div class="confirm-actions">
        <button class="btn ${danger ? 'btn-danger' : 'btn-primary'} btn-block" type="button" data-yes>${esc(confirm)}</button>
        <button class="btn btn-secondary btn-block" type="button" data-no>${esc(cancel)}</button>
      </div></div>`);
    const s = openSheet({ title, body: content, className: 'sheet-confirm', onClose: () => { if (!answered) resolve(false); } });
    content.querySelector('[data-yes]').addEventListener('click', () => { answered = true; s.close().then(() => resolve(true)); });
    content.querySelector('[data-no]').addEventListener('click', () => { answered = true; s.close().then(() => resolve(false)); });
  });
}

export function btnLoading(btn, on) {
  if (!btn) return;
  if (on) {
    if (!btn.querySelector('.btn-spin')) btn.insertAdjacentHTML('beforeend', '<span class="btn-spin" aria-hidden="true"></span>');
    btn.classList.add('is-loading');
    btn.setAttribute('aria-busy', 'true');
  } else {
    btn.classList.remove('is-loading');
    btn.removeAttribute('aria-busy');
  }
}

export function shareOrCopy(title, url) {
  if (navigator.share) {
    navigator.share({ title, url }).catch(() => {});
    return;
  }
  copyText(url).then((ok) => toast(ok ? { msg: 'Link copied', icon: 'link' } : { msg: 'Could not copy the link', tone: 'error' }));
}

export function copyText(text) {
  if (navigator.clipboard && navigator.clipboard.writeText) {
    return navigator.clipboard.writeText(text).then(() => true).catch(() => legacyCopy(text));
  }
  return Promise.resolve(legacyCopy(text));
}
function legacyCopy(text) {
  try {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    const ok = document.execCommand('copy');
    ta.remove();
    return ok;
  } catch (e) { return false; }
}

export { fadeTo };

// Floating nav bar for pushed screens: back button always visible, the
// title and a frosted background fade in once the big title scrolls away.
export function navBar(screen, title, endHtml = '') {
  const bar = document.createElement('div');
  bar.className = 'navbar';
  bar.innerHTML = `<button class="icon-btn is-glass" type="button" data-back aria-label="Back">${icon('back')}</button><span class="navbar-title">${esc(title)}</span><span class="navbar-end">${endHtml}</span>`;
  screen.el.appendChild(bar);
  bar.querySelector('[data-back]').addEventListener('click', () => import('./router.js').then((m) => m.back()));
  const onScroll = () => bar.classList.toggle('is-solid', screen.scroller.scrollTop > 64);
  screen.scroller.addEventListener('scroll', onScroll, { passive: true });
  return bar;
}
