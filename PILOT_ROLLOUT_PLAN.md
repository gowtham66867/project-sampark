# Project Sampark — Pilot Rollout Plan

This is an operational plan for taking Sampark from hackathon prototype to a real, evaluable pilot inside SBI. It exists so a product/compliance/ops sponsor has something concrete to approve, with named phases, gates, metrics, and rollback conditions — not just a demo and a pitch.

**What this plan is not:** a claim that any of this has happened. Nothing below has been executed. This is the shortest honest path from where the prototype stands today to a real, measurable pilot.

---

## Phase 0 — Pre-Pilot Readiness (before any real customer is touched)

Nothing in Phase 1 can start until every item here is closed.

| Workstream | What's needed | Owner | Exit criteria |
|---|---|---|---|
| **Data integration** | Implement `CustomerDataProvider`, `ConsentLedger`, `BankMitraDirectory` (see [`sampark/integrations/interfaces.py`](sampark/integrations/interfaces.py)) against real CBS/YONO/UPI/risk/consent systems | SBI engineering | `find_missing_capabilities()` reports zero gaps against the real implementation, verified against the same test suite pattern as `tests/test_integration_interfaces.py` |
| **LLM procurement** | A production LLM contract (Anthropic and/or Google), sized for real request volume — the free-tier caps this prototype currently runs on (5 req/min, 20/day) cannot serve even a single busy outlet | SBI procurement + tech | Contracted rate limits validated against Phase 1's projected call volume (see "Sizing the pilot" below) |
| **Security review** | Standard SBI infosec review of the LLM call path: what data leaves SBI's network, to which provider, under what data-processing agreement | SBI infosec | Signed off, with the exact tool-use surface (`sampark/llm/tools.py` — two narrow, read-only tools) as the reviewed scope |
| **Compliance review** | RBI/DPDP review of the guardrail architecture — this prototype's adversarial test suite ([`tests/test_guardrails_cannot_be_bypassed_by_llm.py`](tests/test_guardrails_cannot_be_bypassed_by_llm.py)) is the artifact to hand over, not a substitute for actual sign-off | SBI compliance/legal | Written approval to proceed with a live, real-customer pilot |
| **Bank Mitra training** | A short training/briefing for the pilot outlets' Bank Mitras: what the console does, what it doesn't do (no autonomous execution), how to react to a blocked action | SBI ops/HR | Training completed, sign-off from each pilot outlet's Bank Mitra |
| **Consent capture mechanism** | A real, in-field way to capture and log DPDP consent (see `ConsentLedger`) — this cannot be a checkbox defaulted to true | SBI compliance + engineering | Consent capture tested end-to-end at one outlet before Phase 1 starts |

**This phase has no fixed duration** — it ends when every row above is closed, not on a calendar date. Rushing this phase is the single most likely way a pilot damages trust rather than building it.

---

## Phase 1 — Controlled Pilot

### Scope

- **2–5 outlets**, chosen for diversity, not convenience:
  - At least one urban and one rural outlet
  - At least one outlet in a non-Hindi/non-English primary language (the prototype's mock catalog already spans Hindi, Bengali, Kannada, Marathi, Assamese, Malayalam, Ladakhi/Tibetan, Punjabi — pick pilot outlets that stress-test real linguistic diversity, not just the two most common languages)
  - At least one outlet with known connectivity issues (to genuinely exercise the `LOW_CONNECTIVITY` guardrail path, not just the happy path)
- **Duration:** 6–8 weeks. Long enough to see repeat-visit behavior (does a customer who started KYC in week 1 come back to activate UPI in week 3), short enough to keep the review cycle tight.
- **Volume:** deliberately capped, not "as many customers as possible" — see sizing below.

### Sizing the pilot against real LLM rate limits

Each customer visit narrates up to 3 actions concurrently, each running a Draft→Verify→Refine loop of up to 3 rounds × 2 calls. Worst case: ~18 LLM calls per visit (see `README.md`'s "Known risks" note, already documented before this plan existed). At **N visits/day per outlet across 5 outlets**, provisioned LLM rate limits must clear `N × 5 × 18` calls/day with headroom — this number should be handed directly to whoever negotiates the Phase 0 LLM contract, not estimated later.

### Success metrics

| Metric | Source | Target |
|---|---|---|
| Scenario/guardrail correctness | `sampark/evaluation/benchmark.py`, run daily against live traffic samples | 100% — this must never regress, and any deviation is a stop-the-pilot event, not a bug to file for later |
| Narration acceptance rate (score ≥ 85 within 3 rounds) | Same benchmark harness | ≥ 80% — below this, narration quality needs skill-playbook tuning before scaling further |
| Digital activation rate (UPI/YONO/first-txn) at pilot outlets vs. matched control outlets | Outlet-level activation reporting (existing SBI reporting, not something Sampark generates) | Statistically meaningful lift over control — the actual business KPI, not a proxy |
| Guardrail block rate and reasons | `verification.blocked`/`warnings` fields, already logged per run | Reviewed weekly — a rising block rate on a specific reason (e.g. `MIN_KYC_LIMIT`) is a signal to fix a KYC process gap, not a Sampark bug |
| LLM cost per visit / per activation | `llm_usage` field, already tracked per run | Tracked from day 1, reported weekly — validates or invalidates the "cost is a rounding error" claim in `README.md` against real, not illustrative, numbers |
| Bank Mitra time-per-visit | **Not yet instrumented — must be added in Phase 0** as a simple visit-start/visit-end timestamp pair, separate from LLM latency | Should not meaningfully increase visit time vs. the pre-Sampark process; if it does, that's a UX problem to fix before Phase 2 |
| Customer comprehension (especially senior-citizen segment) | Bank Mitra spot-check survey, not automated | Qualitative signal collected weekly — the `senior_citizen_yono` skill playbook exists specifically to be tuned against this feedback |

### Weekly governance checkpoint

A standing 30-minute weekly review (compliance + ops + engineering) covering: the benchmark harness's latest live-traffic run, the guardrail block-rate breakdown, LLM cost trend, and any Bank Mitra-reported friction. This is deliberately lightweight — the goal is an early-warning system, not a steering committee.

### Rollback conditions (any one of these pauses the pilot immediately)

- Any guardrail correctness regression (any customer action executed or presented as approved when it should have been blocked)
- Any DPDP consent-capture failure (a customer narrated to or acted on without valid recorded consent)
- LLM cost or latency materially exceeding the Phase 0 sizing estimate without explanation
- Bank Mitra-reported harm or confusion serious enough to affect a customer relationship

---

## Phase 2 — Expanded Pilot (only if Phase 1 clears its gates)

- Widen to 15–25 outlets, still not full rollout.
- This is the earliest point at which building an `ActionExecutionGateway` (deliberately **not** built in Phase 0/1 — see `sampark/integrations/interfaces.py`'s module docstring) becomes worth discussing: i.e., should any part of a Bank Mitra-confirmed action ever be submitted programmatically, vs. the Bank Mitra keying it into the core system directly as today. This is a genuine risk-tradeoff decision for SBI to make deliberately, not a default to slide into because it's technically possible.
- Re-run the full Phase 1 success-metric set at the larger scale before considering Phase 3.

## Phase 3 — Full Rollout Considerations (82,900 outlets)

Explicitly out of scope for this plan to detail — the honest position is that Phase 3 planning should be written *after* Phase 1/2 produce real data, not before. What can be said now: the per-visit LLM cost economics in `README.md` hold up arithmetically at this scale (sub-rupee per action), but the **infrastructure, support, and training operation** required to actually reach 82,900 outlets is an organizational undertaking on a completely different scale than anything this prototype addresses, and deserves its own planning process once Phase 1/2 have produced evidence to plan from.

---

## Roles and Responsibilities

| Role | Responsibility |
|---|---|
| SBI Engineering | Phase 0 integration work (real `CustomerDataProvider`/`ConsentLedger`/`BankMitraDirectory`), LLM cost/latency monitoring |
| SBI Compliance/Legal | RBI/DPDP review, consent-mechanism sign-off, ongoing guardrail audit |
| SBI Ops (BC/CSP management) | Outlet selection, Bank Mitra training and support, weekly qualitative feedback |
| SBI Infosec | Data-flow review of the LLM call path, provider data-processing agreement review |
| Prototype maintainers | Skill-playbook tuning based on pilot feedback, benchmark harness maintenance, guardrail changes (with compliance sign-off on any guardrail change, always) |

---

## What Would Make This Plan Wrong

Worth stating plainly: this plan assumes Sampark's current architecture (deterministic guardrails, LLM narration-only, human-in-the-loop execution) is the right shape for a pilot. If SBI's own risk appetite, regulatory posture, or operational reality differs from what's assumed here, the right move is to revise this plan against that reality — not to force a pilot to fit a plan written before any real stakeholder feedback existed.
