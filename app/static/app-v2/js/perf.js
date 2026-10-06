// Frame-time meter: jank is measured, not guessed. FPS and worst frame come
// from requestAnimationFrame; long tasks and interaction latency (INP-style)
// come from PerformanceObserver where the browser supports them (Chromium).
let hud = null;
let raf = 0;
let timer = 0;
const frames = [];
let longTasks = 0;
let worstInteraction = 0;
let observers = [];

export function startHud() {
  if (hud) return;
  hud = document.createElement('div');
  hud.className = 'perf-hud';
  hud.setAttribute('aria-hidden', 'true');
  document.getElementById('device').appendChild(hud);
  frames.length = 0;
  longTasks = 0;
  worstInteraction = 0;
  const loop = (t) => {
    frames.push(t);
    while (frames.length && t - frames[0] > 3000) frames.shift();
    raf = requestAnimationFrame(loop);
  };
  raf = requestAnimationFrame(loop);
  try {
    const lt = new PerformanceObserver((list) => { longTasks += list.getEntries().length; });
    lt.observe({ type: 'longtask', buffered: false });
    observers.push(lt);
  } catch (e) { longTasks = -1; }
  try {
    const ev = new PerformanceObserver((list) => {
      list.getEntries().forEach((e) => { if (e.interactionId && e.duration > worstInteraction) worstInteraction = e.duration; });
    });
    ev.observe({ type: 'event', durationThreshold: 16, buffered: false });
    observers.push(ev);
  } catch (e) { worstInteraction = -1; }
  timer = setInterval(paint, 500);
  paint();
}

function paint() {
  if (!hud) return;
  const now = performance.now();
  const lastSec = frames.filter((t) => now - t <= 1000);
  let worst = 0;
  for (let i = 1; i < frames.length; i += 1) worst = Math.max(worst, frames[i] - frames[i - 1]);
  const fps = lastSec.length;
  hud.innerHTML = `<b class="${fps < 50 ? 'is-bad' : ''}">${fps} fps</b><span class="${worst > 34 ? 'is-bad' : ''}">worst ${Math.round(worst)}ms</span><span>LT ${longTasks < 0 ? 'n/a' : longTasks}</span><span class="${worstInteraction > 200 ? 'is-bad' : ''}">INP ${worstInteraction < 0 ? 'n/a' : Math.round(worstInteraction) + 'ms'}</span>`;
}

export function stopHud() {
  cancelAnimationFrame(raf);
  clearInterval(timer);
  observers.forEach((o) => o.disconnect());
  observers = [];
  if (hud) hud.remove();
  hud = null;
}

export function perfSnapshot() {
  const now = performance.now();
  let worst = 0;
  for (let i = 1; i < frames.length; i += 1) worst = Math.max(worst, frames[i] - frames[i - 1]);
  return { fps: frames.filter((t) => now - t <= 1000).length, worst: Math.round(worst), longTasks, inp: Math.round(worstInteraction) };
}
