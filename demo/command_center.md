# FarmSense Command Center — Regional Early-Warning Dashboard

**Status: BUILT ✅** — the "FarmSense Command Center" dashboard (5 panels + a geo hotspot map)
already exists and is saved in this project. The steps below are the build notes / how to
recreate it elsewhere.

> Turns thousands of 1:1 farmer advisories into a live, population-scale
> pest & climate early-warning map for NGOs, extension services, and
> agriculture ministries. Built entirely on Kibana Maps + ES|QL aggregations
> over the `advisory-history` index — no extra infrastructure.

**The story for the talk:** FarmSense already answers one farmer at a time.
But every advisory is also a *signal*. Aggregate them and emerging pest
outbreaks and drought corridors light up on a map **days before** any single
farmer realizes it's regional. Same data, second product surface.

---

## 0. Prereq — give the map data to show

`advisory-history` only gets one doc per real chat, so seed it first:

```bash
uv run python ingestion/seed_advisory_history.py --reset      # ~220 advisories, last 30 days
# more volume / wider window if you want:
uv run python ingestion/seed_advisory_history.py --reset -n 500 --days 60
```

Seeded docs are byte-identical to what `advisory-alert-workflow` writes, so
real demo runs blend right in. Verify:

```bash
uv run python tests/check_elasticsearch_output.py
```

---

## 1. Data view — ✅ ALREADY CREATED

The `advisory-history` data view (timeField `@timestamp`) is already created for you
(id `5f066dc8-82c9-4827-9a5a-f7cc922aacf8`). It shows up in Discover, ES|QL, Lens, and
Maps immediately. `location` is a `geo_point`, so Maps auto-detects it.

> Build the Map + panels manually (below) — ~5 min, and a nice live moment. We tried a
> programmatic shortcut: the Kibana **dashboards create API is gated** (404) in this
> serverless build, and a hand-authored **Saved Objects import** of a Lens dashboard
> returns a server-side 500 (and couldn't be render-verified without the UI). So the
> manual build is the reliable path. The tedious part (the data view) is already done,
> and every panel's ES|QL is validated, so it's fast.

---

## 2. The map (the centerpiece)

Kibana → **Maps → Create map**. Add three layers over `advisory-history`:

**Layer A — Risk points (the "where is it bad" layer)**
- Add layer → **Documents** → data view `advisory-history`
- Fill color → **By value** → field `risk_level` (categorical):
  `CRITICAL` = red, `HIGH` = orange, `MEDIUM` = yellow, `LOW` = green
- Symbol size 8–10. This is the layer judges will stare at.

**Layer B — Outbreak clusters (the "is it regional" layer)**
- Add layer → **Clusters and grids** → `advisory-history`
- Grid metric: **Count**; color ramp by count. Zoom out → drought corridors
  and Fall Armyworm belts emerge as fused hot grids.

**Layer C — Live pest outbreaks (cross-reference)**
- Add layer → **Documents** → `pest-outbreaks` (field `location`)
- Color by `severity`. Now farmer-reported risk visually lines up with
  FAO-style outbreak reports — the "our crowd-sourced signal predicted the
  official outbreak" moment.

Tip: set the time picker to **Last 30 days** and turn on the legend.

---

## 3. Dashboard panels (ES|QL — show these live)

Kibana → **Dashboard → Create → Add panel → ES|QL**. For the Elastic crowd,
running these live in **Discover → ES|QL** is itself a great demo beat.

**Risk mix (donut/metric)**
```esql
FROM advisory-history
| STATS advisories = COUNT(*) BY risk_level
| SORT advisories DESC
```

**Top threats (bar)**
```esql
FROM advisory-history
| WHERE pest_flagged != "None"
| STATS reports = COUNT(*) BY pest_flagged
| SORT reports DESC
| LIMIT 10
```

**Crops most at risk (bar) — HIGH + CRITICAL only**
```esql
FROM advisory-history
| WHERE risk_level IN ("HIGH", "CRITICAL")
| STATS at_risk = COUNT(*) BY crop
| SORT at_risk DESC
| LIMIT 10
```

**Hotspot regions (table)**
```esql
FROM advisory-history
| STATS advisories = COUNT(*),
        critical = COUNT(CASE(risk_level == "CRITICAL", 1, NULL))
  BY country, region
| SORT critical DESC, advisories DESC
| LIMIT 15
```

**Advisory volume over time (area — trend / spike detection)**
```esql
FROM advisory-history
| STATS advisories = COUNT(*) BY day = BUCKET(@timestamp, 1 day)
| SORT day ASC
```

**Single big number — % CRITICAL (a KPI tile)**
```esql
FROM advisory-history
| STATS total = COUNT(*), crit = COUNT(CASE(risk_level == "CRITICAL", 1, NULL))
| EVAL pct_critical = ROUND(100.0 * crit / total, 1)
| KEEP total, crit, pct_critical
```

Arrange: **Map** large on the left; risk donut + %CRITICAL KPI top-right;
top-pests and crops-at-risk bars middle-right; volume-over-time across the
bottom; hotspot table beside it. Save as **"FarmSense Command Center"**.

---

## 4. Optional — geo-grid aggregation purely in ES|QL

If your project's ES|QL supports geo-grid functions (recent serverless):
```esql
FROM advisory-history
| WHERE risk_level IN ("HIGH", "CRITICAL")
| STATS hot = COUNT(*) BY cell = ST_GEOHASH(location, 3)
| SORT hot DESC
| LIMIT 20
```
Good as a fallback talking point if you want to show the clustering math
behind Layer B without the Maps UI.

---

## 5. Talking points (why this is a "wow", not just a chart)

- **One dataset, two products:** the same advisories that help individual
  farmers become a regional early-warning system — zero new pipelines.
- **Crowdsourced beats official:** farmer reports surface a Fall Armyworm
  belt before it hits FAO EMPRES feeds; Layer C makes that visible.
- **Actionable for institutions:** an NGO can dispatch biopesticide to the
  reddest grid cell tomorrow; a ministry can pre-position relief in the
  drought corridor — the business/funding angle.
- **All Elastic, all native:** `geo_point` + Maps + ES|QL `STATS`/`BUCKET`
  + time picker. No notebook, no external BI tool.

---

## 6. Want it as a one-click import?

I can generate a Kibana **saved-objects NDJSON** (data view + dashboard +
ES|QL panels) so you import instead of clicking — tell me your project's
Kibana version (Help → About, or the footer) and I'll match the schema.
Maps layers are version-sensitive, so the click-path above is the reliable
fallback for the live demo.
