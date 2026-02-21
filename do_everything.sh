#!/usr/bin/env bash
# FarmSense: one-command setup — indices, data, tools, agent, ELSER, workflow.
# Run from repo root after: uv sync && cp .env.example .env (fill in ES_URL + ES_API_KEY).
set -e
cd "$(dirname "$0")"

if [[ ! -d .venv ]]; then
  echo "Run 'uv sync' first."
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Create .env with ES_URL and ES_API_KEY (see .env.example)."
  exit 1
fi

PY="${PY:-.venv/bin/python}"

echo "=== 1. Create Elasticsearch indices ==="
"$PY" ingestion/create_indices.py

echo "=== 2. Ingest data ==="
"$PY" ingestion/ingest_crop_knowledge.py
"$PY" ingestion/ingest_crop_calendars.py
"$PY" ingestion/ingest_climate_data.py
"$PY" ingestion/ingest_pest_outbreaks.py
"$PY" ingestion/ingest_soil_profiles.py

echo "=== 3. Create tools + FarmSense Advisor agent ==="
"$PY" agent_config/setup.py

echo ""
echo "Done. In Kibana Agent Chat, select 'FarmSense Advisor' and send a farmer message."
