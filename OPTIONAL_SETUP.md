# Optional FarmSense Setup

These steps are optional. The agent works without them; they add semantic search and advisory logging/alerts.

---

## 1. ELSER (semantic search on crop-knowledge)

The **crop_knowledge_search** tool uses ELSER for semantic search. If ELSER isn't started, that step times out and the agent still returns an advisory using climate, pest, and soil data.

1. Open Kibana → **Machine Learning** → **Trained Models** (or **Inference**).
2. Find **ELSER** (e.g. `.elser-2-elasticsearch`).
3. Click **Start** / **Deploy** and wait until status is **Started**.
4. Retry your farmer query — crop_knowledge_search should now return results.

Or via script: `uv run python agent_config/start_elser.py`

---

## 2. Advisory workflow (log advisories + CRITICAL alerts)

Log every advisory to `advisory-history` and send a webhook when risk is CRITICAL.

### Create the workflow in Kibana

1. Open Kibana → **Workflows** → **Create workflow**
2. Name: `advisory-alert-workflow`
3. Open the YAML editor and paste the contents of `workflows/advisory_alert_workflow.yaml`
4. Save

### Attach the workflow tool to FarmSense Advisor

```bash
uv run python agent_config/add_workflow_tool_to_advisor.py
```

This creates the `log_advisory_workflow` tool and adds it to the agent.

If the workflow execution fails, check **Workflows → Executions** for the error. Common fix: delete and recreate the `advisory-history` index:

```bash
uv run python -c "
import sys; sys.path.insert(0, 'ingestion')
from dotenv import load_dotenv; load_dotenv('.env')
from utils import get_es_client
c = get_es_client()
c.indices.delete(index='advisory-history', ignore_unavailable=True)
"
uv run python ingestion/create_indices.py
```

---

## 3. Re-apply ES|QL query fixes

If you edit tools in the Kibana UI and the queries revert:

```bash
uv run python agent_config/fix_esql_tools.py
```
