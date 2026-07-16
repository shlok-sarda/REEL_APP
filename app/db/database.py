import sqlite3
from contextlib import contextmanager

from app.config import settings


def ensure_db_parent():
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)


def _configure(connection: sqlite3.Connection) -> sqlite3.Connection:
    connection.row_factory = sqlite3.Row
    # WAL lets readers proceed while a write transaction is open. Without it,
    # any slow write (worker finishing a reel, library rebuild) turns
    # concurrent web requests — including Meta's webhook delivery, which
    # disables itself after repeated 5xx — into "database is locked" errors.
    connection.execute("PRAGMA journal_mode=WAL")
    # Queue behind a busy writer instead of throwing immediately.
    connection.execute("PRAGMA busy_timeout=15000")
    # Standard WAL pairing: fsync on checkpoint rather than on every commit.
    connection.execute("PRAGMA synchronous=NORMAL")
    return connection


@contextmanager
def get_connection():
    ensure_db_parent()
    connection = _configure(sqlite3.connect(settings.database_path, timeout=15))
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
