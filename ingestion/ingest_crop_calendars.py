"""Ingest FAO crop calendar CSV into crop-calendars index."""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from utils import get_es_client, bulk_index

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
INDEX = "crop-calendars"


def load_docs():
    path = os.path.join(DATA_DIR, "fao_crop_calendars.csv")
    docs = []
    with open(path, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            doc = {
                "country": row["country"].strip(),
                "region": row["region"].strip(),
                "crop_name": row["crop_name"].strip().lower(),
                "planting_start_month": int(row["planting_start_month"]),
                "planting_end_month": int(row["planting_end_month"]),
                "harvest_start_month": int(row["harvest_start_month"]),
                "harvest_end_month": int(row["harvest_end_month"]),
                "season_type": row["season_type"].strip(),
                "centroid_lat": float(row["centroid_lat"]),
                "centroid_lon": float(row["centroid_lon"]),
            }
            docs.append(doc)
    return docs


def main():
    client = get_es_client()
    docs = load_docs()
    bulk_index(client, INDEX, docs)
    print(f"Done. Ingested {len(docs)} documents to {INDEX}.")


if __name__ == "__main__":
    main()
