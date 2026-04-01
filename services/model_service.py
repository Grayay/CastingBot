import sqlite3
from database.db import get_connection


def normalize_username(username):
    if not username:
        return None
    username = username.strip().lower().lstrip("@")
    if not username:
        return None
    return "@" + username


def get_or_create_admin_db_id(admin_telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT id FROM admins WHERE telegram_id = ?",
        (admin_telegram_id,),
    )
    admin = cursor.fetchone()
    if admin:
        return admin["id"]

    cursor.execute(
        """
        INSERT INTO admins (telegram_id)
        VALUES (?)
        """,
        (admin_telegram_id,),
    )
    conn.commit()
    return cursor.lastrowid


def create_model(full_name, telegram_username, portfolio_link, added_by_admin_id):
    conn = get_connection()
    cursor = conn.cursor()

    normalized_username = normalize_username(telegram_username)
    if not normalized_username:
        return False, "Введите корректный username модели."

    admin_db_id = get_or_create_admin_db_id(added_by_admin_id)

    try:
        cursor.execute(
            """
            INSERT INTO models (
                full_name,
                telegram_username,
                portfolio_link,
                added_by_admin_id
            )
            VALUES (?, ?, ?, ?)
            """,
            (full_name.strip(), normalized_username, portfolio_link.strip(), admin_db_id),
        )
        conn.commit()
        return True, None
    except sqlite3.IntegrityError as e:
        return False, f"DB ERROR: {str(e)}"


def get_model_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM models WHERE telegram_username = ?",
        (normalize_username(username),),
    )
    return cursor.fetchone()


def get_model_by_telegram_id(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM models WHERE telegram_id = ?",
        (telegram_id,),
    )
    return cursor.fetchone()


def update_model_telegram_id(model_id, telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE models SET telegram_id = ? WHERE id = ?",
        (telegram_id, model_id),
    )
    conn.commit()


def find_model_for_user(telegram_id, username):
    model = get_model_by_telegram_id(telegram_id)

    if model:
        return model

    if username:
        return get_model_by_username(username)

    return None