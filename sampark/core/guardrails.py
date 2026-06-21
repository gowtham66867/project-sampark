from __future__ import annotations

from sampark.core.models import AgentAction, Customer


MONEY_ACTION_WORDS = ("upi", "yono", "transaction", "merchant qr")


def consent_gate(customer: Customer) -> dict[str, object]:
    if not customer.consent:
        return {
            "passed": False,
            "reason": "Customer consent missing. Stop journey and capture DPDP consent first.",
            "policy_checks": [
                {
                    "name": "DPDP consent",
                    "status": "blocked",
                    "detail": "No assisted action can start until consent is captured.",
                }
            ],
            "blocked": ["Customer consent missing. Capture DPDP consent before continuing."],
            "warnings": [],
            "human_authorisation": "Bank Mitra must capture consent in the customer's language.",
            "rbi_posture": "No autonomous money movement and no autonomous lending decision.",
        }
    return {
        "passed": True,
        "reason": "Consent captured and linked to this assisted journey.",
        "policy_checks": [
            {
                "name": "DPDP consent",
                "status": "passed",
                "detail": "Consent is linked to this assisted journey.",
            }
        ],
    }


def verify_before_submit(customer: Customer, steps: list[AgentAction]) -> dict[str, object]:
    blocked: list[str] = []
    warnings: list[str] = []
    policy_checks: list[dict[str, str]] = [
        {
            "name": "Consent",
            "status": "passed",
            "detail": "Customer consent is present for this assisted journey.",
        }
    ]

    if customer.kyc_level != "FULL":
        blocked.extend(
            [
                "UPI activation blocked until full KYC is completed.",
                "YONO onboarding blocked until full KYC is completed.",
                "First digital transaction blocked until full KYC is completed.",
            ]
        )
        policy_checks.append(
            {
                "name": "KYC eligibility",
                "status": "blocked",
                "detail": "Full KYC is required before digital activation or money movement.",
            }
        )
    else:
        policy_checks.append(
            {
                "name": "KYC eligibility",
                "status": "passed",
                "detail": "Customer has full KYC.",
            }
        )

    if customer.account_status == "dormant":
        warnings.append("Dormant account reactivation must be completed before digital activation.")
        policy_checks.append(
            {
                "name": "Dormant account",
                "status": "warning",
                "detail": "Reactivation must complete before activation journeys are submitted.",
            }
        )

    if "SUSPICIOUS_BEHAVIOUR" in customer.risk_flags:
        blocked.append("Suspicious behaviour flag requires Bank Mitra escalation before digital activation.")
        policy_checks.append(
            {
                "name": "Fraud/risk review",
                "status": "blocked",
                "detail": "Risk flag must be resolved by authorised staff before proceeding.",
            }
        )

    if "OTP_FAILURE" in customer.risk_flags:
        blocked.append("OTP/device readiness failed. Restart onboarding only after customer-controlled OTP verification.")
        policy_checks.append(
            {
                "name": "OTP and device readiness",
                "status": "blocked",
                "detail": "The customer must control OTP/device credentials.",
            }
        )

    if "MIN_KYC_LIMIT" in customer.risk_flags:
        warnings.append("Minimum-KYC customer: enforce transaction and product limits.")

    if "LOW_CONNECTIVITY" in customer.channel_conditions:
        warnings.append("Low connectivity: use assisted-save mode and submit only after network confirmation.")
        policy_checks.append(
            {
                "name": "Channel readiness",
                "status": "warning",
                "detail": "Network instability requires explicit final confirmation before submission.",
            }
        )

    if "Senior citizen" in customer.segment:
        warnings.append("Confirm language comprehension and allow extra time before customer authorisation.")

    for step in steps:
        title = step.title.lower()
        if blocked and any(word in title for word in MONEY_ACTION_WORDS):
            step.status = "blocked"
            step.payload["guardrail_result"] = "blocked_by_policy"
        elif step.status == "pending":
            step.status = "ready_for_bank_mitra_confirmation"
            step.payload["guardrail_result"] = "ready_for_human_confirmation"

        if step.title == "Next-best product":
            step.payload["mis_selling_control"] = "Explain suitability, costs, lock-in, and customer right to decline."

    return {
        "passed": not blocked,
        "blocked": blocked,
        "warnings": warnings,
        "policy_checks": policy_checks,
        "human_authorisation": "Bank Mitra must confirm every money movement and customer-facing submission.",
        "rbi_posture": "No autonomous money movement and no autonomous lending decision.",
    }
