import sqlite3
import os
from datetime import datetime, UTC

DB_PATH = 'server/database.db'

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Users table - added energy, last_daily_reward, rank
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT,
        photo TEXT,
        gold REAL DEFAULT 100.0,
        ton REAL DEFAULT 0.0,
        usdt REAL DEFAULT 0.0,
        energy INTEGER DEFAULT 100,
        rank TEXT DEFAULT 'برونزي III',
        last_mining_time TEXT,
        last_daily_reward TEXT,
        referrer TEXT,
        banned INTEGER DEFAULT 0
    )
    ''')

    # Buildings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS buildings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT,
        type TEXT,
        level INTEGER DEFAULT 1,
        col INTEGER,
        row INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Tasks table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        reward_gold REAL DEFAULT 0,
        reward_ton REAL DEFAULT 0,
        reward_usdt REAL DEFAULT 0,
        type TEXT,
        link TEXT,
        chat_id TEXT
    )
    ''')

    # Completed tasks junction table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS completed_tasks (
        user_id TEXT,
        task_id INTEGER,
        PRIMARY KEY (user_id, task_id),
        FOREIGN KEY (user_id) REFERENCES users (id),
        FOREIGN KEY (task_id) REFERENCES tasks (id)
    )
    ''')

    # Withdrawals table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS withdrawals (
        id TEXT PRIMARY KEY,
        user_id TEXT,
        amount REAL,
        currency TEXT,
        status TEXT DEFAULT 'pending',
        timestamp TEXT,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')

    # Admin Logs table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        action TEXT,
        admin_id TEXT,
        timestamp TEXT,
        details TEXT
    )
    ''')

    # Global settings table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS global_settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    ''')

    # Default settings
    settings = [
        ('starting_gold', '100.0'),
        ('starting_ton', '0.0'),
        ('starting_usdt', '0.0'),
        ('base_mining_rate', '10.0'),
        ('maintenance_mode', '0'),
        ('referral_percent', '10'),
        ('market_enabled', '1'),
        ('swap_rates', '{"gold_to_ton": 0.0001, "gold_to_usdt": 0.0005}')
    ]
    cursor.executemany('INSERT OR IGNORE INTO global_settings (key, value) VALUES (?, ?)', settings)

    # Default tasks
    default_tasks = [
        ("انضم لقناة المطور", 1000, 0, 0, "telegram", "https://t.me/khaledsaleman", "@khaledsaleman"),
        ("تابعنا على تويتر", 500, 0, 0, "link", "https://x.com/example", None),
        ("مشاهدة فيديو تعليمي", 0, 0, 0.1, "link", "https://youtube.com/example", None)
    ]
    cursor.execute("SELECT COUNT(*) FROM tasks")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO tasks (title, reward_gold, reward_ton, reward_usdt, type, link, chat_id) VALUES (?, ?, ?, ?, ?, ?, ?)', default_tasks)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_db()
