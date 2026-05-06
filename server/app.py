import os
import hashlib
import hmac
import json
import uuid
import sqlite3
import time
from datetime import datetime, UTC
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()

DB_PATH = 'server/database.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

app = Flask(__name__)
CORS(app)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

# Admin Configuration
ADMIN_ID = 2003253093

# In-memory store for game data (In production, use a database)
game_state = {
    "settings": {
        "maintenance_mode": False,
        "referral_percent": 10,
        "market_enabled": True,
        "swap_enabled": True,
        "swap_rates": {"gold_to_ton": 0.0001, "gold_to_usdt": 0.0005},
        "min_withdrawal": 5.0
    },
    "users": {}, # user_id -> {banned: bool, name: str, photo: str, joined: str, completed_tasks: [], balance: {gold, ton, usdt}, referrer: str}
    "tasks": [
        {"id": 1, "title": "انضم لقناة المطور", "reward": {"gold": 1000}, "type": "telegram", "link": "https://t.me/khaledsaleman", "chat_id": "@khaledsaleman"},
        {"id": 2, "title": "تابعنا على تويتر", "reward": {"gold": 500}, "type": "link", "link": "https://x.com/example"},
        {"id": 3, "title": "مشاهدة فيديو تعليمي", "reward": {"usdt": 0.1}, "type": "link", "link": "https://youtube.com/example"}
    ],
    "withdrawals": [], # list of {id, user_id, amount, status, timestamp}
    "admin_logs": [] # list of {action, admin_id, timestamp, details}
}

# In-memory store for events intended for the game frontend
pending_events = {} # user_id -> list of events

def load_settings():
    """Loads settings from the database into game_state."""
    conn = get_db_connection()
    try:
        rows = conn.execute("SELECT key, value FROM global_settings").fetchall()
        for row in rows:
            key, value = row['key'], row['value']
            if key in ['maintenance_mode', 'attack_enabled', 'swap_enabled']:
                game_state["settings"][key] = (value == '1' or value == 'True' or value is True)
            elif key in ['referral_percent', 'daily_task_wins_required']:
                game_state["settings"][key] = int(float(value))
            elif key in ['starting_gold', 'starting_ton', 'starting_usdt', 'base_mining_rate', 'min_withdrawal', 'daily_reward_amount']:
                game_state["settings"][key] = float(value)
            elif key in ['swap_rates', 'daily_task_reward']:
                try:
                    game_state["settings"][key] = json.loads(value)
                except json.JSONDecodeError:
                    pass
            else:
                game_state["settings"][key] = value
    except Exception as e:
        print(f"Error loading settings: {e}")
    finally:
        conn.close()

load_settings()

def verify_telegram_data(init_data):
    """
    Verifies the data received from the Telegram Web App.
    See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-web-app
    """
    if not init_data:
        return False

    try:
        vals = {k: v for k, v in [s.split('=') for s in init_data.split('&')]}
        data_check_string = '\n'.join([f"{k}={v}" for k, v in sorted(vals.items()) if k != 'hash'])

        secret_key = hmac.new("WebAppData".encode(), BOT_TOKEN.encode(), hashlib.sha256).digest()
        h = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()

        return h == vals.get('hash')
    except Exception:
        return False

def is_admin_request(data):
    """Checks if the request is from the authorized admin."""
    init_data = data.get('initData')

    # Simple check for demo/sandbox:
    user_id = data.get('user_id')
    if str(user_id) == str(ADMIN_ID):
        return True
    return False

def log_admin_action(action, details):
    game_state["admin_logs"].append({
        "action": action,
        "admin_id": ADMIN_ID,
        "timestamp": datetime.utcnow().isoformat(),
        "details": details
    })

@app.route('/admin/data', methods=['POST'])
def get_admin_data():
    if not is_admin_request(request.json):
        return jsonify({"status": "error", "error": "Unauthorized"}), 403

    load_settings()
    # Return game state but maybe truncate logs to last 50
    response_state = game_state.copy()

    conn = get_db_connection()
    # Add DB users to response for the Admin Panel list
    db_users = conn.execute("SELECT * FROM users").fetchall()
    users_dict = {}
    for u in db_users:
        user_id = str(u['id'])
        users_dict[user_id] = {
            "name": u['name'],
            "photo": u['photo'],
            "banned": bool(u['banned']),
            "balance": {"gold": u['gold'], "ton": u['ton'], "usdt": u['usdt']},
            "referrer": u['referrer']
        }
    response_state["users"] = users_dict

    conn.close()

    response_state["admin_logs"] = game_state["admin_logs"][-50:]
    response_state["status"] = "ok"
    return jsonify(response_state)

@app.route('/admin/settings', methods=['POST'])
def update_settings():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"status": "error", "error": "Unauthorized"}), 403

    new_settings = data.get('settings')
    if new_settings:
        conn = get_db_connection()
        try:
            for key, value in new_settings.items():
                if key in ['swap_rates', 'daily_task_reward']:
                    db_val = json.dumps(value)
                elif isinstance(value, bool):
                    db_val = '1' if value else '0'
                else:
                    db_val = str(value)
                conn.execute("INSERT OR REPLACE INTO global_settings (key, value) VALUES (?, ?)", (key, db_val))
            conn.commit()
        except Exception as e:
            print(f"Error updating global settings: {e}")
            return jsonify({"status": "error", "error": str(e)}), 500
        finally:
            conn.close()

        load_settings()
        log_admin_action("update_settings", new_settings)
        return jsonify({"status": "ok", "settings": game_state["settings"]})

    return jsonify({"status": "error", "error": "No settings provided"}), 400

@app.route('/admin/users/search', methods=['POST'])
def search_user():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"status": "error", "error": "Unauthorized"}), 403

    query = data.get('query')
    if not query:
        return jsonify({"status": "error", "error": "Missing search query"}), 400

    conn = get_db_connection()
    # Search by ID or Username
    user = conn.execute('SELECT * FROM users WHERE id = ? OR username = ?', (str(query), str(query))).fetchone()
    conn.close()

    if user:
        return jsonify({
            "status": "ok",
            "user": {
                "id": user['id'],
                "username": user['username'],
                "name": user['name'],
                "photo": user['photo'],
                "gold": user['gold'],
                "ton": user['ton'],
                "usdt": user['usdt'],
                "power": user['power'],
                "rank": user['rank'],
                "banned": bool(user['banned'])
            }
        })
    return jsonify({"status": "error", "error": "User not found"}), 404

@app.route('/admin/users/ban', methods=['POST'])
def ban_user():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"status": "error", "error": "Unauthorized"}), 403

    target_query = data.get('target_user_id') # Can be ID or Username
    if not target_query:
        return jsonify({"status": "error", "error": "Missing target user"}), 400

    ban_status = 1 if data.get('ban') is True or str(data.get('ban')) == '1' else 0

    conn = get_db_connection()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ? OR username = ?', (str(target_query), str(target_query))).fetchone()

        if not user:
            return jsonify({"status": "error", "error": "المستخدم غير موجود في قاعدة البيانات"}), 404

        conn.execute('UPDATE users SET banned = ? WHERE id = ?', (ban_status, user['id']))
        conn.commit()
    except Exception as e:
        print(f"Error in ban_user: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500
    finally:
        conn.close()

    log_admin_action("ban_user" if ban_status else "unban_user", {"target": user['id']})
    return jsonify({"status": "ok", "message": f"تم {'حظر' if ban_status else 'فك حظر'} المستخدم بنجاح"})

@app.route('/admin/users/resources', methods=['POST'])
def add_resources():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"status": "error", "error": "Unauthorized"}), 403

    target_id = data.get('target_user_id')
    if not target_id:
        return jsonify({"status": "error", "error": "Missing target_user_id"}), 400

    target_id = str(target_id)
    resources = data.get('resources', {})

    conn = get_db_connection()
    try:
        user = conn.execute('SELECT * FROM users WHERE id = ?', (target_id,)).fetchone()

        if user:
            gold = float(resources.get('gold', 0))
            ton = float(resources.get('ton', 0))
            usdt = float(resources.get('usdt', 0))

            conn.execute('UPDATE users SET gold = gold + ?, ton = ton + ?, usdt = usdt + ? WHERE id = ?',
                         (gold, ton, usdt, target_id))
            conn.commit()
            log_admin_action("add_resources", {"target": target_id, "amount": resources})
            return jsonify({"status": "ok", "message": "Resources added successfully"})
        else:
            return jsonify({"status": "error", "error": "User not found"}), 404
    except (ValueError, TypeError):
        return jsonify({"status": "error", "error": "Invalid resource values"}), 400
    except Exception as e:
        print(f"Error in add_resources: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500
    finally:
        conn.close()

@app.route('/admin/broadcast', methods=['POST'])
def admin_broadcast():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"status": "error", "error": "Unauthorized"}), 403

    message = data.get('message')
    if not message:
        return jsonify({"status": "error", "error": "Missing message"}), 400

    conn = get_db_connection()
    try:
        users = conn.execute('SELECT id FROM users').fetchall()
    except Exception as e:
        print(f"Database error in broadcast: {e}")
        return jsonify({"status": "error", "error": "Database error"}), 500
    finally:
        conn.close()

    success_count = 0
    failure_count = 0
    for user in users:
        user_id = user['id']
        try:
            url = f"{TELEGRAM_API_URL}/sendMessage"
            payload = {"chat_id": user_id, "text": message, "parse_mode": "HTML"}
            res = requests.post(url, json=payload, timeout=5)
            if res.status_code == 200 and res.json().get("ok"):
                success_count += 1
            else:
                print(f"Failed to send broadcast to {user_id}: {res.text}")
                failure_count += 1
        except Exception as e:
            print(f"Exception sending broadcast to {user_id}: {e}")
            failure_count += 1

        time.sleep(0.05) # Rate limit protection

    log_admin_action("broadcast", {"success": success_count, "failure": failure_count})
    return jsonify({
        "status": "ok",
        "message": f"تم إرسال الرسالة إلى {success_count} مستخدم بنجاح. (فشل: {failure_count})",
        "delivered": success_count,
        "failed": failure_count
    })

@app.route('/admin/tasks', methods=['POST'])
def manage_tasks():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"status": "error", "error": "Unauthorized"}), 403

    action = data.get('action') # add, delete
    task_data = data.get('task')

    conn = get_db_connection()
    if action == "add":
        if not task_data: return jsonify({"status": "error", "error": "Missing task data"}), 400
        reward = task_data.get('reward', {})
        conn.execute('''
            INSERT INTO tasks (title, reward_gold, reward_ton, reward_usdt, type, link, chat_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (task_data['title'], reward.get('gold', 0), reward.get('ton', 0), reward.get('usdt', 0),
              task_data['type'], task_data['link'], task_data.get('chat_id')))
        conn.commit()
        log_admin_action("add_task", task_data)
    elif action == "delete":
        if not task_data or "id" not in task_data: return jsonify({"status": "error", "error": "Missing task ID"}), 400
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_data['id'],))
        conn.commit()
        log_admin_action("delete_task", task_data)

    rows = conn.execute('SELECT * FROM tasks').fetchall()
    tasks = []
    for r in rows:
        tasks.append({
            "id": r['id'], "title": r['title'], "type": r['type'], "link": r['link'], "chat_id": r['chat_id'],
            "reward": {"gold": r['reward_gold'], "ton": r['reward_ton'], "usdt": r['reward_usdt']}
        })
    conn.close()
    return jsonify({"status": "ok", "message": f"Task {action}ed", "tasks": tasks})

@app.route('/admin/withdrawals', methods=['POST'])
def manage_withdrawals():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"status": "error", "error": "Unauthorized"}), 403

    action = data.get('action') # approve, reject
    withdraw_id = data.get('id')

    found = False
    for w in game_state["withdrawals"]:
        if w["id"] == withdraw_id:
            w["status"] = "approved" if action == "approve" else "rejected"
            log_admin_action(f"{action}_withdrawal", {"id": withdraw_id})
            found = True
            break

    if found:
        return jsonify({"status": "ok", "message": f"Withdrawal {action}d", "withdrawals": game_state["withdrawals"]})
    return jsonify({"status": "error", "error": "Withdrawal not found"}), 404

@app.route('/check-status', methods=['POST'])
def check_status():
    data = request.json
    if not data or 'user_id' not in data:
        return jsonify({"error": "Missing user_id"}), 400

    load_settings()
    user_id = str(data.get('user_id'))
    referrer = str(data.get('referrer')) if data.get('referrer') else None

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    current_time = datetime.now(UTC).isoformat()

    if not user:
        # Get starting resources from settings
        starting_gold = float(conn.execute("SELECT value FROM global_settings WHERE key = 'starting_gold'").fetchone()['value'])
        starting_ton = float(conn.execute("SELECT value FROM global_settings WHERE key = 'starting_ton'").fetchone()['value'])
        starting_usdt = float(conn.execute("SELECT value FROM global_settings WHERE key = 'starting_usdt'").fetchone()['value'])

        conn.execute('''
            INSERT INTO users (id, username, name, photo, gold, ton, usdt, last_mining_time, referrer)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, data.get('tg_username'), data.get('username', 'Player'), data.get('photo', ''),
              starting_gold, starting_ton, starting_usdt, current_time, referrer))
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    else:
        # Update name and photo if they changed
        conn.execute('UPDATE users SET username = ?, name = ?, photo = ? WHERE id = ?',
                     (data.get('tg_username', user['username']), data.get('username', user['name']), data.get('photo', user['photo']), user_id))
        conn.commit()
        user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()

    # Mining Logic
    last_mining_time_str = user['last_mining_time']
    if last_mining_time_str:
        last_mining_time = datetime.fromisoformat(last_mining_time_str)
        now = datetime.now(UTC)
        time_diff = (now - last_mining_time).total_seconds() / 3600.0 # hours

        # Calculate total production rate
        buildings = conn.execute('SELECT * FROM buildings WHERE user_id = ? AND type = "goldMine"', (user_id,)).fetchall()
        base_mining_rate = float(conn.execute("SELECT value FROM global_settings WHERE key = 'base_mining_rate'").fetchone()['value'])

        total_production = sum(b['level'] * base_mining_rate for b in buildings)
        earned_gold = total_production * time_diff

        if earned_gold > 0:
            conn.execute('UPDATE users SET gold = gold + ?, last_mining_time = ? WHERE id = ?',
                         (earned_gold, current_time, user_id))
            conn.commit()
            user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
        else:
            conn.execute('UPDATE users SET last_mining_time = ? WHERE id = ?', (current_time, user_id))
            conn.commit()

    # Get buildings
    buildings_rows = conn.execute('SELECT * FROM buildings WHERE user_id = ?', (user_id,)).fetchall()
    buildings_list = [dict(row) for row in buildings_rows]

    user_data = dict(user)
    user_data['balance'] = {"gold": user['gold'], "ton": user['ton'], "usdt": user['usdt']}
    user_data['banned'] = bool(user['banned'])
    user_data['energy'] = user['energy']
    user_data['power'] = user['power']
    user_data['rank'] = user['rank']
    user_data['buildings'] = buildings_list

    # Progress for daily tasks
    try:
        user_data['daily_tasks_progress'] = json.loads(user['daily_tasks_progress']) if user['daily_tasks_progress'] else {}
    except:
        user_data['daily_tasks_progress'] = {}

    conn.close()

    return jsonify({
        "maintenance": game_state["settings"]["maintenance_mode"],
        "banned": user_data['banned'],
        "settings": game_state["settings"],
        "user": user_data
    })

@app.route('/leaderboard', methods=['GET'])
def get_leaderboard():
    conn = get_db_connection()
    # Dynamic real-time sorting by Power first, then Gold
    # Filter out users without name (likely incomplete registrations/bots if any)
    rows = conn.execute('''
        SELECT id, username, name, photo, gold, ton, usdt, power
        FROM users
        WHERE name IS NOT NULL AND name != "" AND name != "Unknown"
        ORDER BY power DESC, gold DESC
        LIMIT 50
    ''').fetchall()
    conn.close()

    leaderboard = [dict(r) for r in rows]
    return jsonify({"status": "ok", "leaderboard": leaderboard})

@app.route('/daily-reward/claim', methods=['POST'])
def claim_daily_reward():
    data = request.json
    user_id = str(data.get('user_id'))

    conn = get_db_connection()
    user = conn.execute('SELECT last_daily_reward_time, gold FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user:
        conn.close()
        return jsonify({"status": "error", "error": "User not found"}), 404

    now = datetime.now(UTC)
    last_claim = user['last_daily_reward_time']

    if last_claim:
        last_claim_dt = datetime.fromisoformat(last_claim)
        diff = (now - last_claim_dt).total_seconds()
        if diff < 86400: # 24 hours
            conn.close()
            remaining = int(86400 - diff)
            return jsonify({"status": "error", "error": f"يرجى الانتظار {remaining // 3600} ساعة", "remaining": remaining}), 400

    load_settings()
    reward_amount = game_state["settings"].get("daily_reward_amount", 100.0)

    conn.execute('UPDATE users SET gold = gold + ?, last_daily_reward_time = ? WHERE id = ?',
                 (reward_amount, now.isoformat(), user_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "message": f"تم استلام {reward_amount} ذهب", "reward": reward_amount})

@app.route('/attack/perform', methods=['POST'])
def perform_attack():
    data = request.json
    user_id = str(data.get('user_id'))

    conn = get_db_connection()
    user = conn.execute('SELECT gold, energy, daily_tasks_progress FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user:
        conn.close()
        return jsonify({"status": "error", "error": "User not found"}), 404

    if user['energy'] < 10:
        conn.close()
        return jsonify({"status": "error", "error": "طاقة غير كافية"}), 400

    import random
    win = random.random() > 0.4
    gold_change = random.randint(200, 300) if win else -random.randint(50, 100)

    # Update energy and gold
    new_energy = user['energy'] - 10
    new_gold = max(0, user['gold'] + gold_change)

    # Daily task progress
    try:
        progress = json.loads(user['daily_tasks_progress']) if user['daily_tasks_progress'] else {"wins": 0, "claimed": False, "date": datetime.now(UTC).date().isoformat()}
    except:
        progress = {"wins": 0, "claimed": False, "date": datetime.now(UTC).date().isoformat()}

    today = datetime.now(UTC).date().isoformat()
    if progress.get("date") != today:
        progress = {"wins": 1 if win else 0, "claimed": False, "date": today}
    elif win:
        progress["wins"] = progress.get("wins", 0) + 1

    conn.execute('UPDATE users SET gold = ?, energy = ?, daily_tasks_progress = ? WHERE id = ?',
                 (new_gold, new_energy, json.dumps(progress), user_id))
    conn.commit()
    conn.close()

    return jsonify({
        "status": "ok",
        "win": win,
        "gold_change": gold_change,
        "new_gold": new_gold,
        "new_energy": new_energy,
        "progress": progress
    })

@app.route('/daily-task/claim', methods=['POST'])
def claim_daily_task_reward():
    data = request.json
    user_id = str(data.get('user_id'))

    load_settings()
    wins_required = game_state["settings"].get("daily_task_wins_required", 20)
    reward = game_state["settings"].get("daily_task_reward", {"ton": 0.1})

    conn = get_db_connection()
    user = conn.execute('SELECT daily_tasks_progress FROM users WHERE id = ?', (user_id,)).fetchone()

    if not user:
        conn.close()
        return jsonify({"status": "error", "error": "User not found"}), 404

    try:
        progress = json.loads(user['daily_tasks_progress']) if user['daily_tasks_progress'] else {}
    except:
        progress = {}

    if progress.get("wins", 0) < wins_required:
        conn.close()
        return jsonify({"status": "error", "error": f"تحتاج إلى {wins_required} فوز"}), 400

    if progress.get("claimed"):
        conn.close()
        return jsonify({"status": "error", "error": "تم استلام المكافأة بالفعل"}), 400

    progress["claimed"] = True

    # Apply rewards
    gold_add = reward.get("gold", 0)
    ton_add = reward.get("ton", 0)
    usdt_add = reward.get("usdt", 0)

    conn.execute('UPDATE users SET gold = gold + ?, ton = ton + ?, usdt = usdt + ?, daily_tasks_progress = ? WHERE id = ?',
                 (gold_add, ton_add, usdt_add, json.dumps(progress), user_id))
    conn.commit()
    conn.close()

    return jsonify({"status": "ok", "message": "تم استلام مكافأة المهمة اليومية"})

@app.route('/tasks/list', methods=['GET'])
def list_tasks():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    conn = get_db_connection()
    user = conn.execute('SELECT id FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    # Get completed tasks
    completed_rows = conn.execute('SELECT task_id FROM completed_tasks WHERE user_id = ?', (user_id,)).fetchall()
    completed = [r['task_id'] for r in completed_rows]

    # Get all tasks
    task_rows = conn.execute('SELECT * FROM tasks').fetchall()
    tasks = []
    for r in task_rows:
        tasks.append({
            "id": r['id'], "title": r['title'], "type": r['type'], "link": r['link'], "chat_id": r['chat_id'],
            "reward": {"gold": r['reward_gold'], "ton": r['reward_ton'], "usdt": r['reward_usdt']},
            "completed": r['id'] in completed
        })

    conn.close()
    return jsonify({"tasks": tasks})

@app.route('/referrals/list', methods=['GET'])
def list_referrals():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"status": "error", "error": "Missing user_id", "referrals": []}), 400

    user_id = str(user_id)

    conn = get_db_connection()
    try:
        rows = conn.execute('SELECT * FROM users WHERE referrer = ?', (user_id,)).fetchall()
        referrals = []
        for row in rows:
            referrals.append({
                "id": str(row['id']),
                "name": row['name'] or "Unknown",
                "photo": row['photo'] or "",
                "gold": row['gold'] or 0
            })

        conn.close()
        # Sort by gold descending
        referrals.sort(key=lambda x: x.get("gold", 0), reverse=True)
        return jsonify({"status": "ok", "referrals": referrals})
    except Exception as e:
        conn.close()
        print(f"Error in list_referrals: {e}")
        return jsonify({"status": "error", "error": "Internal Server Error", "referrals": []}), 500

@app.route('/tasks/verify', methods=['POST'])
def verify_task():
    data = request.json
    print(f"Verifying task: {data}")
    user_id = str(data.get('user_id'))
    task_id = int(data.get('task_id'))

    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    if not user:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    completed = conn.execute('SELECT * FROM completed_tasks WHERE user_id = ? AND task_id = ?', (user_id, task_id)).fetchone()
    if completed:
        conn.close()
        return jsonify({"error": "Task already completed"}), 400

    task_row = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task_row:
        conn.close()
        return jsonify({"error": "Task not found"}), 404

    task = dict(task_row)
    task['reward'] = {"gold": task['reward_gold'], "ton": task['reward_ton'], "usdt": task['reward_usdt']}

    # Verification logic
    verified = False
    if task["type"] == "telegram":
        # Check if chat_id is provided, if not fallback to verified for testing
        if not task.get("chat_id"):
            verified = True
        else:
            try:
                url = f"{TELEGRAM_API_URL}/getChatMember"
                res = requests.get(url, params={"chat_id": task["chat_id"], "user_id": user_id})
                res_data = res.json()
                if res_data.get("ok"):
                    status = res_data["result"]["status"]
                    if status in ["member", "administrator", "creator"]:
                        verified = True
            except Exception as e:
                print(f"Telegram verification error: {e}")
    else:
        verified = True

    if verified:
        # Mark as completed
        conn.execute('INSERT INTO completed_tasks (user_id, task_id) VALUES (?, ?)', (user_id, task_id))

        # Apply rewards
        reward = task["reward"]
        gold_reward = reward.get('gold', 0)
        ton_reward = reward.get('ton', 0)
        usdt_reward = reward.get('usdt', 0)

        conn.execute('UPDATE users SET gold = gold + ?, ton = ton + ?, usdt = usdt + ? WHERE id = ?',
                     (gold_reward, ton_reward, usdt_reward, user_id))

        # Referral bonus
        referrer_id = user['referrer']
        if referrer_id:
            # Load referral percent directly from database to ensure it's up to date
            ref_percent_row = conn.execute("SELECT value FROM global_settings WHERE key = 'referral_percent'").fetchone()
            bonus_percent = (float(ref_percent_row['value']) if ref_percent_row else 10.0) / 100.0
            conn.execute('UPDATE users SET gold = gold + ?, ton = ton + ?, usdt = usdt + ? WHERE id = ?',
                         (gold_reward * bonus_percent, ton_reward * bonus_percent, usdt_reward * bonus_percent, referrer_id))

        conn.commit()
        updated_user = conn.execute('SELECT gold, ton, usdt FROM users WHERE id = ?', (user_id,)).fetchone()
        conn.close()
        return jsonify({"status": "ok", "message": "Task verified and reward applied",
                        "new_balance": {"gold": updated_user['gold'], "ton": updated_user['ton'], "usdt": updated_user['usdt']}})

    conn.close()
    return jsonify({"error": "Verification failed"}), 400

@app.route('/notify', methods=['POST'])
def notify():
    data = request.json
    message = data.get('message')
    chat_id = data.get('chat_id')
    init_data = data.get('initData') # For security verification

    # Secure verification (Optional but recommended)
    # if not verify_telegram_data(init_data):
    #     return jsonify({"error": "Unauthorized"}), 401

    if not message or not chat_id:
        return jsonify({"error": "Missing parameters"}), 400

    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": "HTML"
    }

    response = requests.post(url, json=payload)
    return jsonify(response.json()), response.status_code

@app.route('/events', methods=['GET'])
def get_events():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    # Return and clear events for this user
    user_events = pending_events.pop(user_id, [])
    return jsonify({"events": user_events})

@app.route('/trigger-event', methods=['POST'])
def trigger_event():
    """
    Simulates an event triggered by the bot or a game admin.
    Example payload: {"user_id": "12345", "type": "bonus_gold", "payload": {"amount": 500}}
    """
    data = request.json
    user_id = data.get('user_id')
    event_type = data.get('type')
    payload = data.get('payload', {})

    if not user_id or not event_type:
        return jsonify({"error": "Missing user_id or type"}), 400

    if user_id not in pending_events:
        pending_events[user_id] = []

    pending_events[user_id].append({
        "id": str(uuid.uuid4()),
        "type": event_type,
        "payload": payload,
        "timestamp": datetime.utcnow().isoformat()
    })

    return jsonify({"status": "Event queued", "event_count": len(pending_events[user_id])})

@app.route('/buildings/save', methods=['POST'])
def save_buildings():
    data = request.json
    user_id = str(data.get('user_id'))
    buildings = data.get('buildings', [])
    balance = data.get('balance', {})
    energy = data.get('energy')
    power = data.get('power')
    rank = data.get('rank')

    conn = get_db_connection()
    try:
        # Update user state if provided
        if balance:
            conn.execute('''
                UPDATE users SET gold = ?, ton = ?, usdt = ? WHERE id = ?
            ''', (balance.get('gold'), balance.get('ton'), balance.get('usdt'), user_id))

        if energy is not None:
            conn.execute('UPDATE users SET energy = ? WHERE id = ?', (energy, user_id))

        if power is not None:
            conn.execute('UPDATE users SET power = ? WHERE id = ?', (power, user_id))

        if rank:
            conn.execute('UPDATE users SET rank = ? WHERE id = ?', (rank, user_id))

        # Clear existing buildings
        conn.execute('DELETE FROM buildings WHERE user_id = ?', (user_id,))

        # Insert new buildings
        for b in buildings:
            conn.execute('''
                INSERT INTO buildings (user_id, type, level, col, row)
                VALUES (?, ?, ?, ?, ?)
            ''', (user_id, b['type'], b['level'], b['col'], b['row']))

        conn.commit()
        conn.close()
        return jsonify({"status": "ok", "message": "Game progress saved"})
    except Exception as e:
        conn.close()
        return jsonify({"status": "error", "error": str(e)}), 500

@app.route('/buildings/list', methods=['GET'])
def list_buildings():
    user_id = request.args.get('user_id')
    if not user_id:
        return jsonify({"error": "Missing user_id"}), 400

    conn = get_db_connection()
    rows = conn.execute('SELECT * FROM buildings WHERE user_id = ?', (user_id,)).fetchall()
    conn.close()

    return jsonify({"status": "ok", "buildings": [dict(row) for row in rows]})

@app.route('/command', methods=['POST'])
def handle_command():
    # This would be the webhook handler for Telegram
    data = request.json
    # Logic to process Telegram /commands and potentially trigger-event
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=5000, debug=True)
