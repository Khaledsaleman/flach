import os
import hashlib
import hmac
import json
import uuid
from datetime import datetime
from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
from dotenv import load_dotenv

load_dotenv()

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
        return jsonify({"error": "Unauthorized"}), 403

    # Return game state but maybe truncate logs to last 50
    response_state = game_state.copy()
    response_state["admin_logs"] = game_state["admin_logs"][-50:]
    return jsonify(response_state)

@app.route('/admin/settings', methods=['POST'])
def update_settings():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"error": "Unauthorized"}), 403

    new_settings = data.get('settings')
    if new_settings:
        game_state["settings"].update(new_settings)
        log_admin_action("update_settings", new_settings)
    return jsonify({"status": "ok", "settings": game_state["settings"]})

@app.route('/admin/users/ban', methods=['POST'])
def ban_user():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"error": "Unauthorized"}), 403

    target_id = data.get('target_user_id')
    ban_status = data.get('ban', True)
    if target_id:
        if target_id not in game_state["users"]:
             game_state["users"][target_id] = {
                "name": "Unknown",
                "photo": "",
                "joined": datetime.utcnow().isoformat(),
                "banned": False,
                "completed_tasks": [],
                "balance": {"gold": 12450, "ton": 24.5, "usdt": 150},
                "referrer": None
            }
        game_state["users"][target_id]["banned"] = ban_status
        log_admin_action("ban_user" if ban_status else "unban_user", {"target": target_id})
    return jsonify({"status": "ok"})

@app.route('/admin/users/resources', methods=['POST'])
def add_resources():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"error": "Unauthorized"}), 403

    target_id = str(data.get('target_user_id'))
    resources = data.get('resources', {})

    if target_id in game_state["users"]:
        user = game_state["users"][target_id]
        if "balance" not in user: user["balance"] = {"gold": 12450, "ton": 24.5, "usdt": 150}

        user["balance"]["gold"] += float(resources.get('gold', 0))
        user["balance"]["ton"] += float(resources.get('ton', 0))
        user["balance"]["usdt"] += float(resources.get('usdt', 0))

        log_admin_action("add_resources", {"target": target_id, "amount": resources})
        return jsonify({"status": "ok"})

    return jsonify({"error": "User not found"}), 404

@app.route('/admin/broadcast', methods=['POST'])
def admin_broadcast():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"error": "Unauthorized"}), 403

    message = data.get('message')
    if not message:
        return jsonify({"error": "Missing message"}), 400

    success_count = 0
    for user_id in game_state["users"]:
        try:
            url = f"{TELEGRAM_API_URL}/sendMessage"
            payload = {"chat_id": user_id, "text": message, "parse_mode": "HTML"}
            res = requests.post(url, json=payload)
            if res.json().get("ok"):
                success_count += 1
        except Exception:
            continue

    log_admin_action("broadcast", {"count": success_count})
    return jsonify({"status": "ok", "delivered": success_count})

@app.route('/admin/tasks', methods=['POST'])
def manage_tasks():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"error": "Unauthorized"}), 403

    action = data.get('action') # add, delete
    task_data = data.get('task')

    if action == "add":
        task_data["id"] = len(game_state["tasks"]) + 1
        game_state["tasks"].append(task_data)
        log_admin_action("add_task", task_data)
    elif action == "delete":
        game_state["tasks"] = [t for t in game_state["tasks"] if t["id"] != task_data["id"]]
        log_admin_action("delete_task", task_data)

    return jsonify({"status": "ok", "tasks": game_state["tasks"]})

@app.route('/admin/withdrawals', methods=['POST'])
def manage_withdrawals():
    data = request.json
    if not is_admin_request(data):
        return jsonify({"error": "Unauthorized"}), 403

    action = data.get('action') # approve, reject
    withdraw_id = data.get('id')

    for w in game_state["withdrawals"]:
        if w["id"] == withdraw_id:
            w["status"] = "approved" if action == "approve" else "rejected"
            log_admin_action(f"{action}_withdrawal", {"id": withdraw_id})
            break

    return jsonify({"status": "ok", "withdrawals": game_state["withdrawals"]})

@app.route('/check-status', methods=['POST'])
def check_status():
    data = request.json
    user_id = str(data.get('user_id'))

    # Register user if not exists
    if user_id not in game_state["users"]:
        game_state["users"][user_id] = {
            "name": data.get('username', 'Player'),
            "photo": data.get('photo', ''),
            "joined": datetime.utcnow().isoformat(),
            "banned": False,
            "completed_tasks": [],
            "balance": {"gold": 12450, "ton": 24.5, "usdt": 150},
            "referrer": data.get('referrer')
        }

    user = game_state["users"][user_id]

    # Update user data if changed
    user["name"] = data.get('username', user["name"])
    user["photo"] = data.get('photo', user.get("photo"))

    return jsonify({
        "maintenance": game_state["settings"]["maintenance_mode"],
        "banned": user.get("banned", False),
        "settings": game_state["settings"],
        "user": user
    })

@app.route('/tasks/list', methods=['GET'])
def list_tasks():
    user_id = request.args.get('user_id')
    if not user_id or user_id not in game_state["users"]:
        return jsonify({"error": "User not found"}), 404

    user = game_state["users"][user_id]
    completed = user.get("completed_tasks", [])

    # Enrich tasks with completion status
    tasks = []
    for t in game_state["tasks"]:
        task_copy = t.copy()
        task_copy["completed"] = t["id"] in completed
        tasks.append(task_copy)

    return jsonify({"tasks": tasks})

@app.route('/tasks/verify', methods=['POST'])
def verify_task():
    data = request.json
    user_id = str(data.get('user_id'))
    task_id = int(data.get('task_id'))

    if user_id not in game_state["users"]:
        return jsonify({"error": "User not found"}), 404

    user = game_state["users"][user_id]
    if task_id in user.get("completed_tasks", []):
        return jsonify({"error": "Task already completed"}), 400

    task = next((t for t in game_state["tasks"] if t["id"] == task_id), None)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    # Verification logic
    verified = False
    if task["type"] == "telegram":
        # Call Telegram API to check membership
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
            # Fallback for sandbox testing if needed
            # verified = True
    else:
        # For other link types, we assume verified for now
        verified = True

    if verified:
        # Mark as completed
        if "completed_tasks" not in user: user["completed_tasks"] = []
        user["completed_tasks"].append(task_id)

        # Apply rewards
        reward = task["reward"]
        for asset, amount in reward.items():
            if "balance" not in user: user["balance"] = {"gold": 12450, "ton": 24.5, "usdt": 150} # Init with default from index.html if missing
            user["balance"][asset] = user["balance"].get(asset, 0) + amount

            # Referral bonus
            if user.get("referrer"):
                ref_id = user["referrer"]
                if ref_id in game_state["users"]:
                    ref_user = game_state["users"][ref_id]
                    bonus = amount * (game_state["settings"]["referral_percent"] / 100.0)
                    if "balance" not in ref_user: ref_user["balance"] = {"gold": 12450, "ton": 24.5, "usdt": 150}
                    ref_user["balance"][asset] = ref_user["balance"].get(asset, 0) + bonus

        return jsonify({"status": "ok", "message": "Task verified and reward applied", "new_balance": user["balance"]})

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

@app.route('/command', methods=['POST'])
def handle_command():
    # This would be the webhook handler for Telegram
    data = request.json
    # Logic to process Telegram /commands and potentially trigger-event
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    app.run(port=5000, debug=True)
