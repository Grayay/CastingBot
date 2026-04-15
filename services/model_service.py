from psycopg import IntegrityError

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
        "SELECT id FROM admins WHERE telegram_id = %s",
        (admin_telegram_id,),
    )
    admin = cursor.fetchone()
    if admin:
        return admin["id"]

    cursor.execute(
        """
        INSERT INTO admins (telegram_id)
        VALUES (%s)
        RETURNING id
        """,
        (admin_telegram_id,),
    )
    created_admin = cursor.fetchone()
    conn.commit()
    return created_admin["id"]


def create_model(full_name, telegram_username, added_by_admin_id):
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
                added_by_admin_id
            )
            VALUES (%s, %s, %s)
            """,
            (full_name.strip(), normalized_username, admin_db_id),
        )
        conn.commit()
        return True, None
    except IntegrityError as e:
        return False, f"DB ERROR: {str(e)}"


def get_model_by_username(username):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM models WHERE telegram_username = %s",
        (normalize_username(username),),
    )
    return cursor.fetchone()


def get_model_by_telegram_id(telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM models WHERE telegram_id = %s",
        (telegram_id,),
    )
    return cursor.fetchone()


def update_model_telegram_id(model_id, telegram_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE models SET telegram_id = %s WHERE id = %s",
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