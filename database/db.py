import sqlite3
from pathlib import Path

from database.models import create_tables


DB_PATH = Path(__file__).resolve().parent / "bot.db"

_connection = None


def get_connection():
    global _connection

    if _connection is None:
        _connection = sqlite3.connect(DB_PATH)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA foreign_keys = ON")
        create_tables(_connection)

    return _connection