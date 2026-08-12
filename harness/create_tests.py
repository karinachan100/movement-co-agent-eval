"""
create_tests.py — bulk-create the test suite from scenarios.json.

Schema taken directly from the dashboard's "Edit as JSON" on a working test,
rather than guessed, so the payloads match what the platform actually expects.

Creating a test costs nothing. Only running one spends credits.

Usage:
    python -m harness.create_tests --dry-run    # show what would be created
    python -m harness.create_tests              # create everything missing
    python -m harness.create_tests --only S4    # create one scenario
"""

import argparse
import json
import os
from pathlib import Path

SCENARIOS_FILE = Path("scenarios/scenarios.json")

# The agent's opening line. Every simulation starts from this, so it has to
# match what the agent actually says or the conversation starts inconsistently.
AGENT_FIRST_MESSAGE = "Hello, how can I help you today?"


def build_payload(scenario: dict, agent_id: str) -> dict:
    """Build one test payload in the platform's expected shape."""
    return {
        "name": scenario["name"],
        "type": "simulation",
        "chat_history": [
            {
                "role": "agent",
                "message": AGENT_FIRST_MESSAGE,
                "time_in_call_secs": 0,
                "tool_calls": [],
                "tool_results": [],
                "agent_metadata": None,
            }
        ],
        "dynamic_variables": {},
        "conversation_initiation_source": None,
        "from_conversation_metadata": {
            "conversation_id": "",
            "agent_id": agent_id,
            "branch_id": None,
            "workflow_node_id": None,
            "original_agent_reply": [],
        },
        "success_conditions": [scenario["success_criteria"]],
        "simulation_scenario": scenario["scenario"],
        "simulation_max_turns": scenario.get("max_turns", 3),
        "simulation_environment": None,
        "evaluation_model": None,
        "simulated_user_model": None,
        "tool_mock_overrides": {},
        "tool_call_parameters": None,
        "success_examples": [],
        "failure_examples": [],
    }


def existing_names(client) -> set[str]:
    """Names of tests that already exist, so we don't create duplicates."""
    try:
        response = client.conversational_ai.tests.list()
        return {
            getattr(t, "name", "")
            for t in (getattr(response, "tests", None) or [])
        }
    except Exception as error:
        print(f"Could not list existing tests ({error}). Continuing without duplicate check.\n")
        return set()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Show payloads without creating")
    parser.add_argument("--only", help="Create a single scenario, e.g. S4")
    args = parser.parse_args()

    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    api_key = os.getenv("ELEVENLABS_API_KEY")
    agent_id = os.getenv("ELEVENLABS_AGENT_ID")

    if not args.dry_run and not (api_key and agent_id):
        raise SystemExit("Missing ELEVENLABS_API_KEY or ELEVENLABS_AGENT_ID in .env")

    scenarios = json.loads(SCENARIOS_FILE.read_text())["scenarios"]

    if args.only:
        scenarios = [s for s in scenarios if s["id"].upper() == args.only.upper()]
        if not scenarios:
            raise SystemExit(f"No scenario with id {args.only}")

    if args.dry_run:
        print(f"Would create {len(scenarios)} test(s):\n")
        for s in scenarios:
            print(f"  [{s['id']}] {s['name']}")
            print(f"        scenario: {s['scenario'][:90]}...")
            print(f"        criteria: {s['success_criteria'][:90]}...")
            print(f"        max turns: {s.get('max_turns', 3)}\n")
        print("Creating tests is free. Running them costs credits.")
        return

    from .client import get_client

    client = get_client(require_agent=True)
    already = existing_names(client)

    created, skipped, failed = 0, 0, 0

    for scenario in scenarios:
        if scenario["name"] in already:
            print(f"  skip    [{scenario['id']}] already exists")
            skipped += 1
            continue

        payload = build_payload(scenario, agent_id)

        try:
            client.conversational_ai.tests.create(request=payload)
            print(f"  created [{scenario['id']}] {scenario['name']}")
            created += 1
        except Exception as error:
            print(f"  FAILED  [{scenario['id']}] {error}")
            failed += 1

    print(f"\n{created} created, {skipped} skipped, {failed} failed.")
    if created:
        print("\nNext: python -m harness.run_suite --list")


if __name__ == "__main__":
    main()
