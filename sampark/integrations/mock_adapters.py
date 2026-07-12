"""Reference implementations of sampark/integrations/interfaces.py,
backed by the existing mock data. These exist to prove each interface is
concretely satisfiable -- not just a wishlist -- and to give an
integration engineer a working example to diff their real implementation
against.

MockConsentLedger additionally demonstrates the one behavior the current
prototype's static Customer.consent field cannot: an actual audit trail
of who captured consent, when, and how.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from sampark.core.models import BankMitra, Customer
from sampark.data.mock_data import get_bank_mitra, get_customer, list_customers


class MockCustomerDataProvider:
    """Backed directly by sampark/data/mock_data.py -- the exact same
    mock data the rest of the prototype and its 85-test offline suite
    already rely on. A real CustomerDataProvider composes live calls to
    CBS/YONO/UPI/risk systems instead; see interfaces.py's field-mapping
    table for exactly which system supplies which field."""

    def get_customer(self, customer_id: str) -> Customer:
        return get_customer(customer_id)

    def list_customers(self) -> list[Customer]:
        return list_customers()


@dataclass
class ConsentRecord:
    customer_id: str
    language: str
    channel: str
    bank_mitra_id: str
    captured_at: str


class MockConsentLedger:
    """In-memory, append-only consent audit trail. A real ConsentLedger
    must be durable and independently auditable (a database table, not a
    Python list) -- this exists to prove the interface shape and to give
    the orchestrator something real to overlay onto Customer.consent
    during integration testing, without needing a real database yet."""

    def __init__(self) -> None:
        self._records: list[ConsentRecord] = []
        # Seed with the same consent status the mock Customer records
        # already carry, so IntegrationBundle.load_customer_for_visit()
        # produces identical behavior to reading Customer.consent
        # directly, for every existing test scenario.
        self._consent_status: dict[str, bool] = {
            customer.customer_id: customer.consent for customer in list_customers()
        }

    def get_consent_status(self, customer_id: str) -> bool:
        return self._consent_status.get(customer_id, False)

    def record_consent_capture(
        self, customer_id: str, *, language: str, channel: str, bank_mitra_id: str
    ) -> None:
        self._records.append(
            ConsentRecord(
                customer_id=customer_id,
                language=language,
                channel=channel,
                bank_mitra_id=bank_mitra_id,
                captured_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        )
        self._consent_status[customer_id] = True

    def history_for(self, customer_id: str) -> list[ConsentRecord]:
        """Not part of the ConsentLedger Protocol (not every real consent
        system need expose full history the same way) -- provided here as
        a convenience for tests and for demonstrating what an audit
        export would look like."""
        return [record for record in self._records if record.customer_id == customer_id]


class MockBankMitraDirectory:
    """Backed by the current prototype's single hardcoded BankMitra. A
    real BankMitraDirectory looks up one of ~82,900 outlets' Bank Mitras
    by mitra_id, sourced from SBI's existing BC/CSP management platform."""

    def get_bank_mitra(self, mitra_id: str) -> BankMitra:
        mitra = get_bank_mitra()
        if mitra_id != mitra.mitra_id:
            raise KeyError(mitra_id)
        return mitra
