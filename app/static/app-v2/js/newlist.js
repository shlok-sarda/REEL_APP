// New Smart List: iOS card modal. The screen behind recedes, the name and
// rule are drafted (typed in), matching reels can be ticked on and off, and
// the matches update live as the rule is edited.
import { el, esc, debounce, clamp, haptic, sleep } from './util.js';
import { icon } from './icons.js';
import { S, reel, localSearch, emojiFor, savePref, listFromApi, listById, emit } from './store.js';
import * as api from './api.js';
import { LIVE } from './api.js';
import { pushLayer, closeLayer, isOpen, back } from './router.js';
import { animate, moveTo, freeze, isReduced } from './motion.js';
import { toast, apiToast, confirmSheet, btnLoading, errorMessage } from './ui.js';
import { wireFades } from './cards.js';

const EMOJIS = ['🍳', '🍜', '💪', '✈️', '🌴', '🎬', '🛍️', '🧴', '🛠️', '📚', '🎵', '💼', '🌦️', '🏎️', '🎨', '✨'];

export function openNewList(seed = {}) {
  const editing = seed.edit ? listById(seed.edit) : null;
  const st = {
    name: editing ? editing.name : '',
    rule: editing ? editing.description : '',
    emoji: editing ? editing.emoji : '',
    auto: true,
    matches: [],
    selected: new Set(),
    seeded: !!(seed.reelIds && seed.reelIds.length),
    dirty: false,
    drafting: false,
    creating: false,
  };
  if (seed.reelIds) { seed.reelIds.forEach((id) => { if (reel(id) && !st.matches.includes(id)) st.matches.push(id); }); st.matches.forEach((id) => st.selected.add(id)); }
  if (seed.reelId && reel(seed.reelId)) { st.matches.unshift(seed.reelId); st.selected.add(seed.reelId); st.seeded = true; }

  const scrim = el('<div class="nl-scrim" aria-hidden="true"></div>');
  const m = el(`<section class="nl-modal" role="dialog" aria-modal="true" aria-label="${editing ? 'Edit list' : 'New smart list'}">
    <header class="nl-nav" data-drag>
      <button class="link-btn nl-cancel" type="button" data-cancel>Cancel</button>
      <b class="nl-title">${editing ? 'Edit List' : 'New Smart List'}</b>
      <button class="link-btn nl-create" type="button" data-create disabled>${editing ? 'Save' : 'Create'}</button>
    </header>
    <div class="nl-body">
      <p class="nl-error" role="alert" hidden></p>
      <button class="nl-emoji pressable" type="button" data-emoji aria-label="Choose an icon"><span></span></button>
      <div class="nl-emoji-row" data-emojis hidden>${EMOJIS.map((e) => `<button type="button" class="nl-e pressable" data-e="${e}">${e}</button>`).join('')}</div>
      <div class="nl-name-wrap">
        <input class="nl-name" type="text" maxlength="60" placeholder="List name" aria-label="List name" autocomplete="off" />
        <span class="nl-drafting" hidden><span class="sk"></span>${icon('sparkle')}Drafting from your reels</span>
      </div>
      <p class="nl-dupe" data-dupe hidden></p>
      <p class="nl-cap">Include reels about</p>
      <div class="nl-group">
        <label class="nl-row nl-rule"><textarea rows="2" placeholder="Describe what belongs. For example: gym tutorials for arms and shoulders" aria-label="What belongs in this list"></textarea></label>
        ${editing || LIVE ? '' : `<div class="nl-row"><span>Add new matches automatically</span><span class="switch"><input type="checkbox" data-auto checked aria-label="Add new matches automatically"><span class="track"></span><span class="knob"></span></span></div>`}
      </div>
      <p class="nl-help" data-help>New reels that fit this description join on their own.</p>
      ${editing ? '' : `<p class="nl-cap" data-cap>Matching now</p>
      <div class="nl-strip" data-strip></div>`}
      <p class="nl-foot">ClipNest checks every new reel you save against this list and files the ones that fit.</p>
    </div>
  </section>`);
  const overlays = document.getElementById('overlays');
  overlays.appendChild(scrim);
  overlays.appendChild(m);
  const stage = document.getElementById('stage');
  const recessTargets = [stage].concat(Array.from(document.querySelectorAll('#overlays .player, #overlays .search-layer')));
  recess(recessTargets, true);
  stage.setAttribute('inert', '');
  requestAnimationFrame(() => scrim.classList.add('is-on'));
  if (isReduced()) animate(m, [{ opacity: 0 }, { opacity: 1 }], { duration: 160 });
  else { m.style.transform = 'translateY(100%)'; moveTo(m, 'translateY(0%)', { duration: 440, easing: 'snap' }); }

  const nameEl = m.querySelector('.nl-name');
  const ruleEl = m.querySelector('textarea');
  const createBtn = m.querySelector('[data-create]');
  const errEl = m.querySelector('.nl-error');

  let closed = false;
  const layer = pushLayer({
    kind: 'overlay',
    hidesDock: true,
    close: ({ instant }) => {
      if (closed) return;
      closed = true;
      recess(recessTargets, false, instant);
      stage.removeAttribute('inert');
      scrim.classList.remove('is-on');
      const done = () => { m.remove(); scrim.remove(); };
      if (instant) { done(); return; }
      if (isReduced()) { animate(m, [{ opacity: 1 }, { opacity: 0 }], { duration: 140 }).then(done); return; }
      moveTo(m, 'translateY(105%)', { duration: 280, easing: 'in', force: true }).then(done);
    },
  });
  const close = () => (isOpen(layer) ? closeLayer(layer) : Promise.resolve());

  /* ---------- rendering ---------- */
  function setEmoji(e) {
    st.emoji = e;
    m.querySelector('[data-emoji] span').textContent = e || '✨';
  }
  function checkDupe() {
    const n = st.name.trim().toLowerCase();
    const other = S.lists.find((l) => l.name.trim().toLowerCase() === n && (!editing || l.id !== editing.id));
    const box = m.querySelector('[data-dupe]');
    box.hidden = !other;
    if (other) box.innerHTML = `You already have a list called this. <button class="link-btn" type="button" data-open-dupe>Open it</button>`;
    const b = box.querySelector('[data-open-dupe]');
    if (b) b.addEventListener('click', async () => {
      await close();
      if (seed.source === 'search') { const s = await import('./search.js'); await s.closeSearch(); }
      const ld = await import('./screens/listDetail.js');
      ld.openListDetail(other.id);
    });
  }
  function refreshValidity() {
    checkDupe();
    const ok = st.name.trim() && st.rule.trim() && (editing || st.selected.size > 0) && !st.creating && !st.drafting;
    createBtn.disabled = !ok;
  }
  function renderStrip(newIds = []) {
    const strip = m.querySelector('[data-strip]');
    if (!strip) return;
    const cap = m.querySelector('[data-cap]');
    cap.textContent = st.matches.length ? `Matching now · ${st.selected.size} of ${st.matches.length} selected` : 'Matching now';
    if (!st.matches.length) {
      strip.innerHTML = `<p class="nl-strip-empty">${st.rule.trim() ? 'Nothing matches yet. New reels that fit will still land here.' : 'Describe it above and matching reels appear here.'}</p>`;
      return;
    }
    const existing = new Map();
    strip.querySelectorAll('[data-id]').forEach((n) => existing.set(n.dataset.id, n));
    if (strip.querySelector('.nl-strip-empty')) strip.innerHTML = '';
    let prev = null;
    st.matches.forEach((id) => {
      const r = reel(id);
      let n = existing.get(id);
      if (!n) {
        n = el(`<button type="button" class="nl-pick pressable" data-id="${esc(id)}" aria-pressed="false">
          <span class="nl-pick-th" style="--c:${r.color}">${r.lqip ? `<img class="lq" src="${r.lqip}" alt="">` : ''}<img class="full" src="${esc(r.thumb)}" alt="" data-fade decoding="async"><span class="sel-ring">${icon('check')}</span></span>
          <span class="nl-pick-t clamp-2">${esc(r.name)}</span></button>`);
        wireFades(n);
        n.addEventListener('click', () => {
          if (st.selected.has(id)) st.selected.delete(id); else st.selected.add(id);
          st.dirty = true;
          haptic(6);
          paintPick(n, id);
          renderStrip();
          refreshValidity();
        });
        if (newIds.includes(id) && !isReduced()) animate(n, [{ opacity: 0, transform: 'scale(0.9)' }, { opacity: 1, transform: 'scale(1)' }], { duration: 300, easing: 'snap', clear: true });
      }
      paintPick(n, id);
      existing.delete(id);
      const want = prev ? prev.nextElementSibling : strip.firstElementChild;
      if (n !== want) strip.insertBefore(n, prev ? prev.nextSibling : strip.firstChild);
      prev = n;
    });
    existing.forEach((n) => n.remove());
  }
  function paintPick(n, id) {
    const on = st.selected.has(id);
    n.classList.toggle('is-selected', on);
    n.setAttribute('aria-pressed', on ? 'true' : 'false');
  }

  /* ---------- live matching from the rule ---------- */
  const rematch = debounce(() => {
    if (editing) return;
    const q = st.rule.trim() || st.name.trim();
    if (!q) { if (!st.seeded) { st.matches = []; st.selected.clear(); } renderStrip(); refreshValidity(); return; }
    const hits = localSearch(q, 12).map((h) => h.id);
    const before = new Set(st.matches);
    const keep = st.matches.filter((id) => st.selected.has(id));
    const next = keep.concat(hits.filter((id) => !keep.includes(id)));
    const added = next.filter((id) => !before.has(id));
    added.forEach((id) => { if (!st.seeded) st.selected.add(id); });
    st.matches = next.slice(0, Math.max(14, keep.length));
    st.selected.forEach((id) => { if (!st.matches.includes(id)) st.selected.delete(id); });
    renderStrip(added);
    refreshValidity();
  }, 260);

  nameEl.addEventListener('input', () => { st.name = nameEl.value; st.dirty = true; if (!st.emojiPicked) setEmoji(emojiFor(st.name, st.rule) || st.emoji); refreshValidity(); if (!st.rule.trim()) rematch(); });
  ruleEl.addEventListener('input', () => { st.rule = ruleEl.value; st.dirty = true; autoGrow(); if (!st.emojiPicked) setEmoji(emojiFor(st.name, st.rule) || st.emoji); rematch(); refreshValidity(); });
  function autoGrow() { ruleEl.style.height = 'auto'; ruleEl.style.height = Math.min(160, ruleEl.scrollHeight) + 'px'; }
  const auto = m.querySelector('[data-auto]');
  if (auto) auto.addEventListener('change', () => {
    st.auto = auto.checked;
    m.querySelector('[data-help]').textContent = st.auto ? 'New reels that fit this description join on their own.' : 'New reels that fit wait in this list for you to review first.';
  });
  m.querySelector('[data-emoji]').addEventListener('click', () => {
    const row = m.querySelector('[data-emojis]');
    row.hidden = !row.hidden;
    if (!row.hidden && !isReduced()) animate(row, [{ opacity: 0, transform: 'translateY(-6px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 220, clear: true });
  });
  m.querySelectorAll('[data-e]').forEach((b) => b.addEventListener('click', () => {
    st.emojiPicked = true; setEmoji(b.dataset.e); st.dirty = true;
    m.querySelector('[data-emojis]').hidden = true;
    if (!isReduced()) animate(m.querySelector('[data-emoji]'), [{ transform: 'scale(0.8)' }, { transform: 'scale(1)' }], { duration: 420, easing: 'pop' });
  }));

  /* ---------- cancel / drag to dismiss (asks before throwing work away) ---------- */
  async function requestClose() {
    if (st.dirty && !st.creating) {
      const ok = await confirmSheet({ title: editing ? 'Discard your changes?' : 'Discard this list?', body: 'What you typed will be lost.', confirm: 'Discard', danger: true, cancel: 'Keep editing' });
      if (!ok) return;
    }
    close();
  }
  m.querySelector('[data-cancel]').addEventListener('click', requestClose);
  scrim.addEventListener('click', requestClose);
  let drag = null;
  const nav = m.querySelector('[data-drag]');
  nav.addEventListener('pointerdown', (e) => { if (e.target.closest('button')) return; drag = { y: e.clientY, t: performance.now(), v: 0, ly: e.clientY, lt: performance.now() }; freeze(m); nav.setPointerCapture(e.pointerId); });
  nav.addEventListener('pointermove', (e) => {
    if (!drag) return;
    const dy = Math.max(0, e.clientY - drag.y);
    const now = performance.now();
    drag.v = (e.clientY - drag.ly) / Math.max(1, now - drag.lt); drag.ly = e.clientY; drag.lt = now;
    m.style.transform = `translateY(${dy}px)`;
  });
  const endDrag = (e) => {
    if (!drag) return;
    const dy = e.clientY - drag.y; const v = drag.v; drag = null;
    if (dy > 140 || v > 0.7) {
      if (st.dirty) { moveTo(m, 'translateY(0px)', { duration: 300, easing: 'snap', force: true }); requestClose(); }
      else close();
      return;
    }
    moveTo(m, 'translateY(0px)', { duration: 300, easing: 'snap', force: true });
  };
  nav.addEventListener('pointerup', endDrag);
  nav.addEventListener('pointercancel', endDrag);

  /* ---------- create / save ---------- */
  createBtn.addEventListener('click', async () => {
    if (createBtn.disabled) return;
    st.creating = true;
    refreshValidity();
    errEl.hidden = true;
    createBtn.classList.add('is-busy');
    createBtn.textContent = editing ? 'Saving' : 'Creating';
    const slow = setTimeout(() => {
      if (!st.creating) return;
      errEl.classList.add('is-note');
      errEl.textContent = editing ? 'Saving your changes.' : 'Filing every matching reel into your new list. This can take a few seconds.';
      errEl.hidden = false;
    }, 1500);
    try {
      if (editing) {
        await api.updateFolder(editing.id, { name: st.name.trim(), description: st.rule.trim() });
        editing.name = st.name.trim();
        editing.description = st.rule.trim();
        if (st.emoji) { editing.emoji = st.emoji; savePref('listEmoji', { ...S.prefs.listEmoji, [editing.id]: st.emoji }); }
        emit('lists');
        await close();
        toast({ msg: 'List updated' });
        return;
      }
      const ids = st.matches.filter((id) => st.selected.has(id));
      const f = await api.createFolder({ name: st.name.trim(), description: st.rule.trim(), query: seed.query || '', reel_ids: ids });
      const detail = await api.getFolder(f.id);
      const list = listFromApi(f, detail);
      if (st.emoji) { list.emoji = st.emoji; savePref('listEmoji', { ...S.prefs.listEmoji, [f.id]: st.emoji }); }
      S.lists.unshift(list);
      emit('lists');
      haptic(14);
      await close();
      if (seed.source === 'search') { const s = await import('./search.js'); await s.closeSearch(); }
      if (seed.source === 'player') { const p = await import('./player.js'); p.closePlayer(); await sleep(260); }
      const ld = await import('./screens/listDetail.js');
      ld.openListDetail(list.id, { justCreated: true });
    } catch (e) {
      clearTimeout(slow);
      errEl.classList.remove('is-note');
      st.creating = false;
      createBtn.classList.remove('is-busy');
      createBtn.textContent = editing ? 'Save' : 'Create';
      errEl.textContent = errorMessage(e);
      errEl.hidden = false;
      if (!isReduced()) animate(errEl, [{ opacity: 0, transform: 'translateY(-4px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 200, clear: true });
      refreshValidity();
    } finally {
      clearTimeout(slow);
    }
  });

  /* ---------- initial fill ---------- */
  if (editing) {
    nameEl.value = st.name; ruleEl.value = st.rule; setEmoji(st.emoji || emojiFor(st.name, st.rule)); autoGrow();
    refreshValidity();
  } else {
    setEmoji(emojiFor(seed.query || '') || '');
    renderStrip(st.matches);
    if (st.seeded) draft(); else setTimeout(() => { try { nameEl.focus({ preventScroll: true }); } catch (e) { /* ignore */ } }, 420);
  }

  async function draft() {
    st.drafting = true;
    refreshValidity();
    const d = m.querySelector('.nl-drafting');
    d.hidden = false;
    nameEl.classList.add('is-drafting');
    const r0 = reel(st.matches[0]);
    const query = seed.query || (r0 ? (r0.sub || r0.category || r0.name) : '');
    let res = null;
    try { res = await api.suggestFolder({ query, reel_ids: st.matches.filter((id) => st.selected.has(id)) }); }
    catch (e) {
      res = { name: query ? query.charAt(0).toUpperCase() + query.slice(1) : '', description: query ? `Reels about ${query}.` : '' };
      // A link session gets no drafted name (403) but can still save the
      // list, so the starter text needs no apology.
      if (e.status !== 403) {
        errEl.textContent = 'Could not draft a name just now, so we added starter text. Edit it freely.';
        errEl.hidden = false;
      }
    }
    if (closed) return;
    d.hidden = true;
    nameEl.classList.remove('is-drafting');
    await typeInto(nameEl, res.name, (v) => { st.name = v; });
    if (!st.emojiPicked) setEmoji(emojiFor(res.name, res.description) || st.emoji);
    await typeInto(ruleEl, res.description, (v) => { st.rule = v; autoGrow(); }, 8);
    st.drafting = false;
    rematch();
    refreshValidity();
  }

  async function typeInto(input, text, onStep, ms = 18) {
    if (isReduced()) { input.value = text; onStep(text); return; }
    for (let i = 1; i <= text.length; i += 1) {
      if (closed) return;
      input.value = text.slice(0, i);
      onStep(input.value);
      await sleep(ms);
    }
  }
  return { close };
}

function recess(nodes, on, instant) {
  nodes.forEach((n) => {
    if (!n) return;
    if (on) {
      n.classList.add('is-recessed');
      if (isReduced()) { n.style.transform = 'scale(0.94)'; return; }
      n.style.transform = 'translateY(0) scale(1)';
      moveTo(n, 'translateY(10px) scale(0.92)', { duration: 440, easing: 'snap' });
    } else {
      if (instant || isReduced()) { freeze(n); n.style.transform = ''; n.classList.remove('is-recessed'); return; }
      moveTo(n, 'translateY(0px) scale(1)', { duration: 300, easing: 'out' }).then(() => { n.style.transform = ''; n.classList.remove('is-recessed'); });
    }
  });
}

export { clamp, apiToast, btnLoading, back };
