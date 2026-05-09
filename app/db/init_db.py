import csv
import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app.config import settings
from app.db.database import get_connection


SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        telegram_user_id TEXT UNIQUE,
        display_name TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS telegram_link_tokens (
        code TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT NOT NULL DEFAULT '',
        telegram_user_id TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reels (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        url TEXT NOT NULL,
        shortcode TEXT NOT NULL DEFAULT '',
        received_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending',
        media_status TEXT NOT NULL DEFAULT 'not_downloaded',
        local_video_path TEXT NOT NULL DEFAULT '',
        thumbnail_path TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL DEFAULT 'telegram',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user_id, url),
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reel_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reel_id TEXT NOT NULL,
        primary_category TEXT NOT NULL DEFAULT '',
        secondary_category TEXT NOT NULL DEFAULT '',
        item_name TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(reel_id) REFERENCES reels(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS product_links (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reel_item_id INTEGER NOT NULL,
        product_name TEXT NOT NULL DEFAULT '',
        brand TEXT NOT NULL DEFAULT '',
        model TEXT NOT NULL DEFAULT '',
        product_type TEXT NOT NULL DEFAULT '',
        search_query TEXT NOT NULL DEFAULT '',
        best_buy_link TEXT NOT NULL DEFAULT '',
        amazon_link TEXT NOT NULL DEFAULT '',
        flipkart_link TEXT NOT NULL DEFAULT '',
        nykaa_link TEXT NOT NULL DEFAULT '',
        FOREIGN KEY(reel_item_id) REFERENCES reel_items(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS processing_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        reel_id TEXT NOT NULL,
        user_id TEXT NOT NULL DEFAULT 'default',
        job_type TEXT NOT NULL DEFAULT 'process_reel',
        status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0,
        error_message TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        started_at TEXT NOT NULL DEFAULT '',
        finished_at TEXT NOT NULL DEFAULT '',
        UNIQUE(reel_id, job_type, status)
    )
    """,
]

USER_EXTRA_COLUMNS = {
    "google_sub": "TEXT",
    "email": "TEXT NOT NULL DEFAULT ''",
    "picture_url": "TEXT NOT NULL DEFAULT ''",
    "telegram_username": "TEXT NOT NULL DEFAULT ''",
    "last_login_at": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
}


def create_tables():
    with get_connection() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        for column_name, column_type in USER_EXTRA_COLUMNS.items():
            if column_name not in existing_columns:
                connection.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL AND google_sub != ''")


def ensure_default_user():
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO users (
                id, telegram_user_id, display_name, created_at, google_sub, email,
                picture_url, telegram_username, last_login_at, updated_at
            )
            VALUES (?, ?, ?, datetime('now'), NULL, '', '', '', '', datetime('now'))
            """,
            ("default", "default", "Default User"),
        )


def import_legacy_reel_csv(csv_path: Path | None = None):
    csv_path = csv_path or settings.reel_urls_csv
    if not csv_path.exists():
        return

    with get_connection() as connection:
        existing_count = connection.execute("SELECT COUNT(*) FROM reels").fetchone()[0]
        if existing_count and csv_path.stat().st_size == 0:
            return

        with csv_path.open(newline="", encoding="utf-8") as infile:
            reader = csv.DictReader(infile)
            for row in reader:
                reel_id = (row.get("id") or "").strip()
                url = (row.get("url") or "").strip()
                received_at = (row.get("received_at") or "").strip()
                if not reel_id or not url:
                    continue
                connection.execute(
                    """
                    INSERT OR IGNORE INTO reels (
                        id, user_id, url, shortcode, received_at, status, media_status,
                        local_video_path, thumbnail_path, source, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        reel_id,
                        "default",
                        url,
                        "",
                        received_at or "",
                        "pending",
                        "not_downloaded",
                        "",
                        "",
                        "telegram",
                        received_at or "",
                        received_at or "",
                    ),
                )


def initialize_database():
    create_tables()
    ensure_default_user()
    import_legacy_reel_csv()


def main():
    initialize_database()
    print(f"Database ready at: {settings.database_path}")


if __name__ == "__main__":
    main()
