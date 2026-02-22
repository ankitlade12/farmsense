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

async def call_elastic_agent(session_id: str, message: str) -> str:
    """Calls the farm-sense-advisor agent via Kibana API."""
    # Using the /converse endpoint for Agent Builder interacting
    url = f"{KIBANA_URL}/api/agent_builder/converse"
    
    # We do NOT pass conversation_id when starting a fresh session, 
    # otherwise Kibana looks for an existing conversation ID and throws a 404.
    payload = {
        "input": message,
        "agent_id": AGENT_ID
    }
    
    async with httpx.AsyncClient() as client:
        try:
            # The agent executes 7 complex tools including ELSER search. It needs a high timeout.
            resp = await client.post(url, headers=HEADERS, json=payload, timeout=180.0)
            resp.raise_for_status()
            data = resp.json()
            # The converse API returns the agent's response inside response.message
            response_obj = data.get("response", {})
            if "message" in response_obj:
                return response_obj["message"]
            
            # Fallback if the structure is different (e.g., direct text)
            if "message" in data:
                 return data["message"]
            if "text" in data:
                 return data["text"]
                 
            return "No response from FarmSense Advisor."
        except httpx.HTTPStatusError as e:
            text = e.response.text
            return f"Error contacting Elastic Agent Builder API: {e.response.status_code} - {text}"
        except Exception as e:
            return f"Agent invocation failed: {str(e)}"

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
    """End-to-end pipeline execution for a user message."""
    # 1. We could attempt to extract lat/lon from the text to get real-time weather here.
    # For a hackathon demo, if we don't have an NLP extractor doing it perfectly, we trigger the agent first.
    # However, since the agent needs weather, we'll try to extract simple intent or ask the LLM for coords.
    # To keep it robust without extra LLM hops, we just pass the message.
    
    # Ideally, we call a quick LLM extraction for Lat/Lon.
    # For now, let's assume the user provided coordinates or we just let Elastic handle it
    # We will just call the Elastic Agent. The weather tool could be called if coordinates are found.
    
    weather_context = ""
    # Example logic: if the farmer provides a known region like "Oyo", we could look it up.
    # Instead, we just append a note that they should check weather or we hardcode a location for the demo.
    demo_lat, demo_lon = 7.85, 3.95 # Oyo Nigeria center
    weather_forecast = await fetch_weather(demo_lat, demo_lon)
    
    prompt = f"{text}\n\n[System Context: Real-time 7-Day Forecast for user's rough location ({demo_lat}, {demo_lon}):\n{weather_forecast}]"
    
    # 2. Call Primary Agent (Scientific Agronomist)
    print("Calling FarmSense Advisor...")
    raw_advisory = await call_elastic_agent(str(chat_id), prompt)
    print("Primary Agent Response received.")
    
    if "Error" in raw_advisory or "failed" in raw_advisory.lower():
        return raw_advisory
        
    # 3. Call Secondary Agent (Localizer)
    print("Calling Localizer Agent...")
    final_output = await call_localizer_agent(raw_advisory)
    print("Secondary Agent Response received.")
    
    return final_output
