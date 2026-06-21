# Project Sampark

Agentic AI copilot prototype for SBI Bank Mitra / BC outlets, built for the **Digital Adoption** hackathon problem statement.

Sampark demonstrates a closed assisted-banking loop:

1. **Listen** to the Bank Mitra and customer intent in the local language.
2. **Plan** the highest-value next action for the walk-in customer.
3. **Co-execute** with specialist agents for account, UPI, YONO, QR, and product adoption tasks.
4. **Verify** consent, KYC, limits, risk, OTP/device readiness, and suitability before submission.
5. **Learn** from outcomes to improve the next-best-action playbook.

The prototype deliberately keeps the Bank Mitra as the human-in-the-loop actor. It does not move money autonomously and does not make autonomous lending decisions.

## Why It Is Stronger Than A Chatbot

- It is designed for SBI's assisted last-mile channel, not generic self-service chat.
- Every recommendation carries an explainability payload: customer signal, why this action, Bank Mitra check, and expected outcome.
- Every run produces an audit timeline across Listen, Govern, Plan, Co-execute, Verify, and Learn.
- The Govern layer can stop risky actions while allowing safe preparatory actions such as KYC completion.
- Mock integrations are isolated behind clean Python modules so SBI core, AePS, YONO, and Account Aggregator connectors can replace them later.

## Run The Browser Demo

```bash
cd "/Users/gowtham/Downloads/AIAgent/SBI project Sampark"
python3 run_demo.py
```

Open:

```text
http://127.0.0.1:8088
```

## Run The CLI Demo

```bash
python3 run_demo.py --cli --customer c001
python3 run_demo.py --cli --customer c003
python3 run_demo.py --cli --customer c006
python3 run_demo.py --cli --customer c007
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
  -> run_demo.py
  -> SamparkOrchestrator
     -> consent_gate
     -> choose_goal
     -> onboarding_agent / adoption_agent / engagement_agent
     -> verify_before_submit
     -> LearningStore
```

Key modules:

- `sampark/core/orchestrator.py`: closed-loop journey coordination.
- `sampark/core/guardrails.py`: consent, KYC, risk, OTP, channel, and suitability checks.
- `sampark/agents/specialists.py`: specialist action generation with explainability payloads.
- `sampark/data/mock_data.py`: ten customer scenarios for demo and tests.
- `sampark/web`: static Bank Mitra console.

## Run Tests

```bash
python3 -m unittest discover -s tests -v
```

Current QA coverage: **26 passing tests**.

Covered areas include planner branches, KYC blocks, consent block, suspicious-risk block, OTP/device block, low-connectivity warning, senior-citizen warning, merchant QR onboarding, RD suitability controls, action reasoning payloads, audit timeline, learning signals, data isolation, audit ID format, and impact math.

## API Smoke Checks

```bash
curl -s http://127.0.0.1:8088/api/customers
curl -s "http://127.0.0.1:8088/api/run?customer=c003"
curl -s "http://127.0.0.1:8088/api/run?customer=missing"
```

Unknown customers return a structured `404` JSON error.

## What Is Mocked

The prototype mocks SBI core, AePS, YONO, Account Aggregator, OTP, QR, and risk integrations. In a production pilot, these connectors would run inside SBI's VPC/cloud with SBI-approved security, audit, authentication, consent, encryption, and observability controls.

## Submission Mapping

- **Innovation:** agentic assisted-banking console for Bank Mitra outlets, not a generic bot.
- **Business potential:** uses 82,900 BC outlets as the scaling surface.
- **Scalability:** one copilot pattern across outlets, languages, and product journeys.
- **UX:** operational console with local-language intent, reasoned actions, and guardrail states.
- **Technical feasibility:** standard Python, no external dependency burden, clean mocked integration points.
- **Regulatory readiness:** DPDP consent gate, KYC/risk checks, OTP/device readiness, audit timeline, suitability control, and human authorisation.

## Prototype Score

As a hackathon prototype, this is positioned around **9.5/10**: demoable, explainable, policy-aware, and tested. As production software, it would still need SBI-grade identity, access control, connector hardening, persistence, monitoring, security review, and compliance sign-off.
