"""
FarmSense setup: create all tools and the FarmSense Advisor agent via Kibana API.
Run after: uv sync, .env with ES_URL + ES_API_KEY, and indices created + data ingested.

Usage: uv run python agent_config/setup.py

Ref: https://www.elastic.co/docs/solutions/search/agent-builder/kibana-api
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

import requests


def _default_kibana_url():
    es_url = os.environ.get("ES_URL", "").strip().rstrip("/")
    if ".es." in es_url:
        return es_url.replace(".es.", ".kb.").replace(":443", "")
    return ""


KIBANA_URL = (os.environ.get("KIBANA_URL") or _default_kibana_url()).strip().rstrip("/")
API_KEY = os.environ.get("KIBANA_API_KEY") or os.environ.get("ES_API_KEY")
if not KIBANA_URL or not API_KEY:
    print("Set KIBANA_URL and ES_API_KEY (or KIBANA_API_KEY) in .env")
    sys.exit(1)

HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
}

# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "id": "geo_normalize_tool",
        "type": "esql",
        "description": "Resolve country/region to lat/lon. Returns a lat_lon WKT string (e.g. POINT(3.95 7.85)) for use in downstream geo tools.",
        "configuration": {
            "query": (
                "FROM crop-calendars "
                "| WHERE country == ?country_name AND region == ?region_text "
                "| STATS lat = AVG(centroid_lat), lon = AVG(centroid_lon) BY country, region "
                "| EVAL lat_lon = CONCAT(\"POINT (\", TO_STRING(lon), \" \", TO_STRING(lat), \")\") "
                "| KEEP lat_lon, lat, lon, country, region "
                "| LIMIT 1"
            ),
            "params": {
                "country_name": {"type": "string", "description": "Country name (e.g. Nigeria)"},
                "region_text": {"type": "string", "description": "Region or state (e.g. Oyo)"},
            },
        },
    },
    {
        "id": "crop_calendar_tool",
        "type": "esql",
        "description": "Get planting and harvest windows for a crop in a country/region.",
        "configuration": {
            "query": (
                "FROM crop-calendars "
                "| WHERE crop_name == ?crop_name AND (country == ?country OR region == ?region) "
                "| KEEP crop_name, planting_start_month, planting_end_month, "
                "harvest_start_month, harvest_end_month, season_type "
                "| LIMIT 3"
            ),
            "params": {
                "crop_name": {"type": "string", "description": "Crop name (e.g. maize)"},
                "country": {"type": "string", "description": "Country"},
                "region": {"type": "string", "description": "Region or state"},
            },
        },
    },
    {
        "id": "geo_climate_query",
        "type": "esql",
        "description": "Get weekly rainfall and temp within 200 km of a point for the last 90 days.",
        "configuration": {
            "query": (
                "FROM climate-timeseries "
                "| WHERE ST_DISTANCE(point, TO_GEOPOINT(?lat_lon)) < 200000 "
                "AND ts >= NOW() - 90 days "
                "| STATS current_avg_rainfall = AVG(rainfall_mm), "
                "current_avg_temp = AVG(temp_max_celsius) "
                "BY ts_week = BUCKET(ts, 1 week) "
                "| SORT ts_week DESC "
                "| LIMIT 13"
            ),
            "params": {
                "lat_lon": {"type": "string", "description": "WKT point from geo_normalize_tool, e.g. POINT(3.95 7.85)"},
            },
        },
    },
    {
        "id": "pest_outbreak_lookup",
        "type": "esql",
        "description": "Find pest/disease outbreaks within 300 km in the last 30 days.",
        "configuration": {
            "query": (
                "FROM pest-outbreaks "
                "| WHERE ST_DISTANCE(location, TO_GEOPOINT(?lat_lon)) < 300000 "
                "AND report_date >= NOW() - 30 days "
                "| STATS outbreak_count = COUNT(*), max_severity = MAX(severity) "
                "BY pest_name, crop_affected, severity "
                "| SORT outbreak_count DESC "
                "| LIMIT 10"
            ),
            "params": {
                "lat_lon": {"type": "string", "description": "WKT point from geo_normalize_tool, e.g. POINT(3.95 7.85)"},
            },
        },
    },
    {
        "id": "soil_profile_lookup",
        "type": "esql",
        "description": "Get soil type, drainage, water-holding capacity within 100 km of location.",
        "configuration": {
            "query": (
                "FROM soil-profiles "
                "| WHERE ST_DISTANCE(point, TO_GEOPOINT(?lat_lon)) < 100000 "
                "| EVAL dist_m = ST_DISTANCE(point, TO_GEOPOINT(?lat_lon)) "
                "| KEEP soil_type, drainage_class, water_holding_capacity, ph_level, texture, dist_m "
                "| SORT dist_m ASC "
                "| LIMIT 3"
            ),
            "params": {
                "lat_lon": {"type": "string", "description": "WKT point from geo_normalize_tool, e.g. POINT(3.95 7.85)"},
            },
        },
    },
    {
        "id": "crop_knowledge_search",
        "type": "index_search",
        "description": "Semantic search on crop-knowledge for symptoms, pests, and agronomic guidance (ELSER).",
        "configuration": {
            "pattern": "crop-knowledge",
        },
    },
]

# ---------------------------------------------------------------------------
# FarmSense Advisor agent (single agent, full pipeline)
# ---------------------------------------------------------------------------

FARMSENSE_ADVISOR_INSTRUCTIONS = """\
You are FarmSense: an AI agronomist for smallholder farmers. When a farmer describes their situation you MUST run the full pipeline below. Do NOT stop after Step 1.
You may also receive a real-time [7-Day Forecast Context] from the Open-Meteo Live API in the user's message. Use this explicitly in your WHY THIS IS HAPPENING and IMMEDIATE ACTIONS.

**Step 1 – Intake**
Parse the message: crop_name, location (country, region), symptoms, growth_stage, rainfall_concern.
Call geo_normalize_tool(country_name, region_text). It returns a lat_lon in WKT format (e.g. "POINT (3.95 7.85)") — use this EXACT string in every subsequent tool call.
Call crop_calendar_tool(crop_name, country, region) to get the planting/harvest window.

**Step 2 – Intelligence (required — call ALL four tools)**
Pass the EXACT lat_lon WKT string from Step 1 to each tool:
- geo_climate_query(lat_lon) — rainfall and temperature, last 90 days
- pest_outbreak_lookup(lat_lon) — active outbreaks within 300 km, last 30 days
- crop_knowledge_search — semantic query with the farmer's symptoms and crop
- soil_profile_lookup(lat_lon) — soil type, drainage, water-holding capacity
From results, flag: CLIMATE_ANOMALY if rainfall is well below normal; PEST_RISK_HIGH/CRITICAL if relevant outbreaks nearby.

**Step 3 – Advisory (use this EXACT format)**

**RISK LEVEL:** [LOW / MEDIUM / HIGH / CRITICAL]

**PRIMARY DIAGNOSIS:**
[One sentence: most likely cause]

**WHY THIS IS HAPPENING:**
[2–3 sentences with specific numbers from the data: e.g. "Rainfall was X mm/week (Y% below normal)", "Fall Armyworm outbreak reported Z km away with HIGH severity", "Soil is [type] with [drainage] — moisture is lost quickly".]

**IMMEDIATE ACTIONS (Next 48 Hours):**
1. [Specific action]
2. [Specific action]

**PREVENTIVE ACTIONS (Next 2 Weeks):**
1. [Specific action]
2. [Specific action]

**WATCH FOR:**
[Warning signs that need escalation]

Simple language, no jargon, practical for farmers without expensive inputs.

**Step 4 – Log advisory**
Call log_advisory_workflow with: timestamp (ISO), session_id (""), lat, lon, country, crop, symptoms, risk_level, advisory_text, primary_diagnosis, pest_flagged, climate_anomaly."""

ADVISOR_AGENT = {
    "id": "farmsense-advisor",
    "name": "FarmSense Advisor",
    "description": "Full pipeline: intake → climate & pest & knowledge & soil → actionable advisory.",
    "configuration": {
        "instructions": FARMSENSE_ADVISOR_INSTRUCTIONS,
        "tools": [{
            "tool_ids": [
                "geo_normalize_tool",
                "crop_calendar_tool",
                "geo_climate_query",
                "pest_outbreak_lookup",
                "crop_knowledge_search",
                "soil_profile_lookup",
                "log_advisory_workflow",
            ]
        }],
    },
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def upsert_tool(tool):
    tool_id = tool["id"]
    r = requests.get(f"{KIBANA_URL}/api/agent_builder/tools/{tool_id}", headers=HEADERS, timeout=30)
    if r.status_code == 200:
        body = {"description": tool["description"], "configuration": tool["configuration"]}
        r2 = requests.put(f"{KIBANA_URL}/api/agent_builder/tools/{tool_id}", headers=HEADERS, json=body, timeout=30)
        if r2.status_code == 200:
            print(f"  Updated tool: {tool_id}")
            return True
        print(f"  PUT {tool_id}: {r2.status_code} {r2.text[:200]}")
        return False
    else:
        r2 = requests.post(f"{KIBANA_URL}/api/agent_builder/tools", headers=HEADERS, json=tool, timeout=30)
        if r2.status_code in (200, 201):
            print(f"  Created tool: {tool_id}")
            return True
        print(f"  POST {tool_id}: {r2.status_code} {r2.text[:200]}")
        return False


def upsert_agent(agent):
    agent_id = agent["id"]
    r = requests.get(f"{KIBANA_URL}/api/agent_builder/agents/{agent_id}", headers=HEADERS, timeout=30)
    body = {
        "name": agent["name"],
        "description": agent["description"],
        "configuration": agent["configuration"],
    }
    if r.status_code == 200:
        r2 = requests.put(f"{KIBANA_URL}/api/agent_builder/agents/{agent_id}", headers=HEADERS, json=body, timeout=30)
    else:
        body["id"] = agent_id
        r2 = requests.post(f"{KIBANA_URL}/api/agent_builder/agents", headers=HEADERS, json=body, timeout=30)
    if r2.status_code in (200, 201):
        print(f"  Created/updated agent: {agent['name']}")
        return True
    print(f"  Agent {agent_id}: {r2.status_code} {r2.text[:200]}")
    return False


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Setting up FarmSense tools...")
    for t in TOOLS:
        upsert_tool(t)

    print("\nSetting up FarmSense Advisor agent...")
    upsert_agent(ADVISOR_AGENT)

    print("\nStarting ELSER (optional)...")
    try:
        from start_elser import main as start_elser
        start_elser()
    except Exception as e:
        print(f"  ELSER: {e} (start manually in Kibana → ML → Trained Models)")

    print("\nAdding workflow tool (optional)...")
    try:
        from add_workflow_tool_to_advisor import main as add_workflow
        add_workflow()
    except Exception as e:
        print(f"  Workflow: {e} (create workflow in Kibana first, see OPTIONAL_SETUP.md)")

    print("\nDone. In Kibana Agent Chat, select 'FarmSense Advisor' and send a farmer message.")


if __name__ == "__main__":
    main()
