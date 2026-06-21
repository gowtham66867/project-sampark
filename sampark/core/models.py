from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Customer:
    customer_id: str
    name: str
    village: str
    language: str
    segment: str
    kyc_level: str
    account_status: str
    yono_status: str
    upi_status: str
    digital_txn_count: int
    products: list[str]
    consent: bool
    risk_flags: list[str] = field(default_factory=list)
    visit_reason: str = "digital adoption support"
    channel_conditions: list[str] = field(default_factory=list)


@dataclass
class BankMitra:
    mitra_id: str
    name: str
    outlet: str
    language: str


@dataclass
class AgentAction:
    agent: str
    title: str
    detail: str
    status: str = "pending"
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class AuditEvent:
    stage: str
    message: str
    status: str = "recorded"
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class SamparkRun:
    customer: Customer
    bank_mitra: BankMitra
    intent: str
    goal: str
    steps: list[AgentAction]
    verification: dict[str, Any]
    outcome: dict[str, Any]
    audit_id: str
    audit_timeline: list[AuditEvent] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "created_at": self.created_at,
            "customer": self.customer.__dict__,
            "bank_mitra": self.bank_mitra.__dict__,
            "intent": self.intent,
            "goal": self.goal,
            "steps": [step.__dict__ for step in self.steps],
            "verification": self.verification,
            "outcome": self.outcome,
            "audit_timeline": [event.__dict__ for event in self.audit_timeline],
        }
