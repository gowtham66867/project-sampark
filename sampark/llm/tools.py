from __future__ import annotations

from typing import Any

from sampark.core.impact import project_impact
from sampark.data.mock_data import get_customer

_ALLOWED_FIELDS = (
    "kyc_level",
    "account_status",
    "yono_status",
    "upi_status",
    "digital_txn_count",
    "products",
    "language",
    "segment",
)


def build_tool_definitions() -> list[dict[str, Any]]:
    """Anthropic tool-use JSON schemas for the two read-only lookups the
    narrator LLM is allowed to ground itself in. Deliberately narrow: no
    tool exists to change a customer record, add a product, or fetch
    anything outside these two pure functions -- this is the concrete
    mechanism for grounding the LLM in real structured data instead of
    letting it invent facts, without giving it any ability to mutate state
    or move money."""
    return [
        {
            "name": "get_customer_fact",
            "description": (
                "Look up a specific field for the customer currently being "
                "served, to verify a fact before writing about it. Use this "
                "instead of guessing or inferring a value not already given "
                "to you directly."
            ),
            "input_schema": {
                "type": "object",
                "properties": {
                    "field": {"type": "string", "enum": list(_ALLOWED_FIELDS)},
                },
                "required": ["field"],
            },
        },
        {
            "name": "get_impact_projection",
            "description": (
                "Get the illustrative outlet-scale impact numbers, for context "
                "in outreach framing only. Never state these as a promise or "
                "guarantee to a specific customer."
            ),
            "input_schema": {"type": "object", "properties": {}, "required": []},
        },
    ]


def execute_tool_call(name: str, tool_input: dict[str, Any], *, allowed_customer_id: str) -> Any:
    """Dispatches a tool_use block to the underlying mock_data/impact pure
    functions. `allowed_customer_id` is enforced here -- never trusted from
    the model's own input -- so the LLM cannot use get_customer_fact to
    read a different customer's data than the one currently being served."""
    if name == "get_customer_fact":
        field = tool_input.get("field")
        if field not in _ALLOWED_FIELDS:
            raise ValueError(f"Field not allowed: {field}")
        customer = get_customer(allowed_customer_id)
        return {"field": field, "value": getattr(customer, field)}
    if name == "get_impact_projection":
        return project_impact()
    raise ValueError(f"Unknown tool: {name}")
