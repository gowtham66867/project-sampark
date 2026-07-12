"""The integration contract: exact interfaces a real SBI engineering team
would implement to replace this prototype's mocked data with live systems.

This is the single most important file for turning Sampark from a
hackathon prototype into a pilot-ready system. Every method below is
documented with (a) what it must return/do, and (b) which real SBI system
it is standing in for. `sampark/integrations/mock_adapters.py` provides a
reference implementation of every interface here, backed by the existing
mock data -- proving each interface is concretely satisfiable, not just
aspirational.

Nothing in sampark/core/, sampark/agents/, or sampark/llm/ needs to change
to adopt a real implementation of these interfaces: SamparkOrchestrator
already takes its Customer/BankMitra objects as plain arguments (see
sampark/core/orchestrator.py's `run()` signature) rather than reaching
into mock_data.py itself. A real deployment wires a real
CustomerDataProvider/ConsentLedger implementation in at the call site
(run_demo.py or wherever the production entrypoint lives), not inside the
orchestrator.

Deliberately NOT included: an "ActionExecutionGateway" that autonomously
submits a confirmed action to a core banking system. That is intentionally
a separate, later design decision -- see PILOT_ROLLOUT_PLAN.md's
"Phase 2" -- so that adopting real read-side data sources does not, by
itself, change Sampark's current safety property that NOTHING executes
without a Bank Mitra acting outside this software.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from sampark.core.models import BankMitra, Customer


@runtime_checkable
class CustomerDataProvider(Protocol):
    """Replaces sampark/data/mock_data.py's get_customer/list_customers.

    A real implementation composes data from several SBI systems into one
    Customer object per visit:

    | Customer field                              | Real SBI system of record |
    |----------------------------------------------|----------------------------|
    | customer_id, name, village                    | Core Banking System (CBS/Finacle) -- CIF/customer master |
    | kyc_level, account_status, products            | CBS -- KYC module, account status flag, product holding table |
    | segment                                        | CBS product/scheme tagging (e.g. PMJDY flag) or CRM segmentation |
    | yono_status                                    | YONO platform's own user registration/session directory |
    | upi_status, digital_txn_count                  | SBI's UPI switch / digital channel transaction analytics |
    | risk_flags                                     | SBI's AML/fraud risk scoring engine |
    | channel_conditions (e.g. LOW_CONNECTIVITY)      | BC/CSP outlet telemetry, or Bank Mitra field input for that visit |
    | language                                       | CBS customer preference field, or CRM/BC-outlet record |
    | consent                                        | A DPDP-compliant consent ledger (see ConsentLedger below) -- NOT read from CBS |
    | visit_reason                                   | Free text captured by the Bank Mitra for this specific visit; never a system-of-record field |

    Implementations MUST treat this as a live, per-visit read -- caching a
    Customer object across visits risks acting on stale KYC/risk state,
    which is exactly the kind of staleness guardrails.py assumes never
    happens.
    """

    def get_customer(self, customer_id: str) -> Customer:
        """Fetch the current, live state for one customer. Must raise
        KeyError (matching mock_data.py's existing contract, so
        run_demo.py's 404 handling needs no changes) if the customer_id is
        unknown to the underlying systems."""
        ...

    def list_customers(self) -> list[Customer]:
        """Used only by the demo/ops console's customer picker -- NOT a
        pattern a real deployment should use to serve production traffic
        (a real Bank Mitra console would look up one customer per visit by
        ID/mobile number/biometric, never list all customers)."""
        ...


@runtime_checkable
class ConsentLedger(Protocol):
    """A DPDP-compliant consent capture and audit system. This does NOT
    exist even as a real concept in the current prototype -- Customer.consent
    is just a static boolean field on the mock data. A real deployment
    needs an actual consent ledger as a distinct system from core banking,
    because consent status must be independently auditable (who captured
    it, when, in what language, via what channel) separately from account
    state.
    """

    def get_consent_status(self, customer_id: str) -> bool:
        """Returns whether valid, current consent is on file. This is
        what guardrails.consent_gate should be fed, instead of trusting a
        static Customer.consent field, in a real deployment."""
        ...

    def record_consent_capture(
        self, customer_id: str, *, language: str, channel: str, bank_mitra_id: str
    ) -> None:
        """Records that consent was captured for this customer, in this
        language, via this channel (e.g. "in_person_bank_mitra"), by this
        Bank Mitra -- the audit trail a DPDP compliance review will
        actually ask for. Real implementations should be append-only."""
        ...


@runtime_checkable
class BankMitraDirectory(Protocol):
    """Replaces sampark/data/mock_data.py's get_bank_mitra (currently a
    single hardcoded BankMitra). A real deployment has ~82,900 BC outlets,
    each with its own Bank Mitra(s) -- this is the BC/CSP management
    platform SBI already operates, not something new to build from
    scratch."""

    def get_bank_mitra(self, mitra_id: str) -> BankMitra:
        """Fetch the current Bank Mitra record for the outlet handling
        this visit. Must raise KeyError for an unknown mitra_id."""
        ...


class IntegrationBundle:
    """Convenience container bundling the three provider interfaces above,
    so a production entrypoint can construct one object and pass it around
    instead of three. Purely a wiring convenience -- SamparkOrchestrator
    itself still only ever sees plain Customer/BankMitra objects, never
    this bundle, preserving the existing safety-relevant call signature."""

    def __init__(
        self,
        customer_data: CustomerDataProvider,
        consent_ledger: ConsentLedger,
        bank_mitra_directory: BankMitraDirectory,
    ) -> None:
        self.customer_data = customer_data
        self.consent_ledger = consent_ledger
        self.bank_mitra_directory = bank_mitra_directory

    def load_customer_for_visit(self, customer_id: str) -> Customer:
        """Fetches the customer record and overlays live consent status
        from the ConsentLedger -- the one field mock_data.py currently
        stores statically that a real deployment must not."""
        customer = self.customer_data.get_customer(customer_id)
        customer.consent = self.consent_ledger.get_consent_status(customer_id)
        return customer


def find_missing_capabilities(candidate: object) -> dict[str, list[str]]:
    """Diagnostic helper for an integration engineer: given an in-progress
    real implementation object, reports which of the three interfaces it
    satisfies and which methods are still missing from each. Useful during
    incremental integration work, when an object might be a partial
    CustomerDataProvider before it's a complete one.

    Returns e.g. {"CustomerDataProvider": [], "ConsentLedger": ["record_consent_capture"], ...}
    -- an empty list means that interface is fully satisfied.
    """
    report: dict[str, list[str]] = {}
    for protocol in (CustomerDataProvider, ConsentLedger, BankMitraDirectory):
        required = [name for name, value in vars(protocol).items() if not name.startswith("_") and callable(value)]
        missing = [name for name in required if not callable(getattr(candidate, name, None))]
        report[protocol.__name__] = missing
    return report
