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
    CREATE TABLE IF NOT EXISTS instagram_link_tokens (
        code TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        used_at TEXT NOT NULL DEFAULT '',
        instagram_user_id TEXT NOT NULL DEFAULT '',
        instagram_username TEXT NOT NULL DEFAULT '',
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
    CREATE TABLE IF NOT EXISTS reel_processing_diagnostics (
        reel_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        url TEXT NOT NULL DEFAULT '',
        caption_present INTEGER NOT NULL DEFAULT 0,
        hashtags_present INTEGER NOT NULL DEFAULT 0,
        creator_present INTEGER NOT NULL DEFAULT 0,
        transcript_present INTEGER NOT NULL DEFAULT 0,
        transcript_status TEXT NOT NULL DEFAULT '',
        transcript_model TEXT NOT NULL DEFAULT '',
        transcript_attempts INTEGER NOT NULL DEFAULT 0,
        transcript_error TEXT NOT NULL DEFAULT '',
        audio_download_status TEXT NOT NULL DEFAULT '',
        video_download_status TEXT NOT NULL DEFAULT '',
        visual_present INTEGER NOT NULL DEFAULT 0,
        visual_status TEXT NOT NULL DEFAULT '',
        visual_error TEXT NOT NULL DEFAULT '',
        media_upload_status TEXT NOT NULL DEFAULT '',
        r2_video_uploaded INTEGER NOT NULL DEFAULT 0,
        r2_thumbnail_uploaded INTEGER NOT NULL DEFAULT 0,
        processing_version TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
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
    # NOTE: no UNIQUE(reel_id, job_type, status) here — that constraint meant a
    # reel could never have a second 'failed' row, so recovery status flips and
    # claim-time cleanup raised IntegrityError once history accumulated (this
    # crashed the production worker on every claim and rolled back recovery).
    # Active-job dedup is enforced by enqueue_reel_job's existing-row check.
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
        finished_at TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS embedding_store (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        object_type TEXT NOT NULL,
        object_id TEXT NOT NULL,
        model TEXT NOT NULL,
        version TEXT NOT NULL DEFAULT '',
        vector_json TEXT NOT NULL DEFAULT '[]',
        source_text_hash TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(object_type, object_id, model, version)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS reel_item_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        reel_id TEXT NOT NULL,
        reel_item_id INTEGER NOT NULL UNIQUE,
        primary_category TEXT NOT NULL DEFAULT '',
        specific_category TEXT NOT NULL DEFAULT '',
        item_name TEXT NOT NULL DEFAULT '',
        summary TEXT NOT NULL DEFAULT '',
        item_type TEXT NOT NULL DEFAULT '',
        canonical_domain TEXT NOT NULL DEFAULT '',
        canonical_subdomains_json TEXT NOT NULL DEFAULT '[]',
        canonical_entities_json TEXT NOT NULL DEFAULT '[]',
        canonical_location TEXT NOT NULL DEFAULT '',
        vibe_json TEXT NOT NULL DEFAULT '[]',
        intent TEXT NOT NULL DEFAULT '',
        audience_context TEXT NOT NULL DEFAULT '',
        confidence_scores_json TEXT NOT NULL DEFAULT '{}',
        embedding_id INTEGER,
        interpretation_status TEXT NOT NULL DEFAULT 'pending',
        interpretation_source TEXT NOT NULL DEFAULT '',
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(reel_item_id) REFERENCES reel_items(id),
        FOREIGN KEY(reel_id) REFERENCES reels(id),
        FOREIGN KEY(embedding_id) REFERENCES embedding_store(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_interest_nodes (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        node_type TEXT NOT NULL,
        canonical_key TEXT NOT NULL,
        display_hint TEXT NOT NULL DEFAULT '',
        parent_node_id TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL DEFAULT 'active',
        save_count INTEGER NOT NULL DEFAULT 0,
        recent_save_count INTEGER NOT NULL DEFAULT 0,
        growth_velocity REAL NOT NULL DEFAULT 0,
        entropy REAL NOT NULL DEFAULT 0,
        confidence REAL NOT NULL DEFAULT 0,
        centroid_embedding_id INTEGER,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user_id, node_type, canonical_key),
        FOREIGN KEY(centroid_embedding_id) REFERENCES embedding_store(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS user_interest_edges (
        id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        from_node_id TEXT NOT NULL,
        to_node_id TEXT NOT NULL,
        edge_type TEXT NOT NULL,
        weight REAL NOT NULL DEFAULT 0,
        evidence_count INTEGER NOT NULL DEFAULT 0,
        metadata_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(user_id, from_node_id, to_node_id, edge_type)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cluster_memberships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        reel_item_id INTEGER NOT NULL,
        cluster_node_id TEXT NOT NULL,
        assignment_score REAL NOT NULL DEFAULT 0,
        assignment_reason_json TEXT NOT NULL DEFAULT '{}',
        assignment_version TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(reel_item_id) REFERENCES reel_items(id),
        UNIQUE(user_id, reel_item_id, cluster_node_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cluster_titles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        cluster_node_id TEXT NOT NULL,
        title TEXT NOT NULL,
        title_confidence REAL NOT NULL DEFAULT 0,
        generation_reason_json TEXT NOT NULL DEFAULT '{}',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cluster_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        cluster_node_id TEXT NOT NULL,
        event_type TEXT NOT NULL,
        source_cluster_ids_json TEXT NOT NULL DEFAULT '[]',
        target_cluster_ids_json TEXT NOT NULL DEFAULT '[]',
        reason_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS deep_search_documents (
        reel_id TEXT PRIMARY KEY,
        user_id TEXT NOT NULL,
        shortcode TEXT NOT NULL DEFAULT '',
        url TEXT NOT NULL DEFAULT '',
        document_json TEXT NOT NULL,
        search_terms_json TEXT NOT NULL DEFAULT '[]',
        source_version TEXT NOT NULL DEFAULT 'deep_search_v1',
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(reel_id) REFERENCES reels(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS maintenance_flags (
        flag TEXT PRIMARY KEY,
        executed_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS instagram_webhook_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at TEXT NOT NULL,
        kind TEXT NOT NULL DEFAULT '',
        sender_id TEXT NOT NULL DEFAULT '',
        sender_username TEXT NOT NULL DEFAULT '',
        link_code TEXT NOT NULL DEFAULT '',
        outcome TEXT NOT NULL DEFAULT '',
        detail TEXT NOT NULL DEFAULT ''
    )
    """,
    # ---- Smart folders (search -> list + auto-routing). Learned, user-owned
    # folders, distinct from personalization clusters. See app/services/folders.py.
    """
    CREATE TABLE IF NOT EXISTS user_folders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT NOT NULL DEFAULT '',
        query TEXT NOT NULL DEFAULT '',
        profile_vector_json TEXT NOT NULL DEFAULT '[]',
        profile_basis TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS folder_memberships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT NOT NULL,
        folder_id INTEGER NOT NULL,
        reel_id TEXT NOT NULL,
        source TEXT NOT NULL DEFAULT 'manual',
        status TEXT NOT NULL DEFAULT 'member',
        score REAL NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        UNIQUE(folder_id, reel_id),
        FOREIGN KEY(folder_id) REFERENCES user_folders(id),
        FOREIGN KEY(reel_id) REFERENCES reels(id)
    )
    """,
]

USER_EXTRA_COLUMNS = {
    "google_sub": "TEXT",
    "email": "TEXT NOT NULL DEFAULT ''",
    "picture_url": "TEXT NOT NULL DEFAULT ''",
    "telegram_username": "TEXT NOT NULL DEFAULT ''",
    "instagram_user_id": "TEXT NOT NULL DEFAULT ''",
    "instagram_username": "TEXT NOT NULL DEFAULT ''",
    "last_login_at": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
}

# Same migrate-by-ALTER pattern for reels: a long-lived production table was
# created by an older CREATE TABLE and silently lacks columns that newer code
# UPDATEs — the statement then throws "no such column" and rolls back whatever
# transaction it was part of (this froze queue recovery in production).
REEL_EXTRA_COLUMNS = {
    "media_status": "TEXT NOT NULL DEFAULT 'not_downloaded'",
    "local_video_path": "TEXT NOT NULL DEFAULT ''",
    "thumbnail_path": "TEXT NOT NULL DEFAULT ''",
    "source": "TEXT NOT NULL DEFAULT 'telegram'",
    "created_at": "TEXT NOT NULL DEFAULT ''",
    "updated_at": "TEXT NOT NULL DEFAULT ''",
}


PROCESSING_JOBS_COLUMNS = (
    "id, reel_id, user_id, job_type, status, attempts, error_message, created_at, started_at, finished_at"
)


def _migrate_processing_jobs_unique_constraint(connection) -> None:
    """Rebuild processing_jobs if it still carries UNIQUE(reel_id, job_type, status).

    The constraint lives in the table DDL (sqlite autoindex), so it can't be
    dropped — the table must be rebuilt. Written to be resumable: if a previous
    attempt renamed the old table but died before copying, the next boot
    finishes the copy instead of losing rows.
    """
    legacy = connection.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'processing_jobs_legacy_unique'"
    ).fetchone()
    if not legacy:
        row = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'processing_jobs'"
        ).fetchone()
        if not row or "UNIQUE" not in (row["sql"] or "").upper():
            return
        connection.execute("ALTER TABLE processing_jobs RENAME TO processing_jobs_legacy_unique")
        create_statement = next(s for s in SCHEMA_STATEMENTS if "processing_jobs" in s)
        connection.execute(create_statement)
    connection.execute(
        f"""
        INSERT OR IGNORE INTO processing_jobs ({PROCESSING_JOBS_COLUMNS})
        SELECT {PROCESSING_JOBS_COLUMNS} FROM processing_jobs_legacy_unique
        """
    )
    connection.execute("DROP TABLE processing_jobs_legacy_unique")
    # Hygiene while we're here: tonight's recovery may have left duplicate
    # pending rows for the same reel; keep the oldest of each group.
    connection.execute(
        """
        DELETE FROM processing_jobs
        WHERE status = 'pending'
          AND id NOT IN (
              SELECT MIN(id) FROM processing_jobs
              WHERE status = 'pending'
              GROUP BY reel_id, job_type
          )
        """
    )


def create_tables():
    with get_connection() as connection:
        for statement in SCHEMA_STATEMENTS:
            connection.execute(statement)
        _migrate_processing_jobs_unique_constraint(connection)
        existing_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(users)").fetchall()
        }
        for column_name, column_type in USER_EXTRA_COLUMNS.items():
            if column_name not in existing_columns:
                connection.execute(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}")
        existing_reel_columns = {
            row["name"]
            for row in connection.execute("PRAGMA table_info(reels)").fetchall()
        }
        for column_name, column_type in REEL_EXTRA_COLUMNS.items():
            if column_name not in existing_reel_columns:
                connection.execute(f"ALTER TABLE reels ADD COLUMN {column_name} {column_type}")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_google_sub ON users(google_sub) WHERE google_sub IS NOT NULL AND google_sub != ''")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_instagram_user_id ON users(instagram_user_id) WHERE instagram_user_id IS NOT NULL AND instagram_user_id != ''")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_reel_item_features_user_id ON reel_item_features(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_reel_item_features_reel_item_id ON reel_item_features(reel_item_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_interest_nodes_user_node_type ON user_interest_nodes(user_id, node_type)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_interest_edges_user_id ON user_interest_edges(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_cluster_memberships_user_id ON cluster_memberships(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_cluster_titles_cluster_node_id ON cluster_titles(cluster_node_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_deep_search_documents_user_id ON deep_search_documents(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_deep_search_documents_shortcode ON deep_search_documents(shortcode)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_user_folders_user_id ON user_folders(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_folder_memberships_user_id ON folder_memberships(user_id)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_folder_memberships_folder_id ON folder_memberships(folder_id)")


def ensure_default_user():
    with get_connection() as connection:
        connection.execute(
            """
            INSERT OR IGNORE INTO users (
                id, telegram_user_id, display_name, created_at, google_sub, email,
                picture_url, telegram_username, instagram_user_id, instagram_username, last_login_at, updated_at
            )
            VALUES (?, ?, ?, datetime('now'), NULL, '', '', '', '', '', '', datetime('now'))
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
