"""Create all FarmSense Elasticsearch indices with mappings from the development plan."""
import sys
import os

# Allow running from repo root or from ingestion/
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

from utils import get_es_client

client = get_es_client()

indices = {
    "crop-knowledge": {
        "mappings": {
            "properties": {
                "crop_name": {"type": "keyword"},
                "region": {"type": "keyword"},
                "content_type": {"type": "keyword"},
                "text": {"type": "text"},
                "text_semantic": {
                    "type": "semantic_text",
                    "inference_id": ".elser-2-elasticsearch",
                },
                "symptoms": {"type": "text"},
                "pest_names": {"type": "keyword"},
                "source": {"type": "keyword"},
                "language": {"type": "keyword"},
                "last_updated": {"type": "date"},
            }
        }
    },
    "climate-timeseries": {
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "ts": {"type": "date"},
                "location": {"type": "geo_point"},
                "point": {"type": "geo_point"},
                "country": {"type": "keyword"},
                "region_name": {"type": "keyword"},
                "rainfall_mm": {"type": "float"},
                "temp_max_celsius": {"type": "float"},
                "temp_min_celsius": {"type": "float"},
                "humidity_pct": {"type": "float"},
                "solar_radiation": {"type": "float"},
            }
        }
    },
    "pest-outbreaks": {
        "mappings": {
            "properties": {
                "report_date": {"type": "date"},
                "location": {"type": "geo_point"},
                "country": {"type": "keyword"},
                "region": {"type": "keyword"},
                "pest_name": {"type": "keyword"},
                "crop_affected": {"type": "keyword"},
                "severity": {"type": "keyword"},
                "description": {"type": "text"},
                "source": {"type": "keyword"},
            }
        }
    },
    "soil-profiles": {
        "mappings": {
            "properties": {
                "location": {"type": "geo_point"},
                "point": {"type": "geo_point"},
                "country": {"type": "keyword"},
                "region": {"type": "keyword"},
                "soil_type": {"type": "keyword"},
                "drainage_class": {"type": "keyword"},
                "water_holding_capacity": {"type": "keyword"},
                "ph_level": {"type": "float"},
                "organic_carbon_pct": {"type": "float"},
                "texture": {"type": "keyword"},
            }
        }
    },
    "crop-calendars": {
        "mappings": {
            "properties": {
                "country": {"type": "keyword"},
                "region": {"type": "keyword"},
                "crop_name": {"type": "keyword"},
                "planting_start_month": {"type": "integer"},
                "planting_end_month": {"type": "integer"},
                "harvest_start_month": {"type": "integer"},
                "harvest_end_month": {"type": "integer"},
                "season_type": {"type": "keyword"},
                "centroid_lat": {"type": "float"},
                "centroid_lon": {"type": "float"},
            }
        }
    },
    "advisory-history": {
        "mappings": {
            "properties": {
                "@timestamp": {"type": "date"},
                "session_id": {"type": "keyword"},
                "location": {"type": "geo_point"},
                "country": {"type": "keyword"},
                "crop": {"type": "keyword"},
                "symptoms_reported": {"type": "text"},
                "risk_level": {"type": "keyword"},
                "advisory_text": {"type": "text"},
                "primary_diagnosis": {"type": "keyword"},
                "pest_flagged": {"type": "keyword"},
                "climate_anomaly": {"type": "text"},
            }
        }
    },
}

if __name__ == "__main__":
    for index_name, config in indices.items():
        if client.indices.exists(index=index_name):
            print(f"Index {index_name} already exists, skipping.")
        else:
            client.indices.create(index=index_name, body=config)
            print(f"Created index: {index_name}")
