"""
run_suite.py — execute the test suite and cache the results.

The tests themselves are authored in the ElevenLabs dashboard. This script
finds them, runs them with repeat_count so we get pass rates rather than
single-run pass/fail, and writes everything to disk.

Why repeat_count matters:
Agent responses vary between runs. One pass tells you the agent CAN get it
right. It doesn't tell you how often it WILL, and a leakage estimate needs a
rate, not a single observation. ElevenLabs supports repeat_count between 2 and
20, and automatically buckets failures by reason when it's set.

Cost control:
Every run costs credits, and the free tier caps at 10,000/month. So this caches
every result to disk, supports running one category at a time, and defaults to
a low repeat_count. Regenerating the report from cache is free.

Usage:
    python -m harness.run_suite --list              # show tests, spend nothing
    python -m harness.run_suite --category L        # run one category
    python -m harness.run_suite --scenario S4       # run one scenario
    python -m harness.run_suite --all --repeat 5    # full suite
"""

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .client import get_client, get_agent_id

RESULTS_DIR = Path("results")
RESULTS_DIR.mkdir(exist_ok=True)


def list_tests(client) -> list[dict]:
    """Fetch all tests in the workspace, tagged with their scenario ID."""
    response = client.conversational_ai.tests.list()
    raw = getattr(response, "tests", None) or []

    tests = []
    for item in raw:
        name = getattr(item, "name", "") or ""
        test_id = getattr(item, "id", None) or getattr(item, "test_id", None)
        scenario_id = config.scenario_id_from_name(name)
        tests.append({
            "test_id": test_id,
            "name": name,
            "scenario_id": scenario_id,
            "category": config.category_of(scenario_id) if scenario_id else None,
        })
    return tests


def select(tests: list[dict], category: str | None, scenario: str | None) -> list[dict]:
    if scenario:
        return [t for t in tests if t["scenario_id"] == scenario.upper()]
    if category:
        return [t for t in tests if t["category"] == category.upper()]
    return [t for t in tests if t["scenario_id"]]


def run(client, agent_id: str, tests: list[dict], repeat: int) -> dict:
    """Kick off a test run and wait for it to finish."""
    payload = [{"test_id": t["test_id"]} for t in tests]

    print(f"Running {len(tests)} test(s), {repeat}x each = {len(tests) * repeat} runs\n")

    invocation = client.conversational_ai.agents.run_tests(
        agent_id=agent_id,
        tests=payload,
        repeat_count=repeat,
    )

    invocation_id = getattr(invocation, "id", None) or getattr(invocation, "invocation_id", None)
    print(f"Invocation: {invocation_id}")
    print("Waiting for results", end="", flush=True)

    # Poll until every test has finished. A single failed poll shouldn't lose
    # the whole run — the conversations already executed and were paid for.
    raw = {}
    for _ in range(120):
        time.sleep(5)
        print(".", end="", flush=True)
        try:
            result = client.conversational_ai.tests.invocations.get(
                test_invocation_id=invocation_id
            )
            raw = json.loads(result.json()) if hasattr(result, "json") else dict(result)
        except Exception as error:
            print(f"\n  poll failed ({error}), retrying...", end="", flush=True)
            continue

        statuses = [r.get("status") for r in raw.get("test_runs", [])]
        if statuses and all(s not in ("pending", "running", None) for s in statuses):
            break

    print(" done\n")

    if not raw:
        print(f"Could not retrieve results. Check the dashboard for invocation {invocation_id}.")
    return raw


def cache(invocation_data: dict, tests: list[dict]) -> Path:
    """Write the raw invocation plus our scenario mapping to disk."""
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = RESULTS_DIR / f"run-{stamp}.json"

    path.write_text(json.dumps({
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "tests": tests,
        "invocation": invocation_data,
    }, indent=2))

    return path


def summarise(invocation_data: dict, tests: list[dict]) -> None:
    """Print a quick pass-rate view so you can see results without the report."""
    by_id = {t["test_id"]: t for t in tests}
    runs = invocation_data.get("test_runs", [])

    # Group runs by test, since repeat_count produces several per test.
    grouped: dict[str, list[dict]] = {}
    for run_item in runs:
        test_id = run_item.get("test_id")
        grouped.setdefault(test_id, []).append(run_item)

    print(f"{'Scenario':<10} {'Pass rate':<12} Test")
    print("-" * 60)

    for test_id, items in sorted(grouped.items(), key=lambda kv: by_id.get(kv[0], {}).get("scenario_id") or ""):
        meta = by_id.get(test_id, {})
        passed = sum(1 for i in items if i.get("condition_result", {}).get("result") == "success")
        total = len(items)
        rate = passed / total if total else 0
        marker = {"green": "  ", "amber": " !", "red": " X"}[config.band(rate)]
        print(f"{meta.get('scenario_id', '?'):<10} {passed}/{total} {marker:<6} {meta.get('name', test_id)}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--list", action="store_true", help="List tests without running")
    parser.add_argument("--category", help="Run one category: C, R, S, F or L")
    parser.add_argument("--scenario", help="Run one scenario, e.g. S4")
    parser.add_argument("--all", action="store_true", help="Run every mapped test")
    parser.add_argument("--repeat", type=int, default=3, help="Runs per test (2-20)")
    args = parser.parse_args()

    client = get_client()
    tests = list_tests(client)

    if args.list or not (args.category or args.scenario or args.all):
        print(f"{len(tests)} test(s) found\n")
        for t in sorted(tests, key=lambda t: t["scenario_id"] or "zz"):
            tag = t["scenario_id"] or "unmapped"
            print(f"  [{tag:<8}] {t['name']}")
        unmapped = [t for t in tests if not t["scenario_id"]]
        if unmapped:
            print(f"\n{len(unmapped)} test(s) unmapped. Prefix names with a scenario ID "
                  f"(e.g. 'S4 — ...') so the report can categorise them.")
        return

    selected = select(tests, args.category, args.scenario)
    if not selected:
        raise SystemExit("No matching tests. Run with --list to see what exists.")

    repeat = max(2, min(20, args.repeat))
    invocation_data = run(client, get_agent_id(), selected, repeat)

    path = cache(invocation_data, selected)
    summarise(invocation_data, selected)
    print(f"\nCached to {path}. Report generation is free from here.")


if __name__ == "__main__":
    main()
