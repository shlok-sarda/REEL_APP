// Recipes: every cooking reel that became a recipe card, plus cooking reels
// that could become one with a tap.
import { esc, plural, haptic } from '../util.js';
import { icon } from '../icons.js';
import { S, on, emit, reel, cityApps, appLabel, appColor, refreshRecipes } from '../store.js';
import * as api from '../api.js';
import { makeScreen, navBar, toast, errorMessage } from '../ui.js';
import { thumb, wireFades } from '../cards.js';
import { pushScreen } from '../router.js';
import { rise, isReduced, animate, glowBeat } from '../motion.js';
import { openRecipe } from '../recipe.js';
import { openCitySheet } from '../sheets.js';

export function openRecipes() { return pushScreen(createRecipes()); }

function createRecipes() {
  const scr = makeScreen('page recipes');
  const { el: root, scroller } = scr;
  navBar(scr, 'Recipes');
  scroller.innerHTML = `
    <header class="page-head"><p class="eyebrow">Recipes</p><h1 class="display">Cook it, then <em>shop it.</em></h1><p class="sm muted" data-sub></p></header>
    <button class="city-row pressable" type="button" data-city></button>
    <div class="rx-list" data-list></div>
    <section class="rx-cands" data-cands></section>`;
  const $ = (s) => scroller.querySelector(s);
  let first = true;

  function candidates() {
    const have = new Set(S.recipes.map((r) => r.reel_id));
    return S.reels.filter((r) => !have.has(r.id) && (r.sub || '').toLowerCase().includes('recipe'));
  }

  function paint() {
    const apps = cityApps();
    $('[data-sub]').textContent = S.recipes.length ? `${plural(S.recipes.length, 'cooking reel')} turned into ingredient lists you can order in one go.` : 'Cooking reels you save turn into ingredient lists here.';
    $('[data-city]').innerHTML = `<span class="icon-tile is-neutral">${icon('pin')}</span><span><span class="row-title">${S.prefs.city ? `Delivering to ${esc(S.prefs.city)}` : 'Set your city'}</span><span class="row-meta">${apps.map((a) => `<i class="app-dot is-sm" style="--app:${appColor(a)}"></i>${esc(appLabel(a))}`).slice(0, 4).join('')}</span></span>${icon('chev')}`;
    $('[data-list]').innerHTML = S.recipes.length ? S.recipes.map((card) => {
      const r = reel(card.reel_id);
      if (!r) return '';
      const have = (S.prefs.ticks[card.reel_id] || []).length;
      return `<button class="rx-card pressable" type="button" data-rx="${esc(card.reel_id)}">
        ${thumb(r, 'rx-card-img', { full: true })}
        <span class="rx-card-body">
          <span class="eyebrow">${esc(r.creator || 'Recipe')}</span>
          <b class="head">${esc(card.title)}</b>
          <span class="rx-card-meta">${card.total_time ? `<span>${icon('clock')}${esc(card.total_time)}</span>` : ''}<span>${icon('steps')}${plural(card.ingredients.length, 'ingredient')}</span>${have ? `<span class="is-acc">${icon('check')}${have} at home</span>` : ''}</span>
          <span class="rx-card-shop">${icon('cart')}Shop on ${apps.slice(0, 3).map((a) => esc(appLabel(a))).join(', ')}</span>
        </span></button>`;
    }).join('') : `<div class="lesson"><p class="head">No recipes yet.</p><p class="sm">Save a few cooking reels and they become cards with ingredients, steps and buy buttons.</p></div>`;
    $('[data-list]').querySelectorAll('[data-rx]').forEach((b) => b.addEventListener('click', () => openRecipe(b.dataset.rx)));
    const cands = candidates();
    $('[data-cands]').innerHTML = cands.length ? `<div class="sec-head"><h2 class="head">Could be recipes</h2><span class="xs faint">One tap to turn into a card</span></div>
      ${cands.map((r) => `<div class="cand"><span class="cand-th">${thumb(r, 'rc-thumb')}</span><span class="cand-t"><b class="clamp-2">${esc(r.name)}</b><small>${esc(r.creator)}</small></span>
      <button class="btn btn-secondary btn-sm" type="button" data-get="${esc(r.id)}">${icon('sparkle')}Get recipe</button></div>`).join('')}` : '';
    $('[data-cands]').querySelectorAll('[data-get]').forEach((b) => b.addEventListener('click', () => extract(b)));
    wireFades(scroller);
    if (first) { first = false; if (!isReduced()) rise(scroller.querySelectorAll('.rx-card, .cand, .city-row'), { stagger: 50, y: 12 }); }
  }

  async function extract(btn) {
    const rid = btn.dataset.get;
    const row = btn.closest('.cand');
    btn.disabled = true;
    btn.innerHTML = '<span class="btn-spin" style="opacity:1;position:static;margin:0"></span>Reading the reel';
    row.classList.add('is-working');
    try {
      const res = await api.extractRecipe(rid);
      if (res.status !== 'recipe') {
        row.querySelector('small').textContent = 'No step by step recipe in this one.';
        btn.remove();
        row.classList.remove('is-working');
        return;
      }
      haptic(14);
      await refreshRecipes();
      emit('recipes');
      paint();
      const card = scroller.querySelector(`[data-rx="${rid}"]`);
      if (card) { glowBeat(card); card.scrollIntoView({ block: 'center', behavior: isReduced() ? 'auto' : 'smooth' }); }
      toast({ msg: 'Recipe ready', sub: res.card.title, icon: 'sparkle', action: { label: 'Open', fn: () => openRecipe(rid) } });
    } catch (e) {
      btn.disabled = false;
      btn.innerHTML = `${icon('sparkle')}Get recipe`;
      row.classList.remove('is-working');
      toast({ msg: e.status === 403 ? 'Recipes are switched off in the demo library.' : errorMessage(e), tone: 'error' });
    }
  }

  $('[data-city]').addEventListener('click', () => openCitySheet());
  paint();
  // Opening Recipes is the one place new cards may be extracted (as in the
  // classic hub); everywhere else reads cached cards only.
  refreshRecipes({ extract: true }).then(() => paint());
  const offs = [on('recipes', paint), on('city', paint), on('library', paint)];
  return { el: root, scroller, dock: true, destroy: () => offs.forEach((f) => f()) };
}

export { animate };
