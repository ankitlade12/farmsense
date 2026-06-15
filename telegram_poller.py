import os
import asyncio
import httpx
import re
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
ALLOWED_CHAT_IDS = os.environ.get("ALLOWED_CHAT_IDS", "").strip().split(",")
ALLOWED_CHAT_IDS = [x.strip() for x in ALLOWED_CHAT_IDS if x.strip()]

from telegram_server import send_telegram_message, edit_telegram_message, progress_updater, process_and_reply
from orchestrator import reset_conversation

async def poll_telegram():
    print(f"Starting long-polling for FarmSense bot...")
    
    # First, delete any existing webhook to enable getUpdates
    async with httpx.AsyncClient() as client:
        await client.get(f"{TELEGRAM_API_URL}/deleteWebhook")

    offset = 0
    async with httpx.AsyncClient(timeout=60.0) as client:
        while True:
            try:
                url = f"{TELEGRAM_API_URL}/getUpdates?timeout=50&offset={offset}"
                resp = await client.get(url, timeout=60.0)
                data = resp.json()
                
                if not data.get("ok"):
                    continue

                for result in data.get("result", []):
                    offset = result["update_id"] + 1
                    message = result.get("message", {})
                    chat = message.get("chat", {})
                    chat_id = chat.get("id")
                    text = message.get("text", "")

                    if not chat_id or not text:
                        continue

                    if str(chat_id) not in ALLOWED_CHAT_IDS and ALLOWED_CHAT_IDS:
                        print(f"Unauthorized chat_id: {chat_id}")
                        await send_telegram_message(chat_id, "You are not authorized to use this bot.")
                        continue

                    print(f"Received message: {text}")

                    cmd = text.strip().lower()
                    if cmd.startswith("/start"):
                        reset_conversation(chat_id)  # begin a fresh thread
                        welcome_msg = (
                            "👨‍🌾 <b>Welcome to FarmSense!</b> 🌱\n\n"
                            "I'm your AI agronomist assistant. Tell me about your farm to get started:\n\n"
                            "1. <b>What crop</b> are you growing? (e.g. maize, cassava)\n"
                            "2. <b>Where</b> is your farm? (country and region)\n"
                            "3. <b>What symptoms</b> are you seeing?\n"
                            "4. <b>What growth stage</b> is the crop in?\n\n"
                            "<i>Example: I am growing Maize in Oyo. Leaves are completely yellow because of no rain.</i>\n\n"
                            "<i>Tip: I remember our conversation — reply to my questions, or send /new to start over.</i>"
                        )
                        asyncio.create_task(send_telegram_message(chat_id, welcome_msg))
                        continue

                    if cmd.startswith("/new") or cmd.startswith("/reset"):
                        reset_conversation(chat_id)
                        asyncio.create_task(send_telegram_message(chat_id, "🆕 Fresh start. Describe your crop, location, symptoms, and growth stage."))
                        continue

                    msg_id = await send_telegram_message(chat_id, "<i>FarmSense Advisor is analyzing your situation...</i>")
                    if msg_id:
                        updater_task = asyncio.create_task(progress_updater(chat_id, msg_id))
                        asyncio.create_task(process_and_reply(chat_id, text, msg_id, updater_task))
                    else:
                        asyncio.create_task(process_and_reply(chat_id, text, None, None))

            except Exception as e:
                print(f"Polling error: {e}")
                await asyncio.sleep(5)

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("ERROR: No Telegram token found in .env")
        exit(1)
    asyncio.run(poll_telegram())
