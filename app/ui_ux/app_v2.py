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
</head>
<body>
  <div id="device">
    <div id="stage"></div>
    <div id="dock-scrim" aria-hidden="true"></div>
    <div id="dock-host"></div>
    <div id="overlays"></div>
    <div id="toast-host" class="toast-host" aria-live="polite"></div>
    <div id="offline-banner" class="offline-banner" role="status"></div>
  </div>
  <script type="module" src="js/main.js"></script>
  <noscript>ClipNest needs JavaScript. <a href="/app?ui=classic">Open the classic app</a>.</noscript>
</body>
</html>
"""


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
    return bool(email and email in settings.app_v2_accounts) or bool(uid and uid in settings.app_v2_accounts)


def build_app_v2_html(user: dict) -> str:
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
    return SHELL.replace("__BUILD__", build).replace("__CONFIG__", payload)


def asset_path(rel: str) -> Path | None:
    """Resolve a requested asset inside STATIC_DIR, refusing anything outside."""
    try:
        target = (STATIC_DIR / rel).resolve()
    except (OSError, ValueError):
        return None
    if STATIC_DIR.resolve() not in target.parents or not target.is_file():
        return None
    return target
