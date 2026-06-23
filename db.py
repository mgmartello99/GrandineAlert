import sqlite3

DB_NAME = "bot.db"


def _connect():
    conn = sqlite3.connect(DB_NAME)
    # WAL mode: riduce il rischio di "database is locked" quando
    # l'handler Telegram e il thread del monitor accedono al DB
    # quasi in contemporanea
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = _connect()
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            chat_id INTEGER PRIMARY KEY,
            city TEXT,
            lat REAL,
            lon REAL
        )
    """)

    conn.commit()
    conn.close()


def set_city(chat_id, city, lat, lon):
    conn = _connect()
    c = conn.cursor()

    c.execute("""
        INSERT INTO users (chat_id, city, lat, lon)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(chat_id)
        DO UPDATE SET city=excluded.city,
                      lat=excluded.lat,
                      lon=excluded.lon
    """, (chat_id, city, lat, lon))

    conn.commit()
    conn.close()


def get_user(chat_id):
    conn = _connect()
    c = conn.cursor()

    c.execute("SELECT city, lat, lon FROM users WHERE chat_id=?", (chat_id,))
    row = c.fetchone()

    conn.close()
    return row


def get_all_users():
    conn = _connect()
    c = conn.cursor()

    c.execute("SELECT chat_id, city, lat, lon FROM users")
    rows = c.fetchall()

    conn.close()
    return rows