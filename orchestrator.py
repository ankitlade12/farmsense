import os
import httpx
from datetime import datetime
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests

KIBANA_URL = os.environ.get("KIBANA_URL", "").strip().rstrip("/")
if not KIBANA_URL:
    es_url = os.environ.get("ES_URL", "").strip().rstrip("/")
    if ".es." in es_url:
        KIBANA_URL = es_url.replace(".es.", ".kb.").replace(":443", "")

API_KEY = os.environ.get("KIBANA_API_KEY") or os.environ.get("ES_API_KEY")
HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
}
AGENT_ID = "farmsense-advisor"
# The default Agent Builder model can't reliably fill tool params (it sends empty
# args). Force a strong tool-calling model. Override via env if your connector id differs.
CONNECTOR_ID = os.environ.get("ELASTIC_CONNECTOR_ID", "Anthropic-Claude-Sonnet-4-5")

# Per-chat conversation memory (chat_id -> Agent Builder conversation_id) so the bot
# can handle multi-turn follow-ups ("2", "yes I have a stream", ...) with context.
_conversations = {}


def reset_conversation(chat_id) -> None:
    """Forget a chat's thread so the next message starts fresh (used on /start)."""
    _conversations.pop(str(chat_id), None)


async def fetch_weather(lat: float, lon: float) -> str:
    """Fetch 7-day weather forecast from Open-Meteo."""
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=temperature_2m_max,precipitation_sum&timezone=auto"
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(url, timeout=10.0)
            resp.raise_for_status()
            data = resp.json()
            daily = data.get("daily", {})
            times = daily.get("time", [])
            precips = daily.get("precipitation_sum", [])
            temps = daily.get("temperature_2m_max", [])
            
            lines = ["7-Day Forecast:"]
            for i in range(min(7, len(times))):
                lines.append(f"- {times[i]}: {precips[i]}mm rain, Max {temps[i]}°C")
            return "\n".join(lines)
        except Exception as e:
            return f"Weather forecast unavailable: {str(e)}"

# We will implement call_elastic_agent and call_localizer_agent later

async def call_elastic_agent(session_id: str, message: str, conversation_id: str = None):
    """Calls the FarmSense Advisor agent via the Kibana converse API.

    Returns (response_text, conversation_id). Pass the returned conversation_id back
    on the next turn to keep multi-turn context. A stale id (404) is retried fresh.
    """
    url = f"{KIBANA_URL}/api/agent_builder/converse"

    async def _post(conv):
        payload = {"input": message, "agent_id": AGENT_ID, "connector_id": CONNECTOR_ID}
        if conv:
            payload["conversation_id"] = conv
        async with httpx.AsyncClient() as client:
            # The agent runs several tools incl. ELSER — it needs a high timeout.
            resp = await client.post(url, headers=HEADERS, json=payload, timeout=180.0)
            resp.raise_for_status()
            return resp.json()

    try:
        try:
            data = await _post(conversation_id)
        except httpx.HTTPStatusError as e:
            # An expired/unknown conversation_id 404s — start a fresh thread.
            if conversation_id and e.response.status_code == 404:
                data = await _post(None)
            else:
                raise
        new_conv = data.get("conversation_id") or conversation_id
        response_obj = data.get("response", {})
        if isinstance(response_obj, dict) and "message" in response_obj:
            return response_obj["message"], new_conv
        if "message" in data:
            return data["message"], new_conv
        if "text" in data:
            return data["text"], new_conv
        return "No response from FarmSense Advisor.", new_conv
    except httpx.HTTPStatusError as e:
        return f"Error contacting Elastic Agent Builder API: {e.response.status_code} - {e.response.text}", conversation_id
    except Exception as e:
        return f"Agent invocation failed: {str(e)}", conversation_id

async def call_localizer_agent(raw_advisory: str, system_context: str = "") -> str:
    """
    Second LLM Agent to rewrite the scientific advisory into a mobile-friendly format.
    If an OpenAI key is provided, it uses it. Otherwise, it just returns a slightly formatted version of the input to ensure the demo works out of the box.
    """
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    if not openai_api_key:
        print("No OPENAI_API_KEY found. Skipping Localizer Agent LLM call.")
        # Fallback localizer behavior for demo seamlessly
        return f"👨‍🌾 <b>FarmSense Action Plan</b>\n\n{raw_advisory.strip()}"
        
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {openai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "gpt-4o-mini",
        "messages": [
            {
                "role": "system",
                "content": "You are a friendly, expert local extension worker in Africa talking to a smallholder farmer via WhatsApp/Telegram. Rewrite the provided scientific agronomic advisory to be highly legible on a mobile screen. Use emojis, simple language, and clear bullet points for immediate actions. Speak directly to the farmer. Output ONLY the localized text in HTML format (use <b>, <i>, <u> but no markdown asterisks)." + f"\nContext: {system_context}"
            },
            {
                "role": "user",
                "content": raw_advisory
            }
        ]
    }
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, headers=headers, json=payload, timeout=20.0)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except Exception as e:
            print(f"Localizer Agent failed: {e}")
            return raw_advisory # Fallback to raw text

async def process_farmer_message(chat_id: str, text: str) -> str:
    """End-to-end pipeline for one user message, with multi-turn memory.

    The first message in a thread is enriched with a live weather forecast and starts
    a new Agent Builder conversation; follow-ups reuse the stored conversation_id so the
    agent remembers context (e.g. a terse "2" answering its own question).
    """
    cid = str(chat_id)
    prev_conv = _conversations.get(cid)

    if prev_conv:
        # Continuing a thread — send the raw follow-up; the agent already has context.
        prompt = text
    else:
        # First turn — enrich with a live 7-day forecast for the demo location.
        demo_lat, demo_lon = 7.85, 3.95  # Oyo, Nigeria center
        weather_forecast = await fetch_weather(demo_lat, demo_lon)
        prompt = (
            f"{text}\n\n[System Context: Real-time 7-Day Forecast for user's rough "
            f"location ({demo_lat}, {demo_lon}):\n{weather_forecast}]"
        )

    # 1. Primary agent (scientific agronomist) — remembers the thread via conversation_id
    print(f"Calling FarmSense Advisor (chat {cid}, {'follow-up' if prev_conv else 'new thread'})...")
    raw_advisory, conv_id = await call_elastic_agent(cid, prompt, prev_conv)
    if conv_id:
        _conversations[cid] = conv_id

    if "Error" in raw_advisory or "failed" in raw_advisory.lower():
        return raw_advisory

    # 2. Secondary agent (localizer) — mobile-friendly formatting
    final_output = await call_localizer_agent(raw_advisory)
    return final_output
