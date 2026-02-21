"""Ingest synthetic FAO EMPRES-style pest outbreaks into pest-outbreaks index."""
import json
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
INDEX = "pest-outbreaks"


def load_docs():
    path = os.path.join(DATA_DIR, "synthetic_pest_outbreaks.json")
    with open(path, "r") as f:
        return json.load(f)


def main():
    client = get_es_client()
    docs = load_docs()
    bulk_index(client, INDEX, docs)
    print(f"Done. Ingested {len(docs)} documents to {INDEX}.")


if __name__ == "__main__":
    main()
