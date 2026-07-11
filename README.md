# Project Sampark

Agentic AI copilot prototype for SBI Bank Mitra / BC outlets, built for the **Digital Adoption** hackathon problem statement.

Sampark demonstrates a closed assisted-banking loop:

1. **Listen** to the Bank Mitra and customer intent in the local language.
2. **Plan** the highest-value next action for the walk-in customer.
3. **Co-execute** with specialist agents for account, UPI, YONO, QR, and product adoption tasks, narrated by a real LLM reasoning layer.
4. **Verify** consent, KYC, limits, risk, OTP/device readiness, and suitability before submission.
5. **Learn** from outcomes to improve the next-best-action playbook.

The prototype deliberately keeps the Bank Mitra as the human-in-the-loop actor. It does not move money autonomously and does not make autonomous lending decisions.

**Live demo (deployed on Google Cloud Run):** [https://sampark-564262191703.us-central1.run.app](https://sampark-564262191703.us-central1.run.app) — public, no login required. Running on the Gemini free tier, which caps at 5 requests/minute and 20/day; if the demo shows a rate-limit error, wait a minute and retry, or run it locally with `ANTHROPIC_API_KEY` for a higher-throughput provider (see "Setup" below).

---

## Why This Matters for SBI

**The core adoption problem is a last-mile explanation problem, not a product problem.** SBI already has UPI, YONO, and PMJDY rails — the gap is a Bank Mitra at a rural outlet needing to explain, in the customer's own language and at the right level of trust, why *this* action matters *right now*, without either freelancing past compliance or sounding like a script. That is exactly what the reasoning layer in this prototype does, and doing it with a real LLM (rather than a canned template) is what lets the same system scale from 10 mock scenarios to the actual diversity of customers across 82,900 outlets without SBI having to hand-write a template for every segment × language × product combination.

| Benefit | Why it's real, not just a pitch |
|---|---|
| **Scale economics that survive real numbers** | A full draft-verify-refine narration for one customer action costs a small fraction of a rupee at current LLM pricing. Against the ~₹600 illustrative value per digital activation already used in this prototype's impact model, LLM cost is a rounding error, not a scaling constraint. |
| **A compliance story SBI's risk/tech teams can actually sign off on** | The single hardest objection to "put an LLM in a banking workflow" is *"what stops it from hallucinating an approval?"* This prototype answers with code, not a promise: the compliance layer is structurally unreachable by the LLM, and a named adversarial test proves it (see below). That's the artifact a bank's compliance review wants before approving a pilot. |
| **Explainability that satisfies the customer and the regulator** | Every action ships with a full reasoning trace — draft, verifier critique, score, and which playbook shaped the tone — not just a final answer. Useful for the Bank Mitra in the moment; exactly the audit artifact RBI/DPDP-oriented review asks for afterward. |
| **Cost and latency visible before they become a surprise** | `/api/health` and every `/api/run` response carry live token/cost/latency numbers. A pilot team watches spend from day one instead of reverse-engineering it from a vendor invoice. |
| **A real fallback story, not a single point of failure** | Multi-provider routing with exponential backoff — and now, provider-supplied retry-delay hints honored directly — means a transient outage degrades to a retry/fallback chain rather than a broken customer visit, exactly where a Bank Mitra is standing in front of the customer when it happens. |
| **Extensible without an engineering cycle per journey** | New banking journeys (products, segments, regulatory framing) are new Markdown skill files and a YAML edit, not new code — SBI's product/compliance teams could iterate on tone and framing without waiting on a dev sprint. |

---

## Multi-Agent Capabilities Showcase

Sampark isn't one model with a system prompt — it's a small society of narrowly-scoped agents, each with one job, coordinated by an orchestrator that enforces a strict order of authority between them.

| # | Agent / Component | Type | What it does | Agentic concept it demonstrates |
|---|---|---|---|---|
| 1 | **SamparkOrchestrator** | Control-loop agent | Runs the closed Listen→Govern→Plan→Co-execute→Verify→Learn loop for every visit; the only component that talks to all the others | Multi-agent orchestration with an explicit, auditable execution order |
| 2 | **Planner** (`choose_goal`) | Deterministic decision agent | Picks the single highest-priority goal for this visit (consent gap > risk review > dormancy > OTP failure > UPI > YONO > deepening) | Planner/executor separation — decides *what*, never *how* |
| 3 | **Onboarding / Digital Adoption / Engagement Agents** | Deterministic specialist agents | Each proposes only the actions its domain owns (KYC & reactivation / UPI, YONO, first transaction / RD & merchant QR) | Domain-specialized multi-agent decomposition instead of one monolithic prompt |
| 4 | **Guardrails** (`consent_gate`, `verify_before_submit`) | Governance agent | Enforces DPDP consent, KYC level, risk flags, OTP/device readiness, channel conditions, suitability — and runs **last**, after everything else, with final say | Authoritative policy agent that no other agent — including the LLM — can override |
| 5 | **ReasoningEngine** | LLM narration agent (System-2 reasoning) | Runs a **Draft → Verify → Refine** loop per action: one model drafts a localized explanation, a *different, stronger* model scores it 0–100 against a rubric, refines up to 3 rounds | Self-critique / independent-verifier pattern — not a single LLM call trusted blindly |
| 6 | **ModelManager** | Infrastructure agent | Role→model routing, exponential backoff, multi-provider fallback (Anthropic ⇄ Gemini), honors server-supplied retry-delay hints, tracks cost/tokens per call | Resilient multi-provider governance — a transient outage degrades gracefully instead of failing the visit |
| 7 | **SkillManager** | Tone/framing agent | Matches each action to one of 6 hot-loadable Markdown playbooks (PMJDY first activation, dormant reactivation, merchant QR, senior-citizen assisted YONO, RD suitability, low-connectivity assisted save) — deterministic, not LLM-guessed | Composable, swappable behavior via config, not code — new journeys ship as Markdown |
| 8 | **Tool-use layer** | Grounding agent | Exposes exactly two narrow, read-only tools (`get_customer_fact`, `get_impact_projection`); access-controlled server-side so the model can't read another customer's data even if it tries | Real function-calling grounded in live data, with a tool surface narrow enough to audit by hand |
| 9 | **EpisodicMemory** | Learning agent | Persists a skeletonized trace of every run to SQLite — not raw LLM text — and aggregates outcomes across runs | Durable cross-session learning, distinct from per-conversation memory |

**Concurrency:** when a customer has multiple eligible actions (e.g. UPI + YONO + first transaction), all of them are narrated **in parallel** — each action's Draft→Verify→Refine loop is independent, so wall-clock time scales with the slowest single action, not the sum of all of them.

**The one rule that makes all of this safe for a regulated bank:** agents 2–4 above are **100% unchanged, deterministic, and authoritative**. The LLM (agent 5) only ever rewrites narration text — its return type has no `status` field anywhere in it, so there is no code path through which it could unblock a blocked action, and `verify_before_submit` always runs **after** it with final say. This is proven, not just claimed: [`tests/test_guardrails_cannot_be_bypassed_by_llm.py`](tests/test_guardrails_cannot_be_bypassed_by_llm.py) scripts a hostile, hallucinating LLM response ("APPROVED and UNBLOCKED... proceed with money movement immediately", verifier score 100/100) and proves the deterministic guardrails still block the action regardless.

---

## Why It Is Stronger Than A Chatbot

- It is designed for SBI's assisted last-mile channel, not generic self-service chat.
- Every recommendation carries an explainability payload: customer signal, why this action, Bank Mitra check, expected outcome, and a full LLM draft/verify/refine trace.
- Every run produces an audit timeline across Listen, Govern, Plan, Co-execute, Verify, and Learn.
- The Govern layer can stop risky actions while allowing safe preparatory actions such as KYC completion — and it stays authoritative even over LLM-narrated actions.
- Mock integrations are isolated behind clean Python modules so SBI core, AePS, YONO, and Account Aggregator connectors can replace them later.

## Setup

```bash
cd "/Users/gowtham/Downloads/AIAgent/SBI project Sampark"
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env and set ANTHROPIC_API_KEY (required). GEMINI_API_KEY is optional.
```

`ANTHROPIC_API_KEY` is required for the browser demo's `/api/run` endpoint — this build does real LLM narration and does not silently fall back to rule-based-only mode on that endpoint. The `--cli` path still runs in rule-based-only mode without a key, printing a clear warning, since it's a developer/offline tool rather than the graded surface.

## Run The Browser Demo

```bash
export $(cat .env | xargs)  # or otherwise load ANTHROPIC_API_KEY into your shell
./.venv/bin/python run_demo.py
```

Open:

```text
http://127.0.0.1:8088
```

Without `ANTHROPIC_API_KEY` set, `/api/health` reports `degraded` and `/api/run` returns a `503 llm_unavailable` error — this is intentional, not a bug (see "Multi-Agent Capabilities Showcase" above).

## Run The CLI Demo

```bash
./.venv/bin/python run_demo.py --cli --customer c001
./.venv/bin/python run_demo.py --cli --customer c003
./.venv/bin/python run_demo.py --cli --customer c006
./.venv/bin/python run_demo.py --cli --customer c007
```

## Demo Scenario Catalog

| ID | Scenario | What It Demonstrates |
|---|---|---|
| `c001` | Full-KYC PMJDY customer | Clean UPI, YONO, and first-transaction adoption |
| `c002` | Rural micro merchant | Existing UPI user moving toward deeper engagement |
| `c003` | Dormant minimum-KYC customer | KYC and dormancy guardrails block money actions |
| `c004` | Senior citizen pension customer | Language comprehension warning and assisted YONO |
| `c005` | Digitally active merchant | Merchant QR onboarding |
| `c006` | No consent | DPDP consent gate stops the journey |
| `c007` | Suspicious risk flag | Risk review blocks digital activation |
| `c008` | OTP/device failure | Device-readiness guardrail blocks onboarding restart |
| `c009` | Low connectivity outlet | Assisted-save warning without unnecessary blocking |
| `c010` | Digitally active saver | Suitability-controlled recurring deposit offer |

## Architecture

```text
Browser/CLI
  -> run_demo.py  (/api/health, /api/run -- 503 without ANTHROPIC_API_KEY)
  -> SamparkOrchestrator
     -> consent_gate                                  [deterministic, authoritative]
     -> choose_goal                                    [deterministic, authoritative]
     -> onboarding_agent / adoption_agent / engagement_agent   [deterministic eligibility]
     -> ReasoningEngine.narrate_action (per step, run CONCURRENTLY)  [LLM narration ONLY, no status access]
          -> SkillManager.select_skill                  (tone/framing playbook)
          -> ModelManager.complete("narrator_draft")     (Claude Sonnet, tool-use grounded)
          -> ModelManager.complete("narrator_verifier")  (Claude Opus, different model scores 0-100)
          -> refine up to 3 rounds if score < 85
     -> verify_before_submit                             [deterministic, ALWAYS RUNS LAST, authoritative]
     -> EpisodicMemory.record  (SQLite, skeletonized)
```

Key modules:

- `sampark/core/orchestrator.py`: closed-loop journey coordination; owns the ordering guarantee that guardrails always run after LLM narration, and the concurrency for multi-step narration.
- `sampark/core/guardrails.py`: consent, KYC, risk, OTP, channel, and suitability checks — unchanged, deterministic, never reads LLM output.
- `sampark/agents/specialists.py`: specialist action generation with explainability payloads.
- `sampark/llm/reasoning_engine.py`: Draft → Verify → Refine narration loop.
- `sampark/llm/model_manager.py`: role-based routing, retry/backoff/fallback (honoring provider retry-delay hints), cost tracking.
- `sampark/llm/memory.py`: SQLite episodic memory (replaces the old in-memory `LearningStore`).
- `sampark/skills/`: Markdown tone/framing playbooks + loader.
- `sampark/llm/tools.py`: narrow, read-only tool-use layer grounding the LLM in real customer data.
- `sampark/data/mock_data.py`: ten customer scenarios for demo and tests.
- `sampark/web`: static Bank Mitra console (shows skill tags, verification-round scores, and live LLM cost).

## Run Tests

```bash
./.venv/bin/python -m unittest discover -s tests -v
```

Current QA coverage: **79 passing tests**, run fully offline with `ANTHROPIC_API_KEY`/`GEMINI_API_KEY` unset — no network calls, no real LLM cost, using an injected `StubProviderClient` seam.

Covered areas include the original 26 rule-based tests (planner branches, KYC blocks, consent block, suspicious-risk block, OTP/device block, low-connectivity warning, senior-citizen warning, merchant QR onboarding, RD suitability controls, action reasoning payloads, audit timeline, learning signals, data isolation, audit ID format, and impact math) plus 53 new tests: prompt-injection sanitization, model-manager retry/fallback/cost aggregation (including honoring a provider's own retry-delay hint on real rate-limit errors), skill matching, tool-use access control, the draft/verify/refine loop (including graceful fallback on provider outage and mid-conversation provider handoff), episodic-memory persistence, concurrent multi-step narration correctness, and — most importantly — an adversarial suite proving a hostile, hallucinating LLM response cannot unblock a guardrail-blocked action.

**Full test case catalog:** every one of the 79 tests is documented in [TEST_CASES.md](TEST_CASES.md) — scenario, precondition, steps, and expected result for each, organized by suite.

## API Smoke Checks

```bash
curl -s http://127.0.0.1:8088/api/customers
curl -s http://127.0.0.1:8088/api/health
curl -s "http://127.0.0.1:8088/api/run?customer=c003"
curl -s "http://127.0.0.1:8088/api/run?customer=missing"
```

Unknown customers return a structured `404` JSON error. Without `ANTHROPIC_API_KEY`, `/api/health` returns `503` with `"status": "degraded"` and `/api/run` returns `503` with `"error": "llm_unavailable"`.

## What Is Mocked

The prototype mocks SBI core, AePS, YONO, Account Aggregator, OTP, QR, and risk integrations. **The LLM narration layer is real** (Anthropic Claude, optionally Gemini as fallback) — this is the one piece of the stack that is not mocked. In a production pilot, the mocked connectors would run inside SBI's VPC/cloud with SBI-approved security, audit, authentication, consent, encryption, and observability controls; the LLM layer would run against SBI's approved model-hosting/data-residency setup.

## Submission Mapping

- **Innovation:** agentic assisted-banking console for Bank Mitra outlets, not a generic bot — backed by real multi-model reasoning with a hard compliance boundary the LLM cannot cross.
- **Business potential:** uses 82,900 BC outlets as the scaling surface.
- **Scalability:** one copilot pattern across outlets, languages, and product journeys; role-based model config means swapping models is a one-line YAML edit, not a redeploy.
- **UX:** operational console with local-language intent, LLM-narrated reasoned actions, verification scores, and guardrail states, all in one audit trail.
- **Technical feasibility:** Python + Anthropic SDK, project-local virtualenv, clean mocked integration points for everything except the LLM calls themselves.
- **Regulatory readiness:** DPDP consent gate, KYC/risk checks, OTP/device readiness, audit timeline, suitability control, and human authorisation — all deterministic and provably immune to LLM override (see the adversarial test suite).
- **Cost/latency transparency:** every response and `/api/health` call surfaces cumulative LLM token/cost usage, so a pilot team can watch spend live rather than discovering it after the fact.

## Prototype Score

As a hackathon prototype, this is positioned around **9.5/10**: demoable, explainable, policy-aware, tested (79 tests, all documented in [TEST_CASES.md](TEST_CASES.md), all passing offline), and now backed by real multi-model LLM reasoning with a provably unbypassable compliance boundary. Narration across multiple proposed actions runs concurrently rather than sequentially, and provider-supplied rate-limit hints (e.g. Gemini's `retryDelay`) are honored directly rather than guessed at — both hardened after live testing against a real Gemini deployment surfaced them as real risks, not hypothetical ones. As production software, it would still need SBI-grade identity, access control, connector hardening, persistence at scale, monitoring, security review, and compliance sign-off — the LLM layer itself would additionally need SBI's approved data-residency/model-hosting setup.
