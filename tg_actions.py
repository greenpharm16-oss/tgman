import asyncio
import json
import os
import random
import re
import urllib.parse
import urllib.request

from telethon import TelegramClient
from telethon.sessions import StringSession

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION = "".join(os.environ["TG_SESSION"].split())
VK_KEY = os.environ["VK_COMMUNITY_KEY"]
VK_USER_ID = int(os.environ["VK_USER_ID"])

# Чаты: username через запятую или с новой строки (можно ссылки t.me/...)
CHATS = []
for part in os.environ["TG_CHATS"].replace(",", "\n").splitlines():
    part = part.strip()
    part = re.sub(r"^(https?://)?(t\.me/|telegram\.me/)", "", part).lstrip("@").strip("/")
    if part:
        CHATS.append(part)

KEYWORDS = [
    "плитк", "плиточ", "укладк", "санузел", "санузл", "ламинат", "кварц",
    "винил", "заменить", "положить", "фартук", "отделк", "сантехник", "электрик",
    "посоветуйте мастера", "ищу мастера", "нужен мастер", "ищу бригаду",
]
RE = re.compile("|".join(KEYWORDS), re.IGNORECASE)

STATE_FILE = "state/state.json"


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f)


def vk_send(text):
    data = urllib.parse.urlencode({
        "user_id": VK_USER_ID,
        "random_id": random.randint(1, 2**31),
        "message": text,
        "access_token": VK_KEY,
        "v": "5.199",
    }).encode()
    with urllib.request.urlopen("https://api.vk.com/method/messages.send", data, timeout=20) as r:
        res = json.load(r)
    if "error" in res:
        print("VK error:", res["error"].get("error_msg"))


async def main():
    state = load_state()
    sent = 0
    async with TelegramClient(StringSession(SESSION), API_ID, API_HASH) as client:
        for i, chat in enumerate(CHATS, 1):
            try:
                entity = await client.get_entity(chat)
                key = str(entity.id)
                last = state.get(key)

                # первый запуск по чату: запоминаем последнее сообщение, ничего не шлём
                if last is None:
                    latest = await client.get_messages(entity, limit=1)
                    state[key] = latest[0].id if latest else 0
                    print(f"чат #{i}: инициализирован")
                    continue

                new = [m async for m in client.iter_messages(entity, min_id=last, limit=200)]
                new.reverse()

                username = getattr(entity, "username", None)
                title = getattr(entity, "title", None) or chat
                for m in new:
                    text = m.raw_text or ""
                    if not text or not RE.search(text):
                        continue
                    sender = await m.get_sender()
                    name = " ".join(filter(None, [
                        getattr(sender, "first_name", None),
                        getattr(sender, "last_name", None),
                    ])) or "Без имени"
                    nick = getattr(sender, "username", None)
                    who = f"{name} (@{nick})" if nick else name
                    link = (f"https://t.me/{username}/{m.id}" if username
                            else f"https://t.me/c/{entity.id}/{m.id}")
                    vk_send(f"🔔 Telegram: {title}\n\n👤 {who}\n\n{text[:700]}\n\n📝 {link}")
                    sent += 1
                    await asyncio.sleep(1)

                if new:
                    state[key] = max(m.id for m in new)
                print(f"чат #{i}: новых {len(new)}")
            except Exception as e:
                print(f"чат #{i}: ошибка {type(e).__name__}")
            await asyncio.sleep(1)

    save_state(state)
    print("отправлено уведомлений:", sent)


asyncio.run(main())
