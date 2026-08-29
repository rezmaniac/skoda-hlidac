#!/usr/bin/env python3
"""Secure one-time Telegram setup; keeps the bot token out of files and shell history."""

from __future__ import annotations

import getpass
import json
import subprocess
import sys
import urllib.parse
import urllib.request


REPOSITORY = "rezmaniac/skoda-hlidac"


def telegram_call(token: str, method: str, data: dict | None = None) -> dict:
    body = urllib.parse.urlencode(data or {}).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}",
        data=body,
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if not payload.get("ok"):
        raise RuntimeError(f"Telegram odmítl požadavek {method}.")
    return payload


def save_secret(name: str, value: str) -> None:
    subprocess.run(
        ["gh", "secret", "set", name, "--repo", REPOSITORY],
        input=value,
        text=True,
        check=True,
    )


def main() -> int:
    print("Telegram nastavení pro Škoda hlídač")
    print("Token se nebude zobrazovat ani ukládat do souboru.")
    token = getpass.getpass("Vlož token od @BotFather: ").strip()
    if not token:
        print("Token nebyl zadán.", file=sys.stderr)
        return 1

    bot = telegram_call(token, "getMe")["result"]
    updates = telegram_call(token, "getUpdates").get("result", [])
    chats = []
    for update in reversed(updates):
        message = update.get("message") or update.get("edited_message") or {}
        chat = message.get("chat") or {}
        if chat.get("id") is not None:
            chats.append(chat)
    if not chats:
        print(f"\nNejdřív otevři @{bot['username']} v Telegramu, stiskni Start a pošli /start.")
        print("Potom spusť tento skript znovu.")
        return 2

    chat = chats[0]
    chat_id = str(chat["id"])
    display_name = chat.get("title") or " ".join(
        part for part in (chat.get("first_name"), chat.get("last_name")) if part
    ) or chat_id
    print(f"Nalezený příjemce: {display_name}")

    save_secret("TELEGRAM_BOT_TOKEN", token)
    save_secret("TELEGRAM_CHAT_ID", chat_id)
    telegram_call(token, "sendMessage", {
        "chat_id": chat_id,
        "text": "✅ Hlídač vozů je propojený. Testovací zpráva dorazila správně.",
    })
    print("Hotovo: oba GitHub Secrets jsou uložené a testovací zpráva byla odeslána.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
