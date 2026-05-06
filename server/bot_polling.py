import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"
BACKEND_URL = "https://flach.onrender.com"

def send_message(chat_id, text, reply_markup=None):
    url = f"{API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML"
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup

    try:
        requests.post(url, json=payload)
    except Exception as e:
        print(f"Error sending message: {e}")

def handle_update(update):
    if "message" not in update:
        return

    message = update["message"]
    chat_id = message["chat"]["id"]
    text = message.get("text", "")
    user_id = str(message["from"]["id"])

    if text.startswith("/start"):
        parts = text.split()
        referrer = parts[1] if len(parts) > 1 else None

        welcome_text = (
            "🏰 <b>مرحباً بك في عالم CryptoClash!</b>\n\n"
            "الآن يمكنك بناء إمبراطوريتك، تطوير قاعدتك، والمنافسة في أقوى تحديات الكريبتو.\n\n"
        )

        welcome_text += "اضغط على الزر أدناه للدخول إلى اللعبة والبدء في المغامرة:"

        reply_markup = {
            "inline_keyboard": [[
                {"text": "🎮 ابدأ اللعب الآن", "web_app": {"url": "https://khaledsaleman.github.io/flach/"}}
            ]]
        }
        send_message(chat_id, welcome_text, reply_markup)

    elif text == "/gift":
        try:
            response = requests.post(f"{BACKEND_URL}/trigger-event", json={
                "user_id": user_id,
                "type": "bonus_gold",
                "payload": {"amount": 1000}
            })
            if response.status_code == 200:
                send_message(chat_id, "🎁 <b>مفاجأة!</b> تم إرسال 1000 ذهب إلى حسابك. استمتع بها في تطوير قاعدتك! 🎉")
            else:
                send_message(chat_id, "❌ عذراً، لا يمكن معالجة طلبك حالياً.")
        except Exception as e:
            send_message(chat_id, "❌ خطأ في الاتصال بالسيرفر.")

def main():
    if not BOT_TOKEN:
        print("TELEGRAM_BOT_TOKEN not found in .env")
        return

    print("Bot polling active...")
    last_update_id = 0

    while True:
        try:
            url = f"{API_URL}/getUpdates"
            params = {"offset": last_update_id + 1, "timeout": 30}
            response = requests.get(url, params=params)

            if response.status_code == 200:
                data = response.json()
                for update in data.get("result", []):
                    handle_update(update)
                    last_update_id = update["update_id"]
            else:
                print(f"Error fetching updates: {response.status_code}")
                time.sleep(5)

        except Exception as e:
            print(f"Polling error: {e}")
            time.sleep(5)

if __name__ == "__main__":
    main()
