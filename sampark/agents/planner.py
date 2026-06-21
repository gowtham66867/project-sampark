from __future__ import annotations

from sampark.core.models import Customer


def choose_goal(customer: Customer) -> str:
    if not customer.consent:
        return "Capture DPDP consent before any assisted banking journey."
    if "SUSPICIOUS_BEHAVIOUR" in customer.risk_flags:
        return "Pause digital activation and route the visit for Bank Mitra risk review."
    if customer.account_status == "dormant":
        return "Reactivate account, complete full KYC, then prepare UPI/YONO adoption."
    if "OTP_FAILURE" in customer.risk_flags:
        return "Resolve OTP/device readiness before restarting digital onboarding."
    if customer.upi_status != "active":
        return "Activate UPI and complete the customer's first digital transaction."
    if customer.yono_status != "active":
        return "Complete YONO onboarding and demonstrate the first in-app task."
    if "Recurring Deposit" not in customer.products:
        return "Recommend a small-ticket recurring deposit after digital adoption."
    return "Deepen engagement with the next relevant digital product."
