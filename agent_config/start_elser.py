"""
Try to start ELSER trained model deployment via Elasticsearch API.
Run: uv run python agent_config/start_elser.py
Uses ES_URL and ES_API_KEY from .env.
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

# Common ELSER model IDs (Serverless may use .elser-2-elasticsearch)
ELSER_IDS = [".elser-2-elasticsearch", "elser", ".elser-2", "elastic__elser-v2"]


def main():
    client = get_es_client()

    for model_id in ELSER_IDS:
        try:
            # Use official ML client (avoids transport params API differences)
            r = client.ml.start_trained_model_deployment(
                model_id=model_id,
                wait_for="started",
                timeout="2m",
            )
            print(f"Started ELSER deployment: {model_id}")
            print(r)
            return
        except Exception as e:
            err = str(e).lower()
            if "404" in err or "not found" in err or "unknown" in err:
                continue
            if "existing deployment" in err or "already exist" in err:
                print(f"ELSER already running: {model_id}")
                return
            print(f"  {model_id}: {e}")
            continue

    print("Could not start ELSER via API (model may not exist or Serverless uses a different API).")
    print("Start ELSER manually: Kibana → Machine Learning → Trained Models / Inference → find ELSER → Start.")


if __name__ == "__main__":
    main()
