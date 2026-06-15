# FarmSense — Demo Runbook (Elastic Dallas, Jun 16 2026)

Project: `farmsense-cf0964` (Elasticsearch Serverless, us-central1.gcp).
Status as of rebuild: **fully working end-to-end.**

---

## ⚠️ #1 THING THAT WILL MAKE-OR-BREAK THE LIVE DEMO

**In Kibana Agent Chat, you MUST select `Anthropic Claude Sonnet 4.5` as the model.**

Why: the default Agent Builder model can't fill tool parameters — it calls every
tool with empty args `{}` and the run fails. Claude Sonnet 4.5 (and 3.7) fill
params perfectly. There is no API to set a per-agent default connector (verified),
so this is a **manual click each session**. Do it first, before you type anything.

If a run ever returns "tool call arguments were invalid" / empty results → you're
on the wrong model. Switch to Claude Sonnet 4.5 and retry.

---

## Demo flow — Kibana Agent Chat (primary)

1. Kibana → **Agent Builder → Chat**
2. **Model picker → `Anthropic Claude Sonnet 4.5`**  ← do this first
3. Agent dropdown → **FarmSense Advisor**
4. Paste a scenario (below). Run takes ~40–70s (5 tools, called one at a time, incl. ELSER).

### Scenarios (all 5 tested live — each produces a full advisory)
| Scenario | Prompt | Expected |
|---|---|---|
| Maize / Nigeria | *"I'm growing maize in Oyo State, Nigeria. Leaves turning yellow and curling. Very little rain for 3 weeks. 6-leaf stage."* | **HIGH** — drought stress, no pests, Ferric Lixisol, mulch/irrigate |
| Rice / Bangladesh | *"Rice in Dhaka, Bangladesh. After floods, leaf spots and panicles turning brown. Very humid."* | **CRITICAL** — Rice Blast, drain field + tricyclazole |
| Wheat / India | *"Wheat in Uttar Pradesh, India. Some aphids but crop looks healthy. Normal rainfall."* | LOW/MEDIUM — minor aphids |
| Cassava / Kenya | *"Cassava in Western Kenya. Leaves yellowing, plants stunted. Poor soil, no fertilizer."* | nutrient deficiency |
| Tomato / Ethiopia | *"Tomato in Oromia, Ethiopia. Dark lesions on leaves and stems. Cool and very humid."* | late blight |

The agent runs (one tool at a time): geo_normalize → geo_climate_query → pest_outbreak_lookup → crop_knowledge_search (ELSER) → soil_profile_lookup → advisory.

---

## Command Center dashboard (the "wow" second surface) — BUILT ✅

The **FarmSense Command Center** is built and saved (Kibana → Dashboards): 5 panels —
risk-mix bar, top-pests bar, crops-at-risk bar, advisories-over-time bar, and a geo
**hotspot map** (advisory-history points colored by `risk_level`). Seeded with 220
advisories across 11 countries (8.2% CRITICAL); it stores a 30-day range so it opens
with data. Build notes + ES|QL: [`command_center.md`](command_center.md).

To re-seed / add volume: `uv run python ingestion/seed_advisory_history.py --reset -n 400`

---

## Telegram (optional second frontend)

`orchestrator.py` now sends `connector_id=Anthropic-Claude-Sonnet-4-5` automatically,
so the bot works without the Chat UI model picker. Start: `uv run python telegram_poller.py`
(needs `TELEGRAM_BOT_TOKEN` in `.env`). Override the model with `ELASTIC_CONNECTOR_ID`.

---

## Step 4 (Log & Alert) — how to tell the story

The `advisory-alert-workflow` exists (Kibana → Workflows) and indexes advisories to
`advisory-history` + fires a CRITICAL webhook. In this Agent Builder **preview**,
workflow-type tools don't expose their inputs to the LLM (schema is empty), so the
agent can't call it autonomously — it's **not attached** to the agent. Show it as a
platform component: open it in the Workflows UI, and point at the populated
`advisory-history` (which powers the Command Center). Production path: invoke it from
the app layer after the advisory is generated.

---

## What was rebuilt / fixed

- Old serverless project was reaped (NXDOMAIN) → rebuilt on new project `farmsense-cf0964`.
- **Sequential tool calls (key fix):** the chat UI sent empty args to tools called in *parallel* and looped until failure; the agent now calls tools strictly **one at a time**.
- **`crop_calendar_tool` removed** from the agent (a repeat empty-args offender; planting-window context wasn't needed) → agent now has **5 tools**.
- `log_advisory_workflow` removed from the agent (workflow tools expose an empty schema → can't be filled); the workflow still runs platform-side.
- Workflow auto-create fixed: `create_workflow_via_kibana_api.py` uses the real `POST /api/workflows {"workflows":[{"yaml":...}]}`; added `advisory_alert_workflow.json`.
- `orchestrator.py`: passes `connector_id` so Telegram uses Claude 4.5.
- Built the **Command Center** dashboard (5 panels + geo hotspot map).

## Re-verify anytime
```bash
uv run python tests/check_elasticsearch_output.py     # index doc counts
```
Full rebuild from scratch (new project): set `.env`, then `./do_everything.sh`
→ `uv run python ingestion/seed_advisory_history.py --reset`. Start ELSER first if cold.
