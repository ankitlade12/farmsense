"""Test ES|QL tool queries against Elasticsearch (run after ingestion)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from utils import get_es_client


def run_esql(client, query, params=None):
    """Run ES|QL via transport or query API depending on client version."""
    body = {"query": query}
    if params:
        body["params"] = params
    try:
        resp = client.transport.perform_request(
            "POST", "/_query", body=body
        )
        return resp
    except Exception as e:
        # Some deployments use different endpoint
        return {"error": str(e)}


def main():
    client = get_es_client()

    tests = [
        ("crop-calendars (geo_normalize)", 'FROM crop-calendars | WHERE country == "Nigeria" AND region == "Oyo" | STATS lat = AVG(centroid_lat), lon = AVG(centroid_lon) BY country, region | LIMIT 1'),
        ("crop_calendar_tool", 'FROM crop-calendars | WHERE crop_name == "maize" AND country == "Nigeria" | KEEP crop_name, planting_start_month, harvest_end_month | LIMIT 3'),
        ("pest_outbreak (300km)", 'FROM pest-outbreaks | WHERE report_date >= NOW() - 90 days | LIMIT 5'),
        ("soil_profiles", 'FROM soil-profiles | LIMIT 3'),
    ]

    for name, query in tests:
        print(f"\n--- {name} ---")
        print(query[:80] + "..." if len(query) > 80 else query)
        result = run_esql(client, query)
        if "error" in result:
            print("Error:", result["error"])
        else:
            print("Result:", result.get("values", result)[:5] if result else "empty")


if __name__ == "__main__":
    main()
