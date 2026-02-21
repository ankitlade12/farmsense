# Kibana Setup for FarmSense

Do this **after** ingestion (indices and data are in Elasticsearch).

## Automated setup (recommended)

```bash
uv run python agent_config/setup.py
```

This creates all 7 tools and the **FarmSense Advisor** agent. The agent runs the full pipeline (intake → intelligence → advisory) in one conversation.

## Re-apply ES|QL fixes

If tools revert (e.g. after editing in the Kibana UI):

```bash
uv run python agent_config/fix_esql_tools.py
```

## Manual setup in Kibana UI

If you prefer to create everything by hand, or if the API approach fails:

### 1. Create ES|QL tools

In Agent Builder → Tools → New Tool → Type: ES|QL.

**geo_normalize_tool** — Resolve region to lat/lon (returns WKT for downstream tools):
```
FROM crop-calendars | WHERE country == ?country_name AND region == ?region_text | STATS lat = AVG(centroid_lat), lon = AVG(centroid_lon) BY country, region | EVAL lat_lon = CONCAT("POINT (", TO_STRING(lon), " ", TO_STRING(lat), ")") | KEEP lat_lon, lat, lon, country, region | LIMIT 1
```

**crop_calendar_tool** — Planting/harvest windows:
```
FROM crop-calendars | WHERE crop_name == ?crop_name AND (country == ?country OR region == ?region) | KEEP crop_name, planting_start_month, planting_end_month, harvest_start_month, harvest_end_month, season_type | LIMIT 3
```

**geo_climate_query** — Weekly climate, last 90 days:
```
FROM climate-timeseries | WHERE ST_DISTANCE(point, TO_GEOPOINT(?lat_lon)) < 200000 AND ts >= NOW() - 90 days | STATS current_avg_rainfall = AVG(rainfall_mm), current_avg_temp = AVG(temp_max_celsius) BY ts_week = BUCKET(ts, 1 week) | SORT ts_week DESC | LIMIT 13
```

**pest_outbreak_lookup** — Recent outbreaks nearby:
```
FROM pest-outbreaks | WHERE ST_DISTANCE(location, TO_GEOPOINT(?lat_lon)) < 300000 AND report_date >= NOW() - 30 days | STATS outbreak_count = COUNT(*), max_severity = MAX(severity) BY pest_name, crop_affected, severity | SORT outbreak_count DESC | LIMIT 10
```

**soil_profile_lookup** — Soil characteristics:
```
FROM soil-profiles | WHERE ST_DISTANCE(point, TO_GEOPOINT(?lat_lon)) < 100000 | EVAL dist_m = ST_DISTANCE(point, TO_GEOPOINT(?lat_lon)) | KEEP soil_type, drainage_class, water_holding_capacity, ph_level, texture, dist_m | SORT dist_m ASC | LIMIT 3
```

### 2. Create Index Search tool

- **Name:** crop_knowledge_search
- **Index:** crop-knowledge
- **Type:** Index Search (ELSER semantic search on `text_semantic`)

### 3. Create the FarmSense Advisor agent

- **Name:** FarmSense Advisor
- **Tools:** all 7 tools above + log_advisory_workflow (if workflow exists)
- **Instructions:** copy from `agent_config/setup.py` (the `FARMSENSE_ADVISOR_INSTRUCTIONS` string)

### 4. ELSER (optional)

If crop_knowledge_search fails with a timeout:
1. Kibana → Machine Learning → Trained Models
2. Find ELSER (`.elser-2-elasticsearch`) → Start/Deploy
3. Wait until status is Started, then retry

### 5. Advisory workflow (optional)

See [OPTIONAL_SETUP.md](OPTIONAL_SETUP.md) for creating the advisory-alert-workflow and attaching it to the agent.
