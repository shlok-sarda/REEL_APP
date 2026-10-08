// Floating glass dock: Home, the search pill (a real input so the keyboard
// opens on the first tap, even on iPhone), Lists, You. In search mode the side
// buttons tuck away and the pill grows to full width, transform-only (FLIP).
import { el } from './util.js';
import { icon } from './icons.js';
import { onNav, switchTab } from './router.js';
import { animate, isReduced } from './motion.js';
import { S, on, displayName } from './store.js';
import { onLongPress } from './ui.js';

let dock = null;
let input = null;
let mode = 'idle';
const handlers = { focus: null, input: null, submit: null, clear: null };
let devOpener = null;
// Long-press on You opens Display settings.
export function setDevOpener(fn) { devOpener = fn; }

export function initDock(h) {
  Object.assign(handlers, h);
  dock = el(`<nav class="dock" aria-label="Main">
    <button class="dock-btn" type="button" data-tab="home" aria-label="Home">${icon('home')}<i class="dock-dot"></i></button>
    <form class="dock-pill" role="search" action="#">
      <span class="dock-pill-bg" aria-hidden="true"></span>
      <span class="dock-pill-inner">
        ${icon('search', 'dock-search-ic')}
        <input type="search" name="q" enterkeyhint="search" autocomplete="off" autocorrect="off" spellcheck="false" placeholder="Search reels" aria-label="Search your reels" />
        <button class="dock-clear" type="button" aria-label="Close search">${icon('x')}</button>
      </span>
      <span class="dock-progress" aria-hidden="true"></span>
    </form>
    <button class="dock-btn" type="button" data-tab="lists" aria-label="Lists">${icon('stack')}<i class="dock-dot"></i></button>
    <button class="dock-btn dock-you" type="button" data-you aria-label="You"><span class="dock-av"></span><i class="dock-busy" aria-hidden="true"></i></button>
  </nav>`);
  document.getElementById('dock-host').appendChild(dock);
  input = dock.querySelector('input');
  dock.querySelectorAll('[data-tab]').forEach((b) => b.addEventListener('click', () => switchTab(b.dataset.tab)));
  // You lives here, not in a header: the library gets the whole top of Home.
  const you = dock.querySelector('[data-you]');
  const paintYou = () => {
    const name = displayName();
    const av = you.querySelector('.dock-av');
    if (name) av.textContent = name.charAt(0).toUpperCase(); else av.innerHTML = icon('user');
    // A reel being sorted shows as a dot; the detail is in You > Activity.
    you.classList.toggle('is-busy', S.processing.length > 0);
  };
  paintYou();
  on('library', paintYou);
  on('session', paintYou);
  onLongPress(you, () => devOpener && devOpener());
  you.addEventListener('click', () => import('./screens/you.js').then((m) => m.openYou()));
  input.addEventListener('focus', () => { if (handlers.focus) handlers.focus(); });
  input.addEventListener('input', () => { if (handlers.input) handlers.input(input.value); });
  dock.querySelector('form').addEventListener('submit', (e) => { e.preventDefault(); if (handlers.submit) handlers.submit(input.value); input.blur(); });
  dock.querySelector('.dock-clear').addEventListener('click', () => { if (handlers.clear) handlers.clear(); });
  onNav((s) => {
    dock.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('is-active', b.dataset.tab === s.tab));
    const hide = !s.dock;
    dock.classList.toggle('is-hidden', hide);
    document.getElementById('device').classList.toggle('dock-off', hide);
    dock.toggleAttribute('inert', hide);
  });
  // Keep the dock above the on-screen keyboard (iOS does not resize the
  // layout viewport, so bottom-anchored things would sit under the keys).
  const vv = window.visualViewport;
  if (vv) {
    const place = () => {
      const kb = Math.max(0, window.innerHeight - vv.height - vv.offsetTop);
      document.getElementById('device').style.setProperty('--kb', kb > 60 ? `${Math.round(kb)}px` : '0px');
    };
    vv.addEventListener('resize', place);
    vv.addEventListener('scroll', place);
  }
}

export function dockInput() { return input; }
export function setDockLoading(on) { if (dock) dock.classList.toggle('is-loading', !!on); }
export function setDockValue(v) { if (input) input.value = v; }

export function setDockMode(next) {
  if (!dock || next === mode) return;
  const pill = dock.querySelector('.dock-pill');
  const bg = dock.querySelector('.dock-pill-bg');
  const inner = dock.querySelector('.dock-pill-inner');
  const before = pill.getBoundingClientRect();
  mode = next;
  dock.classList.toggle('is-search', next === 'search');
  if (next === 'search') dock.classList.remove('is-hidden');
  const after = pill.getBoundingClientRect();
  if (isReduced() || !before.width || !after.width) return;
  const sx = before.width / after.width;
  const dx = (before.left + before.width / 2) - (after.left + after.width / 2);
  animate(bg, [{ transform: `translateX(${dx}px) scaleX(${sx})` }, { transform: 'translateX(0) scaleX(1)' }], { duration: 380, easing: 'snap' });
  animate(inner, [{ transform: `translateX(${before.left - after.left}px)` }, { transform: 'translateX(0)' }], { duration: 380, easing: 'snap' });
  dock.querySelectorAll('.dock-btn').forEach((b, i) => {
    const dir = i === 0 ? -1 : 1;
    if (next === 'search') animate(b, [{ opacity: 1, transform: 'translateX(0) scale(1)' }, { opacity: 0, transform: `translateX(${dir * 24}px) scale(0.6)` }], { duration: 200, easing: 'out' });
    else animate(b, [{ opacity: 0, transform: `translateX(${dir * 24}px) scale(0.6)` }, { opacity: 1, transform: 'translateX(0) scale(1)' }], { duration: 320, easing: 'snap', delay: 60 });
  });
}

export function dockMode() { return mode; }
