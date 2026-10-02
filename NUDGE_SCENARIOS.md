# Nudge scenarios, run against the live code

Generated 2026-10-02 08:18 UTC by `scripts/simulate_nudges.py` against a throwaway database. Every reply below came from `app.services.nudge.fire()`, the exact function production calls; only the Instagram Graph call itself was replaced with a recorder. Re-run this after any change to `app/services/nudge.py` to see every situation at once.

| Situation | Condition | What gets sent |
|---|---|---|
| Reel 1 saved (before processing) | instant, on save | Thank you for saving a reel with me. It is processing now, give me a couple of minutes. |
| Reel 1 finishes processing | once ever, carries 1-of-5 | Saved it as Triceps Press Down. Here is your library: https://clipnest.in/g/nRtFCwhnOLl_LK52GLPJVTQGOHosIVuFN7nS8t8PhAs That is 1 of 5. At five reels it starts grouping them for you. |
| Reel 2 finishes processing | active, not a milestone | (nothing sent) |
| Reel 3 finishes processing | active, not a milestone | (nothing sent) |
| Reel 4 finishes processing | active, not a milestone | (nothing sent) |
| Reel 5 finishes processing | crosses the home-screen line | 5 reels now. Put ClipNest on your home screen so you are not digging through DMs for this link: https://clipnest.in/g/nRtFCwhnOLl_LK52GLPJVTQGOHosIVuFN7nS8t8PhAs |
| Reels 6 through 16 finish | 11 reels, all silent (shown once) | (nothing sent) |
| Reel 17 finishes processing | crosses the heads-up line | 17 saved. At 20 you will need a free account to keep going. One tap, and everything you have stays exactly where it is. |
| Reels 18 and 19 finish | silent | (nothing sent) |
| Reel 20 finishes processing | hits the lock | That is 20 reels. Sign in to keep saving and it is all still here: https://clipnest.in/g/nRtFCwhnOLl_LK52GLPJVTQGOHosIVuFN7nS8t8PhAs |
| Reel 21 arrives | GUEST_LOCK_ENABLED=1: held, not processed | Holding that one for you. Sign in and it saves straight away: https://clipnest.in/g/nRtFCwhnOLl_LK52GLPJVTQGOHosIVuFN7nS8t8PhAs |
| Reels actually processed after 21 sends | 20 (the 21st was held, costs nothing) | - |
| 23 hours since their last message, 1 reel saved | the quiet nudge, early-journey wording | You saved Triceps Press Down yesterday. Send me one more and I can start grouping them for you. |
| The 150s sweep runs again immediately after | same dormancy: must stay silent | (nothing sent) |
| They replied, then went quiet again | fresh dormancy: nudges again | (nothing sent) |
| 23 hours quiet, 3 reels saved (short of 5) | quiet nudge, mid-journey wording | 3 saved so far. One more gets you to five, which is where it starts sorting itself. |
| 23 hours quiet, 8 reels saved (past 5) | quiet nudge, established-library wording | Still here whenever you find something worth keeping. Your library: https://clipnest.in/g/yShJPilMaFO2rSO44kdl8kXwFhmPsxWk9v7gLOcQ3fg |
| 25 hours since their last message | window is shut: permanently silent | (nothing sent) |
| They send a message with no reel in it | the DM thread is the only way back in | Here is your library: https://clipnest.in/g/GLIchjLQOi1nVFj3XIBxTzibIog3B66duqnzN2_gEO8 |
| They send a no-reel message seconds after the library link | cooldown correctly suppresses the repeat | (nothing sent) |
| A real user, not in GUEST_TEST_SENDERS, saves a reel | the gate that protects everyone else | (nothing sent) |
| A converted user (signed in with Google) saves another reel | the bot already got what it wanted | (nothing sent) |
| Reel 2 finishes a moment after reel 1 | not a milestone: silent regardless of cooldown | (nothing sent) |
| A second reel is held seconds after the lock fires | repeatable M7 respects cooldown: correctly silent | (nothing sent) |
