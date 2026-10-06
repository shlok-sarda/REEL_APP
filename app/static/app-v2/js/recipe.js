// Recipe sheet: ingredients you can tick off, steps you can follow, and a
// shop flow per delivery app (Blinkit, Zepto, Instamart and friends) that
// walks through each item and keeps track of what is already in the cart.
import { el, esc, plural, haptic } from './util.js';
import { icon } from './icons.js';
import { S, reel, recipeFor, cityApps, appLabel, appColor, savePref, on } from './store.js';
import { openSheet, toast, copyText } from './ui.js';
import { animate, isReduced, glowBeat } from './motion.js';
import { thumb, wireFades } from './cards.js';
import { openCitySheet } from './sheets.js';

function ticksFor(rid) { return new Set(S.prefs.ticks[rid] || []); }
function saveTicks(rid, set) { savePref('ticks', { ...S.prefs.ticks, [rid]: Array.from(set) }); }
function shopFor(rid, app) { return new Set((S.prefs.shop[rid] || {})[app] || []); }
function saveShop(rid, app, set) {
  const cur = S.prefs.shop[rid] || {};
  savePref('shop', { ...S.prefs.shop, [rid]: { ...cur, [app]: Array.from(set) } });
}

export function openRecipe(rid) {
  const card = recipeFor(rid);
  const r = reel(rid);
  if (!card || !r) { toast({ msg: 'No recipe saved for this reel yet.', tone: 'error' }); return null; }
  const body = el('<div class="rx"></div>');
  const s = openSheet({ body, label: card.title, className: 'sheet-recipe', full: true });
  let pane = 'ing';
  const offCity = on('city', () => { if (body.querySelector('.rx-main')) renderMain(); });
  s.onClose = offCity;

  function shoppable() { return (card.shopping || []).filter((x) => x && x.links && !x.pantry); }

  function renderMain(animateIn) {
    const apps = cityApps().filter((a) => shoppable().some((x) => x.links[a]));
    const ticks = ticksFor(rid);
    body.innerHTML = `<div class="rx-main">
      <button class="rx-hero pressable" type="button" data-play aria-label="Watch the reel">${thumb(r, 'rx-hero-img', { full: true, eager: true })}<span class="rx-play">${icon('play')}</span></button>
      <p class="eyebrow rx-ey">Recipe${r.creator ? ' · from ' + esc(r.creator) : ''}</p>
      <h2 class="title rx-title">${esc(card.title)}</h2>
      <div class="rx-meta">
        ${card.total_time ? `<span class="rx-pill">${icon('clock')}${esc(card.total_time)}</span>` : ''}
        ${card.servings ? `<span class="rx-pill">${icon('user')}${esc(card.servings)}</span>` : ''}
        <span class="rx-pill">${icon('steps')}${plural(card.ingredients.length, 'ingredient')}</span>
      </div>
      <section class="rx-shop">
        <div class="rx-shop-head"><div><p class="rx-shop-t">${icon('cart')}Shop the recipe</p><p class="xs faint">${plural(shoppable().length, 'item')} to buy. Salt, oil and other pantry staples are left out.</p></div>
          <button class="chip rx-city" type="button" data-city>${icon('pin')}${esc(S.prefs.city || 'Set city')}</button></div>
        <div class="rx-apps">${apps.map((a) => {
          const n = shoppable().filter((x) => x.links[a]).length;
          const done = shopFor(rid, a).size;
          return `<button class="rx-app pressable" type="button" data-app="${a}"><span class="app-dot" style="--app:${appColor(a)}"></span><span class="rx-app-t"><b>${esc(appLabel(a))}</b><small>${done ? `${done} of ${n} in cart` : `Buy all ${n}`}</small></span>${icon('chev')}</button>`;
        }).join('')}</div>
      </section>
      <div class="seg rx-seg" role="tablist"><button type="button" role="tab" data-pane="ing" class="${pane === 'ing' ? 'is-on' : ''}">Ingredients</button><button type="button" role="tab" data-pane="steps" class="${pane === 'steps' ? 'is-on' : ''}">Steps</button><span class="seg-thumb"></span></div>
      <div class="rx-pane" data-p="ing" ${pane === 'ing' ? '' : 'hidden'}>
        <p class="xs faint rx-hint">Tap what you already have. Tap Buy for anything you need.</p>
        <ul class="rx-ing">${card.ingredients.map((ing, i) => {
          const row = (card.shopping || [])[i];
          return `<li class="ing ${ticks.has(i) ? 'is-have' : ''}" data-i="${i}">
            <button class="ing-check" type="button" aria-pressed="${ticks.has(i)}" aria-label="I have ${esc(ing)}">${icon('check')}</button>
            <span class="ing-name">${esc(ing)}${row && row.brand ? `<small>${esc(row.brand)}</small>` : ''}</span>
            ${row && row.pantry ? '<span class="ing-tag">Pantry</span>' : ''}
            ${row && row.links ? `<button class="chip ing-buy" type="button" data-buy="${i}">${icon('bag')}Buy</button>` : ''}
            ${row && row.links ? `<div class="ing-links" hidden>${cityApps().filter((a) => row.links[a]).map((a) => `<a class="ing-app" href="${esc(row.links[a])}" target="_blank" rel="noopener noreferrer"><span class="app-dot" style="--app:${appColor(a)}"></span>${esc(appLabel(a))}${icon('ext')}</a>`).join('')}</div>` : ''}
          </li>`;
        }).join('')}</ul>
      </div>
      <div class="rx-pane" data-p="steps" ${pane === 'steps' ? '' : 'hidden'}>
        <p class="xs faint rx-hint" data-steps-prog></p>
        <ol class="rx-steps">${card.steps.map((st, i) => `<li class="rx-step" data-s="${i}"><span class="rx-step-n">${i + 1}</span><p>${esc(st)}</p></li>`).join('')}</ol>
      </div>
      ${r.url ? `<a class="btn btn-secondary btn-block rx-watch" href="${esc(r.url)}" target="_blank" rel="noopener">${icon('ig')}Open the reel on Instagram</a>` : ''}
    </div>`;
    wireFades(body);
    wireMain();
    placeThumb(false);
    paintSteps();
    if (animateIn && !isReduced()) animate(body.querySelector('.rx-main'), [{ opacity: 0, transform: 'translateX(-24px)' }, { opacity: 1, transform: 'translateX(0)' }], { duration: 300, easing: 'snap', clear: true });
  }

  function placeThumb(anim) {
    const seg = body.querySelector('.rx-seg');
    if (!seg) return;
    const on = seg.querySelector('.is-on');
    const th = seg.querySelector('.seg-thumb');
    th.style.width = `${on.offsetWidth}px`;
    const x = `translateX(${on.offsetLeft}px)`;
    if (!anim) { th.style.transition = 'none'; th.style.transform = x; th.getBoundingClientRect(); th.style.transition = ''; }
    else th.style.transform = x;
  }

  const stepsDone = new Set();
  function paintSteps() {
    const lis = body.querySelectorAll('.rx-step');
    let current = -1;
    lis.forEach((li, i) => { const d = stepsDone.has(i); li.classList.toggle('is-done', d); if (!d && current < 0) current = i; });
    lis.forEach((li, i) => li.classList.toggle('is-current', i === current));
    const prog = body.querySelector('[data-steps-prog]');
    if (prog) prog.textContent = stepsDone.size ? `${stepsDone.size} of ${lis.length} done. Tap a step when you finish it.` : 'Tap a step when you finish it.';
  }

  function wireMain() {
    body.querySelector('[data-play]').addEventListener('click', async () => {
      await s.close();
      const { openPlayer, playerOpen } = await import('./player.js');
      if (!playerOpen()) openPlayer([rid], 0, null);
    });
    body.querySelector('[data-city]').addEventListener('click', () => openCitySheet());
    body.querySelectorAll('[data-app]').forEach((b) => b.addEventListener('click', () => renderShop(b.dataset.app)));
    body.querySelectorAll('[data-pane]').forEach((b) => b.addEventListener('click', () => {
      if (pane === b.dataset.pane) return;
      pane = b.dataset.pane;
      body.querySelectorAll('[data-pane]').forEach((x) => x.classList.toggle('is-on', x === b));
      placeThumb(true);
      body.querySelectorAll('.rx-pane').forEach((p) => {
        const show = p.dataset.p === pane;
        p.hidden = !show;
        if (show && !isReduced()) animate(p, [{ opacity: 0, transform: `translateX(${pane === 'steps' ? 16 : -16}px)` }, { opacity: 1, transform: 'translateX(0)' }], { duration: 240 });
      });
    }));
    body.querySelectorAll('.ing').forEach((li) => {
      const i = Number(li.dataset.i);
      li.querySelector('.ing-check').addEventListener('click', () => {
        const t = ticksFor(rid);
        if (t.has(i)) t.delete(i); else t.add(i);
        saveTicks(rid, t);
        const on = t.has(i);
        li.classList.toggle('is-have', on);
        li.querySelector('.ing-check').setAttribute('aria-pressed', String(on));
        haptic(6);
        if (on && !isReduced()) animate(li.querySelector('.ing-check'), [{ transform: 'scale(0.7)' }, { transform: 'scale(1)' }], { duration: 380, easing: 'pop' });
      });
      const buy = li.querySelector('[data-buy]');
      if (buy) buy.addEventListener('click', () => {
        const links = li.querySelector('.ing-links');
        const open = links.hidden;
        body.querySelectorAll('.ing-links').forEach((x) => { if (x !== links) x.hidden = true; });
        body.querySelectorAll('.ing-buy').forEach((x) => x.classList.remove('is-on'));
        links.hidden = !open;
        buy.classList.toggle('is-on', open);
        if (open && !isReduced()) animate(links, [{ opacity: 0, transform: 'translateY(-4px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 200, clear: true });
      });
    });
    body.querySelectorAll('.rx-step').forEach((li) => li.addEventListener('click', () => {
      const i = Number(li.dataset.s);
      if (stepsDone.has(i)) stepsDone.delete(i); else stepsDone.add(i);
      haptic(6);
      paintSteps();
    }));
  }

  function renderShop(app) {
    const items = shoppable().filter((x) => x.links[app]);
    const done = shopFor(rid, app);
    body.innerHTML = `<div class="shop">
      <div class="shop-head">
        <button class="icon-btn is-filled" type="button" data-back aria-label="Back to recipe">${icon('back')}</button>
        <span class="app-dot is-lg" style="--app:${appColor(app)}"></span>
        <div class="shop-title"><b>${esc(appLabel(app))}</b><small>${esc(card.title)}</small></div>
      </div>
      <div class="shop-progress"><div class="shop-bar"><i></i></div><p class="sm" data-prog></p></div>
      <p class="sm muted shop-how">Tap an item. ${esc(appLabel(app))} opens with it searched, add it to your cart, then come back here. We tick it off for you.</p>
      <ul class="shop-list">${items.map((x, i) => `<li><a class="shop-item pressable ${done.has(i) ? 'is-done' : ''}" data-i="${i}" href="${esc(x.links[app])}" target="_blank" rel="noopener noreferrer">
        <span class="shop-tick">${icon('check')}</span>
        <span class="shop-name"><b>${esc(x.branded_query || x.query)}</b><small>${esc(x.display)}</small></span>
        <span class="shop-open">Open${icon('ext')}</span></a></li>`).join('')}</ul>
      ${app === 'instamart' ? `<button class="btn btn-secondary btn-block shop-copy" type="button" data-copy>${icon('copy')}Copy the whole list</button><p class="xs faint shop-copy-hint">In Instamart, open Shopping List, choose Write it, and paste. It fills the cart in one go.</p>` : ''}
      <button class="btn btn-primary btn-block shop-done" type="button" data-done>Done shopping</button>
    </div>`;
    if (!isReduced()) animate(body.querySelector('.shop'), [{ opacity: 0, transform: 'translateX(28px)' }, { opacity: 1, transform: 'translateX(0)' }], { duration: 320, easing: 'snap', clear: true });
    const paintProg = () => {
      const n = shopFor(rid, app).size;
      body.querySelector('[data-prog]').innerHTML = n >= items.length ? `<b>All ${items.length} in your cart.</b> Time to cook.` : `<b>${n} of ${items.length}</b> added`;
      body.querySelector('.shop-bar i').style.transform = `scaleX(${items.length ? n / items.length : 0})`;
    };
    paintProg();
    body.querySelector('[data-back]').addEventListener('click', () => renderMain(true));
    body.querySelectorAll('.shop-item').forEach((a) => a.addEventListener('click', () => {
      const set = shopFor(rid, app);
      set.add(Number(a.dataset.i));
      saveShop(rid, app, set);
      a.classList.add('is-done');
      haptic(8);
      if (!isReduced()) animate(a.querySelector('.shop-tick'), [{ transform: 'scale(0.6)' }, { transform: 'scale(1)' }], { duration: 420, easing: 'pop' });
      paintProg();
      if (set.size >= items.length) glowBeat(body.querySelector('.shop-progress'));
    }));
    const cp = body.querySelector('[data-copy]');
    if (cp) cp.addEventListener('click', () => {
      const text = items.map((x) => x.branded_query || x.query || x.display).join(String.fromCharCode(10));
      copyText(text).then((ok) => {
        if (!ok) { toast({ msg: 'Could not copy the list', tone: 'error' }); return; }
        cp.innerHTML = `${icon('check')}Copied. Paste it in Instamart`;
        cp.classList.add('is-done');
      });
    });
    body.querySelector('[data-done]').addEventListener('click', () => {
      const n = shopFor(rid, app).size;
      renderMain(true);
      if (n) toast({ msg: n >= items.length ? 'Everything is in your cart' : `${n} of ${items.length} items in your cart`, icon: 'cart' });
    });
  }

  renderMain(false);
  return s;
}
