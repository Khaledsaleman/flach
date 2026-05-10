import sqlite3
import os

DB_PATH = 'server/database.db'

def update_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Add wallet_address to users if not exists
    try:
        cursor.execute('ALTER TABLE users ADD COLUMN wallet_address TEXT')
        print("Added wallet_address to users table")
    except sqlite3.OperationalError:
        print("wallet_address already exists in users table")

    # Update withdrawals table
    # Since SQLite doesn't support easy ALTER TABLE for multiple columns or if table is complex,
    # we check if columns exist.

    columns = [info[1] for info in cursor.execute('PRAGMA table_info(withdrawals)').fetchall()]

    if 'address' not in columns:
        cursor.execute('ALTER TABLE withdrawals ADD COLUMN address TEXT')
        print("Added address to withdrawals table")

    if 'rejection_reason' not in columns:
        cursor.execute('ALTER TABLE withdrawals ADD COLUMN rejection_reason TEXT')
        print("Added rejection_reason to withdrawals table")

    # Also add daily_tasks_progress and referral_rewards_balance if missing (though they seem to be used in app.py)
    # Looking at app.py, it uses daily_tasks_progress from users table.
    if 'daily_tasks_progress' not in columns:
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN daily_tasks_progress TEXT')
            print("Added daily_tasks_progress to users table")
        except sqlite3.OperationalError:
            pass

    if 'referral_rewards_balance' not in columns:
        try:
            cursor.execute('ALTER TABLE users ADD COLUMN referral_rewards_balance TEXT')
            print("Added referral_rewards_balance to users table")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

if __name__ == "__main__":
    update_db()
