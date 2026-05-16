import os

from psycopg import connect
from psycopg.rows import dict_row

import config  # noqa: F401 - ensures .env is loaded
from database.models import create_tables
from services.access_control import bootstrap_access_control


_connection = None


def _required_env(name):
    value = os.getenv(name)
    if value is None or not str(value).strip():
        raise RuntimeError(f"Missing required environment variable: {name}")
    return str(value).strip()


def _build_connection_kwargs():
    kwargs = {
        "host": _required_env("POSTGRES_HOST"),
        "port": int(os.getenv("POSTGRES_PORT", "5432")),
        "dbname": _required_env("POSTGRES_DB"),
        "user": _required_env("POSTGRES_USER"),
        "password": _required_env("POSTGRES_PASSWORD"),
    }
    return kwargs


def get_connection():
    global _connection

    if _connection is None or _connection.closed:
        _connection = connect(**_build_connection_kwargs(), row_factory=dict_row)
        create_tables(_connection)
        bootstrap_access_control(_connection)

    return _connection
