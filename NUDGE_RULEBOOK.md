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

## 4. The messages

Each fires at most **once ever** unless marked repeatable. Cooldown between
any two messages to one person: **10 minutes** (`DM_COOLDOWN_MINUTES`).

### M1 — first contact acknowledgement
**Trigger:** their very first reel is saved, immediately, before processing.
**Fires:** once ever.
**Why:** the most fragile moment in the funnel. Someone shared a reel to an
account they have never interacted with and then heard nothing for five
minutes. They are not thinking "it must be processing", they are thinking this
is dead. This message costs one send and converts "broken" into "working".

> Got it. Give me two minutes, I am watching the reel.

### M2 — the reel is ready
**Trigger:** processing completes. **Repeatable**, subject to cooldown.
**Why:** the magic moment. It works because it names something they never
typed, which proves the app watched the video rather than read the caption.
Lead with the title, always.

> Ready: {title}. Your library is here: {link}

On the first reel only, append the progress frame:

> Ready: {title}. Your library is here: {link}
> That is 1 of 5. At five reels it starts grouping them for you.

**Why "1 of 5" and never "send 4 more":** Nunes and Drèze (2006) gave one group
a ten stamp card with two already filled and another a blank eight stamp card.
Identical work remaining. Completion was 34% against 19%. Progress already
made beats distance still to go, for free.

### M3 — last call
**Trigger:** 23 hours since their **most recent inbound message**, and they
have sent nothing since, and they are not `converted`.
**Fires:** once per dormancy. **This is the single highest leverage message in
the funnel**, because after it you can never speak to them again.
**Why:** anchor to the last message, never to the first reel. The window resets
on every message they send, so anchoring to the first reel fires the shot
hours early and wastes it.

> You saved {title} yesterday. Anything else you want to keep, just send it
> here. It takes about five before this really starts being useful.

Low pressure on purpose. This is a door left open, not a sales pitch, and a
pitch here is what gets reported.

### M4 — home screen
**Trigger:** reel count crosses 5.
**Why here and not earlier:** at five reels the library finally looks like
something worth returning to. Asking someone to install anything when they have
one reel is asking before there is a reason.

> {n} reels now. Put ClipNest on your home screen so you are not digging
> through DMs for this link: {link}

**Known ceiling, do not design around it:** installing requires escaping
Instagram's in-app browser into Safari, which is fiddly, and iOS cannot be
prompted programmatically. Expect very few to do it. It is worth saying once
because the home screen is the only door you own that is not Meta's.

### M5 — heads up
**Trigger:** reel count crosses 17.
**Why:** the lock must never be an ambush. A warned wall is a deadline; an
unwarned one is a betrayal.

> {n} saved. At 20 you will need a free account to keep going. One tap, and
> everything you have stays exactly where it is.

### M6 — the lock
**Trigger:** reel count reaches 20, not signed in.
**Why:** maximum accumulated value, so maximum to lose. Goal gradient
territory, where effort accelerates toward a visible finish line.

> That is 20 reels. Sign in to keep saving and it is all still here: {link}

### M7 — saved past the lock
**Trigger:** a reel arrives while `locked`. **Repeatable**, subject to cooldown.
**Why:** never reject their reel. Buffer it, and make signing in pay off
instantly instead of merely unblocking them.

> Holding that one for you. Sign in and it saves straight away: {link}

### M8 — recovery
**Trigger:** any message with no reel in it. **Repeatable**, subject to
cooldown.
**Why:** the DM thread is the only way back to their library. Their Instagram
id is permanent, so any message must be able to regenerate the link. Deleting
the conversation must never cost someone their account.

> Here is your library: {link}

## 5. Precedence

If more than one applies, highest wins and the rest are dropped, not queued:

`M6 lock` → `M5 heads up` → `M4 home screen` → `M7 past lock` → `M2 ready` →
`M8 recovery` → `M3 last call`

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
