from database.db import get_connection


def create_casting(
    title,
    description,
    admin_id,
    message_id,
    channel_id,
    responsible_admin_name=None,
    photo_file_id=None,
):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO castings (
            title,
            description,
            admin_id,
            responsible_admin_name,
            message_id,
            channel_id,
            photo_file_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            title.strip(),
            description.strip(),
            admin_id,
            responsible_admin_name,
            message_id,
            channel_id,
            photo_file_id,
        ),
    )
    created_casting = cursor.fetchone()
    conn.commit()

    return created_casting["id"]


def get_casting_by_message(channel_id, message_id):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT *
        FROM castings
        WHERE channel_id = %s AND message_id = %s AND is_deleted = FALSE
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
        WHERE c.admin_id = %s AND c.is_deleted = FALSE
        GROUP BY c.id
        ORDER BY c.created_at DESC, c.id DESC
        """,
        (admin_id,),
    )
    return cursor.fetchall()


def get_all_castings():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT
            c.*,
            COUNT(r.id) AS responses_count
        FROM castings c
        LEFT JOIN responses r ON r.casting_id = c.id
        WHERE c.is_deleted = FALSE
        GROUP BY c.id
        ORDER BY c.created_at DESC, c.id DESC
        """
    )
    return cursor.fetchall()


def get_responsible_bookers_for_brand_title(title):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT DISTINCT
            c.admin_id,
            c.responsible_admin_name
        FROM castings c
        WHERE c.is_deleted = FALSE
          AND c.title = %s
        ORDER BY c.admin_id ASC
        """,
        (title,),
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
        WHERE c.id = %s AND c.admin_id = %s AND c.is_deleted = FALSE
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
        SET is_closed = TRUE
        WHERE id = %s AND admin_id = %s AND is_deleted = FALSE
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
        SET is_deleted = TRUE
        WHERE id = %s AND admin_id = %s AND is_deleted = FALSE
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
        WHERE casting_id = %s AND model_id = %s
        """,
        (casting_id, model_id),
    )
    return cursor.fetchone() is not None


def save_response(casting_id, model_id, comment=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO responses (casting_id, model_id, comment)
        VALUES (%s, %s, %s)
        """,
        (casting_id, model_id, comment),
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
            r.comment,
            r.created_at
        FROM responses r
        JOIN models m ON m.id = r.model_id
        JOIN castings c ON c.id = r.casting_id
        WHERE r.casting_id = %s AND c.admin_id = %s AND c.is_deleted = FALSE
        ORDER BY r.created_at DESC, r.id DESC
        """,
        (casting_id, admin_id),
    )
    return cursor.fetchall()