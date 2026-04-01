def create_tables(connection):
    cursor = connection.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS models (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        full_name TEXT NOT NULL,
        telegram_username TEXT NOT NULL UNIQUE,
        telegram_id INTEGER,
        portfolio_link TEXT NOT NULL,
        added_by_admin_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (added_by_admin_id) REFERENCES admins(id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS castings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        admin_id INTEGER NOT NULL,
        message_id INTEGER NOT NULL,
        channel_id INTEGER NOT NULL,
        is_closed INTEGER NOT NULL DEFAULT 0,
        is_deleted INTEGER NOT NULL DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS responses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        casting_id INTEGER NOT NULL,
        model_id INTEGER NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(casting_id, model_id),
        FOREIGN KEY (casting_id) REFERENCES castings(id),
        FOREIGN KEY (model_id) REFERENCES models(id)
    )
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