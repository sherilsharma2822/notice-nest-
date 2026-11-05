"""Find your Telegram chat ID.

1. In Telegram, open your bot (created with @BotFather) and press Start / send "hi".
2. Put TELEGRAM_BOT_TOKEN in .env
3. Run:  python tools/get_telegram_chat_id.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402

from app.config import Config  # noqa: E402


def main() -> None:
    if not Config.TELEGRAM_BOT_TOKEN:
        print("Put TELEGRAM_BOT_TOKEN in your .env file first.")
        raise SystemExit(1)
    resp = requests.get(f"https://api.telegram.org/bot{Config.TELEGRAM_BOT_TOKEN}/getUpdates", timeout=20)
    if resp.status_code != 200:
        print(f"Telegram said HTTP {resp.status_code}. Check the bot token.")
        raise SystemExit(1)
    seen = {}
    for update in resp.json().get("result", []):
        chat = (update.get("message") or {}).get("chat") or {}
        if chat.get("id"):
            seen[chat["id"]] = chat.get("first_name") or chat.get("title") or "?"
    if not seen:
        print("No messages found. Send any message to your bot in Telegram, then run this again.")
        return
    for chat_id, name in seen.items():
        print(f"Chat ID {chat_id}  (name: {name})")


if __name__ == "__main__":
    main()
