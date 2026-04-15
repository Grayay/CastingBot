def create_tables(connection):
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id BIGSERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        name TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS models (
        id BIGSERIAL PRIMARY KEY,
        full_name TEXT NOT NULL,
        telegram_username TEXT NOT NULL UNIQUE,
        telegram_id BIGINT,
        added_by_admin_id BIGINT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        FOREIGN KEY (added_by_admin_id) REFERENCES admins(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS castings (
        id BIGSERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        admin_id BIGINT NOT NULL,
        message_id BIGINT NOT NULL,
        channel_id BIGINT NOT NULL,
        is_closed BOOLEAN NOT NULL DEFAULT FALSE,
        is_deleted BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS responses (
        id BIGSERIAL PRIMARY KEY,
        casting_id BIGINT NOT NULL,
        model_id BIGINT NOT NULL,
        comment TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        UNIQUE(casting_id, model_id),
        FOREIGN KEY (casting_id) REFERENCES castings(id),
        FOREIGN KEY (model_id) REFERENCES models(id)
    )
    """)

    cursor.execute("""
    ALTER TABLE responses
    ADD COLUMN IF NOT EXISTS comment TEXT
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_castings_admin_id
    ON castings(admin_id)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_castings_message_lookup
    ON castings(channel_id, message_id)
    """)

    cursor.execute("""
    CREATE INDEX IF NOT EXISTS idx_responses_casting_id
    ON responses(casting_id)
    """)

    connection.commit()