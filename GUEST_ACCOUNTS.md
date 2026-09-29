# Guest accounts — build checklist

Goal: someone saves their first reel from Instagram with **no Google login**,
gets a working library immediately, and only signs in once they have something
worth keeping. Today the funnel demands Google before Instagram does anything,
which is where people fall out.

Sequence is by dependency: build the URL, then deliver it, then let strangers
in, then make it persuasive. Each phase is shippable alone.

---

## Verified facts — do not re-derive these

Established 2026-09-29 against Meta docs and live production. Re-checking these
costs hours; they are settled.

- **There is no first-contact API.** A free-form DM is only permitted within 24
  hours of *their* last message, and each inbound message resets the clock.
  `HUMAN_AGENT` extends to 7 days but needs App Review and is explicitly not
  for automation. Every nudge must ride on a message they just sent. A lapsed
  user is unreachable, permanently. Design around it, not through it.
- **"200 DMs/hour" is folklore** — absent from Meta's docs. Real documented
  caps are per-second (100/s text). Not a constraint at this size.
- **Three isolated cookie jars**: Instagram's in-app browser, Safari, and a
  home-screen PWA each have their own. A cookie session dies at every hop. The
  token must live in the URL; that is the only thing that survives.
- **PWA install is impossible inside Instagram's browser.** They must open in
  Safari first. iOS has no `beforeinstallprompt`, so it cannot be triggered,
  only explained.
- **Cost is ₹0.82/reel** (measured, post-optimisation). 10 free reels = ₹8.2
  of exposure per guest who never converts.
- **Prod is readable without Render access**: `/health?token=<TELEGRAM_INGEST_SECRET>`
  — `_debug_authorized` reuses that secret and the local `.env` has it.

---

## Phase 0 — can the app send a DM at all? ✅ DONE 2026-09-29

- [x] `app/services/instagram_send.py` — `send_text()`, returns `{ok, detail}`, never raises
- [x] PING probe in the webhook (`14057fc`, `3d3599a`)
- [x] Webhook rows in the gated health view (`237e7ec`, `3d6f418`)
- [x] **Verified in production**: reply `sent` with a real Meta message id
- [x] Side effect: the Sept-17 username lookup came alive at the same moment —
      `INSTAGRAM_ACCESS_TOKEN` had never been added to Render
- [ ] Run `/admin/instagram/backfill` to fill historical blank usernames

## Phase 1 — a personal library URL ✅ DONE 2026-09-29 (`c568876`)

- [x] `users.library_token`, 43-char `secrets.token_urlsafe(32)`, minted lazily
      by `get_or_create_library_token()`. Permanent by design — reissuing per
      visit would kill every older link sitting in a DM thread
- [x] `GET /g/<token>` in `webapp.py` — sets the session, redirects to `/app`
- [x] Unknown or short token redirects to `/`, never hints
- [x] Scoped session: `GUEST_LINK_SESSION_KEY`. Browsing and saving open,
      destructive endpoints refuse it
- [x] `block_demo_link_writes` → **`block_link_session_writes`**, now covering
      both bearer-link doorways instead of a second guard at 15 call sites
- [x] Tapping your own link while properly signed in does **not** downgrade you
- [x] `GET /auth/library-link` returns your own URL (signed-in only, and
      refused to link sessions so a link cannot copy itself)
- [x] Tested: token stable, cross-user read 403, stranger blocked from
      destructive, migration onto a production-shaped table leaves rows intact
- [x] Verified in prod: `/g/<bogus>` → 303 (a missing column would have 500'd)

## Phase 2 — deliver that URL after a save ✅ MOSTLY DONE (`82d8fff`, `7a1e96e`)

- [x] Reply with the library link when a reel saves
- [x] **Burst suppression within a delivery.** Instagram sends each shared
      reel as its own message event, so replies are collected and sent once
      per person after the loop. Also fixes a count that was quoted mid-loop
      while still climbing
- [x] Send failures logged and swallowed; ingest is never affected
- [x] Every send outcome logged as a `reply` row, visible in the health view
- [x] Skips rather than sends when `PUBLIC_BASE_URL` would make a relative link
- [x] **Gated.** Admins always; others need `DM_REPLY_ACCOUNTS`;
      `DM_REPLY_FOR_EVERYONE=1` for rollout. Shipped after the ungated version
      tried to DM a real 27-reel user (`armadillo.4419417`) who had never been
      messaged before. It failed on a network timeout, so nothing was
      delivered — luck, not design
- [ ] **Move the send off the request path.** It runs synchronously inside the
      webhook; the timeout above held the response 8 seconds. Instagram
      expects fast webhook replies and may retry or mark the endpoint
      unhealthy at volume. Fix before `DM_REPLY_FOR_EVERYONE`
- [ ] Cooldown *across* deliveries, not just within one — someone sending ten
      reels over two minutes still gets several replies

## Phase 3 — let strangers in (this is where the funnel actually opens)

Currently a DM from an unknown sender is buffered and the person hears nothing.
That is exactly how **@haiden.jpeg** was lost — the only recorded case so far.

- [ ] On first DM from an unknown sender, create a guest user row
      (`instagram_user_id` + `instagram_username`, no `google_sub`). The schema
      already permits this: `google_sub` is nullable with no unique constraint
- [ ] Save their reel immediately instead of buffering it
- [ ] Reply with their new library URL
- [ ] Recovery path: any later message re-sends their link. The IGSID is stable
      forever, so losing the DM thread must not lose the account

## Phase 4 — nudges, the lock, and the merge

- [ ] Per-user saved-reel count
- [ ] Milestone replies, wording generated from what they actually saved
      (`main_subject` is already stored) with a **static fallback** on any
      model error
- [ ] **Promotional-content validator** before every generated send; on any
      doubt, ship the static string. A single bad DM risks the one channel the
      product has
- [ ] Home-screen nudge around reel 4
- [ ] Warning around reel 7, lock at reel 10
- [ ] Reels sent after the lock are **buffered, not rejected** — reuse
      `_drain_buffered_reels`, so signing in instantly saves what's pending
- [ ] **The merge.** Signing in with Google must attach `google_sub` to the
      existing guest row, never create a second one. Rule: always attach, never
      migrate data between rows
- [ ] `complete_instagram_link` currently throws 409 when the IGSID already has
      an owner (`app/services/auth.py:460`). Make it merge when that owner is a
      guest with no `google_sub`
- [ ] Two real accounts colliding: refuse and handle by hand. At 18 users, do
      not build for it

## Cross-cutting

- [ ] PWA manifest, `apple-touch-icon`, `apple-mobile-web-app-title` so the
      icon reads "Clipnest" while the URL underneath carries the token
- [ ] Do **not** set a manifest `start_url` that strips the token — it would
      produce an icon that opens logged out. Test on a real iPhone
- [ ] Detect Instagram's in-app browser and show "open in Safari" before asking
      anyone to install
- [ ] **Token expiry alarm.** `INSTAGRAM_ACCESS_TOKEN` dies ~mid-November and
      everything above fails *silently* when it does. This already happened
      once: the Sept-17 username fix sat dead for twelve days
- [ ] Guest counters: how many created, how many hit the lock, how many convert
- [ ] Cost guard: at ₹0.82/reel, 500 unconverted guests is ~₹4,100

---

## Open risks

| Risk | Why it matters | Status |
|---|---|---|
| Token expires mid-Nov | Silent total failure of DMs *and* usernames | No alarm yet |
| Meta flags automated replies | Loses the only channel the product has | Unproven at volume |
| Merge bug empties a library | Happens at the exact moment of asking for commitment | Not built |
| Nobody arrives | Measured 2026-09-17: 18 users, ~6 active, traffic is the real constraint | Unsolved, and not solved by this work |

The last one is the honest caveat on this whole document. This flow makes
arrivals convert. It does not create arrivals.
