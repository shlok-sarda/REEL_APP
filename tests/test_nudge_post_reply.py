"""Every post or photo share gets its reply, signed in or not, at any count.
Plain python:

    python3 tests/test_nudge_post_reply.py
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

work = Path(tempfile.mkdtemp(prefix="nudge_test_"))
os.environ.update({"DATABASE_URL": f"sqlite:///{work / 'app.db'}", "STORAGE_DIR": str(work / "st")})

from app.services import nudge  # noqa: E402

failures: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + name + (f" :: {detail}" if detail and not ok else ""))
    if not ok:
        failures.append(name)


def user(signed_in: bool, n: int, sent: set[str] | None = None) -> dict:
    return {"id": "u1", "signed_in": signed_in, "reel_count": n, "already_sent": sent or set(), "last_sent_at": {}}


for signed_in in (False, True):
    who = "signed in" if signed_in else "guest"
    for n in (1, 3, 5, 9, 17, 48, 100):
        got = nudge.decide(user(signed_in, n, {"m15_photo_post", "m1_first_ack", "m2_first_library"}), "photo_post")
        check(f"{who} post at reel {n} gets the photo line", got == "m15_photo_post", str(got))
    got = nudge.decide(user(signed_in, 30), "unreadable_share")
    check(f"{who} share with no link gets told to copy it", got == "m16_unreadable_share", str(got))
    got = nudge.decide(user(signed_in, 30), "reel_failed")
    check(f"{who} failed reel still answered", got == "m9_could_not_read", str(got))

# Nothing else changed for signed in people: a saved reel is still quiet.
for trigger in ("reel_saved", "reel_ready", "already_saved", "timer"):
    got = nudge.decide(user(True, 30), trigger)
    check(f"signed in {trigger} stays quiet", got is None, str(got))
check("guest reel 3 still quiet", nudge.decide(user(False, 3, {"m1_first_ack", "m2_first_library"}), "reel_ready") is None)

print()
print("ALL PASS" if not failures else f"{len(failures)} FAILED")
sys.exit(1 if failures else 0)
