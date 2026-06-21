from __future__ import annotations

from copy import deepcopy

from sampark.core.models import BankMitra, Customer


CUSTOMERS = {
    "c001": Customer(
        customer_id="c001",
        name="Sita Devi",
        village="Rampur, Bihar",
        language="Hindi",
        segment="PMJDY savings customer",
        kyc_level="FULL",
        account_status="active",
        yono_status="not_onboarded",
        upi_status="not_active",
        digital_txn_count=0,
        products=["Savings Account"],
        consent=True,
        visit_reason="Wants help starting UPI and YONO after opening savings account.",
    ),
    "c002": Customer(
        customer_id="c002",
        name="Ramesh Kumar",
        village="Dharwad, Karnataka",
        language="Kannada",
        segment="Rural micro merchant",
        kyc_level="FULL",
        account_status="active",
        yono_status="installed_inactive",
        upi_status="active",
        digital_txn_count=2,
        products=["Savings Account", "UPI"],
        consent=True,
        visit_reason="Merchant wants more digital collection options.",
    ),
    "c003": Customer(
        customer_id="c003",
        name="Amina Begum",
        village="Murshidabad, West Bengal",
        language="Bengali",
        segment="Dormant PMJDY customer",
        kyc_level="MIN",
        account_status="dormant",
        yono_status="not_onboarded",
        upi_status="not_active",
        digital_txn_count=0,
        products=["Savings Account"],
        consent=True,
        risk_flags=["MIN_KYC_LIMIT"],
        visit_reason="Dormant account holder wants to restart banking services.",
    ),
    "c004": Customer(
        customer_id="c004",
        name="Meena Patil",
        village="Satara, Maharashtra",
        language="Marathi",
        segment="Senior citizen pension customer",
        kyc_level="FULL",
        account_status="active",
        yono_status="not_onboarded",
        upi_status="active",
        digital_txn_count=4,
        products=["Savings Account", "UPI"],
        consent=True,
        visit_reason="Needs assisted YONO setup for pension balance checks.",
    ),
    "c005": Customer(
        customer_id="c005",
        name="Iqbal Ansari",
        village="Kishanganj, Bihar",
        language="Urdu",
        segment="Rural micro merchant",
        kyc_level="FULL",
        account_status="active",
        yono_status="active",
        upi_status="active",
        digital_txn_count=12,
        products=["Savings Account", "UPI", "Recurring Deposit"],
        consent=True,
        visit_reason="Merchant wants QR acceptance for small shop payments.",
    ),
    "c006": Customer(
        customer_id="c006",
        name="Lalita Oraon",
        village="Gumla, Jharkhand",
        language="Hindi",
        segment="PMJDY savings customer",
        kyc_level="FULL",
        account_status="active",
        yono_status="not_onboarded",
        upi_status="not_active",
        digital_txn_count=0,
        products=["Savings Account"],
        consent=False,
        visit_reason="Asks about digital services but has not consented to assisted journey.",
    ),
    "c007": Customer(
        customer_id="c007",
        name="Biren Das",
        village="Nalbari, Assam",
        language="Assamese",
        segment="Small farmer",
        kyc_level="FULL",
        account_status="active",
        yono_status="not_onboarded",
        upi_status="not_active",
        digital_txn_count=0,
        products=["Savings Account"],
        consent=True,
        risk_flags=["SUSPICIOUS_BEHAVIOUR"],
        visit_reason="Requests urgent UPI setup after unusual account activity.",
    ),
    "c008": Customer(
        customer_id="c008",
        name="Kavitha Nair",
        village="Palakkad, Kerala",
        language="Malayalam",
        segment="Self-help group member",
        kyc_level="FULL",
        account_status="active",
        yono_status="installed_inactive",
        upi_status="not_active",
        digital_txn_count=0,
        products=["Savings Account"],
        consent=True,
        risk_flags=["OTP_FAILURE"],
        visit_reason="Tried onboarding but OTP/device verification failed.",
    ),
    "c009": Customer(
        customer_id="c009",
        name="Tsering Dolma",
        village="Leh, Ladakh",
        language="Hindi",
        segment="Remote village savings customer",
        kyc_level="FULL",
        account_status="active",
        yono_status="not_onboarded",
        upi_status="not_active",
        digital_txn_count=0,
        products=["Savings Account"],
        consent=True,
        channel_conditions=["LOW_CONNECTIVITY"],
        visit_reason="Needs assisted setup in a low-connectivity outlet.",
    ),
    "c010": Customer(
        customer_id="c010",
        name="Harpreet Singh",
        village="Moga, Punjab",
        language="Punjabi",
        segment="Digitally active savings customer",
        kyc_level="FULL",
        account_status="active",
        yono_status="active",
        upi_status="active",
        digital_txn_count=9,
        products=["Savings Account", "UPI"],
        consent=True,
        visit_reason="Asks for a simple savings habit after using UPI regularly.",
    ),
}


BANK_MITRA = BankMitra(
    mitra_id="bm-82900-044",
    name="Anil Prasad",
    outlet="SBI CSP Rampur",
    language="Hindi",
)


def get_customer(customer_id: str) -> Customer:
    if customer_id not in CUSTOMERS:
        raise KeyError(f"Unknown customer id: {customer_id}")
    return deepcopy(CUSTOMERS[customer_id])


def list_customers() -> list[Customer]:
    return [deepcopy(customer) for customer in CUSTOMERS.values()]


def get_bank_mitra() -> BankMitra:
    return deepcopy(BANK_MITRA)
