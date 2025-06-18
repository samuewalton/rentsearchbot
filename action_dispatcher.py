import json
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from proxies import get_random_proxy

from rank_actions import ActionType

API_ID = 27192546
API_HASH = "c723c6a76df29fa005b8ad1080a95a1d"

ACTIONS_FILE = "rank_actions.json"
SESSIONS_FILE = "session_status.json"


async def send_notification(client, user_id, message):
    try:
        await client.send_message(user_id, message)
        return True
    except Exception as e:
        print(f"[!] Failed to send message to {user_id}: {e}")
        return False


async def handle_action(action, sessions):
    session_data = sessions.get(action["asset_name"])
    if not session_data:
        print(f"[!] No session found for {action['asset_name']}")
        return

    session_string = session_data.get("string")
    if not session_string:
        print(f"[!] Session string missing for {action['asset_name']}")
        return

    proxy = session_data.get("proxy") or get_random_proxy()
    async with TelegramClient(StringSession(session_string), API_ID, API_HASH, proxy=proxy) as client:
        message = f"נכס {action['asset_name']} ירד למקום {action['rank']} בחיפוש עבור '{action['keyword']}'."
        if action["action"] == ActionType.SUGGEST_REPLACEMENT:
            message += "\nנשקל לספק נכס חלופי."
        elif action["action"] == ActionType.REFUND_PARTIAL:
            message += "\nיוחזר חלק מהתשלום בהתאם."

        await send_notification(client, user_id=action["target_id"], message=message)


async def main():
    with open(ACTIONS_FILE, "r", encoding="utf-8") as f:
        actions = json.load(f)

    with open(SESSIONS_FILE, "r", encoding="utf-8") as f:
        sessions = json.load(f)

    await asyncio.gather(*(handle_action(a, sessions) for a in actions))


if __name__ == "__main__":
    asyncio.run(main())
