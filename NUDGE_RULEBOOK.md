# Nudge rulebook

What the bot is allowed to say, when, and why. This document is the input to
the decision step: the server gathers a user's state, hands it here, and gets
back one message or silence.

Written to be argued with. If a rule looks wrong, it probably is, and it is
cheaper to fix here than in production.

---

## 1. The constraints that are not negotiable

These come from Meta and from measurement, not from taste.

- **The app can never message first.** A free-form DM is legal only inside 24
  hours of *their* last message, and every message they send resets that clock
  to a fresh 24 hours. `HUMAN_AGENT` extends it to 7 days but needs App Review
  and is explicitly not for automation. When the window shuts, that person is
  unreachable forever. No tag, no endpoint, no workaround.
- **Reports are the real limit, not a message count.** There is no documented
  per-conversation cap. What gets accounts restricted is velocity spikes,
  copy that reads promotional, cold outreach, and recipients reporting you.
  Every message here is a reply to something they just did, which is the
  explicitly permitted category, so the only live risk is irritating your own
  users into reporting.
- **Each reel costs ₹0.82** to process. Every unconverted guest is that times
  their reel count.
- **Never a dash.** Not an em dash, not an en dash. These go out under Shlok's
  name and a dash reads as machine-written.

## 2. What the model decides, and what it must not

| Decision | Who | Why |
|---|---|---|
| Is the 24h window open | **Code** | Arithmetic on a timestamp. A wrong guess is a failed send or a policy problem, and the model cannot check |
| When to wake up | **Code** | The 150s janitor thread in `main.py` ticks. Nothing else can |
| Is this user eligible at all | **Code** | Allowlist, cooldown, already-sent history. Must be replayable and countable |
| Which message applies | **Model**, from section 4 | |
| The exact wording | **Model** | The only part code is genuinely bad at |
| Did it send | **Code** | Reads the HTTP response |

The model may always return **silence**. Silence is a valid and often correct
answer, and the rulebook should make it the default when nothing below clearly
applies.

## 3. User states

| State | Meaning |
|---|---|
| `new` | Account just created, no reel finished yet |
| `early` | 1 to 4 reels |
| `active` | 5 to 16 reels |
| `approaching` | 17 to 19 reels |
| `locked` | 20+ reels, not signed in |
| `converted` | Signed in with Google. **The bot stops nudging. It has what it wanted** |
| `dormant` | Window closed. Unreachable. Not a state we can act on, only count |
| `locked` enforcement | `GUEST_LOCK_ENABLED=1` makes the wall real: reels past 20 are held, not processed |

## 4. The messages

**The bot speaks when someone is drifting, not when they act.** The first
draft of this document confirmed every reel, which came to 21 messages for 21
reels, aimed at a person who was actively saving and needed no reminding. A
user who reaches 20 reels should hear from us about six times in total.

Each fires **once ever** unless marked repeatable. Cooldown between any two
messages to one person: **10 minutes** (`DM_COOLDOWN_MINUTES`).

### M1 — first contact, instant
**Trigger:** their very first reel is saved, before processing. Once ever.
**Why:** the most fragile moment in the funnel. Someone messaged an account
they have never interacted with and then heard nothing for five minutes. They
are not thinking "it must be processing", they are thinking this is dead.

> Thank you for saving a reel with me. It is processing now, give me a couple of minutes.

### M2 — the first library link
**Trigger:** their first reel finishes processing. Once ever.
**Why:** the magic moment, and the only one that needs announcing. It names
something they never typed, which proves the app watched the video rather
than read the caption. The "1 of 5" frame rides here.

> Saved it as {title}. Here is your library: {link} That is 1 of 5. At five reels it starts grouping them for you.

**Why "1 of 5" and never "send 4 more":** Nunes and Drèze (2006) gave one group
a ten stamp card with two already filled and another a blank eight stamp card.
Identical work remaining. Completion was 34% against 19%.

### Reels two onward: silence
No message. They have seen the library, the link never changes, and a
confirmation per reel is the single biggest annoyance risk in the design.

### M3 — the quiet nudge
**Trigger:** 23 hours since their **most recent inbound message** with nothing
since, and not `converted`. Repeatable, once per dormancy.
**Why:** the only message aimed at someone forgetting the app exists, which is
the entire reason the bot has a voice. Anchor to the last message, never the
first reel: the window resets on every message they send, so anchoring to the
first reel fires hours early and wastes the only shot left.

Asks for one specific small thing rather than describing the product:

> Send me one more reel and I can start grouping them for you.

> {n} saved so far. One more gets you to five, which is where it starts sorting itself.

> Still here whenever you find something worth keeping. Your library: {link}

**No cap is needed, and this is not an oversight.** The 24 hour window already
enforces one. A nudge that goes unanswered is followed by the window closing,
after which the person cannot be messaged at all, so at most one nudge per
dormancy can ever be sent. A counter for it would only ever hold 0 or 1.

### M4 — home screen
**Trigger:** reel count crosses 5. Once ever.
**Why here:** at five reels the library finally looks worth returning to.
Asking anyone to install something when they have one reel is asking before
there is a reason.

> {n} reels now. Put ClipNest on your home screen so you are not digging through DMs for this link: {link}

**Known ceiling:** installing means escaping Instagram's in-app browser into
Safari, and iOS cannot be prompted programmatically. Expect very few. Worth
saying once because the home screen is the only door you own that is not
Meta's.

### M5 — heads up
**Trigger:** reel count crosses 17. Once ever.
**Why:** a warned wall is a deadline, an unwarned one is a betrayal.

> {n} saved. At 20 you will need a free account to keep going. One tap, and everything you have stays exactly where it is.

### M6 — the lock
**Trigger:** reel count reaches 20, not signed in. Once ever.
**Why:** maximum accumulated value, so maximum to lose.

> That is 20 reels. Sign in to keep saving and it is all still here: {link}

### M7 — a reel arrives past the lock
**Trigger:** a reel sent while locked. Repeatable, subject to cooldown.
**Why:** never reject their reel. It is buffered, not dropped, so signing in
pays off instantly rather than merely unblocking them. The wall is real:
`GUEST_LOCK_ENABLED` stops the reel being processed, because every one past
the wall costs ₹0.82 of a guest who has not signed in.

> Holding that one for you. Sign in and it saves straight away: {link}

### M8 — recovery
**Trigger:** any message with no reel in it. Repeatable, subject to cooldown.
**Why:** the DM thread is the only way back to their library, and their
Instagram id is permanent, so any message must regenerate the link.

> Here is your library: {link}

## 5. Precedence

Highest wins, the rest are dropped rather than queued:

`M6 lock` → `M5 heads up` → `M4 home screen` → `M7 past lock` →
`M2 first library` → `M1 first ack` → `M8 recovery` → `M3 quiet nudge`

## 5a. What a full journey actually costs

Measured by walking a simulated user from reel 1 to reel 21:

| | Messages |
|---|---|
| First draft, confirm everything | 21 |
| This design | **6** |

M1, M2, home screen at 5, heads up at 17, lock at 20, and one held reel.
Plus a quiet nudge each time they drift.

## 6. Validator

Runs on every generated message. Any failure ships the static fallback instead.
The fallback is always the plain version of the same message from section 4.

- Contains no URL other than that user's own `/g/<token>` link
- No discount, offer, limited time, act now, or any urgency construction
- No claim about a feature that does not exist
- No em dash, no en dash
- 1000 bytes or under
- Does not say "saved" when nothing was saved
- Not a duplicate of the last message sent to this person

A failed validation is logged, not retried. A slightly plain message is a
non-event. A bad one costs the only channel this product has.

## 7. What the bot never does

- Message anyone not in `GUEST_TEST_SENDERS` or `DM_REPLY_ACCOUNTS`, until
  `DM_REPLY_FOR_EVERYONE` is deliberately set
- Send twice within the cooldown
- Repeat a once-only message
- Nudge a `converted` user. It already got what it was for
- Ask twice for something already refused
- Send anything when silence is the honest answer

## 8. How to tell whether it works

Without these the rulebook is just opinion:

- Guests created, and how many reach 1 / 5 / 20 reels
- Link opens per guest, and how many open it more than once
- Conversion at the lock, which is the number the whole design exists to move
- Messages sent per user per week, the annoyance proxy
- Blocks and reports, the only metric that can end the product

## 9. The honest caveat

Measured 2026-09-17: 18 users, about 6 active, and the constraint is that
almost nobody arrives. This rulebook improves the conversion of people who
show up. It does not make anyone show up.

The 20 reel benchmark comes from Shlok's observation that his six users past
20 reels stayed one to two months. Worth respecting, but the causation likely
runs backwards: they crossed 20 because they were the kind of user who stays,
not the reverse. Locking at 20 buys better information at roughly ₹16.40 per
unconverted guest rather than ₹8.20. That is a bet on his own read of his
users, and it should be revisited once there is conversion data at either
number.
