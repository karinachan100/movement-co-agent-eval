# Movement Co — Agent Deployment Readiness

A test suite and evaluation harness for an ElevenLabs voice agent, built to answer the question an enterprise buyer actually asks before signing:

**Can we put this agent in front of real support volume, and where does it leak money?**

Not "does the agent work." That's a QA question, and it doesn't help anyone decide anything.

---

## Why this exists

I built this while getting hands-on with the ElevenLabs Agents platform. The agent itself took twenty minutes. The interesting part was working out how you'd actually assess one for production.

Most agent testing I found groups tests by function: does it escalate, does it stay in scope, does it handle interruptions. Useful for an engineer, useless for a buyer. A pass rate of 85% tells you nothing about whether to deploy, because it treats "agent was slightly verbose" and "agent gave medical advice" as equally weighted failures.

So this suite groups scenarios by **commercial consequence** instead.

---

## The five categories

| Category | The question it answers | Why it matters |
|---|---|---|
| **Containment** | What share of queries resolve without a human? | This is the entire business case |
| **Revenue leakage** | Which wrong answers cost money directly? | Each failure has a dirham value × call volume |
| **Silent failure** | Where is it confidently wrong and nobody notices? | Invisible to standard QA. Kills deployments |
| **False escalation** | Where does it hand off unnecessarily? | Destroys containment, collapses the ROI case |
| **Liability** | Where could one failure block go-live? | Cannot be averaged into a pass rate |

**Silent failure** is the category most testing misses. The agent gives a confidently wrong answer, the member accepts it and hangs up satisfied, no escalation fires, no complaint is logged. It appears in no dashboard. That's the failure mode that actually surfaces three months into a deployment.

---

## The setup

**Movement Co** is a fictional fitness class marketplace. Members subscribe monthly for credits and spend them booking classes at partner studios.

The knowledge base is fiction I wrote, and that's deliberate. Because I authored it, I know exactly what's true — so every wrong answer is provably wrong rather than a judgment call. It's engineered to make failures detectable:

- **Precise numbers throughout.** 8 credits base, 1.5x peak multiplier, 20% rollover cap, 25 AED late fee. One right answer per question
- **A "not covered" section.** Medical advice, corporate pricing, instructor details — the boundary the liability scenarios test against
- **Deliberate gaps.** No member account data exists, so "how many credits do I have left" has no answer. Tests whether the agent admits the gap or invents a number
- **A plausible fake tier.** Real plans are Starter, Standard, Premium. Scenario S1 asks to upgrade to "Platinum" — exactly the kind of tier a member might half-remember

---

## What's in here

```
agent/
  system_prompt.md      Standing instructions — how the agent behaves
  knowledge_base.md     The facts — what the agent knows
  SETUP.md              Click-by-click build guide, no code required

scenarios/
  test_suite.md         18 scenarios grouped by commercial consequence
```

Each scenario states the correct answer from the knowledge base, the pass criterion, and what a failure costs.

Every section of the system prompt maps to a category in the test suite. That's not accidental — **the system prompt is the claim, the test suite is the check.** The point isn't testing whether the model is capable. It's testing whether my instructions held under pressure.

---

## Designing around the credit budget

The ElevenLabs free tier gives 10,000 credits a month. Eighteen multi-turn scenarios is not free, so the harness is built to run incrementally rather than all-or-nothing:

- **Run by scenario or by category**, not just the full suite
- **Cache every transcript to disk.** A scenario runs once; regenerating the report costs nothing
- **Measure before committing.** Run one scenario, check the delta, extrapolate

Worth noting the free tier carries no commercial license, so this is a prototyping exercise, not something production-ready.

I'd rather design around the constraint than pretend it isn't there. Working out what a pilot costs to run before running it is most of the job.

---

## Status

- [x] Agent built and live on ElevenLabs
- [x] Knowledge base and system prompt authored
- [x] 18 scenarios specified with pass criteria and failure costs
- [ ] Harness built against the ElevenLabs Agent Testing API
- [ ] Full suite executed
- [ ] Readiness report generated

---

## Output

Not a pass/fail scorecard. A deployment recommendation:

| Metric | Definition |
|---|---|
| Containment rate | % of realistic queries fully resolved without escalation |
| Leakage per 1,000 conversations | Failure rate × dirham cost × volume assumption |
| Silent failure rate | % answered confidently and wrongly |
| False escalation rate | % escalated unnecessarily |
| Liability blockers | Count. Any non-zero value blocks deployment |

The answer is go / no-go with named blockers, not a percentage.
