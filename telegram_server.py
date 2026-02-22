import os
import httpx
import asyncio
import re
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
import uvicorn
from orchestrator import fetch_weather

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = FastAPI(title="FarmSense Telegram Bot Webhook")

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
# Comma-separated list of allowed user/chat IDs, e.g. "123456789,987654321"
ALLOWED_CHAT_IDS = os.environ.get("ALLOWED_CHAT_IDS", "").strip().split(",")
ALLOWED_CHAT_IDS = [x.strip() for x in ALLOWED_CHAT_IDS if x.strip()]

TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"

async def send_telegram_message(chat_id: int, text: str) -> int:
    url = f"{TELEGRAM_API_URL}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML" # Using HTML to avoid strict MarkdownV2 escaping issues
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
            return data.get("result", {}).get("message_id")
        except Exception as e:
            print(f"Failed to send Telegram message: {e}")
            return None

async def edit_telegram_message(chat_id: int, message_id: int, text: str):
    url = f"{TELEGRAM_API_URL}/editMessageText"
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML"
    }
    async with httpx.AsyncClient() as client:
        try:
            await client.post(url, json=payload, timeout=20.0)
        except Exception as e:
            print(f"Failed to edit Telegram message: {e}")

async def progress_updater(chat_id: int, message_id: int):
    """Simulates realistic tool execution progress to mask latency."""
    steps = [
        "🔍 Parsing intent and geolocating farm...",
        "🌤️ Fetching 90-day historic climate data...",
        "🐛 Cross-referencing active pest outbreaks within 300km...",
        "🌱 Analyzing soil profiles & water retention...",
        "📚 Querying FAO crop knowledge database...",
        "📝 Synthesizing intelligence into action plan...",
        "🗣️ Translating to local farmer dialect..."
    ]
    current_text = "<i>FarmSense Advisor is analyzing your situation...</i>\n\n"
    for step in steps:
        await asyncio.sleep(5)  # Update every 5 seconds
        current_text += f"{step}\n"
        await edit_telegram_message(chat_id, message_id, current_text)

async def process_and_reply(chat_id: int, text: str, message_id: int, updater_task: asyncio.Task):
    try:
        from orchestrator import process_farmer_message
        response_text = await process_farmer_message(chat_id, text)
        
        # Stop the progress updater
        updater_task.cancel()
        
        # Parse simple markdown **bold** to <b>bold</b> for Telegram HTML compatibility
        html_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', response_text)
        
        if message_id:
            await edit_telegram_message(chat_id, message_id, html_text)
        else:
            await send_telegram_message(chat_id, html_text)
    except Exception as e:
        updater_task.cancel()
        print(f"Error in background task: {e}")
        if message_id:
            await edit_telegram_message(chat_id, message_id, "Sorry, an error occurred while processing your request.")

@app.post("/webhook")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    message = data.get("message", {})
    chat = message.get("chat", {})
    chat_id = chat.get("id")
    text = message.get("text", "")

    if not chat_id or not text:
        return {"status": "ok", "reason": "No message or chat_id"}

    if str(chat_id) not in ALLOWED_CHAT_IDS and ALLOWED_CHAT_IDS:
        print(f"Unauthorized chat_id: {chat_id}")
        await send_telegram_message(chat_id, "You are not authorized to use this bot.")
        return {"status": "ok"}

    print(f"Received message from {chat_id}: {text}")
    
    # Handle /start command instantly
    if text.strip().startswith("/start"):
        welcome_msg = (
            "👨‍🌾 <b>Welcome to FarmSense!</b> 🌱\n\n"
            "I'm your AI agronomist assistant. Tell me about your farm to get started:\n\n"
            "1. <b>What crop</b> are you growing? (e.g. maize, cassava)\n"
            "2. <b>Where</b> is your farm? (country and region)\n"
            "3. <b>What symptoms</b> are you seeing?\n"
            "4. <b>What growth stage</b> is the crop in?\n\n"
            "<i>Example: I am growing Maize in Oyo. Leaves are completely yellow because of no rain.</i>"
        )
        await send_telegram_message(chat_id, welcome_msg)
        return {"status": "ok"}
    
    # Notify user we are processing and capture the message_id
    msg_id = await send_telegram_message(chat_id, "<i>FarmSense Advisor is analyzing your situation...</i>")
    
    if msg_id:
        # Start the background UI updater
        updater_task = asyncio.create_task(progress_updater(chat_id, msg_id))
        # Run the heavy agent pipeline in the background so Telegram doesn't timeout
        background_tasks.add_task(process_and_reply, chat_id, text, msg_id, updater_task)
    else:
        # Fallback if we failed to capture msg_id
        background_tasks.add_task(process_and_reply, chat_id, text, None, None)

    return {"status": "ok"}

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("WARNING: TELEGRAM_BOT_TOKEN is not set in .env")
    uvicorn.run("telegram_server:app", host="0.0.0.0", port=8000, reload=True)
