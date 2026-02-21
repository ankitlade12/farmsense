# FarmSense — AI Agronomist for Smallholder Farmers

*AI agronomist in your pocket — free, instant, hyper-local.*

## Overview

FarmSense is built on **Elastic Agent Builder** and delivers hyper-contextual crop advisories by reasoning across four open datasets:

- **Geo-aware climate analysis** — current vs. historical rainfall near the farmer's location (ES|QL + `geo_point`)
- **Semantic crop knowledge** — FAO/CGIAR agronomic guidance via ELSER semantic search
- **Regional pest outbreaks** — active outbreaks within 300 km (geo-distance filtering)
- **Soil profile matching** — soil type, drainage, and water-holding capacity for the region

A farmer describes their situation in plain language; the **FarmSense Advisor** agent runs a full pipeline (intake → intelligence → advisory) and returns a specific, actionable advisory in under 60 seconds. For critical pest risk, an Elastic Workflow logs an auditable alert.

The demo uses **realistic synthetic data** (seasonal rainfall, real pest/soil names) so advisories match what you'd see with real data — see [ARCHITECTURE.md](ARCHITECTURE.md) for details.

## Architecture

One agent (**FarmSense Advisor**) with 7 tools runs the full flow:

```
Farmer input → geo_normalize → crop_calendar → geo_climate + pest_outbreak + crop_knowledge + soil_profile → Advisory → log_advisory_workflow
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full diagram and data realism table.

## Tech Stack

| Component         | Technology                     |
|-------------------|--------------------------------|
| Search & Storage  | Elasticsearch Serverless       |
| Agent Framework   | Elastic Agent Builder          |
| Semantic Search   | ELSER v2                       |
| Geo / Time-series | ES\|QL, `geo_point`            |
| Automation        | Elastic Workflows              |
| Ingestion         | Python 3.10+, elasticsearch-py |

## Quick Start

### One-command setup

```bash
uv sync
cp .env.example .env   # fill in ES_URL + ES_API_KEY
./do_everything.sh
```

This creates indices, ingests data, creates tools and the **FarmSense Advisor** agent, starts ELSER (if available), and attaches the advisory workflow tool.

### Step-by-step

```bash
uv sync
cp .env.example .env   # fill in ES_URL + ES_API_KEY

# Create indices + ingest data
uv run python ingestion/create_indices.py
uv run python ingestion/ingest_crop_knowledge.py
uv run python ingestion/ingest_crop_calendars.py
uv run python ingestion/ingest_climate_data.py
uv run python ingestion/ingest_pest_outbreaks.py
uv run python ingestion/ingest_soil_profiles.py

# Create tools + agent
uv run python agent_config/setup.py
```

### Test it

In Kibana, open **Agent Builder → Chat**, select **FarmSense Advisor** from the agent dropdown, and send:

> I'm growing maize in Oyo State, Nigeria. The leaves are turning yellow and curling. We've had very little rain for 3 weeks. Plants are at 6-leaf stage.

**Optional:** ELSER (semantic search), advisory workflow (logging + alerts) → see [OPTIONAL_SETUP.md](OPTIONAL_SETUP.md).

## Project Structure

```
farmsense/
├── agent_config/           # Kibana Agent Builder setup
│   ├── setup.py            # Create tools + FarmSense Advisor agent
│   ├── fix_esql_tools.py   # Re-apply ES|QL query fixes
│   ├── start_elser.py      # Start ELSER model deployment
│   ├── add_workflow_tool_to_advisor.py
│   └── create_workflow_via_kibana_api.py
├── ingestion/              # Data loading scripts
│   ├── create_indices.py   # Index mappings
│   ├── ingest_*.py         # One per index
│   └── utils.py            # ES client helper
├── data/                   # Synthetic datasets
├── demo/                   # Demo scenarios and sample outputs
├── workflows/              # Elastic Workflow YAML
├── tests/                  # Verification scripts
├── do_everything.sh        # One-command setup
└── pyproject.toml          # Dependencies (uv/pip)
```

## Data Sources (Synthetic)

| Index              | Modelled after                | Documents |
|--------------------|-------------------------------|-----------|
| crop-knowledge     | FAO/CGIAR guides              | ~20       |
| climate-timeseries | NASA POWER weekly aggregates  | ~3,200    |
| pest-outbreaks     | FAO EMPRES reports            | 7         |
| soil-profiles      | ISRIC SoilGrids               | 6         |
| crop-calendars     | FAO crop calendar             | 17        |
| advisory-history   | Audit log (written by agent)  | —         |

## License

MIT — see [LICENSE](LICENSE).
