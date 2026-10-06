# Chatbot handoff

Start here if you are a new session picking up the ClipNest DM chatbot. Shlok wants
to design the chatbot in its own session, separate from launch and infrastructure
work. Read this, then `NUDGE_RULEBOOK.md`, then run the simulator before changing
anything.

Last updated 2026-10-06.

---

## What the bot is for

ClipNest users save Instagram reels by DMing them to **@clipnest.in**. A stranger's
first DM creates an account for them on the spot (no app, no signup), and the bot
replies with a personal library link. The bot's job after that is narrow:
**re-engage people who are drifting, and get them to sign in with Google at 20
reels.** It is not there to confirm every action. An active saver needs nothing
from it.

## Where it stands

- A deterministic state machine is **live in production**, gated to one test
  account (`url_testing_finale`). Static copy, no AI yet.
- Eight message types at fixed triggers. A user who reaches 20 reels hears from the
  bot about **6 times** in total, plus one nudge each time they go quiet.
- Verified for real: outbound DMs work, and the 23-hour quiet nudge fired on the
  test account.
- The model-written layer Shlok wants is **not built**. That is this session's job.

## Constraints that are settled (verified, do not re-derive)

- **The account can never message first.** Free-form replies are only allowed
  within 24 hours of the user's last message, and every message they send resets
  the clock. `HUMAN_AGENT` extends to 7 days but needs App Review and is explicitly
  not for automation. When the window shuts, that person is unreachable until they
  write again.
- **Reports are the real limit, not a message count.** There is no documented
  per-conversation cap ("200 DMs an hour" is folklore). Annoyed users reporting
  the account is what gets it restricted, and the account is the product's only
  channel.
- Message text must be **1000 bytes or less**.
- **No em or en dashes** in anything sent under Shlok's name. They read as AI.
- **Signed-in users get no messages.** `decide()` returns nothing for any account
  with a Google identity. All existing users signed up through Google, so they are
  never messaged.
- **Money:** reel processing costs about Rs 0.82 a reel. Any new model call must be
  estimated in rupees and approved by Shlok **before** anything is spent.

## The split agreed with Shlok

| Decision | Who decides |
|---|---|
| Is the 24h window open | Code (timestamp arithmetic; a wrong guess is a failed send or a policy problem) |
| When to wake up | Code (the janitor loop) |
| Is this user eligible at all | Code (allowlist, cooldown, history; must be replayable and countable) |
| Which message applies | Code today. The rulebook allows the model to choose; still open |
| The exact wording | **Model**, with the static copy as a fallback |
| Did it send | Code (reads the HTTP response) |

Shlok wants the bot "over-engineered" and psychology-driven, and has pushed for a
full chatbot. That is open for discussion here. The table above is the floor.

---

## How it works now

Every trigger goes through one function:

```
nudge.fire(user_id, trigger, title="")
  load_state -> replies_allowed (the gate) -> window_open -> decide(user, trigger)
  -> cooldown (skipped for once-ever messages) -> render(key) -> send_text
  -> record in nudge_log and users.last_dm_at
```

**Triggers**

| Trigger | Fired by | File |
|---|---|---|
| `reel_saved` | Webhook, when a reel is saved | `app/api/routes/instagram.py` |
| `reel_ready` | Worker, after a reel finishes processing | `app/workers/process_queue.py` |
| `plain_message` | Webhook, a message with no reel in it | `app/api/routes/instagram.py` |
| `reel_held` | Webhook, a reel sent past the 20-reel lock | `app/api/routes/instagram.py` |
| `timer` | Janitor loop every 150s, users 23 to 24h quiet | `app/main.py` -> `run_last_call_sweep()` |

**Messages** (full copy and reasoning in `NUDGE_RULEBOOK.md`)

| Key | When | Repeats |
|---|---|---|
| `m1_first_ack` | First reel saved, instantly | Once ever |
| `m2_first_library` | First reel processed: library link plus "1 of 5" | Once ever |
| `m3_quiet_nudge` | 23h after their last message, nothing since | Once per quiet spell |
| `m4_home_screen` | Reel count reaches 5 | Once ever |
| `m5_heads_up` | Reel count reaches 17 | Once ever |
| `m6_lock` | Reel count reaches 20, not signed in | Once ever |
| `m7_past_lock` | A reel arrives while locked (it is held, not processed) | Repeatable, cooldown |
| `m8_recovery` | Any message without a reel: resends the library link | Repeatable, cooldown |

**State it reads:** `users.last_inbound_at` (the window), `users.last_dm_at`
(cooldown), `users.library_token`, the `nudge_log` table (once-ever), the reel
count, and `google_sub` (signed in means converted).

**Gates** (Render env vars, closed by default): `GUEST_TEST_SENDERS` (handles or
Instagram ids), `DM_REPLY_ACCOUNTS`, `DM_REPLY_FOR_EVERYONE`,
`GUEST_AUTOCREATE_FOR_EVERYONE`, `GUEST_LOCK_ENABLED`, `DM_COOLDOWN_MINUTES`
(default 10). There is deliberately no admin bypass.

## Testing

- `QUEUE_JANITOR=off python3 scripts/simulate_nudges.py` runs every situation
  through the real `fire()` against a throwaway database, with only the Instagram
  call faked. About two seconds. Run it after every change; it is how the bugs
  below were found.
- Replay the funnel on the live test account:
  `https://clipnest.in/health?token=<TELEGRAM_INGEST_SECRET>&reset_guest=url_testing_finale`.
  It refuses any handle not in `GUEST_TEST_SENDERS` and any signed-in account.
- Production diagnostics: `/health?token=<TELEGRAM_INGEST_SECRET>`, under
  `queue_debug.instagram_webhook`. It shows recent sends with skip reasons and the
  live gate values. The secret is in the local `.env`; never paste its value
  anywhere.

## Mistakes already made (do not reintroduce)

1. **Confirming every reel**: 21 DMs for 21 reels. The bot speaks when people
   drift, not when they act.
2. **Cooldown checked before deciding** silently ate `m2` after `m1` every time.
   Once-ever messages skip the cooldown.
3. **An admin bypass on the gate** messaged an account nobody had listed. Removed.
4. **A cap on repeated nudges** turned out to be dead code. The 24h window already
   caps it: an unanswered nudge is followed by the window closing.
5. **Anchoring the quiet nudge to the first reel** fires hours early. It anchors to
   their most recent message.

---

## What to build next

1. **Model-written wording** inside `render()`. Keep the static copy as the
   fallback. Input: the message key plus context (reel count, stage, recent titles
   and categories, which already exist per reel). Output: one message.
2. **A validator before every generated send** (rulebook section 6). Only their own
   `/g/` link; no discounts, urgency or promo language; no features that do not
   exist; no dashes; 1000 bytes or less; never "saved" when nothing was saved; not
   identical to the last message. On any failure, send the static copy and log it.
3. **Choose a cheap model** and estimate the rupee cost per message before asking
   Shlok. The codebase already uses OpenAI (`gpt-4.1-mini` for extraction).
4. **Measure** messages per user per week, blocks and reports, and conversion at
   the lock, comparing static copy against model wording.

## Open questions to settle with Shlok

- Should the bot **reply conversationally** when people ask questions, or only send
  the eight messages? Conversation means open-ended output on the only channel.
- May the model **pick which message** to send, or only word the one code picked?
- **How personal** should it get, for example naming the reels someone saved?
- The `m2` and `m3` lines promise "at five reels it starts grouping them". Guests are
  not on the Collections allowlist, so that may not be true. Verify it, or rewrite
  those lines.

## Working with Shlok

- Brutal honesty, no validation by default, short answers.
- He often sends voice-transcribed messages. Read for intent.
- Research before quoting any number, and label verified versus guessed.
- Wait until he has finished explaining his rules before building, and read them
  back before anything runs unsupervised.
- Show him any copy or AI prompt before it is used.
- After a validated change, push to `origin/main` (Render auto-deploys).
  Boot-test the committed tree in a worktree first. Several sessions share this
  working tree, so check `git status` and `git log` before committing.
- Locally, `QUEUE_JANITOR=off` is mandatory.

## Files

`NUDGE_RULEBOOK.md` (also `ClipNest_Nudge_Rulebook.pdf`), `GUEST_ACCOUNTS.md`,
`NUDGE_SCENARIOS.md`, `app/services/nudge.py`, `scripts/simulate_nudges.py`.
