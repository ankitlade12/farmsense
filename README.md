# 🌾 FarmSense — AI Agronomist for Smallholder Farmers
Python 3.10+ • Elasticsearch Serverless • License: MIT

*AI agronomist in your pocket — free, instant, hyper-local.*

Deliver hyper-contextual crop advisories by reasoning across open datasets — built for extension workers and smallholder farmers.

---

## Quick Highlights
- **Hyper-Contextual Advisories:** Synthesizes geo-aware climate analysis, semantic crop knowledge, regional pest outbreaks, and soil profile matching.
- **Real-Time Intelligence:** Uses ES|QL and `geo_point` filters to fetch exact recent rainfall and local pest alerts within milliseconds.
- **Semantic Crop Knowledge:** Leverages ELSER v2 for deep semantic search across FAO/CGIAR agronomic guidance.
- **Automated Alerts & Audits:** Elastic Workflows automatically log auditable alerts for critical pest risks.
- **Realistic Synthetic Data:** Pre-loaded with synthetic seasonal rainfall, ISRIC-style soil profiles, and realistic pest outbreaks (e.g., Fall Armyworm) to simulate a production environment.

---

## High Level Workflow

### User Flow
| Step | Phase | What Happens |
|---|---|---|
| 1 | 💬 **Intake** | Farmer describes situation (crop, location, symptoms, rain) in plain language via Kibana Chat. |
| 2 | 🔬 **Intelligence** | Agent normalizes the location and runs 4 parallel queries (Climate, Pest, Agronomy, Soil). |
| 3 | 📊 **Advisory** | Synthesizes data into a concrete advisory with risk level, primary diagnosis, and actions. |
| 4 | 📋 **Action & Log** | Logs the generated advisory for auditing. If risk is critical, triggers a webhook alert. |

---

## The Problem
When smallholder farmers face crop issues or strange weather patterns:
- **Generic Advice:** Agricultural manuals provide static information that isn't tailored to the farmer's specific soil, recent local climate, or emerging regional pest outbreaks.
- **Accessibility:** Access to expert agronomists is limited, expensive, and slow.
- **Usability:** Existing digital tools require complex form-filling or institutional expertise to operate, rather than understanding natural language.
- **No Integration:** No tool answers: "Based on the exact rainfall in my region over the last 30 days and my local soil type, what is causing my maize leaves to curl?"

## The Solution
FarmSense is a consumer-friendly AI agronomist that:
- **Ingests** your natural language description of crop issues and location.
- **Simulates** an expert's reasoning by cross-referencing 4 independent data streams (Climate, Pest, Soil, Crop Guidelines).
- **Delivers** a concrete, plain-language advisory with actionable immediate and preventive steps.
- **Provides** a full audit trail and autonomous alerting for severe biological threats.

---

## Architecture and Technical Overview

### System Architecture
One central agent (**FarmSense Advisor**) orchestrated via **Elastic Agent Builder**, utilizing 7 specialized tools to run the full flow.

### Data Pipeline
```text
┌───────────────────────────────────────────────────────────────┐
│                      FARMER INPUT                             │
│   "Maize in Oyo State, Nigeria. Leaves yellowing..."          │
└──────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────┐
│               FarmSense Advisor (single agent)                │
│                                                               │
│  Step 1 — Intake                                              │
│    geo_normalize_tool → lat_lon string                        │
│    crop_calendar_tool → planting/harvest window               │
│                                                               │
│  Step 2 — Intelligence (4 parallel queries)                   │
│    geo_climate_query    → rainfall + temp, last 90 days       │
│    pest_outbreak_lookup → outbreaks within 300 km             │
│    crop_knowledge_search → ELSER semantic search              │
│    soil_profile_lookup  → soil type, drainage, WHC            │
│                                                               │
│  Step 3 — Advisory                                            │
│    Synthesize into actionable diagnosis + actions             │
│                                                               │
│  Step 4 — Log                                                 │
│    log_advisory_workflow → advisory-history + alert           │
└──────────────────────────┬────────────────────────────────────┘
                           │
                           ▼
┌───────────────────────────────────────────────────────────────┐
│                   ELASTIC WORKFLOW                             │
│   Index to advisory-history; if CRITICAL → webhook alert      │
└───────────────────────────────────────────────────────────────┘
```

### Technical Deep Dive
**Geo-Aware Climate Analysis**  
Using ES|QL and `geo_point` mapping, the agent queries weekly rainfall and temperature aggregates within a 200 km radius over the last 90 days.

**Semantic Crop Knowledge**  
Leveraging the ELSER v2 model, FarmSense performs semantic searches on agricultural guidelines (FAO/CGIAR), matching the farmer's symptom descriptions to known agronomic issues.

**Regional Pest Outbreaks**  
Queries active pest outbreaks (e.g., from FAO EMPRES reports) within a 300 km radius of the farmer's coordinates using geo-distance filtering.

---

## Tech Stack
| Layer | Technology | Purpose |
|---|---|---|
| Search & Storage | Elasticsearch Serverless | Core vector, lexical, and geo-spatial data store |
| Agent Framework | Elastic Agent Builder | Orchestrates the LLM, tools, and user interaction |
| Semantic Search | ELSER v2 | Deep semantic retrieval for text-heavy agronomic data |
| Geo / Time-series | ES\|QL, `geo_point` | Fast analytical queries for climate and proximity |
| Automation | Elastic Workflows | Audit logging and critical pest alerts |
| Ingestion & Backend| Python 3.10+, `uv` | Scripts to populate indices and configure the agent |

---

## Features
- **🌍 Geo-Normalization Assistant:** Automatically converts plain-text region names into precise lat/lon coordinates for downstream tools.
- **🌦️ Hyper-Local Climate Matching:** Analyzes exact recent rainfall trends instead of relying on generic seasonal assumptions.
- **🐛 Proximity-based Pest Alerts:** Filters verified pest outbreaks by exact distance to the farmer.
- **🌱 Soil-Aware Modelling:** Adapts advice based on whether the local soil is matching (e.g., sandy vs. clay, drainage capacity).
- **⏱️ Instant Advisory:** Full pipeline executes and returns a comprehensive guide in under 60 seconds.
- **🚨 Automated Critical Alerts:** Built-in Elastic Workflow integration to alert authorities or NGOs automatically if a critical pest threshold is met.

---

## Quick Start

### Prerequisites
- Python 3.10+ with `uv`
- Elasticsearch Serverless project
- Kibana access

### Step 1: Clone and Setup
```bash
git clone https://github.com/your-username/farmsense.git
cd farmsense
```

### Step 2: Install Dependencies
```bash
uv sync
```

### Step 3: Configure Environment
Copy the environment template and fill in your Elasticsearch connection details:
```bash
cp .env.example .env
# Edit .env and add your ES_URL and ES_API_KEY
```

### Step 4: One-Command Setup
Run the setup script to create indices, ingest data, and deploy the agent:
```bash
./do_everything.sh
```
*(Alternatively, you can run the scripts step-by-step as outlined in the [original steps](#project-structure).)*

### Step 5: Open the App
In **Kibana**, navigate to **Agent Builder → Chat**, select **FarmSense Advisor** from the agent dropdown, and you are ready to use the app!

---

## Demo Walkthrough

1. Open **Kibana Agent Builder Chat**.
2. Select **FarmSense Advisor**.
3. Send a prompt like:  
   > *"I'm growing maize in Oyo State, Nigeria. The leaves are turning yellow and curling. We've had very little rain for 3 weeks. Plants are at 6-leaf stage."*
4. Watch the agent normalize the geo-location, query climate and pest data, and immediately return a complete advisory with actionable next steps.

---

## Agent Tools & Indices

### Key Indices (Pre-loaded with Synthetic Data)
| Index | Modelled after | Purpose |
|---|---|---|
| `crop-knowledge` | FAO/CGIAR guides | Text + ELSER `semantic_text` for guidance |
| `climate-timeseries` | NASA POWER weekly | Weekly rainfall & temp by location via `ts`, `point` |
| `pest-outbreaks` | FAO EMPRES reports | Outbreaks with `geo_point` and severity |
| `soil-profiles` | ISRIC SoilGrids | Soil type, drainage, water-holding capacity |
| `crop-calendars` | FAO crop calendar | Planting/harvest windows by country & region |
| `advisory-history` | Audit log | Generated advisories with risk levels |

### Agent Tools
| Tool | Type | What it does |
|---|---|---|
| `geo_normalize_tool` | ES\|QL | Region name → lat_lon string for downstream tools |
| `crop_calendar_tool` | ES\|QL | Crop + region → planting/harvest months |
| `geo_climate_query` | ES\|QL | Weekly rainfall/temp within 200 km, last 90 days |
| `pest_outbreak_lookup` | ES\|QL | Active outbreaks within 300 km, last 30 days |
| `soil_profile_lookup` | ES\|QL | Nearest soil profiles within 100 km |
| `crop_knowledge_search`| Index Search | ELSER semantic search on agronomic guidance |
| `log_advisory_workflow`| Workflow | Log advisory + trigger CRITICAL alert webhook |

---

### Telegram Bot Integration (Frontend)

FarmSense includes a production-ready mobile frontend via Telegram, utilizing FastAPI and the Elastic Agent API.

1. **Configure Environment:** Create a bot via [@BotFather](https://t.me/botfather) and add the following to your `.env`:
   ```env
   TELEGRAM_BOT_TOKEN=your_bot_token_here
   ALLOWED_CHAT_IDS=123456789,987654321  # Optional: Protect your bot from unauthorized users
   ```

2. **Start the FastAPI Server:**
   ```bash
   uv run python telegram_server.py
   ```

3. **Expose locally via ngrok:**
   ```bash
   ngrok http 8000
   ```

4. **Register the Webhook:**
   ```bash
   curl -F "url=https://<YOUR_NGROK_URL>/webhook" https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
   ```

5. **Test it:** Open Telegram, find your bot, and send `/start` or a farming query to watch the real-time AI execution pipeline!

## Project Structure
```text
farmsense/
├── agent_config/           # Kibana Agent Builder setup tools
├── ingestion/              # Data loading scripts (mappings, ELSER, etc.)
├── data/                   # Synthetic dataset CSV/JSONs
├── demo/                   # Demo scenarios and sample outputs
├── workflows/              # Elastic Workflow YAML definitions
├── tests/                  # Verification scripts
├── do_everything.sh        # One-command setup
└── pyproject.toml          # App dependencies
```

---

## Environment Variables
| Variable | Required | Description |
|---|---|---|
| `ES_URL` | Yes | Elasticsearch Serverless URL |
| `ES_API_KEY` | Yes | API Key to authenticate with Elasticsearch |

---

## Design Decisions
- **ES|QL over traditional DSL:** We used ES|QL extensively for the geo-climate, pest, and soil tools to allow complex aggregations and geo-filtering in visually simple, fast pipe-separated queries.
- **Parallel Intelligence Gathering:** The agent is given explicit instructions to query climate, pest, and soil data *in parallel* to keep the user's wait time under 60 seconds.
- **Workflow-Driven Alerts:** Instead of building a custom backend, we utilized Elastic Workflows natively to listen for "CRITICAL" risk evaluations by the agent and dispatch webhooks.
- **Synthetic vs Real Data:** Current indices use high-quality synthetic data to guarantee the demo works reliably anywhere, while the schema perfectly mirrors real-world datasets (ISRIC, NASA POWER) for seamless production upgrades.
- **Semantic First:** ELSER v2 powers the crop knowledge search to ensure that when a farmer says "leaves are weird," the engine understands semantic equivalents like "chlorosis" or "abnormal foliage."

---

## License
MIT License — see [LICENSE](LICENSE) file for details.
