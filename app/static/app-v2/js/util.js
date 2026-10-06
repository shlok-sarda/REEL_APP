// Small helpers. Port note: no backslashes in this file (it may be pasted
// into a non-raw Python string later). Regexes use character classes only.

export const $ = (sel, root = document) => root.querySelector(sel);
export const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export function esc(value) {
  return String(value == null ? '' : value).replace(/[&<>"']/g, (c) => ESC[c]);
}

export function html(strings, ...values) {
  return strings.reduce((out, s, i) => out + s + (i < values.length ? values[i] : ''), '');
}

export function el(markup) {
  const t = document.createElement('template');
  t.innerHTML = markup.trim();
  return t.content.firstElementChild;
}

export const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
export const plural = (n, one, many) => `${n} ${n === 1 ? one : (many || one + 's')}`;
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const raf = () => new Promise((r) => requestAnimationFrame(() => r()));

export function fmtDuration(sec) {
  const s = Math.max(0, Math.round(Number(sec) || 0));
  return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0');
}

export function cleanCreator(c) {
  const name = String(c || '').split(' | ')[0].trim();
  return name.toLowerCase() === 'unknown' ? '' : name;
}

export function greetingWord(d = new Date()) {
  const h = d.getHours();
  if (h < 5) return 'Up late';
  if (h < 12) return 'Good morning';
  if (h < 17) return 'Good afternoon';
  return 'Good evening';
}

export function savedLabel(iso) {
  const t = Date.parse(String(iso || '').replace(' ', 'T'));
  if (!Number.isFinite(t)) return '';
  const days = Math.round((Date.now() - t) / 86400000);
  if (days < 1) return 'Saved today';
  if (days === 1) return 'Saved yesterday';
  if (days < 30) return `Saved ${days} days ago`;
  return 'Saved ' + new Date(t).toLocaleDateString([], { day: 'numeric', month: 'short' });
}

export function words(text) {
  return String(text || '').toLowerCase().split(/[^a-z0-9]+/).filter(Boolean);
}

export function titleCase(s) {
  return String(s || '').replace(/(^|[ ])([a-z])/g, (m, a, b) => a + b.toUpperCase());
}

export function debounce(fn, ms) {
  let t = 0;
  const d = (...args) => { clearTimeout(t); t = setTimeout(() => fn(...args), ms); };
  d.cancel = () => clearTimeout(t);
  return d;
}

// Storage that never throws: private mode, blocked storage and previews all
// return the fallback instead of breaking the page.
export const store = {
  get(key, fallback) {
    try {
      const v = localStorage.getItem('cn2_' + key);
      return v == null ? fallback : JSON.parse(v);
    } catch (e) { return fallback; }
  },
  set(key, value) {
    try { localStorage.setItem('cn2_' + key, JSON.stringify(value)); } catch (e) { /* storage unavailable */ }
  },
  del(key) {
    try { localStorage.removeItem('cn2_' + key); } catch (e) { /* storage unavailable */ }
  },
};

export function haptic(ms = 8) {
  try { if (navigator.vibrate) navigator.vibrate(ms); } catch (e) { /* not supported */ }
}

export const NL = String.fromCharCode(10);

export function uid() {
  return Math.random().toString(36).slice(2, 9);
}
