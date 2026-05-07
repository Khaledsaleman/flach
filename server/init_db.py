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
        username TEXT,
        name TEXT,
        photo TEXT,
        gold REAL DEFAULT 100.0,
        ton REAL DEFAULT 0.0,
        usdt REAL DEFAULT 0.0,
        energy INTEGER DEFAULT 100,
        power REAL DEFAULT 0.0,
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

    # Support FAQs table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS support_faqs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        answer TEXT
    )
    ''')

    # Support Agents table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS support_agents (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT,
        username TEXT,
        photo TEXT
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
        ('attack_enabled', '1'),
        ('daily_reward_amount', '100.0'),
        ('daily_task_enabled', '1'),
        ('daily_task_wins_required', '20'),
        ('daily_task_reward', '{"ton": 0.1}'),
        ('daily_task_expiry_type', 'fixed'),
        ('daily_task_expiry_value', '24'),
        ('daily_task_start_time', ''),
        ('referral_reward_per_user', '{"gold": 1000}'),
        ('referral_rewards_enabled', '1'),
        ('swap_rates', '{"gold_to_ton": 0.0001, "gold_to_usdt": 0.0005}')
    ]
    cursor.executemany('INSERT OR IGNORE INTO global_settings (key, value) VALUES (?, ?)', settings)

    # Default tasks - REMOVED AS PER REQUIREMENTS
    # default_tasks = [
    #     ("انضم لقناة المطور", 1000, 0, 0, "telegram", "https://t.me/khaledsaleman", "@khaledsaleman"),
    #     ("تابعنا على تويتر", 500, 0, 0, "link", "https://x.com/example", None),
    #     ("مشاهدة فيديو تعليمي", 0, 0, 0.1, "link", "https://youtube.com/example", None)
    # ]
    # cursor.execute("SELECT COUNT(*) FROM tasks")
    # if cursor.fetchone()[0] == 0:
    #     cursor.executemany('INSERT INTO tasks (title, reward_gold, reward_ton, reward_usdt, type, link, chat_id) VALUES (?, ?, ?, ?, ?, ?, ?)', default_tasks)

    # Default FAQs
    default_faqs = [
        ("كيف أربح GOLD؟", "يمكنك ربح الذهب من خلال ترقية مناجم الذهب في قاعدتك، الفوز في المعارك، وإكمال المهام اليومية."),
        ("كيف يعمل نظام الإحالة؟", "قم بدعوة أصدقائك باستخدام رابط الإحالة الخاص بك واربح نسبة من أرباحهم بالإضافة إلى مكافأة فورية عند انضمامهم."),
        ("كيف أسحب TON؟", "يمكنك سحب عملات TON من خلال قسم المحفظة عند وصولك للحد الأدنى للسحب."),
        ("كيف أطور القاعدة؟", "اضغط على أي مبنى في قاعدتك لرؤية متطلبات الترقية، ثم اضغط على زر ترقية إذا كنت تملك الموارد الكافية."),
        ("ماذا أفعل إذا واجهت مشكلة؟", "يمكنك التواصل مباشرة مع فريق الدعم من خلال الضغط على 'التواصل مع وكيل' في هذه القائمة.")
    ]
    cursor.execute("SELECT COUNT(*) FROM support_faqs")
    if cursor.fetchone()[0] == 0:
        cursor.executemany('INSERT INTO support_faqs (question, answer) VALUES (?, ?)', default_faqs)

    conn.commit()
    conn.close()
    print(f"Database initialized at {DB_PATH}")

if __name__ == "__main__":
    init_db()
