"""Query Elasticsearch and print index summary + sample docs. Run after ingestion."""
import os
import sys
import json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from utils import get_es_client


def main():
    client = get_es_client()

    indices = [
        "crop-knowledge",
        "crop-calendars",
        "climate-timeseries",
        "pest-outbreaks",
        "soil-profiles",
        "advisory-history",
    ]

    print("=" * 60)
    print("ELASTICSEARCH OUTPUT CHECK")
    print("=" * 60)

    for index in indices:
        try:
            count = client.count(index=index)["count"]
            print(f"\n--- {index} (total: {count} docs) ---")
            if count == 0:
                print("  (empty)")
                continue
            resp = client.search(index=index, body={"query": {"match_all": {}}, "size": 2})
            for i, hit in enumerate(resp["hits"]["hits"][:2], 1):
                doc = hit["_source"]
                # Truncate long fields for readability
                preview = {}
                for k, v in list(doc.items())[:6]:
                    if isinstance(v, str) and len(v) > 60:
                        preview[k] = v[:60] + "..."
                    elif isinstance(v, dict):
                        preview[k] = str(v)[:50] + "..."
                    else:
                        preview[k] = v
                print(f"  Sample {i}: {json.dumps(preview, default=str)}")
        except Exception as e:
            print(f"  Error: {e}")

    print("\n" + "=" * 60)
    print("Done. Data is in Elasticsearch.")
    print("=" * 60)


if __name__ == "__main__":
    main()
