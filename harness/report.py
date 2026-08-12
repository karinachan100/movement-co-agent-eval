"""
report.py — turn cached pass rates into a deployment readiness assessment.

This is the layer ElevenLabs doesn't provide. Their dashboard tells you which
tests passed. This tells you whether to deploy, and what it costs if you do.

Reads from cached results only, so running this costs nothing.

Usage:
    python -m harness.report                 # use the most recent run
    python -m harness.report --file results/run-20260812-143000.json
"""

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

from . import config

RESULTS_DIR = Path("results")
OUTPUT = Path("readiness_report.html")


def _as_text(value) -> str:
    """
    Coerce a rationale into a readable string.

    The evaluator returns rationale in different shapes depending on how many
    success conditions a test has — sometimes a plain string, sometimes a dict
    or list of per-condition results. Rather than assume one shape, pull out
    whatever readable text is in there.
    """
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        for key in ("rationale", "summary", "explanation", "reason", "message", "text"):
            if key in value:
                return _as_text(value[key])
        return " ".join(_as_text(v) for v in value.values() if v)[:400]
    if isinstance(value, (list, tuple)):
        return " ".join(_as_text(v) for v in value if v)[:400]
    return str(value)


def _passed(run_item: dict) -> bool:
    """Did this individual run pass?"""
    outcome = run_item.get("condition_result") or {}
    if isinstance(outcome, dict):
        result = outcome.get("result")
        if isinstance(result, str):
            return result.lower() == "success"
        if isinstance(result, bool):
            return result
    return False


def _rationale(run_item: dict) -> str:
    outcome = run_item.get("condition_result") or {}
    text = _as_text(outcome.get("rationale") if isinstance(outcome, dict) else outcome)
    return (text or "No rationale returned")[:180]


def latest_run() -> Path:
    runs = sorted(RESULTS_DIR.glob("run-*.json"))
    if not runs:
        raise SystemExit("No cached runs found. Run the suite first.")
    return runs[-1]


def load(path: Path) -> tuple[list[dict], dict]:
    data = json.loads(path.read_text())
    return data["tests"], data["invocation"]


def compute(tests: list[dict], invocation: dict) -> dict:
    """Collapse individual runs into per-scenario pass rates and failure buckets."""
    by_id = {t["test_id"]: t for t in tests}
    grouped: dict[str, list[dict]] = defaultdict(list)

    for run_item in invocation.get("test_runs", []):
        grouped[run_item.get("test_id")].append(run_item)

    scenarios = []
    for test_id, items in grouped.items():
        meta = by_id.get(test_id, {})
        scenario_id = meta.get("scenario_id")
        if not scenario_id:
            continue

        passed = sum(1 for i in items if _passed(i))
        total = len(items)
        rate = passed / total if total else 0.0

        # Group failures by the evaluator's stated reason.
        buckets: dict[str, int] = defaultdict(int)
        for i in items:
            if not _passed(i):
                buckets[_rationale(i)] += 1

        scenarios.append({
            "id": scenario_id,
            "category": scenario_id[0],
            "name": meta.get("name", test_id),
            "passed": passed,
            "total": total,
            "rate": rate,
            "band": config.band(rate),
            "failure_buckets": dict(buckets),
        })

    return {"scenarios": sorted(scenarios, key=lambda s: s["id"])}


def metrics(scenarios: list[dict]) -> dict:
    """The five headline numbers."""
    def in_cat(letter):
        return [s for s in scenarios if s["category"] == letter]

    def mean_rate(items):
        return sum(s["rate"] for s in items) / len(items) if items else None

    containment = mean_rate(in_cat("C"))
    silent = in_cat("S")
    false_esc = in_cat("F")
    liability = in_cat("L")

    # Leakage: for each R scenario, failure rate x volume share x cost.
    leakage = 0.0
    leakage_detail = []
    for s in in_cat("R"):
        cost = config.FAILURE_COST_AED.get(s["id"])
        weight = config.VOLUME_WEIGHT.get(s["id"], 0)
        if cost is None:
            continue
        failure_rate = 1 - s["rate"]
        occurrences = config.ASSUMED_MONTHLY_CONVERSATIONS * weight * failure_rate
        amount = occurrences * cost
        leakage += amount
        if amount > 0:
            leakage_detail.append({
                "id": s["id"],
                "failure_rate": failure_rate,
                "occurrences": occurrences,
                "cost": cost,
                "amount": amount,
            })

    blockers = [s for s in liability if s["rate"] < 1.0]

    return {
        "containment": containment,
        "silent_failure_rate": 1 - mean_rate(silent) if silent else None,
        "false_escalation_rate": 1 - mean_rate(false_esc) if false_esc else None,
        "leakage_monthly_aed": leakage,
        "leakage_detail": leakage_detail,
        "blockers": blockers,
    }


def verdict(m: dict) -> tuple[str, str]:
    """Go / no-go, with the reason."""
    if m["blockers"]:
        ids = ", ".join(b["id"] for b in m["blockers"])
        return "NO-GO", f"Liability failure in {ids}. A single failure here blocks deployment regardless of other scores."

    if m["containment"] is not None and m["containment"] < 0.8:
        return "NO-GO", f"Containment at {m['containment']:.0%}. Below the level where the automation case closes."

    if m["silent_failure_rate"] and m["silent_failure_rate"] > 0.2:
        return "CONDITIONAL", f"Silent failure rate at {m['silent_failure_rate']:.0%}. Fix grounding before scaling beyond a pilot."

    if m["leakage_monthly_aed"] > 500:
        return "CONDITIONAL", f"Projected leakage of {m['leakage_monthly_aed']:,.0f} AED/month. Viable, but the leaking scenarios need prompt work first."

    return "GO", "No liability blockers, containment holds, leakage within tolerance."


def pct(value) -> str:
    return f"{value:.0%}" if value is not None else "n/a"


def render(scenarios: list[dict], m: dict, source: Path) -> str:
    call, reason = verdict(m)
    colours = {"GO": "#1a7f4b", "CONDITIONAL": "#b06d00", "NO-GO": "#b3261e"}
    bands = {"green": "#1a7f4b", "amber": "#b06d00", "red": "#b3261e"}

    rows = ""
    for s in scenarios:
        buckets = "".join(
            f"<div class='bucket'>{count} run(s): {reason_text}</div>"
            for reason_text, count in s["failure_buckets"].items()
        )
        rows += f"""
        <tr>
          <td class="id">{s['id']}</td>
          <td>{s['name']}</td>
          <td class="rate" style="color:{bands[s['band']]}">{s['passed']}/{s['total']}</td>
          <td>{buckets or '<span class="none">—</span>'}</td>
        </tr>"""

    leak_rows = "".join(
        f"<li><b>{d['id']}</b>: fails {d['failure_rate']:.0%} of the time, "
        f"~{d['occurrences']:.0f} occurrences/month at {d['cost']} AED = "
        f"<b>{d['amount']:,.0f} AED</b></li>"
        for d in m["leakage_detail"]
    ) or "<li>No quantifiable leakage detected in this run.</li>"

    cat_summary = ""
    for letter, meta in config.CATEGORIES.items():
        items = [s for s in scenarios if s["category"] == letter]
        if not items:
            continue
        avg = sum(s["rate"] for s in items) / len(items)
        cat_summary += f"""
        <div class="cat">
          <div class="cat-head">
            <span class="cat-name">{meta['name']}</span>
            <span class="cat-rate" style="color:{bands[config.band(avg)]}">{avg:.0%}</span>
          </div>
          <div class="cat-q">{meta['question']}</div>
          <div class="cat-r">{meta['reading']}</div>
        </div>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Movement Co — Agent Deployment Readiness</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
         max-width: 900px; margin: 40px auto; padding: 0 24px; color: #1a1a1a; line-height: 1.55; }}
  h1 {{ font-size: 26px; margin-bottom: 4px; }}
  .sub {{ color: #666; font-size: 14px; margin-bottom: 32px; }}
  .verdict {{ border-left: 4px solid {colours[call]}; padding: 16px 20px; background: #fafafa; margin-bottom: 32px; }}
  .verdict-call {{ font-size: 22px; font-weight: 700; color: {colours[call]}; }}
  .verdict-reason {{ margin-top: 6px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 14px; margin-bottom: 32px; }}
  .cat {{ border: 1px solid #e4e4e4; border-radius: 6px; padding: 14px; }}
  .cat-head {{ display: flex; justify-content: space-between; align-items: baseline; }}
  .cat-name {{ font-weight: 600; }}
  .cat-rate {{ font-weight: 700; font-size: 18px; }}
  .cat-q {{ font-size: 13px; color: #555; margin-top: 6px; }}
  .cat-r {{ font-size: 12px; color: #888; margin-top: 4px; font-style: italic; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 14px; margin-bottom: 32px; }}
  th {{ text-align: left; border-bottom: 2px solid #1a1a1a; padding: 8px 6px; font-size: 12px;
        text-transform: uppercase; letter-spacing: .04em; }}
  td {{ border-bottom: 1px solid #eee; padding: 10px 6px; vertical-align: top; }}
  .id {{ font-weight: 700; width: 48px; }}
  .rate {{ font-weight: 700; width: 70px; }}
  .bucket {{ font-size: 12px; color: #777; margin-bottom: 4px; }}
  .none {{ color: #ccc; }}
  h2 {{ font-size: 17px; margin-top: 36px; }}
  .note {{ font-size: 13px; color: #777; border-top: 1px solid #eee; margin-top: 40px; padding-top: 16px; }}
</style></head><body>

<h1>Movement Co — Agent Deployment Readiness</h1>
<div class="sub">Generated {datetime.now(timezone.utc).strftime('%d %b %Y')} · source: {source.name}</div>

<div class="verdict">
  <div class="verdict-call">{call}</div>
  <div class="verdict-reason">{reason}</div>
</div>

<div class="grid">{cat_summary}</div>

<h2>Projected revenue leakage</h2>
<p>Assumes {config.ASSUMED_MONTHLY_CONVERSATIONS:,} conversations/month and the volume weights in
<code>config.py</code>. These weights are estimates — real ones would come from the customer's
existing call logs.</p>
<ul>{leak_rows}</ul>
<p><b>Total: {m['leakage_monthly_aed']:,.0f} AED/month</b></p>

<h2>Scenario detail</h2>
<table>
  <tr><th>ID</th><th>Scenario</th><th>Passed</th><th>Failure buckets</th></tr>
  {rows}
</table>

<div class="note">
Pass rates come from running each test multiple times via <code>repeat_count</code>, because agent
responses vary between runs. A single pass shows the agent can succeed; the rate shows how often it
will. Failure buckets group runs by the evaluator's stated reason, so the report shows <i>how</i>
it fails rather than only <i>that</i> it fails.
</div>

</body></html>"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Specific cached run to use")
    args = parser.parse_args()

    path = Path(args.file) if args.file else latest_run()
    tests, invocation = load(path)

    computed = compute(tests, invocation)
    if not computed["scenarios"]:
        raise SystemExit("No mapped scenarios in that run. Check test naming.")

    m = metrics(computed["scenarios"])
    OUTPUT.write_text(render(computed["scenarios"], m, path))

    call, reason = verdict(m)
    print(f"\n{call} — {reason}\n")
    print(f"Containment:       {pct(m['containment'])}")
    print(f"Silent failure:    {pct(m['silent_failure_rate'])}")
    print(f"False escalation:  {pct(m['false_escalation_rate'])}")
    print(f"Leakage:           {m['leakage_monthly_aed']:,.0f} AED/month")
    print(f"Liability blockers: {len(m['blockers'])}")
    print(f"\nWritten to {OUTPUT}")


if __name__ == "__main__":
    main()
