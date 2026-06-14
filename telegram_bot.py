"""
Competitor Radar — Telegram bot (long polling).

Run alongside the web app:
    python telegram_bot.py

Commands (also available as buttons in the chat keyboard and the "/" menu):
  /start, /help — what this bot is for
  /refresh      — run data collection now (calls POST /api/refresh)
  /digest       — send this week's digest right now
  /status       — last run / next run / items tracked

Environment:
  TELEGRAM_BOT_TOKEN   bot token from @BotFather
  TELEGRAM_CHAT_ID     if set, only this chat can use the commands above
  RADAR_API_URL        base URL of the running app (default http://localhost:8000)

The weekly digest itself is sent automatically by the scheduler in app.py
(Monday 09:00, timezone from SCHEDULER_TZ) — this bot is for on-demand commands.
"""
import os
import time
import traceback

import requests
from dotenv import load_dotenv

import config

load_dotenv()

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ALLOWED_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
API_URL = os.environ.get("RADAR_API_URL", "http://localhost:8000").rstrip("/")
TG_API = f"https://api.telegram.org/bot{TOKEN}"

WELCOME = (
    "🛰 <b>Competitor Radar</b>\n\n"
    "I track fintech competitors for you: app releases, pricing changes, "
    "blog posts, news and ads — currently <b>{n}</b> brands ({names}).\n\n"
    "Every Monday I send a digest of the past week here automatically.\n\n"
    "Use the buttons below, or these commands:\n"
    "/digest — send this week's digest now\n"
    "/refresh — run data collection now\n"
    "/status — last run / next run / items tracked"
)

# Persistent on-screen button menu (shown under the message box).
KEYBOARD_BUTTONS = [
    ["🔄 Refresh", "📰 Digest"],
    ["📊 Status", "ℹ️ Help"],
]
REPLY_MARKUP = {"keyboard": [[{"text": b} for b in row] for row in KEYBOARD_BUTTONS], "resize_keyboard": True}

# Maps button labels to the commands they trigger.
BUTTON_COMMANDS = {
    "🔄 Refresh": "/refresh",
    "📰 Digest": "/digest",
    "📊 Status": "/status",
    "ℹ️ Help": "/help",
}

# Commands shown in Telegram's built-in "/" menu.
BOT_COMMANDS = [
    {"command": "start", "description": "What this bot does"},
    {"command": "refresh", "description": "Run data collection now"},
    {"command": "digest", "description": "Send this week's digest"},
    {"command": "status", "description": "Last run / next run / items tracked"},
    {"command": "help", "description": "Show help and buttons"},
]


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    try:
        r = requests.post(f"{TG_API}/sendMessage", json=payload, timeout=30)
        data = r.json()
        if not data.get("ok"):
            print(f"sendMessage failed: {data}", flush=True)
        return data
    except requests.RequestException as e:
        print(f"sendMessage error: {e}", flush=True)
        return None


def handle_command(chat_id, text):
    cmd = text.split()[0].split("@")[0].lower()

    if cmd in ("/start", "/help"):
        names = ", ".join(c["name"] for c in config.COMPETITORS)
        send_message(chat_id, WELCOME.format(n=len(config.COMPETITORS), names=names),
                      reply_markup=REPLY_MARKUP)

    elif cmd == "/refresh":
        send_message(chat_id, "⏳ Running collection… this can take a minute.")
        try:
            r = requests.post(f"{API_URL}/api/refresh", timeout=300)
            r.raise_for_status()
            stats = r.json()
            errors = stats.get("errors") or []
            msg = (f"✅ Done: found {stats['found']}, new {stats['inserted']}"
                   + (f", errors {len(errors)}" if errors else ""))
        except Exception as e:
            msg = f"⚠️ Refresh failed: {e}"
        send_message(chat_id, msg)

    elif cmd == "/digest":
        try:
            r = requests.get(f"{API_URL}/api/telegram-digest", timeout=120)
            r.raise_for_status()
            for part in r.json()["messages"]:
                send_message(chat_id, part)
        except Exception as e:
            send_message(chat_id, f"⚠️ Could not build digest: {e}")

    elif cmd == "/status":
        try:
            r = requests.get(f"{API_URL}/api/overview", timeout=30)
            r.raise_for_status()
            data = r.json()
            last = data.get("last_run") or {}
            msg = (
                f"Last run: {last.get('finished_at') or last.get('started_at') or '—'}\n"
                f"Next run: {data.get('next_run') or '—'}\n"
                f"Items tracked: {data.get('total_items')}"
            )
        except Exception as e:
            msg = f"⚠️ Could not fetch status: {e}"
        send_message(chat_id, msg)

    else:
        send_message(chat_id, "Unknown command. Try /help.", reply_markup=REPLY_MARKUP)


def setup_bot_commands():
    try:
        requests.post(f"{TG_API}/setMyCommands", json={"commands": BOT_COMMANDS}, timeout=30)
    except requests.RequestException as e:
        print(f"setMyCommands failed: {e}", flush=True)


def main():
    if not TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set.")
    setup_bot_commands()
    print("Telegram bot started (long polling)…", flush=True)
    offset = 0
    while True:
        try:
            r = requests.get(f"{TG_API}/getUpdates",
                              params={"timeout": 30, "offset": offset}, timeout=40)
            data = r.json()
            if not data.get("ok"):
                print(f"getUpdates error: {data}", flush=True)
                time.sleep(5)
                continue
            for upd in data.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message") or {}
                text = msg.get("text", "")
                chat_id = msg.get("chat", {}).get("id")
                if not chat_id or not text:
                    continue
                if ALLOWED_CHAT_ID and str(chat_id) != str(ALLOWED_CHAT_ID):
                    continue
                if text in BUTTON_COMMANDS:
                    text = BUTTON_COMMANDS[text]
                if not text.startswith("/"):
                    continue
                try:
                    handle_command(chat_id, text)
                except Exception as e:
                    traceback.print_exc()
                    send_message(chat_id, f"⚠️ Internal error: {e}")
        except requests.RequestException as e:
            print(f"Polling error: {e}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
