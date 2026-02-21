"""
Try to create the advisory-alert-workflow in Kibana via API, then add the workflow tool to FarmSense Advisor.
If the workflow API is not available (common), this script prints the YAML to paste in Kibana and then runs
add_workflow_tool_to_advisor.py (which will succeed only after you create the workflow in the UI).

Usage:
  uv run python agent_config/create_workflow_via_kibana_api.py

Or after creating the workflow manually in Kibana:
  uv run python agent_config/add_workflow_tool_to_advisor.py
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "ingestion"))
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

def _default_kibana_url():
    es_url = os.environ.get("ES_URL", "").strip().rstrip("/")
    if ".es." in es_url:
        return es_url.replace(".es.", ".kb.").replace(":443", "")
    return ""

KIBANA_URL = (os.environ.get("KIBANA_URL") or _default_kibana_url()).strip().rstrip("/")
API_KEY = os.environ.get("KIBANA_API_KEY") or os.environ.get("ES_API_KEY")
if not KIBANA_URL or not API_KEY:
    print("Set KIBANA_URL and ES_API_KEY in .env")
    sys.exit(1)

import requests

HEADERS = {
    "Authorization": f"ApiKey {API_KEY}",
    "kbn-xsrf": "true",
    "Content-Type": "application/json",
}

WORKFLOW_ID = "advisory-alert-workflow"
WORKFLOW_JSON_PATH = os.path.join(os.path.dirname(__file__), "..", "workflows", "advisory_alert_workflow.json")
WORKFLOW_YAML_PATH = os.path.join(os.path.dirname(__file__), "..", "workflows", "advisory_alert_workflow.yaml")


def try_saved_objects_create():
    """Try creating workflow as a Kibana saved object (type may not exist)."""
    with open(WORKFLOW_JSON_PATH) as f:
        workflow_def = json.load(f)
    payload = [{
        "type": "workflow",
        "id": WORKFLOW_ID,
        "attributes": {
            "title": workflow_def.get("name", WORKFLOW_ID),
            "description": workflow_def.get("description", ""),
            "workflowDefinition": workflow_def,
        },
    }]
    r = requests.post(
        f"{KIBANA_URL}/api/saved_objects/_bulk_create",
        headers=HEADERS,
        params={"overwrite": "true"},
        json=payload,
        timeout=30,
    )
    if r.status_code == 200:
        data = r.json()
        if data.get("saved_objects") and len(data["saved_objects"]) > 0:
            ob = data["saved_objects"][0]
            if not ob.get("error"):
                return True
    return False


def try_internal_workflows_api():
    """Try internal or plugin workflow create endpoint (may 404)."""
    with open(WORKFLOW_JSON_PATH) as f:
        workflow_def = json.load(f)
    for path in ["/internal/workflows/workflow", "/api/workflows/workflow", "/api/workflows"]:
        r = requests.post(
            f"{KIBANA_URL}{path}",
            headers=HEADERS,
            json=workflow_def,
            timeout=30,
        )
        if r.status_code in (200, 201):
            return True
        if r.status_code != 404:
            pass  # log if needed
    return False


def main():
    print("Creating advisory-alert-workflow and attaching to FarmSense Advisor...")
    workflow_created = False

    if try_saved_objects_create():
        print("  Created workflow via saved_objects API.")
        workflow_created = True
    elif try_internal_workflows_api():
        print("  Created workflow via internal/workflows API.")
        workflow_created = True

    if not workflow_created:
        print("  Kibana does not expose a public API to create workflows.")
        print("  Create the workflow in Kibana, then re-run this script (or run add_workflow_tool_to_advisor.py).")
        print("")
        print("  Steps:")
        print("  1. Open Kibana → Workflows (or Management → Workflows).")
        print("  2. Create workflow → name exactly: advisory-alert-workflow")
        print("  3. Paste the YAML from:")
        print(f"     {os.path.abspath(WORKFLOW_YAML_PATH)}")
        print("  4. Save the workflow.")
        print("  5. Run again:")
        print("     uv run python agent_config/create_workflow_via_kibana_api.py")
        print("     or: uv run python agent_config/add_workflow_tool_to_advisor.py")
        print("")
        if os.path.exists(WORKFLOW_YAML_PATH):
            print("  YAML preview (first 30 lines):")
            with open(WORKFLOW_YAML_PATH) as f:
                for i, line in enumerate(f):
                    if i >= 30:
                        print("  ...")
                        break
                    print("  ", line.rstrip())
        print("")
        # Still run add_workflow_tool so that if they already created the workflow, it gets attached
        print("  Attempting to add workflow tool to FarmSense Advisor (will succeed if workflow already exists)...")

    # Add workflow tool to agent (works only when workflow exists in Kibana)
    sys.path.insert(0, os.path.dirname(__file__))
    import add_workflow_tool_to_advisor as add_tool
    add_tool.main()


if __name__ == "__main__":
    main()
