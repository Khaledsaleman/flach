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
