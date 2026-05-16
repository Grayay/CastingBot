from config import BOOKER_IDS, CHIEF_BOOKER_IDS, parse_id_list


LEGACY_BOOKER_IDS_SEEDED_KEY = "legacy_booker_ids_seeded"


def _get_connection(connection=None):
    if connection is not None:
        return connection

    from database.db import get_connection

    return get_connection()


def _normalize_telegram_id(user_id):
    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def _row_value(row, key):
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    return getattr(row, key, None)


def _normalize_id_list(values):
    if values is None:
        return []
    if isinstance(values, str):
        return parse_id_list(values)
    return parse_id_list(",".join(str(value) for value in values))


def ensure_authorized_bookers_schema(connection=None):
    conn = _get_connection(connection)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS authorized_bookers (
            telegram_id BIGINT PRIMARY KEY,
            username TEXT NULL,
            full_name TEXT NULL,
            added_by BIGINT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.commit()


def ensure_access_control_meta_schema(connection=None):
    conn = _get_connection(connection)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS access_control_meta (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.commit()


def _set_access_control_meta(conn, key, value):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO access_control_meta (key, value, updated_at)
        VALUES (%s, %s, NOW())
        ON CONFLICT (key)
        DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
        """,
        (key, value),
    )


def seed_legacy_booker_ids_once(connection=None, legacy_ids=None):
    conn = _get_connection(connection)
    ensure_authorized_bookers_schema(conn)
    ensure_access_control_meta_schema(conn)

    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT value
        FROM access_control_meta
        WHERE key = %s
        """,
        (LEGACY_BOOKER_IDS_SEEDED_KEY,),
    )
    seeded_meta = cursor.fetchone()
    if str(_row_value(seeded_meta, "value")).strip().lower() == "true":
        return 0

    seeded_count = 0
    for telegram_id in _normalize_id_list(BOOKER_IDS if legacy_ids is None else legacy_ids):
        cursor.execute(
            """
            INSERT INTO authorized_bookers (telegram_id, added_by)
            VALUES (%s, NULL)
            ON CONFLICT (telegram_id) DO NOTHING
            """,
            (telegram_id,),
        )
        seeded_count += max(cursor.rowcount or 0, 0)

    _set_access_control_meta(conn, LEGACY_BOOKER_IDS_SEEDED_KEY, "true")
    conn.commit()
    print(f"event=legacy_booker_ids_seeded count={seeded_count}")
    return seeded_count


def bootstrap_access_control(connection=None):
    conn = _get_connection(connection)
    return seed_legacy_booker_ids_once(conn)


def is_chief_booker(user_id):
    telegram_id = _normalize_telegram_id(user_id)
    if telegram_id is None:
        return False
    return telegram_id in CHIEF_BOOKER_IDS


def _is_regular_authorized_booker(user_id, connection=None):
    telegram_id = _normalize_telegram_id(user_id)
    if telegram_id is None:
        return False

    conn = _get_connection(connection)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT telegram_id
        FROM authorized_bookers
        WHERE telegram_id = %s
        """,
        (telegram_id,),
    )
    return cursor.fetchone() is not None


def is_authorized_booker(user_id, connection=None):
    if is_chief_booker(user_id):
        return True
    return _is_regular_authorized_booker(user_id, connection)


def add_authorized_booker(telegram_id, username=None, full_name=None, added_by=None, connection=None):
    telegram_id = _normalize_telegram_id(telegram_id)
    if telegram_id is None:
        return False

    conn = _get_connection(connection)
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO authorized_bookers (telegram_id, username, full_name, added_by)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (telegram_id) DO NOTHING
        RETURNING telegram_id
        """,
        (telegram_id, username, full_name, added_by),
    )
    created = cursor.fetchone() is not None
    conn.commit()
    return created


def remove_authorized_booker(telegram_id, connection=None):
    telegram_id = _normalize_telegram_id(telegram_id)
    if telegram_id is None or is_chief_booker(telegram_id):
        return False

    conn = _get_connection(connection)
    cursor = conn.cursor()
    cursor.execute(
        """
        DELETE FROM authorized_bookers
        WHERE telegram_id = %s
        """,
        (telegram_id,),
    )
    conn.commit()
    return cursor.rowcount > 0


def list_authorized_bookers(connection=None):
    conn = _get_connection(connection)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT telegram_id, username, full_name, added_by, created_at
        FROM authorized_bookers
        ORDER BY telegram_id ASC
        """
    )
    return cursor.fetchall()
