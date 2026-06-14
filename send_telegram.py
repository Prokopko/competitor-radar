"""
Sends the weekly digest to Telegram.

Environment variables:
  TELEGRAM_BOT_TOKEN   token from @BotFather
  TELEGRAM_CHAT_ID     where to send (find it: python get_chat_id.py)

Usage:
  python send_telegram.py            # send the latest week's digest
  python send_telegram.py --refresh  # collect fresh data first, then send
  python send_telegram.py --week 1   # previous week's digest

This is a standalone script: hook it up to cron directly, or call it
from n8n as a command. The same digest is also served by the
GET /api/telegram-digest endpoint — more convenient for n8n HTTP nodes.
"""
import argparse
import os
import sys
import time

import requests

import database
import telegram_digest

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")


def send_message(text: str):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, json=payload, timeout=30)
    data = r.json()
    if not data.get("ok"):
        raise RuntimeError(f"Telegram error: {data}")
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh", action="store_true",
                        help="run collection before sending")
    parser.add_argument("--week", type=int, default=0,
                        help="week index (0 — most recent)")
    args = parser.parse_args()

    if not TOKEN or not CHAT_ID:
        sys.exit("TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID must be set in the environment.")

    database.init_db()

    if args.refresh:
        from collectors import run_collection
        print("Collecting data…")
        stats = run_collection(progress=print)
        print(f"Collected: found {stats['found']}, new {stats['inserted']}, "
              f"errors {len(stats['errors'])}")

    messages = telegram_digest.build_messages(week_index=args.week)
    for i, msg in enumerate(messages):
        send_message(msg)
        print(f"Sent message {i + 1}/{len(messages)} ({len(msg)} chars)")
        if i < len(messages) - 1:
            time.sleep(0.5)  # small pause to avoid hitting rate limits

    print("Done.")


if __name__ == "__main__":
    main()
