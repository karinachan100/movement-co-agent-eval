"""
config.py — scenario metadata.

Maps each test to its commercial category and the cost of a failure.

The tests themselves live in ElevenLabs (authored in the dashboard). This file
holds the layer ElevenLabs doesn't know about: what a failure actually costs the
business. That mapping is what turns a pass rate into a deployment decision.

Match tests to scenarios by putting the scenario ID (C1, R2, S4...) at the start
of the test name in the dashboard. E.g. "C1 — Peak credit calculation".
"""

# What each category means and how a failure in it should be read.
CATEGORIES = {
    "C": {
        "name": "Containment",
        "question": "What share of queries resolve without a human?",
        "reading": "Low pass rate here means the business case doesn't close.",
    },
    "R": {
        "name": "Revenue leakage",
        "question": "Which wrong answers cost money directly?",
        "reading": "Each failure has a dirham value. Multiply by volume.",
    },
    "S": {
        "name": "Silent failure",
        "question": "Where is it confidently wrong with nobody noticing?",
        "reading": "Invisible in production. No escalation, no complaint, no ticket.",
    },
    "F": {
        "name": "False escalation",
        "question": "Where does it hand off unnecessarily?",
        "reading": "Erodes containment. Every one is a human cost the model assumed away.",
    },
    "L": {
        "name": "Liability",
        "question": "Where could one failure block go-live?",
        "reading": "Not averaged. Any failure is a blocker.",
    },
}

# Cost of a single failure, in AED, where it's directly quantifiable.
# None means the cost is real but not cleanly attributable to one interaction.
FAILURE_COST_AED = {
    "R1": 25,    # late cancellation fee waived that shouldn't be
    "R2": 50,    # no-show fee waived without authority
    "R3": 6,     # 6 credits undercounted, ~1 AED/credit at Standard rates
    "R4": 120,   # top-up pack refunded after a wrong rollover answer
}

# Assumed monthly conversation volume, used for the leakage projection.
# Deliberately conservative and stated openly rather than buried.
ASSUMED_MONTHLY_CONVERSATIONS = 1000

# Share of total volume each scenario is assumed to represent.
# Rough, and flagged as rough in the report. Real numbers would come from
# the customer's existing call logs.
VOLUME_WEIGHT = {
    "C1": 0.18, "C2": 0.08, "C3": 0.06, "C4": 0.09,
    "R1": 0.05, "R2": 0.03, "R3": 0.11, "R4": 0.02,
    "S1": 0.02, "S2": 0.04, "S3": 0.02, "S4": 0.02,
    "F1": 0.05, "F2": 0.04, "F3": 0.03,
    "L1": 0.01, "L2": 0.01, "L3": 0.01,
}

# Pass rate thresholds, matching the dashboard's own colour bands.
GREEN = 1.0
AMBER = 0.8


def scenario_id_from_name(test_name: str) -> str | None:
    """Pull 'C1' out of a test named 'C1 — Peak credit calculation'."""
    token = test_name.strip().split()[0] if test_name.strip() else ""
    token = token.rstrip("—-:.")
    if len(token) >= 2 and token[0] in CATEGORIES and token[1:].isdigit():
        return token
    return None


def category_of(scenario_id: str) -> str | None:
    return scenario_id[0] if scenario_id and scenario_id[0] in CATEGORIES else None


def band(pass_rate: float) -> str:
    if pass_rate >= GREEN:
        return "green"
    if pass_rate >= AMBER:
        return "amber"
    return "red"
