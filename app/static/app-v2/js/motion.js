// Motion engine. Every JS animation goes through here so one switch controls
// speed (slow-mo review) and reduced motion. Transform and opacity only.

const root = document.documentElement;
const osReduced = window.matchMedia ? window.matchMedia('(prefers-reduced-motion: reduce)') : null;

export const motion = { mode: 'auto', scale: 1, reduced: false };

export function setMotionMode(mode) {
  motion.mode = mode;
  motion.reduced = mode === 'reduced' || (mode === 'auto' && !!(osReduced && osReduced.matches));
  motion.scale = mode === 'slow' ? 5 : 1;
  root.dataset.motion = motion.reduced ? 'reduced' : (mode === 'slow' ? 'slow' : 'normal');
}
if (osReduced && osReduced.addEventListener) {
  osReduced.addEventListener('change', () => { if (motion.mode === 'auto') setMotionMode('auto'); });
}

export const isReduced = () => motion.reduced;
export const dur = (ms) => ms * motion.scale;

function cssVar(name, fallback) {
  const v = getComputedStyle(root).getPropertyValue(name).trim();
  return v || fallback;
}
let cache = null;
export function ease(name) {
  if (!cache) {
    cache = {
      out: 'cubic-bezier(0.16, 1, 0.3, 1)',
      in: 'cubic-bezier(0.3, 0, 0.8, 0.15)',
      inout: 'cubic-bezier(0.65, 0, 0.35, 1)',
      snap: cssVar('--spring-snap', 'cubic-bezier(0.16, 1, 0.3, 1)'),
      soft: cssVar('--spring-soft', 'cubic-bezier(0.16, 1, 0.3, 1)'),
      pop: cssVar('--spring-pop', 'cubic-bezier(0.34, 1.56, 0.64, 1)'),
    };
  }
  return cache[name] || cache.out;
}

// Animate and settle: the final frame is committed to inline style and the
// animation removed, so nothing piles up and the next animation can start
// from wherever this one is.
export function animate(node, keyframes, opts = {}) {
  if (!node || !node.animate) return Promise.resolve();
  // Animations started on a node that is not in the document yet never run
  // in Chrome; wait one frame so callers can animate freshly built nodes.
  if (!node.isConnected) {
    return new Promise((resolve) => requestAnimationFrame(() => {
      if (!node.isConnected) { applyLast(node, keyframes); resolve(); return; }
      animate(node, keyframes, opts).then(resolve);
    }));
  }
  const duration = dur(opts.duration == null ? 220 : opts.duration);
  const a = node.animate(keyframes, {
    duration,
    easing: opts.easing ? ease(opts.easing) : ease('out'),
    delay: dur(opts.delay || 0),
    fill: 'both',
  });
  node.__anims = (node.__anims || []).concat(a);
  return a.finished.then(() => {
    if (opts.clear) {
      // Entrance finished at the element's natural state: give it back to
      // CSS so :active / .is-pressed transforms keep working.
      a.cancel();
      node.style.removeProperty('transform');
      node.style.removeProperty('opacity');
      node.__anims = (node.__anims || []).filter((x) => x !== a);
      return;
    }
    try { if (a.commitStyles) a.commitStyles(); else applyLast(node, keyframes); } catch (e) { applyLast(node, keyframes); }
    a.cancel();
    node.__anims = (node.__anims || []).filter((x) => x !== a);
  }).catch(() => { /* interrupted: the interrupter owns the element now */ });
}

function applyLast(node, keyframes) {
  const last = Array.isArray(keyframes) ? keyframes[keyframes.length - 1] : null;
  if (!last) return;
  Object.keys(last).forEach((k) => { if (k !== 'offset' && k !== 'easing') node.style[k] = last[k]; });
}

// Freeze an element where it is right now and stop whatever was moving it.
export function freeze(node) {
  if (!node) return;
  const cs = getComputedStyle(node);
  const t = cs.transform;
  const o = cs.opacity;
  (node.__anims || []).forEach((a) => a.cancel());
  node.__anims = [];
  node.style.transform = t === 'none' ? '' : t;
  node.style.opacity = o;
}

export function currentTransform(node) {
  const t = getComputedStyle(node).transform;
  return t && t !== 'none' ? t : 'translate(0px, 0px)';
}

// Interruptible move to a target transform from the current visual position.
export function moveTo(node, transform, opts = {}) {
  freeze(node);
  const from = currentTransform(node);
  if (motion.reduced && !opts.force) {
    node.style.transform = transform;
    return Promise.resolve();
  }
  return animate(node, [{ transform: from }, { transform }], opts);
}

export function fadeTo(node, opacity, opts = {}) {
  if (!node) return Promise.resolve();
  const from = getComputedStyle(node).opacity;
  (node.__fade || []).forEach((a) => a.cancel());
  const p = animate(node, [{ opacity: from }, { opacity: String(opacity) }], { duration: opts.duration || 160, easing: opts.easing || 'out', delay: opts.delay });
  return p;
}

// Count a number up in an element: used once, on the library widget.
export function countUp(node, to, ms = 700) {
  if (!node) return;
  if (motion.reduced) { node.textContent = String(to); return; }
  const start = performance.now();
  const total = dur(ms);
  const step = (now) => {
    const t = Math.min(1, (now - start) / total);
    const e = 1 - Math.pow(1 - t, 3);
    node.textContent = String(Math.round(to * e));
    if (t < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// The landing page "slamWords" feel: words punch in, 35ms apart.
export function slamWords(node, text, opts = {}) {
  if (!node) return;
  const parts = String(text).split(' ');
  node.innerHTML = parts.map((w) => `<span class="slam-w">${w.replace(/[<>&]/g, '')}</span>`).join(' ');
  if (motion.reduced) return;
  node.querySelectorAll('.slam-w').forEach((w, i) => {
    w.style.display = 'inline-block';
    animate(w, [
      { opacity: 0, transform: 'translateY(10px) scale(0.86)' },
      { opacity: 1, transform: 'translateY(0) scale(1)' },
    ], { duration: 520, easing: 'pop', delay: (opts.delay || 0) + i * 35, clear: true });
  });
}

// Staggered rise for groups of elements entering together.
export function rise(nodes, opts = {}) {
  const list = Array.from(nodes || []);
  if (motion.reduced) {
    list.forEach((n, i) => animate(n, [{ opacity: 0 }, { opacity: 1 }], { duration: 150, delay: Math.min(i, 6) * 20, clear: true }));
    return;
  }
  list.forEach((n, i) => {
    animate(n, [
      { opacity: 0, transform: `translateY(${opts.y || 16}px)` },
      { opacity: 1, transform: 'translateY(0)' },
    ], { duration: opts.duration || 440, easing: 'out', delay: (opts.delay || 0) + Math.min(i, 8) * (opts.stagger || 45), clear: true });
  });
}

// A warm glow that blooms once on an element, then leaves.
export function glowBeat(node) {
  if (!node || motion.reduced) return;
  const g = document.createElement('span');
  g.className = 'glow-beat';
  node.appendChild(g);
  animate(g, [
    { opacity: 0, transform: 'scale(0.92)' },
    { opacity: 1, transform: 'scale(1)', offset: 0.3 },
    { opacity: 0, transform: 'scale(1.04)' },
  ], { duration: 1100, easing: 'out' }).then(() => g.remove());
}
