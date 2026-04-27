import sqlite3
from contextlib import contextmanager

from app.config import settings


def ensure_db_parent():
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def get_connection():
    ensure_db_parent()
    connection = sqlite3.connect(settings.database_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()
