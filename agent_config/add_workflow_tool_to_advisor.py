"""
Create the log_advisory_workflow tool (if the workflow exists in Kibana) and add it to FarmSense Advisor.
Run after creating the advisory-alert-workflow in Kibana: Workflows → Create → advisory-alert-workflow.
Usage: uv run python agent_config/add_workflow_tool_to_advisor.py
"""
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

WORKFLOW_TOOL_ID = "log_advisory_workflow"
ADVISOR_AGENT_ID = "farmsense-advisor"


def get_tool(tool_id):
    r = requests.get(f"{KIBANA_URL}/api/agent_builder/tools/{tool_id}", headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    return r.json()


def create_tool(payload):
    r = requests.post(f"{KIBANA_URL}/api/agent_builder/tools", headers=HEADERS, json=payload, timeout=30)
    if r.status_code in (200, 201):
        print(f"  Created tool: {payload['id']}")
        return True
    print(f"  Create tool failed: {r.status_code} {r.text[:300]}")
    return False


def get_agent(agent_id):
    r = requests.get(f"{KIBANA_URL}/api/agent_builder/agents/{agent_id}", headers=HEADERS, timeout=30)
    if r.status_code != 200:
        return None
    return r.json()


def update_agent(agent_id, body):
    r = requests.put(f"{KIBANA_URL}/api/agent_builder/agents/{agent_id}", headers=HEADERS, json=body, timeout=30)
    if r.status_code != 200:
        print(f"  PUT agent failed: {r.status_code} {r.text[:200]}")
        return False
    print(f"  Updated agent: {agent_id}")
    return True


def main():
    print("Adding advisory workflow tool to FarmSense Advisor...")

    # 1. Ensure workflow tool exists (create if workflow exists in Kibana)
    current_tool = get_tool(WORKFLOW_TOOL_ID)
    if not current_tool:
        workflow_tool_payload = {
            "id": WORKFLOW_TOOL_ID,
            "type": "workflow",
            "description": "Index advisory to advisory-history and trigger critical alert webhook if risk is CRITICAL.",
            "configuration": {
                "workflow_id": "advisory-alert-workflow",
            },
        }
        if not create_tool(workflow_tool_payload):
            print("  Tip: The API could not find the workflow (it may use an internal ID). Create the workflow tool in Kibana:")
            print("       Agents → More → View all tools → New tool → Type: Workflow → select 'advisory-alert-workflow' →")
            print("       Tool ID: log_advisory_workflow → Save. Then re-run this script to add it to FarmSense Advisor.")
            sys.exit(1)
    else:
        print(f"  Tool already exists: {WORKFLOW_TOOL_ID}")

    # 2. Add log_advisory_workflow to FarmSense Advisor
    agent = get_agent(ADVISOR_AGENT_ID)
    if not agent:
        print(f"  Agent {ADVISOR_AGENT_ID} not found. Run create_single_farmsense_agent.py first.")
        sys.exit(1)

    config = agent.get("configuration") or {}
    config = dict(config)
    tools_config = config.get("tools") or [{"tool_ids": []}]
    tool_ids = list(tools_config[0].get("tool_ids") or [])

    if WORKFLOW_TOOL_ID in tool_ids:
        print("  FarmSense Advisor already has log_advisory_workflow.")
        return

    tool_ids.append(WORKFLOW_TOOL_ID)
    config["tools"] = [{"tool_ids": tool_ids}]

    body = {
        "name": agent.get("name"),
        "description": agent.get("description"),
        "labels": agent.get("labels", []),
        "configuration": config,
    }
    if agent.get("avatar_symbol") is not None:
        body["avatar_symbol"] = agent["avatar_symbol"]
    if agent.get("avatar_color") is not None:
        body["avatar_color"] = agent["avatar_color"]

    if update_agent(ADVISOR_AGENT_ID, body):
        print("Done. FarmSense Advisor now includes log_advisory_workflow. After each advisory, the agent can call it to log and optionally send CRITICAL alerts.")
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
