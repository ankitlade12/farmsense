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
IMPORTANT: Call tools STRICTLY ONE AT A TIME. Never issue more than one tool call in a single step — make one call, wait for its result, then make the next. Whenever you call a tool, fill in concrete values for ALL of its parameters (from the farmer's message or a previous tool result). NEVER call a tool with empty arguments.
You may also receive a real-time [7-Day Forecast Context] from the Open-Meteo Live API in the user's message. Use this explicitly in your WHY THIS IS HAPPENING and IMMEDIATE ACTIONS.

**Step 1 – Intake**
Parse the message: crop_name, location (country, region), symptoms, growth_stage, rainfall_concern.
Call geo_normalize_tool(country_name, region_text) with the EXACT country and region from the farmer's message (e.g. country_name="Nigeria", region_text="Oyo State"). It returns a lat_lon in WKT format (e.g. "POINT (3.95 7.85)") — use this EXACT string in every subsequent tool call.

**Step 2 – Intelligence (call these tools ONE AT A TIME — make one call, wait for its result, then the next; do NOT batch or parallelize them)**
Take the EXACT lat_lon WKT string that geo_normalize_tool returned (e.g. "POINT (3.95 7.85)") and include it in every call below. Each call MUST contain its parameter value — never send empty arguments:
1. geo_climate_query — pass lat_lon = the POINT string (rainfall & temp, last 90 days)
2. pest_outbreak_lookup — pass lat_lon = the POINT string (outbreaks within 300 km, last 30 days)
3. crop_knowledge_search — pass nlQuery = the farmer's symptoms + crop (e.g. "maize leaves yellowing curling drought")
4. soil_profile_lookup — pass lat_lon = the POINT string (soil type, drainage, water-holding capacity)
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

**Step 4 – Follow up**
After presenting the advisory, end with ONE short, friendly follow-up question for the farmer.
(Audit logging and CRITICAL pest-risk webhook alerts are handled automatically by the
advisory-alert-workflow at the platform layer — do not call a logging tool yourself.)"""

ADVISOR_AGENT = {
    "id": "farmsense-advisor",
    "name": "FarmSense Advisor",
    "description": "Full pipeline: intake → climate & pest & knowledge & soil → actionable advisory.",
    "configuration": {
        "instructions": FARMSENSE_ADVISOR_INSTRUCTIONS,
        # NOTE: log_advisory_workflow is intentionally NOT attached. Workflow-type
        # tools don't expose their inputs as an LLM schema in this Agent Builder
        # preview (schema.properties is empty), so the model calls them with {} and
        # the index step fails on an empty timestamp. The advisory-alert-workflow
        # still exists for audit/alerting; invoke it at the app layer (see
        # orchestrator) or from the Workflows UI.
        "tools": [{
            "tool_ids": [
                "geo_normalize_tool",
                "geo_climate_query",
                "pest_outbreak_lookup",
                "crop_knowledge_search",
                "soil_profile_lookup",
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

    print("\nCreating advisory-alert-workflow (optional)...")
    try:
        # Create the workflow so it exists for audit/alerting + the Command Center
        # story, but do NOT attach it as an agent tool (see ADVISOR_AGENT note).
        from create_workflow_via_kibana_api import try_workflows_api
        if try_workflows_api():
            print("  Workflow ready (not attached to agent — invoke app-layer / Workflows UI).")
    except Exception as e:
        print(f"  Workflow: {e} (create it in Kibana Workflows, paste workflows/advisory_alert_workflow.yaml)")

    print("\nDone. In Kibana Agent Chat, select 'FarmSense Advisor' and send a farmer message.")


if __name__ == "__main__":
    main()
