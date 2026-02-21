"""Verify FarmSense indices exist and have expected document counts."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from utils import get_es_client

INDICES = [
    "crop-knowledge",
    "climate-timeseries",
    "pest-outbreaks",
    "soil-profiles",
    "crop-calendars",
    "advisory-history",
]


def main():
    client = get_es_client()
    for index in INDICES:
        exists = client.indices.exists(index=index)
        count = client.count(index=index)["count"] if exists else 0
        status = "OK" if exists else "MISSING"
        print(f"  {index}: {status}, docs = {count}")
    print("Done.")


if __name__ == "__main__":
    main()
