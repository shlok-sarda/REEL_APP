// Card markup shared by every screen. Thumbnails reserve their box, show a
// dominant colour + tiny blurred preview, then fade the real image in.
import { esc, fmtDuration, el } from './util.js';
import { icon } from './icons.js';
import { S, reelsFor, monogram, isLinkSession } from './store.js';

export function thumb(r, cls = 'rc-thumb', opts = {}) {
  const lq = r.lqip ? `<img class="lq" src="${r.lqip}" alt="" aria-hidden="true">` : '';
  const src = opts.full ? r.full : r.thumb;
  const img = src ? `<img class="full" src="${esc(src)}" alt="" loading="${opts.eager ? 'eager' : 'lazy'}" decoding="async" data-fade>` : '';
  return `<span class="${cls}" style="--c:${r.color}">${lq}${img}${opts.dur && r.duration ? `<span class="rc-dur">${fmtDuration(r.duration)}</span>` : ''}${opts.inner || ''}</span>`;
}

// Fade images in once loaded (cached ones appear instantly, no flash).
export function wireFades(root) {
  root.querySelectorAll('img[data-fade]').forEach((img) => {
    img.removeAttribute('data-fade');
    if (img.complete && img.naturalWidth) { img.classList.add('is-loaded', 'is-instant'); return; }
    img.addEventListener('load', () => img.classList.add('is-loaded'), { once: true });
    img.addEventListener('error', () => { img.remove(); }, { once: true });
  });
}

export function reelCard(r, opts = {}) {
  const sel = opts.selectable ? `<span class="sel-ring">${icon('check')}</span>` : '';
  return `<article class="rc ${opts.selected ? 'is-selected' : ''}" data-rid="${esc(r.id)}" tabindex="0" role="button" aria-label="Play ${esc(r.name)}">
    ${thumb(r, 'rc-thumb', { dur: true, eager: opts.eager })}${sel}
    <div class="rc-meta"><h3 class="rc-title clamp-2">${esc(r.name)}</h3><p class="rc-sub">${esc(r.creator)}</p></div>
  </article>`;
}

export function processingCard(p) {
  const steps = ['Downloading', 'Watching the video', 'Sorting it'];
  const step = Math.max(0, Math.min(3, p.step || 0));
  const label = p.status === 'queued' ? 'Waiting in line' : steps[Math.max(0, step - 1)] || 'Starting';
  return `<article class="rc is-processing" data-job="${p.jobId}" aria-label="New reel, ${esc(label)}">
    <span class="rc-thumb sk-surface"><span class="rc-state"><span class="ico">${icon('sparkle')}</span><p><b>New reel</b>${esc(label)}</p>
    <span class="rc-steps">${[1, 2, 3].map((i) => `<i class="${i < step ? 'is-done' : i === step ? 'is-now' : ''}"></i>`).join('')}</span></span></span>
    <div class="rc-meta"><h3 class="rc-title clamp-2">Sorting your reel</h3><p class="rc-sub">${esc(p.shortcode ? 'instagram.com/reel/' + p.shortcode : 'From your DMs')}</p></div>
  </article>`;
}

export function failedCard(f) {
  return `<article class="rc is-failed" data-failed="${esc(f.rid)}">
    <span class="rc-thumb"><span class="rc-state"><span class="ico">${icon('alert')}</span><p><b>Could not read this one</b>${esc(f.why || 'Something went wrong while processing.')}</p>
    ${isLinkSession() ? '' : `<span class="rc-actions"><button class="btn btn-secondary" type="button" data-retry="${esc(f.rid)}">Try again</button></span>`}</span></span>
    <div class="rc-meta"><h3 class="rc-title clamp-2">Reel not sorted yet</h3><p class="rc-sub">${esc(f.shortcode ? 'instagram.com/reel/' + f.shortcode : '')}</p></div>
  </article>`;
}

export function skeletonCards(n = 4) {
  return Array.from({ length: n }, () => `<article class="rc sk-card" aria-hidden="true"><span class="rc-thumb sk"></span><div class="rc-meta"><div class="sk sk-line"></div><div class="sk sk-line is-short"></div></div></article>`).join('');
}

// List cover: a 2x2 reel collage, or the category emoji tile (A/B 3).
export function listCover(list, mode = 'collage') {
  const ids = (list.members || []).concat(list.suggestions || []);
  const rs = reelsFor(ids).slice(0, 4);
  if (mode === 'icon' || !rs.length) {
    return `<span class="cover cover-icon">${list.emoji ? `<span class="cover-emoji">${list.emoji}</span>` : `<span class="cover-mono">${esc(monogram(list.name))}</span>`}</span>`;
  }
  return `<span class="cover cover-collage n${rs.length}">${rs.map((r) => `<i style="--c:${r.color}">${r.lqip ? `<img class="lq" src="${r.lqip}" alt="">` : ''}<img class="full" src="${esc(r.thumb)}" alt="" loading="lazy" decoding="async" data-fade></i>`).join('')}</span>`;
}

export function emojiTile(emoji, text, cls = '') {
  return emoji ? `<span class="icon-tile ${cls}">${emoji}</span>` : `<span class="icon-tile is-mono ${cls}">${esc(monogram(text))}</span>`;
}

export function fan(rs, cls = 'fan') {
  return `<span class="${cls}">${rs.slice(0, 3).map((r) => `<i style="--c:${r.color}"><img src="${esc(r.thumb)}" alt="" decoding="async"></i>`).join('')}</span>`;
}

export function node(markup) { return el(markup); }

export function coverMode() { return (S.ab && S.ab.covers) || 'collage'; }

// Keyed patch: existing nodes are reused and moved, never rebuilt, so
// scroll position, focus and loaded images survive background refreshes.
export function patchList(container, items, keyOf, render, opts = {}) {
  const existing = new Map();
  container.querySelectorAll(':scope > [data-key]').forEach((n) => existing.set(n.dataset.key, n));
  const fresh = [];
  let prev = null;
  items.forEach((item) => {
    const key = keyOf(item);
    const sig = opts.sigOf ? opts.sigOf(item) : '';
    let n = existing.get(key);
    if (!n || (opts.sigOf && n.dataset.sig !== sig)) {
      const node = el(render(item));
      node.dataset.key = key;
      if (opts.sigOf) node.dataset.sig = sig;
      wireFades(node);
      if (n) n.replaceWith(node); else fresh.push(node);
      n = node;
    }
    existing.delete(key);
    const want = prev ? prev.nextElementSibling : container.firstElementChild;
    if (n !== want) container.insertBefore(n, prev ? prev.nextSibling : container.firstChild);
    prev = n;
  });
  existing.forEach((n) => n.remove());
  return fresh;
}

// One set of listeners per grid: tap plays, press-down warms the video,
// long-press opens details. Works for nodes added later by patchList.
export function delegateReelGrid(container, idsFn, handlers) {
  let timer = 0; let fired = false; let start = null;
  container.addEventListener('pointerdown', (e) => {
    const card = e.target.closest('.rc[data-rid]');
    if (!card || e.target.closest('button')) return;
    fired = false;
    start = { x: e.clientX, y: e.clientY };
    if (handlers.warm) handlers.warm(card.dataset.rid);
    clearTimeout(timer);
    timer = setTimeout(() => { fired = true; if (handlers.long) handlers.long(card.dataset.rid, card); }, 460);
  });
  const cancel = () => clearTimeout(timer);
  container.addEventListener('pointermove', (e) => { if (start && (Math.abs(e.clientX - start.x) > 8 || Math.abs(e.clientY - start.y) > 8)) cancel(); });
  container.addEventListener('pointerup', cancel);
  container.addEventListener('pointercancel', cancel);
  container.addEventListener('contextmenu', (e) => { if (e.target.closest('.rc[data-rid]')) e.preventDefault(); });
  container.addEventListener('click', (e) => {
    const card = e.target.closest('.rc[data-rid]');
    if (!card || e.target.closest('button')) return;
    if (fired) { fired = false; return; }
    const ids = idsFn();
    if (handlers.tap) handlers.tap(card.dataset.rid, ids, card);
  });
  container.addEventListener('keydown', (e) => {
    const card = e.target.closest('.rc[data-rid]');
    if (!card || (e.key !== 'Enter' && e.key !== ' ')) return;
    e.preventDefault();
    if (handlers.tap) handlers.tap(card.dataset.rid, idsFn(), card);
  });
}
