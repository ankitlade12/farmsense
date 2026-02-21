"""
Re-apply ES|QL query fixes to Kibana tools (use ts/point fields, alias BUCKET outputs).
Run if tools revert after edits: uv run python agent_config/fix_esql_tools.py
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

def _default_kibana_url():
    es_url = os.environ.get("ES_URL", "").strip().rstrip("/")
    if ".es." in es_url:
        return es_url.replace(".es.", ".kb.").replace(":443", "")
    return ""

KIBANA_URL = (os.environ.get("KIBANA_URL") or _default_kibana_url()).strip().rstrip("/")
API_KEY = os.environ.get("KIBANA_API_KEY") or os.environ.get("ES_API_KEY")
if not KIBANA_URL or not API_KEY:
    print("Set KIBANA_URL and ES_API_KEY in .env")
    sys.exit(1)

import requests

HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
}


def get_tool(tool_id):
    r = requests.get(f"{KIBANA_URL}/api/agent_builder/tools/{tool_id}", headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    return r.json()


def update_tool(tool_id, body):
    r = requests.put(f"{KIBANA_URL}/api/agent_builder/tools/{tool_id}", headers=HEADERS, json=body, timeout=30)
    if r.status_code != 200:
        print(f"  PUT {tool_id}: {r.status_code} {r.text[:250]}")
        return False
    print(f"  Updated: {tool_id}")
    return True


def main():
    print("Applying ES|QL query fixes to Kibana tools...")

    # 1. geo_climate_query: alias BUCKET output so SORT can reference it
    tool_id = "geo_climate_query"
    current = get_tool(tool_id)
    if current:
        config = current.get("configuration", {})
        config = dict(config)
        config["query"] = (
            "FROM climate-timeseries "
            "| WHERE ST_DISTANCE(point, TO_GEOPOINT(?lat_lon)) < 200000 "
            "AND ts >= NOW() - 90 days "
            "| STATS current_avg_rainfall = AVG(rainfall_mm), "
            "current_avg_temp = AVG(temp_max_celsius) "
            "BY ts_week = BUCKET(ts, 1 week) "
            "| SORT ts_week DESC "
            "| LIMIT 13"
        )
        update_tool(tool_id, {
            "description": current.get("description"),
            "configuration": config,
        })
    else:
        print(f"  Could not GET {tool_id}")

    # 2. soil_profile_lookup: compute distance before KEEP so SORT can use it
    tool_id = "soil_profile_lookup"
    current = get_tool(tool_id)
    if current:
        config = current.get("configuration", {})
        config = dict(config)
        config["query"] = (
            "FROM soil-profiles "
            "| WHERE ST_DISTANCE(point, TO_GEOPOINT(?lat_lon)) < 100000 "
            "| EVAL dist_m = ST_DISTANCE(point, TO_GEOPOINT(?lat_lon)) "
            "| KEEP soil_type, drainage_class, water_holding_capacity, ph_level, texture, dist_m "
            "| SORT dist_m ASC "
            "| LIMIT 3"
        )
        update_tool(tool_id, {
            "description": current.get("description"),
            "configuration": config,
        })
    else:
        print(f"  Could not GET {tool_id}")

    # 3. pest_outbreak_lookup
    tool_id = "pest_outbreak_lookup"
    current = get_tool(tool_id)
    if current:
        config = current.get("configuration", {})
        config = dict(config)
        config["query"] = (
            "FROM pest-outbreaks | WHERE ST_DISTANCE(location, TO_GEOPOINT(?lat_lon)) < 300000 "
            "AND report_date >= NOW() - 30 days | STATS outbreak_count = COUNT(*), max_severity = MAX(severity) "
            "BY pest_name, crop_affected, severity | SORT outbreak_count DESC | LIMIT 10"
        )
        update_tool(tool_id, {"description": current.get("description"), "configuration": config})
        print(f"  Updated: {tool_id}")
    else:
        print(f"  Could not GET {tool_id}")

    print("Done.")


if __name__ == "__main__":
    main()
