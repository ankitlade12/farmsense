"""Shared Elasticsearch client and helpers for FarmSense ingestion."""
import os
from elasticsearch import Elasticsearch


def get_es_client():
    """Initialize Elasticsearch client from environment variables.
    Use either ES_CLOUD_ID or ES_URL (Elasticsearch endpoint)."""
    api_key = os.environ.get("ES_API_KEY")
    if not api_key:
        raise ValueError("Set ES_API_KEY in environment (e.g. .env)")

    cloud_id = os.environ.get("ES_CLOUD_ID")
    es_url = os.environ.get("ES_URL", "").strip().rstrip("/")

    if cloud_id:
        return Elasticsearch(cloud_id=cloud_id, api_key=api_key)
    if es_url:
        return Elasticsearch(hosts=[es_url], api_key=api_key)
    raise ValueError("Set either ES_CLOUD_ID or ES_URL in environment (e.g. .env)")


def bulk_index(client, index_name, documents):
    """Bulk index documents into Elasticsearch."""
    from elasticsearch.helpers import bulk

    actions = [{"_index": index_name, "_source": doc} for doc in documents]
    success, errors = bulk(client, actions, raise_on_error=False)
    print(f"Indexed {success} docs to {index_name}. Errors: {len(errors)}")
    if errors:
        for e in errors[:5]:
            print("  ", e)
    return success, errors
