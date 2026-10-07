"""The new app UI (v2): static ES modules in app/static/app-v2, served from a
build-versioned path so a deploy can never mix old and new modules in a
phone's cache. Gated to admins + APP_V2_ACCOUNTS while it bakes.

The design source of truth and its local replica live in
design-explorations/app-v2 (not in git); app/static/app-v2 is the shipped copy
with a real-network api.js.
"""
import json
import os
from pathlib import Path

STATIC_DIR = Path(__file__).resolve().parent.parent / "static" / "app-v2"

# The page shell. Lives here, not as app-v2/index.html, because .gitignore
# excludes *.html (generated pages) and a missing shell 500s /app.
SHELL = """<!DOCTYPE html>
<html lang="en" data-motion="normal">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <meta name="theme-color" content="#0a0a0b" />
  <meta name="apple-mobile-web-app-capable" content="yes" />
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
  <meta name="apple-mobile-web-app-title" content="ClipNest" />
  <base href="/v2/__BUILD__/" />
  <link rel="icon" type="image/png" href="/static/favicon.png" />
  <link rel="apple-touch-icon" href="/static/apple-touch-icon.png" />
  <title>ClipNest</title>
  <link rel="stylesheet" href="css/tokens.css" />
  <link rel="stylesheet" href="css/base.css" />
  <link rel="stylesheet" href="css/components.css" />
  <link rel="stylesheet" href="css/screens.css" />
  <link rel="stylesheet" href="css/player.css" />
  <link rel="stylesheet" href="css/sheets.css" />
  <link rel="stylesheet" href="css/dev.css" />
  <script>window.__CN__ = __CONFIG__;</script>
__HEAD_EXTRA__
</head>
<body>
  <div id="device">
    <div id="stage"></div>
    <div id="dock-scrim" aria-hidden="true"></div>
    <div id="dock-host"></div>
__CLAIM_HTML__
    <div id="overlays"></div>
    <div id="toast-host" class="toast-host" aria-live="polite"></div>
    <div id="offline-banner" class="offline-banner" role="status"></div>
  </div>
  <script type="module" src="js/main.js"></script>
  <noscript>ClipNest needs JavaScript. <a href="/app?ui=classic">Open the classic app</a>.</noscript>
__CLAIM_SCRIPT__
</body>
</html>
"""


# Claim card for guests who arrived by a /g/ library link: home screen at 5
# reels, Google sign-in from 17, impossible to dismiss at 20. It floats above
# the dock inside #device, under the player (z 40) and sheets (z 60), and lives
# here in the shell rather than in app-v2/js because sync_live.py replaces
# those files wholesale. No backslashes anywhere below: non-raw Python string.
CLAIM_CSS = """<style>
#cn-claim { position:absolute; left:var(--gut); right:var(--gut); bottom:calc(var(--dock-h) + var(--safe-bottom) + 14px); z-index:30;
  background:var(--s2); border:1px solid var(--line-strong); border-radius:var(--r-lg); padding:14px 16px 12px; box-shadow:var(--sh-3);
  opacity:0; transform:translateY(10px); transition:opacity .28s ease, transform .28s ease; }
#cn-claim.show { opacity:1; transform:none; }
#cn-claim.locked { border-color:var(--accent-line); box-shadow:var(--sh-3), 0 0 0 1px var(--accent-tint); }
.cn-claim-title { margin:0; font-family:var(--serif); font-size:1.0625rem; font-weight:600; letter-spacing:-0.01em; color:var(--text); }
.cn-claim-body { margin:4px 0 0; font-family:var(--sans); font-size:var(--t-xs); line-height:1.45; color:var(--muted); }
.cn-claim-steps { margin:8px 0 0; font-family:var(--sans); font-size:var(--t-xs); font-weight:600; color:var(--text); }
.cn-claim-action { margin-top:12px; }
.cn-claim-action:empty { display:none; }
.cn-claim-btn { display:flex; align-items:center; justify-content:center; min-height:44px; padding:0 18px; border-radius:var(--r-pill);
  background:var(--brand-grad); color:var(--accent-ink); font-family:var(--sans); font-size:var(--t-sm); font-weight:600; text-decoration:none;
  box-shadow:var(--sh-accent); transition:transform .15s ease, opacity .15s ease; }
.cn-claim-btn:hover { opacity:.92; }
.cn-claim-btn:active { transform:scale(.97); }
.cn-claim-btn:focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
.cn-claim-note { margin:8px 0 0; font-family:var(--sans); font-size:var(--t-2xs); line-height:1.4; color:var(--faint); }
.cn-claim-err { margin:8px 0 0; font-family:var(--sans); font-size:var(--t-2xs); color:var(--danger); }
/* No display rule on the skip button: one would override [hidden]. */
.cn-claim-skip { margin-top:6px; background:none; border:0; padding:4px 0; color:var(--muted); font-family:var(--sans); font-size:var(--t-2xs); cursor:pointer; transition:opacity .15s ease; }
.cn-claim-skip:hover { opacity:.75; }
.cn-claim-skip:active { opacity:.55; }
.cn-claim-skip:focus-visible { outline:2px solid var(--accent); outline-offset:2px; border-radius:4px; }
/* While the card floats over the bottom of the screen, give every screen that
   much extra room at the end, or the last items could never scroll into view
   (the locked card cannot be dismissed). */
#device.cn-claim-on .screen { padding-bottom:calc(var(--dock-h) + var(--safe-bottom) + 40px + var(--cn-claim-h, 0px)); }
</style>"""

CLAIM_HTML = """    <section id="cn-claim" hidden aria-live="polite">
      <p id="cn-claim-title" class="cn-claim-title"></p>
      <p id="cn-claim-body" class="cn-claim-body"></p>
      <p id="cn-claim-steps" class="cn-claim-steps" hidden></p>
      <div id="cn-claim-action" class="cn-claim-action"></div>
      <p id="cn-claim-note" class="cn-claim-note" hidden></p>
      <p id="cn-claim-err" class="cn-claim-err" hidden></p>
      <button id="cn-claim-skip" class="cn-claim-skip" type="button" hidden>Not now</button>
    </section>"""

CLAIM_SCRIPT = """  <script>
    (function () {
      const STAGE = '__CLAIM_STAGE__';
      const LIB_TOKEN = '__LIB_TOKEN__';
      const LOGIN_CSRF = '__LOGIN_CSRF__';
      const GOOGLE_CLIENT_ID = '__GOOGLE_CLIENT_ID__';
      if (!STAGE || !LIB_TOKEN) return;
      const ua = navigator.userAgent || '';
      const inInstagram = /Instagram/i.test(ua);
      const isIOS = /iPhone|iPad|iPod/i.test(ua);
      const isAndroid = /Android/i.test(ua);
      const $ = function (id) { return document.getElementById(id); };
      const card = $('cn-claim'), title = $('cn-claim-title'), body = $('cn-claim-body'), steps = $('cn-claim-steps');
      const action = $('cn-claim-action'), note = $('cn-claim-note'), err = $('cn-claim-err'), skip = $('cn-claim-skip');
      const skipKey = 'cn_claim_skip_' + STAGE;
      try { if (STAGE !== 'locked' && localStorage.getItem(skipKey)) return; } catch (e) {}
      const fullUrl = location.origin + '/g/' + LIB_TOKEN;
      const MANUAL = 'If nothing happens, tap ··· at the top right and choose Open in external browser.';

      // Instagram's browser can neither add to the Home Screen nor sign in
      // with Google, so offer a way out: Meta's own handoff on iPhone, a
      // Chrome intent on Android. Both are undocumented, hence the note.
      function escapeHref() {
        if (isAndroid) {
          return 'intent://' + location.host + '/g/' + LIB_TOKEN +
            '#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=' +
            encodeURIComponent(fullUrl) + ';end';
        }
        return 'instagram://extbrowser/?url=' + encodeURIComponent(fullUrl);
      }
      function escapeButton(label, explain) {
        const a = document.createElement('a');
        a.className = 'cn-claim-btn';
        a.href = escapeHref();
        a.textContent = label;
        action.appendChild(a);
        note.textContent = explain + ' ' + MANUAL;
        note.hidden = false;
      }

      if (STAGE === 'home') {
        title.textContent = 'Add ClipNest to your Home Screen';
        body.textContent = 'It works just like an app. Open your library in one tap, without going through Instagram.';
        if (inInstagram) {
          escapeButton('Continue in browser', 'Adding to your Home Screen works from your browser.');
        } else if (isIOS) {
          steps.textContent = 'Tap Share, then Add to Home Screen.'; steps.hidden = false;
        } else if (isAndroid) {
          steps.textContent = 'Tap ⋮, then Add to Home screen.'; steps.hidden = false;
        } else {
          return;
        }
      } else {
        if (STAGE === 'locked') {
          card.classList.add('locked');
          title.textContent = 'You’ve reached 20 saved reels';
          body.textContent = 'Sign in with Google to continue saving. Your library stays exactly as it is, and any reels you’ve sent since will be added automatically.';
        } else {
          title.textContent = 'Secure your library';
          body.textContent = 'Sign in with Google to keep your saved reels safe and accessible on any device.';
        }
        if (inInstagram) {
          escapeButton('Continue in browser to sign in', 'Google sign-in isn’t available inside Instagram.');
        } else if (!GOOGLE_CLIENT_ID || !LOGIN_CSRF) {
          return;
        }
      }

      if (STAGE !== 'locked') {
        skip.hidden = false;
        skip.addEventListener('click', function () {
          try { localStorage.setItem(skipKey, '1'); } catch (e) {}
          card.classList.remove('show');
          document.getElementById('device').classList.remove('cn-claim-on');
          setTimeout(function () { card.hidden = true; }, 280);
        });
      }
      card.hidden = false;
      const device = document.getElementById('device');
      function reserve() { device.style.setProperty('--cn-claim-h', (card.offsetHeight + 14) + 'px'); }
      device.classList.add('cn-claim-on');
      reserve();
      // The Google button renders late and changes the card height.
      if (window.ResizeObserver) { new ResizeObserver(reserve).observe(card); }
      requestAnimationFrame(function () { card.classList.add('show'); });

      if (STAGE !== 'home' && !inInstagram) {
        const slot = document.createElement('div');
        action.appendChild(slot);
        const s = document.createElement('script');
        s.src = 'https://accounts.google.com/gsi/client';
        s.async = true;
        s.onload = function () {
          window.google.accounts.id.initialize({
            client_id: GOOGLE_CLIENT_ID,
            callback: async function (response) {
              err.hidden = true;
              try {
                const r = await fetch('/auth/google', {
                  method: 'POST', credentials: 'same-origin',
                  headers: { 'Content-Type': 'application/json' },
                  body: JSON.stringify({ credential: response.credential, csrf_token: LOGIN_CSRF, visitor: '' })
                });
                if (!r.ok) {
                  const b = await r.json().catch(function () { return {}; });
                  throw new Error(b.detail || 'Sign in failed. Please try again.');
                }
                location.reload();
              } catch (e) { err.textContent = e.message; err.hidden = false; }
            }
          });
          window.google.accounts.id.renderButton(slot, {
            theme: 'filled_black', size: 'large', shape: 'pill', text: 'continue_with',
            width: Math.min(400, Math.max(200, action.clientWidth))
          });
        };
        document.head.appendChild(s);
      }
    })();
  </script>"""


def _token_safe(value: str) -> str:
    return "".join(c for c in (value or "") if c.isalnum() or c in "._-")


def build_id() -> str:
    """Render exposes the deployed commit; locally this is 'dev'."""
    return (os.getenv("RENDER_GIT_COMMIT") or "dev")[:7]


def app_v2_enabled(user: dict | None) -> bool:
    from app.config import settings
    from app.services.auth import user_is_admin

    if not user:
        return False
    if user_is_admin(user):
        return True
    email = (user.get("email") or "").strip().lower()
    uid = (user.get("id") or "").strip().lower()
    if bool(email and email in settings.app_v2_accounts) or bool(uid and uid in settings.app_v2_accounts):
        return True
    # The guest-flow test account has no email to list, so it is named by
    # Instagram handle in GUEST_TEST_SENDERS, and test accounts see the new UI.
    from app.services.nudge import sender_allowed

    return sender_allowed(user.get("instagram_user_id") or "", user.get("instagram_username") or "")


def build_app_v2_html(
    user: dict,
    library_token: str = "",
    claim_stage: str = "",
    login_csrf: str = "",
    google_client_id: str = "",
) -> str:
    from app.services.discover import recipes_enabled
    from app.services.library import collections_enabled
    from app.services.search_report import search_report_enabled

    user_id = user["id"]
    build = build_id()
    config = {
        "userId": user_id,
        "build": build,
        "flags": {
            "showRecipes": recipes_enabled(user_id),
            "showCollections": collections_enabled(user_id),
            "showReport": search_report_enabled(user_id),
        },
    }
    # "</" can never appear inside the inline JSON, so it cannot close the tag.
    payload = json.dumps(config).replace("</", "<\\/")
    html = SHELL.replace("__BUILD__", build).replace("__CONFIG__", payload)

    token = _token_safe(library_token)
    head_extra, claim_html, claim_script = "", "", ""
    if token:
        # Opened by a /g/ link: iPhone builds the Home Screen icon from the
        # on-screen URL, Android from the manifest, so both must carry the key.
        # Not full-screen: Google's sign-in popup misbehaves in iPhone
        # full-screen web apps, and sign-in is what the guest flow converts on.
        html = html.replace('  <meta name="apple-mobile-web-app-capable" content="yes" />\n', "")
        head_extra = f'  <link rel="manifest" href="/g/{token}/manifest.webmanifest" />\n'
    stage = claim_stage if claim_stage in ("home", "signin", "locked") else ""
    if token and stage:
        head_extra += CLAIM_CSS
        claim_html = CLAIM_HTML
        claim_script = (
            CLAIM_SCRIPT.replace("__CLAIM_STAGE__", stage)
            .replace("__LIB_TOKEN__", token)
            .replace("__LOGIN_CSRF__", _token_safe(login_csrf))
            .replace("__GOOGLE_CLIENT_ID__", _token_safe(google_client_id))
        )
    return (
        html.replace("__HEAD_EXTRA__", head_extra)
        .replace("__CLAIM_HTML__", claim_html)
        .replace("__CLAIM_SCRIPT__", claim_script)
    )


def asset_path(rel: str) -> Path | None:
    """Resolve a requested asset inside STATIC_DIR, refusing anything outside."""
    try:
        target = (STATIC_DIR / rel).resolve()
    except (OSError, ValueError):
        return None
    if STATIC_DIR.resolve() not in target.parents or not target.is_file():
        return None
    return target
