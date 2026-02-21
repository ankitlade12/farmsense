# FarmSense Architecture

## In practice

- **Who uses it:** Extension workers, NGO field staff, or farmers with a smartphone. They open Kibana Chat, select **FarmSense Advisor**, and describe their situation (crop, location, symptoms, rain).
- **What they get:** A concrete advisory with **risk level**, **primary diagnosis**, **why it's happening** (citing actual climate/pest/soil data for that location), and **immediate + preventive actions** in plain language.
- **Data in production:** Climate from CHIRPS or NASA POWER; pests from national plant protection / FAO EMPRES; soil from ISRIC; crop calendars from FAO. The demo uses **synthetic but realistic** data so the agent's answers behave like a real deployment.

## Pipeline

```
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

## Indices

| Index              | Purpose                                 | Key fields                       |
|--------------------|-----------------------------------------|----------------------------------|
| crop-knowledge     | FAO/CGIAR text + ELSER semantic_text    | text, text_semantic, crop_name   |
| climate-timeseries | Weekly rainfall & temp by location      | ts, point, rainfall_mm           |
| pest-outbreaks     | Outbreaks with geo_point and severity   | location, report_date, severity  |
| soil-profiles      | Soil type, drainage, water-holding      | point, soil_type, drainage_class |
| crop-calendars     | Planting/harvest by country & region    | centroid_lat/lon, crop_name      |
| advisory-history   | Audit log of generated advisories       | risk_level, advisory_text        |

## Tools

| Tool                   | Type         | What it does                                           |
|------------------------|--------------|--------------------------------------------------------|
| geo_normalize_tool     | ES\|QL       | Region name → lat_lon string for downstream tools      |
| crop_calendar_tool     | ES\|QL       | Crop + region → planting/harvest months                |
| geo_climate_query      | ES\|QL       | Weekly rainfall/temp within 200 km, last 90 days       |
| pest_outbreak_lookup   | ES\|QL       | Active outbreaks within 300 km, last 30 days           |
| soil_profile_lookup    | ES\|QL       | Nearest soil profiles within 100 km                    |
| crop_knowledge_search  | Index Search | ELSER semantic search on agronomic guidance            |
| log_advisory_workflow  | Workflow     | Log advisory + trigger CRITICAL alert webhook          |

## Data realism (demo)

| Data            | Demo                                                    | Production                                |
|-----------------|---------------------------------------------------------|-------------------------------------------|
| Climate         | Synthetic weekly data; West African dry season pattern  | CHIRPS, NASA POWER, national weather APIs |
| Pest outbreaks  | Synthetic with real names (Fall Armyworm, etc.)          | FAO EMPRES, national surveillance         |
| Soil            | ISRIC-style types (Ferric Lixisol, etc.)                | ISRIC SoilGrids, national soil maps       |
| Crop calendars  | FAO-style planting/harvest by country/region            | FAO or ministry crop calendars            |
| Crop knowledge  | Short agronomic texts; ELSER for semantic search        | FAO/CGIAR guides, extension bulletins     |
