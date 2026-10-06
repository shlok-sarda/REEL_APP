// Home: a dashboard of widgets. Each widget only appears when the person has
// that kind of data (places, recipes, lists), so new widgets slot in later
// without redesigning the screen.
import { el, esc, plural, greetingWord, sleep, haptic, savedLabel } from '../util.js';
import { icon } from '../icons.js';
import { S, on, emit, displayName, isGuest, cityApps, appLabel, savePref, reelsFor, localSearch, refresh, listFromApi } from '../store.js';
import * as api from '../api.js';
import { makeScreen, onLongPress, toast, apiToast, btnLoading, openSheet, copyText, errorMessage } from '../ui.js';
import { listCover, wireFades, coverMode, skeletonCards } from '../cards.js';
import { animate, rise, countUp, glowBeat, isReduced, slamWords } from '../motion.js';
import { pushScreen } from '../router.js';
import { openPlayer, warmPlayer } from '../player.js';
import { openSearch } from '../search.js';
import { openNewList } from '../newlist.js';
import { openActivity } from '../sheets.js';

let devOpener = null;
export function setDevOpener(fn) { devOpener = fn; }

export function createHome() {
  const { el: root, scroller } = makeScreen('home');
  scroller.innerHTML = `
    <div class="ptr" aria-hidden="true"><span class="spinner-mark"></span></div>
    <header class="home-head">
      <button class="brand pressable" type="button" data-brand aria-label="ClipNest"><img src="assets/icon-192.png" alt="" width="36" height="36"></button>
      <div class="home-hello"><p class="eyebrow" data-greet></p><p class="home-name" data-name></p></div>
      <div class="home-head-end"><span data-status></span><button class="avatar pressable" type="button" data-you aria-label="You"></button></div>
    </header>
    <div class="home-cards" data-cards></div>
    <div class="bento" data-bento></div>
    <p class="home-foot xs faint" data-foot></p>`;
  const $ = (s) => scroller.querySelector(s);
  const bento = $('[data-bento]');
  const inst = { el: root, scroller, dock: true };
  let typing = null;
  let visible = true;

  /* ---------- header ---------- */
  function paintHead() {
    $('[data-greet]').textContent = greetingWord();
    const name = displayName();
    $('[data-name]').textContent = name || 'Your nest';
    if (name) $('[data-you]').textContent = name.charAt(0).toUpperCase(); else $('[data-you]').innerHTML = icon('user');
    const st = $('[data-status]');
    const n = S.processing.length;
    const was = st.querySelector('.pill-status');
    if (n) {
      const html = `<button class="pill-status" type="button" data-act><span class="pulse-dot"></span>Sorting ${n}</button>`;
      if (!was || was.textContent.trim() !== `Sorting ${n}`) {
        st.innerHTML = html;
        st.querySelector('[data-act]').addEventListener('click', openActivity);
        if (!was && !isReduced()) animate(st.firstElementChild, [{ opacity: 0, transform: 'scale(0.8)' }, { opacity: 1, transform: 'scale(1)' }], { duration: 360, easing: 'pop', clear: true });
      }
    } else if (was) {
      animate(was, [{ opacity: 1 }, { opacity: 0 }], { duration: 160 }).then(() => { st.innerHTML = ''; });
    }
  }
  onLongPress($('[data-brand]'), () => devOpener && devOpener());
  $('[data-brand]').addEventListener('click', () => { scroller.scrollTo({ top: 0, behavior: isReduced() ? 'auto' : 'smooth' }); });
  $('[data-you]').addEventListener('click', () => import('./you.js').then((m) => m.openYou()));

  /* ---------- top cards: guest claim, Instagram, name, failed ---------- */
  function paintCards() {
    const box = $('[data-cards]');
    const parts = [];
    const sess = S.session || {};
    if (isGuest()) {
      const stage = sess.claim_stage || 'signin';
      if (stage === 'locked' || !S.prefs.claimSkip[stage]) parts.push(['claim-' + stage, claimCard(stage)]);
    }
    const u = sess.user || {};
    if (S.loaded && !u.preferred_name && !S.prefs.nameSkip && !isGuest()) parts.push(['name', nameCard()]);
    if (S.failed.length) parts.push(['failed', `<section class="hcard hcard-failed" data-k="failed"><span class="icon-tile is-danger">${icon('alert')}</span><div><p class="hcard-t">${plural(S.failed.length, 'reel')} could not be sorted</p><p class="xs muted">Usually a download hiccup. Trying again almost always works.</p></div><button class="btn btn-secondary btn-sm" type="button" data-retry-all>Try again</button></section>`]);
    const keys = parts.map((p) => p[0]).join('|');
    if (box.dataset.keys === keys) return;
    box.dataset.keys = keys;
    box.innerHTML = parts.map((p) => p[1]).join('');
    wireCards(box);
    if (!isReduced()) rise(box.children, { y: 10, duration: 360 });
  }

  function claimCard(stage) {
    const counts = { home: 5, signin: 17, locked: 20 };
    const n = Math.min(S.reels.length, counts[stage] || S.reels.length);
    const inInsta = !!(S.dev && S.dev.inInsta);
    const browser = /Android/i.test(navigator.userAgent) ? 'Chrome' : 'Safari';
    let title = ''; let body = ''; let action = '';
    if (stage === 'home') {
      title = 'Add ClipNest to your home screen';
      body = inInsta ? 'One tap back to your library, instead of digging through DMs for the link.' : `One tap back to your library. In ${browser}, tap Share, then Add to Home Screen.`;
      action = inInsta ? `<a class="btn btn-primary btn-sm" href="#" data-escape>Open in ${browser}</a>` : '';
    } else {
      title = stage === 'locked' ? 'You have saved 20 reels' : 'Keep your library safe';
      body = stage === 'locked' ? 'Sign in with Google to keep saving. Everything stays where it is, and anything you sent since saves straight away.' : 'Sign in with Google so this library is yours for good. Everything you saved stays right here.';
      action = inInsta ? `<a class="btn btn-primary btn-sm" href="#" data-escape>Open in ${browser} to sign in</a>` : `<button class="btn btn-primary btn-sm" type="button" data-signin>${icon('user')}Continue with Google</button>`;
    }
    const meter = stage !== 'home' ? `<div class="meter"><div class="meter-bar"><i style="transform:scaleX(${Math.min(1, n / 20)})"></i></div><span class="xs faint">${n} of 20 free saves</span></div>` : '';
    return `<section class="hcard hcard-claim ${stage === 'locked' ? 'is-locked' : ''}" data-k="claim">
      <p class="hcard-t">${esc(title)}</p><p class="sm muted">${esc(body)}</p>${meter}
      <div class="hcard-actions">${action}${stage !== 'locked' ? '<button class="link-btn is-muted" type="button" data-skip>Not now</button>' : ''}</div>
      ${inInsta ? '<p class="xs faint hcard-hint">Nothing happened? Tap the three dots at the top, then Open in external browser.</p>' : ''}
    </section>`;
  }

  function nameCard() {
    return `<section class="hcard hcard-name" data-k="name"><p class="hcard-t">What should we call you?</p><p class="xs muted">Just your first name is fine.</p>
      <form class="hcard-form" data-nameform><input class="field" name="n" type="text" maxlength="60" placeholder="Your name" autocomplete="given-name" aria-label="Your name" /><button class="btn btn-primary btn-sm" type="submit">Save</button></form>
      <button class="link-btn is-muted" type="button" data-nameskip>Skip for now</button></section>`;
  }

  function wireCards(box) {
    const q = (s) => box.querySelector(s);
    if (q('[data-skip]')) q('[data-skip]').addEventListener('click', () => {
      const stage = (S.session && S.session.claim_stage) || 'signin';
      savePref('claimSkip', { ...S.prefs.claimSkip, [stage]: true });
      collapse(q('[data-k="claim"]'), paintCards);
    });
    if (q('[data-signin]')) q('[data-signin]').addEventListener('click', () => openSignIn());
    if (q('[data-escape]')) q('[data-escape]').addEventListener('click', (e) => { e.preventDefault(); toast({ msg: 'This opens the same library in your browser, signed in.', icon: 'ext' }); });
    if (q('[data-nameform]')) q('[data-nameform]').addEventListener('submit', async (e) => {
      e.preventDefault();
      const input = e.currentTarget.querySelector('input');
      const name = input.value.trim();
      if (!name) { input.focus(); return; }
      const btn = e.currentTarget.querySelector('button');
      btnLoading(btn, true);
      const prev = S.session.user.preferred_name;
      S.session.user.preferred_name = name;
      try {
        await api.saveProfileName(name);
        paintHead();
        collapse(q('[data-k="name"]'), paintCards);
        haptic(10);
        toast({ msg: `Nice to meet you, ${name}` });
      } catch (err) {
        S.session.user.preferred_name = prev;
        btnLoading(btn, false);
        apiToast(err);
      }
    });
    if (q('[data-nameskip]')) q('[data-nameskip]').addEventListener('click', () => { savePref('nameSkip', true); collapse(q('[data-k="name"]'), paintCards); });
    if (q('[data-retry-all]')) q('[data-retry-all]').addEventListener('click', async (e) => {
      btnLoading(e.currentTarget, true);
      try { const res = await api.retryFailed(); await refresh(); toast({ msg: `${plural(res.requeued_count, 'reel')} back in the queue` }); }
      catch (err) { btnLoading(e.currentTarget, false); apiToast(err); }
    });
  }

  function collapse(node, after) {
    if (!node) { after(); return; }
    if (isReduced()) { node.remove(); after(); return; }
    animate(node, [{ opacity: 1, transform: 'scale(1)' }, { opacity: 0, transform: 'scale(0.96)' }], { duration: 200, easing: 'in' }).then(() => { node.remove(); after(); });
  }

  /* ---------- widgets ---------- */
  function widgets() {
    const out = [];
    const reels = S.reels;
    if (S.processing.length) out.push(wProcessing());
    out.push(wLibrary());
    // Until places and recipes arrive, hold their exact boxes so nothing
    // below jumps when they land.
    const placesPending = !S.extrasLoaded && reels.length;
    if (reels.length) out.push(wLatest(!S.places.length && !placesPending));
    if (S.places.length) out.push(wPlaces());
    else if (placesPending) out.push({ key: 'places', cls: 'w-places w-pending', tag: 'div', html: '<span class="w-map" aria-hidden="true"></span><span class="w-foot"><span class="sk sk-line" style="width:60%"></span><span class="sk sk-line is-short"></span></span>' });
    if (S.recipesEnabled && S.extrasLoaded) out.push(wRecipes());
    else if (S.recipesEnabled) out.push({ key: 'recipes', cls: 'w-recipes w-pending', tag: 'div', html: '<span class="w-foot"><span class="sk sk-line" style="width:60%"></span><span class="sk sk-line is-short"></span></span>' });
    out.push(wAsk(!(S.recipesEnabled)));
    out.push(wLists());
    if (reels.length) out.push(wRecent());
    if (S.collections.length) out.push(wShelves());
    return out;
  }

  function wProcessing() {
    const steps = ['Waiting in line', 'Downloading', 'Watching the video', 'Sorting it'];
    return { key: 'proc', cls: 'w-proc w-wide', tag: 'button', html: `
      <span class="w-proc-ico"><span class="pulse-dot"></span></span>
      <span class="w-proc-text"><b>Sorting ${plural(S.processing.length, 'new reel')}</b><small>${S.processing.map((p) => steps[p.status === 'queued' ? 0 : p.step]).filter(Boolean)[0] || 'Starting'}. They land in your library when ready.</small></span>
      <span class="w-proc-bars">${S.processing.slice(0, 4).map((p) => `<i><b style="transform:scaleX(${p.status === 'queued' ? 0.06 : Math.min(1, p.step / 3)})"></b></i>`).join('')}${S.processing.length > 4 ? `<em>+${S.processing.length - 4}</em>` : ''}</span>` };
  }

  function wLibrary() {
    const n = S.reels.length;
    const shelves = S.collections.length;
    const fanReels = S.reels.slice(0, 3);
    return { key: 'lib', cls: 'w-library w-tall', tag: 'button', label: `Your library, ${n} reels`, html: `
      <span class="w-glow" aria-hidden="true"></span>
      <span class="eyebrow">Your library</span>
      <span class="w-count" data-count>${n}</span>
      <span class="w-cap">${n === 1 ? 'reel' : 'reels'}${shelves ? `, sorted onto <em>${plural(shelves, 'shelf', 'shelves')}</em>` : ''}</span>
      <span class="w-fan">${fanReels.map((r) => `<i style="--c:${r.color}"><img src="${esc(r.thumb)}" alt="" decoding="async"></i>`).join('')}</span>
      <span class="w-go">${icon('chev')}</span>` };
  }

  function wLatest(tall) {
    const r = S.reels[0];
    return { key: 'latest:' + r.id, cls: `w-latest ${tall ? 'w-tall' : ''}`, tag: 'button', rid: r.id, label: `Play latest, ${r.name}`, html: `
      <span class="w-latest-media" style="--c:${r.color}">${r.lqip ? `<img class="lq" src="${r.lqip}" alt="">` : ''}<img class="full" src="${esc(r.thumb)}" alt="" data-fade decoding="async"></span>
      <span class="w-latest-text"><span class="eyebrow">Latest</span><b class="clamp-2">${esc(r.name)}</b></span>
      <span class="w-latest-play">${icon('play')}</span>` };
  }

  function wPlaces() {
    const ps = S.places;
    const lats = ps.map((p) => p.lat); const lngs = ps.map((p) => p.lng);
    const minLa = Math.min(...lats); const maxLa = Math.max(...lats); const minLn = Math.min(...lngs); const maxLn = Math.max(...lngs);
    const spanLa = Math.max(8, maxLa - minLa); const spanLn = Math.max(8, maxLn - minLn);
    const dots = ps.map((p, i) => {
      const x = ps.length === 1 ? 50 : 22 + ((p.lng - minLn) / spanLn) * 56;
      const y = ps.length === 1 ? 34 : 50 - ((p.lat - minLa) / spanLa) * 32;
      return `<i class="w-dot" style="left:${x.toFixed(1)}%;top:${y.toFixed(1)}%;--d:${i * 400}ms"><b>${p.reels.length}</b></i>`;
    }).join('');
    const reelCount = new Set(ps.flatMap((p) => p.reels)).size;
    return { key: 'places', cls: 'w-places', tag: 'button', label: `${ps.length} places`, html: `
      <span class="w-map" aria-hidden="true">${dots}</span>
      <span class="w-foot"><b>${plural(ps.length, 'place')}</b><small>${esc(ps.slice(0, 2).map((p) => p.place).join(', '))}${reelCount ? ` · ${plural(reelCount, 'reel')}` : ''}</small></span>` };
  }

  function wRecipes() {
    const rs = reelsFor(S.recipes.map((x) => x.reel_id)).slice(0, 3);
    const app = appLabel(cityApps()[0] || 'blinkit');
    return { key: 'recipes:' + S.recipes.length, cls: 'w-recipes', tag: 'button', label: `${S.recipes.length} recipes`, html: `
      <span class="w-rec-top">${rs.length ? `<span class="w-rec-stack">${rs.map((r) => `<i style="--c:${r.color}"><img src="${esc(r.thumb)}" alt="" decoding="async"></i>`).join('')}</span>` : '<span class="w-emoji">🍳</span>'}</span>
      <span class="w-foot"><b>${S.recipes.length ? plural(S.recipes.length, 'recipe') : 'Recipes'}</b><small>${S.recipes.length ? `Shop on ${esc(app)}` : 'Cooking reels turn into shopping lists'}</small></span>` };
  }

  function wAsk(wide) {
    return { key: 'ask', cls: `w-ask ${wide ? 'w-wide' : ''}`, tag: 'button', label: 'Ask your library', html: `
      <span class="w-ask-ic">${icon('search')}</span>
      <span class="w-foot"><b>Ask your library</b><small class="w-typed"><span data-typed></span><i class="caret"></i></small></span>` };
  }

  function wLists() {
    const lists = S.lists;
    const mode = coverMode();
    if (!S.extrasLoaded) return { key: 'lists:loading', cls: 'w-lists w-wide', tag: 'section', html: `<div class="w-head"><b class="head">Your lists</b></div><div class="w-list-row">${'<span class="w-li"><span class="w-li-cover"><span class="cover sk"></span></span><span class="sk sk-line"></span><span class="sk sk-line"></span><span class="sk sk-line is-short"></span></span>'.repeat(3)}</div>` };
    if (!lists.length) {
      return { key: 'lists:empty', cls: 'w-lists w-wide is-empty', tag: 'section', html: `
        <div class="w-head"><b class="head">Your lists</b><button class="w-add" type="button" data-newlist aria-label="New list">${icon('plus')}</button></div>
        <p class="sm muted w-lists-empty">Lists that fill themselves. Describe one once, like <b>gym tutorials for arms</b>, and every matching reel joins on its own.</p>
        <button class="btn btn-secondary btn-sm" type="button" data-newlist>${icon('sparkle')}Make your first list</button>` };
    }
    const sig = lists.map((l) => `${l.id}:${l.name}:${l.members.length}:${l.suggestions.length}:${l.emoji}:${mode}`).join('|');
    return { key: 'lists:' + sig, cls: 'w-lists w-wide', tag: 'section', html: `
      <div class="w-head"><b class="head">Your lists</b><span class="w-head-end"><button class="link-btn" type="button" data-alllists>See all</button><button class="w-add" type="button" data-newlist aria-label="New list">${icon('plus')}</button></span></div>
      <div class="w-list-row">${lists.map((l) => `<button class="w-li pressable" type="button" data-list="${l.id}">
        <span class="w-li-cover">${listCover(l, mode)}${l.suggestions.length ? `<span class="count-badge">${l.suggestions.length}</span>` : ''}</span>
        <b class="clamp-2">${esc(l.name)}</b><small>${plural(l.members.length, 'reel')}</small></button>`).join('')}</div>` };
  }

  function wRecent() {
    const rs = S.reels.slice(0, 8);
    return { key: 'recent:' + rs.map((r) => r.id).join(','), cls: 'w-recent w-wide', tag: 'section', html: `
      <div class="w-head"><b class="head">Recently saved</b><button class="link-btn" type="button" data-all>See all ${S.reels.length}</button></div>
      <div class="w-rail">${rs.map((r) => `<button class="rr pressable" type="button" data-rid="${esc(r.id)}" aria-label="Play ${esc(r.name)}">
        <span class="rr-thumb" style="--c:${r.color}">${r.lqip ? `<img class="lq" src="${r.lqip}" alt="">` : ''}<img class="full" src="${esc(r.thumb)}" alt="" loading="lazy" decoding="async" data-fade></span>
        <b class="clamp-2">${esc(r.name)}</b></button>`).join('')}</div>` };
  }

  function wShelves() {
    const cols = S.collections;
    return { key: 'shelves:' + cols.map((c) => c.key + c.ids.length).join(','), cls: 'w-shelves w-wide', tag: 'section', html: `
      <div class="w-head"><b class="head">Sorted for you</b><span class="xs faint">${plural(cols.length, 'shelf', 'shelves')}</span></div>
      <div class="w-shelf-grid">${cols.map((c) => `<button class="w-shelf pressable" type="button" data-col="${esc(c.key)}">${c.emoji ? `<span class="w-shelf-e">${c.emoji}</span>` : `<span class="w-shelf-e is-mono">${esc(c.title.charAt(0))}</span>`}<span class="w-shelf-t">${esc(c.title)}</span><span class="w-shelf-n">${c.ids.length}</span></button>`).join('')}</div>` };
  }

  /* ---------- empty / onboarding / skeleton ---------- */
  function emptyBento() {
    const igLinked = !(S.session && S.session.instagram_connected === false);
    if (!igLinked) return linkInstagramWidget();
    return `<section class="w-tile w-welcome w-wide" data-k="welcome">
      <span class="w-glow" aria-hidden="true"></span>
      <p class="eyebrow">Start here</p>
      <h2 class="title">Send your first <em>reel.</em></h2>
      <ol class="steps"><li><span>Open any reel on Instagram and tap <b>Share</b>.</span></li><li><span>Send it to <b>@clipnest.in</b>, like sending it to a friend.</span></li><li><span>It shows up here, sorted, in about a minute.</span></li></ol>
      <div class="mini-share" aria-hidden="true"><div class="grab"></div><div class="row-av"><div class="av is-us"><i></i><span>clipnest.in</span></div><div class="av is-ghost"><i></i><span></span></div><div class="av is-ghost"><i></i><span></span></div><div class="av is-ghost"><i></i><span></span></div></div></div>
      <a class="btn btn-primary btn-block" href="https://ig.me/m/clipnest.in" target="_blank" rel="noopener">${icon('ig')}Open Instagram</a>
    </section>${ghostTiles()}`;
  }

  function ghostTiles() {
    return `<div class="w-tile w-ghost"><span class="w-ghost-ic">${icon('pin')}</span><b>Places</b><small>Spots you save land on a map.</small></div>
    <div class="w-tile w-ghost"><span class="w-ghost-ic">${icon('chef')}</span><b>Recipes</b><small>Cooking reels become shopping lists.</small></div>
    <div class="w-tile w-ghost w-wide"><span class="w-ghost-ic">${icon('lists')}</span><b>Lists that fill themselves</b><small>Describe a list once and matching reels join on their own.</small></div>`;
  }

  function linkInstagramWidget() {
    return `<section class="w-tile w-welcome w-wide" data-k="link">
      <span class="w-glow" aria-hidden="true"></span>
      <p class="eyebrow">One step left</p>
      <h2 class="title">Link Instagram <em>first.</em></h2>
      <p class="sm muted">Reels you send to @clipnest.in can only reach this library once we know your Instagram account. It takes one DM.</p>
      <div class="link-flow" data-linkflow><button class="btn btn-primary btn-block" type="button" data-getcode>Get my code</button></div>
    </section>${ghostTiles()}`;
  }

  function skeletonBento() {
    return `<div class="w-tile w-library w-tall sk sk-delay"></div><div class="w-tile sk sk-delay"></div><div class="w-tile sk sk-delay"></div>
      <div class="w-tile sk sk-delay"></div><div class="w-tile sk sk-delay"></div><div class="w-tile w-wide sk sk-delay" style="min-height:178px"></div>`;
  }

  function errorBento() {
    const off = S.loadError && S.loadError.status === 0;
    return `<section class="w-tile w-welcome w-wide"><p class="eyebrow">${off ? 'Offline' : 'Something went wrong'}</p><h2 class="title">Could not load your <em>library.</em></h2>
      <p class="sm muted">${esc(errorMessage(S.loadError))}</p><button class="btn btn-primary btn-block" type="button" data-reload>Try again</button></section>`;
  }

  /* ---------- paint: keyed, never rebuilds what has not changed ---------- */
  let mode = '';
  function paint(opts = {}) {
    paintHead();
    paintCards();
    let next;
    if (S.loadError && !S.loaded) next = 'error';
    else if (!S.loaded) next = 'skeleton';
    else if (!S.reels.length && !S.processing.length && !S.failed.length) next = 'empty';
    else next = 'full';
    if (next !== mode) {
      bento.innerHTML = '';
      bento.className = 'bento is-' + next;
      mode = next;
      if (next === 'skeleton') bento.innerHTML = skeletonBento();
      if (next === 'error') { bento.innerHTML = errorBento(); bento.querySelector('[data-reload]').addEventListener('click', () => { import('../store.js').then((m) => m.loadAll()); }); }
      if (next === 'empty') { bento.innerHTML = emptyBento(); wireEmpty(); if (!isReduced()) rise(bento.children, { stagger: 60 }); }
    }
    if (next !== 'full') { $('[data-foot]').textContent = ''; stopTyping(); return; }
    const ws = widgets();
    const existing = new Map();
    bento.querySelectorAll(':scope > [data-wkey]').forEach((n) => existing.set(n.dataset.wslot, n));
    const fresh = [];
    let prev = null;
    ws.forEach((w) => {
      const slot = w.key.split(':')[0];
      w.key = slot + ':' + hash(w.html);
      let n = existing.get(slot);
      if (!n || n.dataset.wkey !== w.key || n.dataset.wcls !== w.cls) {
        const node = el(`<${w.tag} class="w-tile ${w.cls}" ${w.tag === 'button' ? 'type="button"' : ''} data-wslot="${slot}" data-wkey="${esc(w.key)}" data-wcls="${esc(w.cls)}" ${w.rid ? `data-rid="${esc(w.rid)}"` : ''} ${w.label ? `aria-label="${esc(w.label)}"` : ''}>${w.html}</${w.tag}>`);
        wireWidget(node, slot);
        wireFades(node);
        if (n) { n.replaceWith(node); if (opts.landed && slot === 'latest') glowBeat(node); } else fresh.push(node);
        n = node;
      }
      existing.delete(slot);
      const want = prev ? prev.nextElementSibling : bento.firstElementChild;
      if (n !== want) bento.insertBefore(n, prev ? prev.nextSibling : bento.firstChild);
      prev = n;
    });
    existing.forEach((n) => n.remove());
    const first = !S.session_flags.homeIntroDone;
    if (first) {
      S.session_flags.homeIntroDone = true;
      rise(bento.children, { stagger: 50, duration: 460 });
      countUp(bento.querySelector('[data-count]'), S.reels.length, 800);
      setTimeout(() => glowBeat(bento.querySelector('.w-library')), 420);
    } else if (fresh.length && !isReduced()) {
      fresh.forEach((n) => animate(n, [{ opacity: 0, transform: 'scale(0.97)' }, { opacity: 1, transform: 'scale(1)' }], { duration: 320, easing: 'snap', clear: true }));
    }
    $('[data-foot]').textContent = S.reels.length ? `${plural(S.reels.length, 'reel')} · DM more to @clipnest.in` : '';
    startTyping();
  }

  function hash(str) {
    let h = 5381;
    for (let i = 0; i < str.length; i += 1) h = ((h * 33) ^ str.charCodeAt(i)) >>> 0;
    return h.toString(36);
  }

  function wireWidget(n, slot) {
    if (slot === 'lib') n.addEventListener('click', () => import('./allReels.js').then((m) => m.openAllReels()));
    if (slot === 'latest') {
      n.addEventListener('pointerdown', () => warmPlayer(S.byId.get(n.dataset.rid)));
      n.addEventListener('click', () => openPlayer(S.reels.map((r) => r.id), 0, n.querySelector('.w-latest-media')));
    }
    if (slot === 'places') n.addEventListener('click', () => import('./places.js').then((m) => m.openPlaces()));
    if (slot === 'recipes') n.addEventListener('click', () => import('./recipes.js').then((m) => m.openRecipes()));
    if (slot === 'ask') n.addEventListener('click', () => openSearch(typing && typing.current ? typing.current : undefined));
    if (slot === 'proc') n.addEventListener('click', openActivity);
    n.querySelectorAll('[data-newlist]').forEach((b) => b.addEventListener('click', (e) => { e.stopPropagation(); openNewList({}); }));
    n.querySelectorAll('[data-alllists]').forEach((b) => b.addEventListener('click', () => import('../router.js').then((m) => m.switchTab('lists'))));
    n.querySelectorAll('[data-list]').forEach((b) => b.addEventListener('click', () => import('./listDetail.js').then((m) => m.openListDetail(Number(b.dataset.list), { origin: b.querySelector('.w-li-cover') }))));
    n.querySelectorAll('[data-all]').forEach((b) => b.addEventListener('click', () => import('./allReels.js').then((m) => m.openAllReels())));
    n.querySelectorAll('.rr[data-rid]').forEach((b) => {
      b.addEventListener('pointerdown', () => warmPlayer(S.byId.get(b.dataset.rid)));
      b.addEventListener('click', () => { const ids = S.reels.map((r) => r.id); openPlayer(ids, ids.indexOf(b.dataset.rid), b.querySelector('.rr-thumb')); });
    });
    n.querySelectorAll('[data-col]').forEach((b) => b.addEventListener('click', () => import('./collection.js').then((m) => m.openCollection(b.dataset.col))));
  }

  function wireEmpty() {
    const gc = bento.querySelector('[data-getcode]');
    if (gc) gc.addEventListener('click', () => startLinkFlow(bento.querySelector('[data-linkflow]')));
  }

  async function startLinkFlow(box) {
    const btn = box.querySelector('[data-getcode]');
    btnLoading(btn, true);
    let res;
    try { res = await api.connectInstagram(); }
    catch (e) { btnLoading(btn, false); apiToast(e); return; }
    box.innerHTML = `<div class="code-box"><span class="code">${esc(res.code)}</span><span class="xs faint">Expires in 15 minutes</span></div>
      <button class="btn btn-primary btn-block" type="button" data-copyopen>${icon('copy')}Copy code and open Instagram</button>
      <button class="btn btn-secondary btn-block" type="button" data-check>I sent it</button>
      <p class="xs faint link-status" data-linkstatus>Send the code once as a DM to @clipnest.in.</p>`;
    if (!isReduced()) rise(box.children, { y: 8, stagger: 40, duration: 300 });
    box.querySelector('[data-copyopen]').addEventListener('click', () => {
      copyText(res.code).then(() => toast({ msg: 'Code copied. Paste it in the DM.', icon: 'copy' }));
      window.open('https://ig.me/m/clipnest.in', '_blank', 'noopener');
    });
    box.querySelector('[data-check]').addEventListener('click', async (e) => {
      const b = e.currentTarget;
      btnLoading(b, true);
      try {
        const sess = await api.checkInstagram();
        btnLoading(b, false);
        if (!sess.instagram_connected) { box.querySelector('[data-linkstatus]').textContent = 'Not seen yet. It can take a few seconds after you send it. Try again in a moment.'; return; }
        S.session = sess;
        haptic(16);
        const card = box.closest('.w-welcome');
        glowBeat(card);
        card.querySelector('.title').innerHTML = '';
        slamWords(card.querySelector('.title'), 'Linked. Now send a reel.');
        setTimeout(() => { mode = ''; paint(); }, 1600);
      } catch (err) { btnLoading(b, false); apiToast(err); }
    });
  }

  /* ---------- Ask widget: types real queries that have results ---------- */
  function startTyping() {
    const target = bento.querySelector('[data-typed]');
    if (!target) return;
    if (typing && typing.target === target) return;
    stopTyping();
    const pool = ['veg food in bali', 'high protein recipe', 'tricep exercise', 'horror movie', 'sunset', 'mac app'].filter((q) => localSearch(q, 1).length);
    const qs = pool.length ? pool : ['describe what you remember'];
    typing = { target, i: 0, current: qs[0], timer: 0, alive: true };
    if (isReduced()) { target.textContent = qs[0]; return; }
    const t = typing;
    const typeNext = () => {
      if (!t.alive) return;
      const q = qs[t.i % qs.length];
      t.current = q;
      let pos = 0;
      const tick = () => {
        if (!t.alive) return;
        if (!visible) { t.timer = setTimeout(tick, 400); return; }
        pos += 1;
        target.textContent = q.slice(0, pos);
        if (pos < q.length) t.timer = setTimeout(tick, 52);
        else t.timer = setTimeout(erase, 1700);
      };
      const erase = () => {
        if (!t.alive) return;
        pos -= 1;
        target.textContent = q.slice(0, Math.max(0, pos));
        if (pos > 0) t.timer = setTimeout(erase, 24);
        else { t.i += 1; t.timer = setTimeout(typeNext, 380); }
      };
      tick();
    };
    t.timer = setTimeout(typeNext, 700);
  }
  function stopTyping() { if (typing) { typing.alive = false; clearTimeout(typing.timer); typing = null; } }

  /* ---------- pull to refresh (transform only) ---------- */
  const ptr = $('.ptr');
  let pull = null;
  scroller.addEventListener('touchstart', (e) => { if (scroller.scrollTop <= 0) pull = { y: e.touches[0].clientY, d: 0 }; }, { passive: true });
  scroller.addEventListener('touchmove', (e) => {
    if (!pull) return;
    pull.d = Math.max(0, e.touches[0].clientY - pull.y);
    if (scroller.scrollTop > 0) { pull = null; ptr.style.opacity = '0'; return; }
    const d = Math.min(90, pull.d * 0.45);
    ptr.style.transform = `translateY(${d}px) scale(${0.6 + Math.min(1, d / 60) * 0.4})`;
    ptr.style.opacity = String(Math.min(1, d / 50));
    ptr.classList.toggle('is-armed', d > 56);
  }, { passive: true });
  scroller.addEventListener('touchend', async () => {
    if (!pull) return;
    const armed = pull.d * 0.45 > 56;
    pull = null;
    if (!armed) { animate(ptr, [{ opacity: ptr.style.opacity || 0 }, { opacity: 0 }], { duration: 150 }); return; }
    ptr.classList.add('is-loading');
    haptic(8);
    try { const landed = await refresh(); if (!landed.length) toast({ msg: 'Up to date', icon: 'check', duration: 1600 }); }
    catch (e) { apiToast(e); }
    ptr.classList.remove('is-loading', 'is-armed');
    animate(ptr, [{ opacity: 1 }, { opacity: 0 }], { duration: 200 }).then(() => { ptr.style.transform = ''; });
  });

  /* ---------- events ---------- */
  const offs = [
    on('loaded', () => paint()),
    on('loadError', () => paint()),
    on('extras', () => paint()),
    on('lists', () => paint()),
    on('recipes', () => paint()),
    on('city', () => paint()),
    on('library', (d) => {
      paint({ landed: d && d.landed && d.landed.length });
      if (d && d.landed && d.landed.length && visible) {
        const r = S.byId.get(d.landed[0]);
        if (r) toast({ msg: 'New reel sorted', sub: r.name + (r.collections[0] ? ` · ${r.collections[0]}` : ''), icon: 'sparkle', action: { label: 'Play', fn: () => openPlayer([r.id], 0, null) } });
      }
    }),
    on('session', () => paint()),
  ];
  inst.onShow = () => { visible = true; };
  inst.onHide = () => { visible = false; };
  inst.scrollTop = () => scroller.scrollTo({ top: 0, behavior: isReduced() ? 'auto' : 'smooth' });
  inst.destroy = () => { offs.forEach((f) => f()); stopTyping(); };
  inst.repaint = () => { mode = ''; paint(); };
  paint();
  return inst;
}

/* ---------- simulated Google sign-in for guest libraries ---------- */
export function openSignIn() {
  const body = el(`<div class="signin"><div class="signin-ic"><img src="assets/icon-192.png" alt="" width="56" height="56"></div>
    <p class="sm muted">Your reels, lists and Instagram link stay exactly where they are. You just will not lose them.</p>
    <button class="btn btn-primary btn-block" type="button" data-go>${icon('user')}Continue with Google</button>
    <p class="xs faint">Demo: no real account is touched.</p></div>`);
  const s = openSheet({ title: 'Keep this library', body, className: 'sheet-signin' });
  body.querySelector('[data-go]').addEventListener('click', async (e) => {
    btnLoading(e.currentTarget, true);
    await sleep(900);
    S.session.guest = false;
    S.session.user.email = 'you@gmail.com';
    await s.close();
    emit('session');
    haptic(14);
    toast({ msg: 'Signed in. This library is yours for good.' });
  });
}
