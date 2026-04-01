from database.db import get_connection


def create_casting(title, description, admin_id, message_id, channel_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO castings (
            title,
            description,
            admin_id,
            message_id,
            channel_id
        )
        VALUES (?, ?, ?, ?, ?)
        """,
        (title.strip(), description.strip(), admin_id, message_id, channel_id),
    )
    conn.commit()

    return cursor.lastrowid


def get_casting_by_message(channel_id, message_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM castings
        WHERE channel_id = ? AND message_id = ? AND is_deleted = 0
        """,
        (channel_id, message_id),
    )
    return cursor.fetchone()


def get_castings_by_admin(admin_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            c.*,
            COUNT(r.id) AS responses_count
        FROM castings c
        LEFT JOIN responses r ON r.casting_id = c.id
        WHERE c.admin_id = ? AND c.is_deleted = 0
        GROUP BY c.id
        ORDER BY c.created_at DESC, c.id DESC
        """,
        (admin_id,),
    )
    return cursor.fetchall()


def get_casting_by_id_for_admin(casting_id, admin_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            c.*,
            COUNT(r.id) AS responses_count
        FROM castings c
        LEFT JOIN responses r ON r.casting_id = c.id
        WHERE c.id = ? AND c.admin_id = ? AND c.is_deleted = 0
        GROUP BY c.id
        """,
        (casting_id, admin_id),
    )
    return cursor.fetchone()


def close_casting(casting_id, admin_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE castings
        SET is_closed = 1
        WHERE id = ? AND admin_id = ? AND is_deleted = 0
        """,
        (casting_id, admin_id),
    )
    conn.commit()

    return cursor.rowcount > 0


def delete_casting(casting_id, admin_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE castings
        SET is_deleted = 1
        WHERE id = ? AND admin_id = ? AND is_deleted = 0
        """,
        (casting_id, admin_id),
    )
    conn.commit()

    return cursor.rowcount > 0


def response_exists(casting_id, model_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT id
        FROM responses
        WHERE casting_id = ? AND model_id = ?
        """,
        (casting_id, model_id),
    )
    return cursor.fetchone() is not None


def save_response(casting_id, model_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO responses (casting_id, model_id)
        VALUES (?, ?)
        """,
        (casting_id, model_id),
    )
    conn.commit()


def get_responses_for_casting(casting_id, admin_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            m.full_name,
            m.telegram_username,
            m.portfolio_link,
            r.created_at
        FROM responses r
        JOIN models m ON m.id = r.model_id
        JOIN castings c ON c.id = r.casting_id
        WHERE r.casting_id = ? AND c.admin_id = ? AND c.is_deleted = 0
        ORDER BY r.created_at DESC, r.id DESC
        """,
        (casting_id, admin_id),
    )
    return cursor.fetchall()