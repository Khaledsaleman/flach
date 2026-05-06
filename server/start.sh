#!/bin/bash
# تشغيل السيرفر في الخلفية
gunicorn server.app:app --bind 0.0.0.0:$PORT &
# تشغيل البوت
python server/bot_polling.py
