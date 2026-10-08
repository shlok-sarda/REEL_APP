// You: account, Instagram link, activity, preferences, help, and the
// technical details that used to sit on the main Profile screen.
import { el, esc, plural, haptic, sleep } from '../util.js';
import { icon } from '../icons.js';
import { S, on, emit, displayName, isGuest, appLabel, savePref, cityApps } from '../store.js';
import * as api from '../api.js';
import { LIVE, config } from '../api.js';
import { makeScreen, navBar, toast, apiToast, openSheet, confirmSheet, btnLoading, copyText } from '../ui.js';
import { pushScreen } from '../router.js';
import { rise, isReduced, animate } from '../motion.js';
import { openActivity, openCitySheet } from '../sheets.js';

export function openYou() { return pushScreen(createYou()); }

function fmt(iso) {
  const t = Date.parse(String(iso || '').replace(' ', 'T'));
  return Number.isFinite(t) ? new Date(t).toLocaleString([], { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
}

function createYou() {
  const scr = makeScreen('page you');
  const { el: root, scroller } = scr;
  navBar(scr, 'You');
  const $ = (s) => scroller.querySelector(s);
  let techOpen = false;

  function paint() {
    const u = (S.session && S.session.user) || {};
    const name = displayName();
    const linked = !!(S.session && S.session.instagram_connected);
    const status = S.processing.length ? `Sorting ${plural(S.processing.length, 'reel')}` : S.failed.length ? `${plural(S.failed.length, 'reel')} need a retry` : 'All caught up';
    scroller.innerHTML = `
      <header class="you-head">
        <span class="you-av">${esc((name || 'Y').charAt(0).toUpperCase())}</span>
        <h1 class="title">${esc(name || (isGuest() ? 'Guest library' : 'You'))}</h1>
        <p class="sm muted">${isGuest() ? 'Saved through Instagram. Sign in to keep it for good.' : esc(u.email || '')}</p>
      </header>
      <div class="you-stats">
        <div><b>${S.reels.length}</b><span>Reels</span></div>
        <div><b>${S.lists.length}</b><span>Lists</span></div>
        <div><b>${S.places.length}</b><span>Places</span></div>
      </div>
      ${isGuest() ? `<section class="you-sec"><div class="group"><button class="row has-icon pressable" type="button" data-signin><span class="icon-tile">${icon('user')}</span><span><span class="row-title">Sign in with Google</span><span class="row-meta">Keeps this library yours on any device</span></span>${icon('chev')}</button></div></section>` : ''}
      <section class="you-sec"><h2 class="eyebrow is-quiet">Instagram</h2>
        <div class="group">
          ${linked ? `<div class="row has-icon"><span class="icon-tile">${icon('ig')}</span><span><span class="row-title">Linked</span><span class="row-meta">Reels you DM to @clipnest.in land here</span></span><span class="in-chip">${icon('check')}On</span></div>
            <a class="row has-icon pressable" href="https://ig.me/m/clipnest.in" target="_blank" rel="noopener"><span class="icon-tile is-neutral">${icon('send')}</span><span><span class="row-title">Open the DM</span><span class="row-meta">Send a reel now</span></span>${icon('ext')}</a>`
          : `<button class="row has-icon pressable" type="button" data-link><span class="icon-tile">${icon('ig')}</span><span><span class="row-title">Link Instagram</span><span class="row-meta">One DM with a code, then every reel you send lands here</span></span>${icon('chev')}</button>`}
        </div></section>
      <section class="you-sec"><h2 class="eyebrow is-quiet">Activity</h2>
        <div class="group"><button class="row has-icon pressable" type="button" data-activity><span class="icon-tile ${S.failed.length ? 'is-danger' : ''}">${icon(S.failed.length ? 'alert' : S.processing.length ? 'sparkle' : 'check')}</span><span><span class="row-title">${esc(status)}</span><span class="row-meta">${S.failed.length ? 'Usually a download hiccup. Tap to try again.' : `${plural(S.reels.length, 'reel')} sorted`}</span></span>${icon('chev')}</button></div></section>
      <section class="you-sec"><h2 class="eyebrow is-quiet">Preferences</h2>
        <div class="group">
          ${S.recipesEnabled ? `<button class="row has-icon pressable" type="button" data-city><span class="icon-tile is-neutral">${icon('cart')}</span><span><span class="row-title">Shopping city</span><span class="row-meta">${esc(S.prefs.city || 'Not set')} · ${cityApps().slice(0, 3).map((a) => esc(appLabel(a))).join(', ')}</span></span>${icon('chev')}</button>` : ''}
          <label class="row has-icon"><span class="icon-tile is-neutral">${icon('vol')}</span><span><span class="row-title">Play with sound</span><span class="row-meta">When you open a reel</span></span><span class="switch"><input type="checkbox" data-sound ${S.prefs.soundOn ? 'checked' : ''} aria-label="Play with sound"><span class="track"></span><span class="knob"></span></span></label>
        </div></section>
      <section class="you-sec"><h2 class="eyebrow is-quiet">Help</h2>
        <div class="group">
          <button class="row has-icon pressable" type="button" data-how><span class="icon-tile is-neutral">${icon('info')}</span><span><span class="row-title">How ClipNest works</span></span>${icon('chev')}</button>
          <button class="row has-icon pressable" type="button" data-install><span class="icon-tile is-neutral">${icon('home')}</span><span><span class="row-title">Add to your home screen</span></span>${icon('chev')}</button>
        </div></section>
      ${u.is_admin ? `<section class="you-sec" data-admin><h2 class="eyebrow is-quiet">People (admin)</h2><div class="group"><div class="row"><span class="sk sk-line" style="width:60%"></span></div></div></section>` : ''}
      <section class="you-sec"><button class="tech-toggle pressable" type="button" data-tech aria-expanded="${techOpen}">${icon('settings')}<span>Technical details</span>${icon(techOpen ? 'up' : 'down')}</button>
        <div class="tech" data-techbody ${techOpen ? '' : 'hidden'}></div></section>
      ${LIVE ? `<section class="you-sec"><div class="group"><a class="row has-icon pressable" href="/app?ui=classic"><span class="icon-tile is-neutral">${icon('undo')}</span><span><span class="row-title">Use the classic app</span><span class="row-meta">Come back any time from /app?ui=v2</span></span>${icon('chev')}</a></div></section>` : ''}
      <button class="btn btn-danger btn-block you-logout" type="button" data-logout>${icon('logout')}Log out</button>
      <p class="xs faint you-build">${LIVE ? `ClipNest · new app · build ${esc(config().build)}` : 'ClipNest app v2 replica · build a281692-local'}</p>`;
    wire();
    if (techOpen) paintTech();
    if (u.is_admin) loadAdmin();
  }

  function paintTech() {
    const box = $('[data-techbody]');
    const jobs = (S.jobs || []).slice(0, 10);
    const diag = (S.diagnostics || []).slice(0, 8);
    const pill = (s) => `<span class="st-pill is-${esc(String(s).toLowerCase())}">${esc(s)}</span>`;
    box.innerHTML = `<p class="xs faint">For debugging. Most people never need this.</p>
      <h3 class="eyebrow is-quiet tech-h">Recent jobs</h3>
      ${jobs.map((j) => `<div class="tech-row"><div><b>${esc(j.reel_shortcode || j.reel_id)}</b><small>${esc(j.job_type)} · ${esc(fmt(j.finished_at || j.started_at || j.created_at))} · attempts ${j.attempts || 0}</small>${j.error_message ? `<small class="tech-err">${esc(j.error_message)}</small>` : ''}</div>${pill(j.status)}</div>`).join('') || '<p class="xs faint">No jobs yet.</p>'}
      <h3 class="eyebrow is-quiet tech-h">Stored reels</h3>
      ${diag.map((r) => `<div class="tech-row"><div><b>${esc(r.shortcode || r.id)}</b><small>${r.item_count || 0} items · video ${esc(r.video_download_status || '')} · transcript ${esc(r.transcript_status || '')} · visual ${esc(r.visual_status || '')}</small>${r.transcript_error ? `<small class="tech-err">${esc(String(r.transcript_error).slice(0, 140))}</small>` : ''}</div>${pill(r.status || '')}</div>`).join('') || '<p class="xs faint">Nothing stored yet.</p>'}`;
  }

  async function loadAdmin() {
    const box = $('[data-admin] .group');
    if (!box) return;
    try {
      const res = await api.getAdminUsers();
      box.innerHTML = res.users.map((u) => `<div class="row"><span><span class="row-title">${esc(u.name || u.email || u.id)}</span><span class="row-meta">${esc(u.email || '')}</span></span><span class="row-end">${u.reel_count} reels · ${u.instagram_connected ? 'IG linked' : 'no IG'}</span></div>`).join('') || '<div class="row"><span class="row-meta">No signups yet</span></div>';
    } catch (e) { box.innerHTML = '<div class="row"><span class="row-meta">Could not load people.</span></div>'; }
  }

  function wire() {
    const q = (s) => scroller.querySelector(s);
    if (q('[data-link]')) q('[data-link]').addEventListener('click', openLinkSheet);
    q('[data-activity]').addEventListener('click', openActivity);
    if (q('[data-signin]')) q('[data-signin]').addEventListener('click', () => import('./home.js').then((m) => m.openSignIn()));
    if (q('[data-city]')) q('[data-city]').addEventListener('click', () => openCitySheet());
    q('[data-sound]').addEventListener('change', (e) => { savePref('soundOn', e.target.checked); haptic(6); });
    q('[data-how]').addEventListener('click', openHow);
    q('[data-install]').addEventListener('click', openInstall);
    q('[data-tech]').addEventListener('click', () => {
      techOpen = !techOpen;
      const b = q('[data-tech]');
      b.setAttribute('aria-expanded', String(techOpen));
      b.querySelector('svg:last-child').outerHTML = icon(techOpen ? 'up' : 'down');
      const body = q('[data-techbody]');
      body.hidden = !techOpen;
      if (techOpen) { paintTech(); if (!isReduced()) animate(body, [{ opacity: 0, transform: 'translateY(-6px)' }, { opacity: 1, transform: 'translateY(0)' }], { duration: 220, clear: true }); }
    });
    q('[data-logout]').addEventListener('click', async () => {
      const ok = await confirmSheet({ title: 'Log out?', body: isGuest() ? 'This is a guest library. Your link in the Instagram DM still opens it.' : 'Your library stays saved. Sign back in with Google any time.', confirm: 'Log out', danger: true });
      if (!ok) return;
      try { await api.logout(); } catch (e) { /* clear the view regardless */ }
      if (LIVE) { window.location.href = '/'; return; }
      showSignedOut();
    });
  }

  function openLinkSheet() {
    const body = el(`<div class="link-flow"><p class="sm muted">We send you a short code. You DM it once to @clipnest.in from the Instagram account you save reels with.</p><button class="btn btn-primary btn-block" type="button" data-getcode>Get my code</button></div>`);
    const s = openSheet({ title: 'Link Instagram', body });
    body.querySelector('[data-getcode]').addEventListener('click', async (e) => {
      btnLoading(e.currentTarget, true);
      let res;
      try { res = await api.connectInstagram(); } catch (err) { btnLoading(e.currentTarget, false); apiToast(err); return; }
      body.innerHTML = `<div class="code-box"><span class="code">${esc(res.code)}</span><span class="xs faint">Expires in 15 minutes</span></div>
        <button class="btn btn-primary btn-block" type="button" data-copyopen>${icon('copy')}Copy code and open Instagram</button>
        <button class="btn btn-secondary btn-block" type="button" data-check>I sent it</button><p class="xs faint link-status" data-st>Send the code once as a DM.</p>`;
      body.querySelector('[data-copyopen]').addEventListener('click', () => { copyText(res.code).then(() => toast({ msg: 'Code copied', icon: 'copy' })); window.open('https://ig.me/m/clipnest.in', '_blank', 'noopener'); });
      body.querySelector('[data-check]').addEventListener('click', async (ev) => {
        btnLoading(ev.currentTarget, true);
        try {
          const sess = await api.checkInstagram();
          btnLoading(ev.currentTarget, false);
          if (!sess.instagram_connected) { body.querySelector('[data-st]').textContent = 'Not seen yet. Give it a few seconds and try again.'; return; }
          S.session = sess; emit('session'); haptic(14);
          await s.close(); toast({ msg: 'Instagram linked' }); paint();
        } catch (err) { btnLoading(ev.currentTarget, false); apiToast(err); }
      });
    });
  }

  function openHow() {
    openSheet({ title: 'How ClipNest works', body: `<ol class="steps how"><li><span><b>Share it.</b> Tap share on any reel and send it to @clipnest.in, like sending it to a friend.</span></li><li><span><b>It files itself.</b> ClipNest watches the video, reads what is on screen, and sorts it onto a shelf.</span></li><li><span><b>Ask for it later.</b> Search the way you remember it. Make lists that fill themselves. Shop recipes, find places on a map.</span></li></ol>` });
  }
  function openInstall() {
    const ios = /iPhone|iPad|iPod/i.test(navigator.userAgent);
    openSheet({ title: 'Add to your home screen', body: `<ol class="steps how"><li><span>Open this page in <b>${ios ? 'Safari' : 'Chrome'}</b>, not inside Instagram.</span></li><li><span>Tap <b>${ios ? 'Share' : 'the three dots menu'}</b>.</span></li><li><span>Choose <b>Add to Home Screen</b>. ClipNest opens like an app from then on.</span></li></ol>` });
  }

  function showSignedOut() {
    const ov = el(`<section class="signed-out"><img src="assets/icon-192.png" alt="" width="64" height="64"><h1 class="title">Signed <em>out.</em></h1><p class="sm muted">Your library is saved. This is the replica, so nothing real happened.</p><button class="btn btn-primary" type="button">Sign back in</button></section>`);
    document.getElementById('device').appendChild(ov);
    if (!isReduced()) animate(ov, [{ opacity: 0 }, { opacity: 1 }], { duration: 240 });
    ov.querySelector('button').addEventListener('click', () => { ov.remove(); location.reload(); });
  }

  paint();
  const offs = [on('library', () => paint()), on('session', () => paint()), on('lists', () => paint())];
  if (!isReduced()) requestAnimationFrame(() => rise(scroller.querySelectorAll('.you-head, .you-stats, .you-sec'), { stagger: 40, y: 10, duration: 360 }));
  return { el: root, scroller, dock: true, destroy: () => offs.forEach((f) => f()) };
}

export { sleep };
