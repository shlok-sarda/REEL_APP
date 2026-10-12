"""Show what Instagram actually sent for shares the bot could not read.

The open question before launch: when someone shares a reel with the paper
plane (not Copy link), does the message carry an instagram.com/reel/ link the
bot can find? Shares it could read are logged as "saved" with the link. Shares
it could not are logged as "ignored" with the shape of the message: its keys,
the attachment types, and the hosts of any links inside. If rows below show
attachments like ig_reel next to "no reel url found", paper plane shares are
being lost and that outranks everything else.

Reads only. Point it at a copy of the production database:

    python3 scripts/show_native_share.py ~/Desktop/prod_app.db
"""

from __future__ import annotations

import sqlite3
import sys


def main() -> None:
    if len(sys.argv) != 2:
        print(__doc__)
        sys.exit(2)
    connection = sqlite3.connect(f"file:{sys.argv[1]}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row

    span = connection.execute(
        "SELECT MIN(received_at) AS first, MAX(received_at) AS last, COUNT(*) AS n FROM instagram_webhook_events"
    ).fetchone()
    print(f"webhook log: {span['n']} rows, {span['first']} to {span['last']}")
    print("(the log keeps only its newest 200 rows, so this is a recent window)\n")

    print("reel events by outcome:")
    for row in connection.execute(
        "SELECT outcome, COUNT(*) AS n FROM instagram_webhook_events WHERE kind = 'reel' GROUP BY outcome ORDER BY n DESC"
    ):
        print(f"  {row['n']:>4}  {row['outcome']}")

    rows = connection.execute(
        """
        SELECT received_at, sender_username, outcome, detail
        FROM instagram_webhook_events
        WHERE detail LIKE '%msg_keys%' AND detail LIKE '%attachments%'
        ORDER BY id DESC
        LIMIT 25
        """
    ).fetchall()
    print(f"\nshares with an attachment the bot found no reel link in: {len(rows)}")
    for row in rows:
        print(f"\n  {row['received_at']}  @{row['sender_username'] or '?'}  {row['outcome']}")
        print(f"    {row['detail']}")
    if not rows:
        print("  none in this window. Share one reel with the paper plane from a test account, then run this again.")


if __name__ == "__main__":
    main()
