from __future__ import annotations

from sampark.core.models import AgentAction, Customer


def reasoning(signal: str, why: str, mitra_check: str, outcome: str) -> dict[str, str]:
    return {
        "customer_signal": signal,
        "why_this_action": why,
        "bank_mitra_must_verify": mitra_check,
        "expected_outcome": outcome,
    }


def onboarding_agent(customer: Customer) -> list[AgentAction]:
    actions: list[AgentAction] = []
    if customer.account_status == "dormant":
        actions.append(
            AgentAction(
                agent="Onboarding Agent",
                title="Account reactivation",
                detail="Guide Bank Mitra through biometric verification and dormant-account reactivation request.",
                payload=reasoning(
                    "Account is dormant.",
                    "Digital activation should not start until the account can safely transact.",
                    "Biometric match, customer presence, and reactivation acknowledgement.",
                    "Account reactivation request is ready for assisted submission.",
                ),
            )
        )
    if customer.kyc_level != "FULL":
        actions.append(
            AgentAction(
                agent="Onboarding Agent",
                title="Full KYC completion",
                detail="Collect missing KYC data, verify documents, and prepare submission for Bank Mitra approval.",
                payload=reasoning(
                    f"KYC level is {customer.kyc_level}.",
                    "UPI, YONO, and product journeys need full eligibility before execution.",
                    "Original document check, demographic match, and customer consent.",
                    "KYC submission is prepared before digital actions continue.",
                ),
            )
        )
    return actions


def adoption_agent(customer: Customer) -> list[AgentAction]:
    actions: list[AgentAction] = []
    if customer.upi_status != "active":
        actions.append(
            AgentAction(
                agent="Digital Adoption Agent",
                title="UPI activation",
                detail=f"Explain UPI setup in {customer.language}, create handle, and wait for Bank Mitra confirmation.",
                payload=reasoning(
                    f"UPI status is {customer.upi_status}.",
                    "UPI is the highest-frequency adoption habit for assisted digital banking.",
                    "Customer owns the mobile number/device and understands PIN safety.",
                    "UPI handle is ready after Bank Mitra confirmation.",
                ),
            )
        )
    if customer.yono_status != "active":
        actions.append(
            AgentAction(
                agent="Digital Adoption Agent",
                title="YONO onboarding",
                detail=f"Install/sign in to YONO, complete assisted onboarding, and show balance enquiry in {customer.language}.",
                payload=reasoning(
                    f"YONO status is {customer.yono_status}.",
                    "YONO creates a durable self-service channel beyond the CSP visit.",
                    "Customer can unlock the app and understands credential safety.",
                    "Customer completes the first safe in-app task.",
                ),
            )
        )
    if customer.digital_txn_count == 0:
        actions.append(
            AgentAction(
                agent="Digital Adoption Agent",
                title="First digital transaction",
                detail="Co-drive a Rs 10 live demo transfer or merchant collect request after customer confirmation.",
                payload=reasoning(
                    "Customer has no recorded digital transactions.",
                    "A small assisted transaction turns onboarding into actual adoption.",
                    "Customer confirms payee, amount, and final authorisation.",
                    "First successful transaction is completed with human confirmation.",
                ),
            )
        )
    return actions


def engagement_agent(customer: Customer) -> list[AgentAction]:
    if customer.digital_txn_count == 0 or customer.kyc_level != "FULL":
        return []
    if "Recurring Deposit" not in customer.products:
        return [
            AgentAction(
                agent="Engagement Agent",
                title="Next-best product",
                detail="Offer a Rs 500 recurring deposit as the next digital product, with plain-language explanation.",
                payload=reasoning(
                    "Customer is digitally active and does not have a recurring deposit.",
                    "A small-ticket RD is a low-complexity deepening product after adoption.",
                    "Suitability, affordability, lock-in terms, and no pressure selling.",
                    "Customer receives a compliant explanation and may opt in later.",
                ),
            )
        ]
    if "Merchant QR" not in customer.products and "merchant" in customer.segment.lower():
        return [
            AgentAction(
                agent="Engagement Agent",
                title="Merchant QR onboarding",
                detail="Prepare a merchant QR setup flow and explain settlement timing in plain language.",
                payload=reasoning(
                    "Customer is tagged as a rural micro merchant.",
                    "QR acceptance can increase digital transactions at the outlet and merchant shop.",
                    "Business ownership, settlement account, fees, and consent.",
                    "Merchant QR request is ready for Bank Mitra-confirmed submission.",
                ),
            )
        ]
    return []
