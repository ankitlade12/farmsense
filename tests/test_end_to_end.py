"""Full pipeline test: run after agents are configured in Kibana.

This script only verifies that data is present and indices are queryable.
Actual end-to-end (natural language -> advisory) must be run in Kibana Chat
or via Elastic Agent Builder API.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from utils import get_es_client


def main():
    client = get_es_client()

    # Require minimum docs for pipeline to be useful
    checks = [
        ("crop-knowledge", 1),
        ("crop-calendars", 1),
        ("climate-timeseries", 1),
        ("pest-outbreaks", 0),  # optional
        ("soil-profiles", 1),
    ]
    ok = True
    for index, min_count in checks:
        count = client.count(index=index)["count"]
        if count < min_count:
            print(f"FAIL: {index} has {count} docs (min {min_count})")
            ok = False
        else:
            print(f"OK: {index} has {count} docs")

    if ok:
        print("\nData layer ready. Configure agents in Kibana and run demo scenarios from demo/demo_scenarios.md")
    else:
        print("\nRun ingestion scripts first. See README Quick Start.")
        sys.exit(1)


if __name__ == "__main__":
    main()
