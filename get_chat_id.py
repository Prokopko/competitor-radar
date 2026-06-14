"""
Helper: find your chat_id.

How to use:
  1) export TELEGRAM_BOT_TOKEN="7712345678:AAH...xyz"
  2) send your bot any message in Telegram (e.g. /start)
  3) python get_chat_id.py

The script asks Telegram for the latest updates and shows the senders' chat_id.
Put that chat_id into TELEGRAM_CHAT_ID.
"""
import os
import sys

import requests

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


def main():
    if not TOKEN:
        sys.exit("TELEGRAM_BOT_TOKEN is not set (export TELEGRAM_BOT_TOKEN=...)")

    url = f"https://api.telegram.org/bot{TOKEN}/getUpdates"
    r = requests.get(url, timeout=20)
    data = r.json()

    if not data.get("ok"):
        sys.exit(f"Telegram returned an error: {data}")

    updates = data.get("result", [])
    if not updates:
        print("No updates yet. Send your bot a message in Telegram and run this again.")
        return

    seen = {}
    for upd in updates:
        msg = upd.get("message") or upd.get("channel_post") or {}
        chat = msg.get("chat", {})
        if chat:
            cid = chat.get("id")
            label = chat.get("title") or " ".join(
                filter(None, [chat.get("first_name"), chat.get("last_name")])
            ) or chat.get("username") or chat.get("type")
            seen[cid] = label

    print("Chats found:")
    for cid, label in seen.items():
        print(f"  chat_id = {cid}   ({label})")
    print("\nPut the chat_id you need into the TELEGRAM_CHAT_ID variable.")


if __name__ == "__main__":
    main()
