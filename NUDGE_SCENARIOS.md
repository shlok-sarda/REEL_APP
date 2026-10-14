# Nudge scenarios, run against the live code

Generated 2026-10-14 16:24 UTC by `scripts/simulate_nudges.py` against a throwaway database. Every reply below came from `app.services.nudge.fire()`, the exact function production calls; only the Instagram Graph calls themselves were replaced with recorders. Re-run this after any change to `app/services/nudge.py` to see every situation at once.

`[Open my library]` is a button under the message. `(Is it free)` is a chip above the keyboard. Before every message the person sees "seen" and then the typing dots.

| Situation | Condition | What gets sent |
|---|---|---|
| Reel 1 saved (before processing) | instant, on save | Got it. I am watching that reel now. Your library link comes back here in a few minutes. |
| Reel 1 finishes processing | once ever, carries 1-of-5 | Saved your first reel. That is 1 of 5. Send a few more and shelves start appearing on your Home. [Open my library] |
| Reel 2 finishes processing | active, not a milestone | (nothing sent) |
| Reel 3 finishes processing | active, not a milestone | (nothing sent) |
| Reel 4 finishes processing | active, not a milestone | (nothing sent) |
| Reel 5 finishes processing | crosses the home-screen line | 5 reels in. Put ClipNest on your home screen so this link is never buried in DMs again. [Open my library] |
| Reels 6 through 16 finish | 11 reels, all silent (shown once) | (nothing sent) |
| Reel 17 finishes processing | crosses the heads-up line | 17 saved. At 20 I will ask you to sign in with Google, so your library is safe if this chat ever disappears. One tap, nothing moves. [Sign in now] |
| Reels 18 and 19 finish | silent | (nothing sent) |
| Reel 20 finishes processing | hits the lock | That is 20 reels. Sign in to keep saving. Everything you have stays exactly where it is. [Sign in to keep them] |
| Reel 21 arrives | GUEST_LOCK_ENABLED=1: held, not processed | Holding that one for you. Sign in and it saves straight away. [Sign in to keep them] |
| Reels actually processed after 21 sends | 20 (the 21st was held, costs nothing) | - |
| 23 hours since their last message, 1 reel saved | the quiet nudge, early-journey wording | You saved your first reel yesterday. Send me one more and I can start grouping them. |
| The 150s sweep runs again immediately after | same dormancy: must stay silent | (nothing sent) |
| They replied, then went quiet again | fresh dormancy: nudges again | (nothing sent) |
| 23 hours quiet, 3 reels saved (short of 5) | quiet nudge, mid-journey wording | 3 saved so far. A few more and they sort themselves onto shelves. |
| 23 hours quiet, 8 reels saved (past 5) | quiet nudge, established-library wording | Still here whenever you find something worth keeping. [Open my library] |
| 25 hours since their last message | window is shut: permanently silent | (nothing sent) |
| Their first reel fails two minutes after the ack | must not be eaten by the cooldown the ack just started | I could not read that one. Private, deleted, or a photo post are the usual reasons. Try another reel. |
| A second reel fails right after | one failure reply per cooldown, not one per reel | (nothing sent) |
| They share a reel the bot cannot find a link in | says it did not save, and how to send it instead | I could not find the reel in that message. Open the reel, tap the three dots, Copy link, and paste it here. |
| First reel, with 12 other new people's reels ahead of it | says the real wait (2 minutes a reel, rounded up to 5) | Got it. A few reels are ahead of yours, so this one takes about 25 minutes. I will message you here the moment it is ready. |
| A real user, not in GUEST_TEST_SENDERS, saves a reel | the gate that protects everyone else | (nothing sent) |
| A converted user (signed in with Google) saves another reel | the bot already got what it wanted | (nothing sent) |
| Reel 2 finishes a moment after reel 1 | not a milestone: silent regardless of cooldown | (nothing sent) |
| A second reel is held seconds after the lock fires | repeatable M7 respects cooldown: correctly silent | (nothing sent) |
| Sends a reel they already saved | nothing queued or paid for; the title is not quoted | You already have that one. It is in your library. [Open my library] |
| Sends a reel they already saved, which has no title | same reply: titles are never quoted | You already have that one. It is in your library. [Open my library] |
| They share a post or a photo instead of a reel | told reels only; a pasted /p/ link still saves, most were videos | I only save reels for now, not posts or photos. Share a reel and I will add it. |
| A later reel fails, and they already have a library | the failure reply carries the library button | I could not read that one. Private, deleted, or a photo post are the usual reasons. Try another reel. [Open my library] |
| Types 'delete my data' | acknowledged only; the deleting is done by hand from the health page | Got it. Your data will be deleted within 7 days. |
| A signed in user types 'delete my data' | the one question a signed in user is always answered on | Got it. Your data will be deleted within 7 days. |
| Their 51st reel of the month arrives | said once a month; the reel is not read or paid for | That is this month's 50 reels. New reels save again from the 1st. Everything already saved is still there. [Open my library] |
| A 52nd arrives | already told this month: silent | (nothing sent) |
| Three reels arrive at once past the lock | one message, carrying the count | Holding 3 reels for you. Sign in and they all save at once. [Sign in to keep them] |
| A guest sends a reel after 10 days without one | welcome back, since later reels are otherwise silent | Saved. Your library is where you left it. [Open my library] |
| A brand new person's first reel counts as returning | the first reel acknowledgement wins | Got it. I am watching that reel now. Your library link comes back here in a few minutes. |
| A signed in user's reel cannot be read | told, with their library button | I could not read that one. Private, deleted, or a photo post are the usual reasons. Try another reel. [Open my library] |
| First library message, but Instagram rejects the button | falls back to the plain text with the link, never silence | Saved your first reel. Here is your library: https://clipnest.in/g/f_8dQt-EdCvDo7kpM-8EcGiXLRg6ytbczxNjzhXUF_4 That is 1 of 5. Send a few more and shelves start appearing on your Home. |
| Unreadable share, but Instagram rejects the chips | same words go out as plain text | I could not find the reel in that message. Open the reel, tap the three dots, Copy link, and paste it here. |
