from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional, Protocol

from sampark.core.utils import get_logger, log_event


class LLMProviderError(Exception):
    """Raised by a provider client on any call failure. ModelManager decides
    whether to retry the same (provider, model) or move to the next fallback
    hop based on `retryable`.

    `retry_after_seconds`, when a provider client can extract it from a rate
    limit response (e.g. Gemini's `retryDelay` field, Anthropic's
    `retry-after` header), overrides ModelManager's own exponential backoff
    for that attempt -- honoring the server's own guidance is more reliable
    than guessing a fixed schedule against a real per-minute quota wall."""

    def __init__(
        self, message: str, retryable: bool = True, retry_after_seconds: Optional[float] = None
    ) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.retry_after_seconds = retry_after_seconds


@dataclass
class LLMResponse:
    text: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    raw: dict[str, Any] = field(default_factory=dict)
    # Populated when the model asked to call a tool: list of
    # {"id": ..., "name": ..., "input": {...}}. Empty for a plain text reply.
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


class LLMProviderClient(Protocol):
    """Structural seam. AnthropicProviderClient/GeminiProviderClient
    implement this for real calls; StubProviderClient implements it for
    offline tests. ModelManager depends only on this Protocol, never on a
    concrete SDK type -- this is what keeps ModelManager network-free to
    import and to unit test."""

    provider_name: str

    def complete(
        self,
        *,
        model: str,
        system: Optional[str],
        messages: list[dict[str, str]],
        max_tokens: int,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse: ...


@dataclass
class RoleConfig:
    provider: str
    model: str
    max_tokens: int
    fallback: list[dict[str, str]] = field(default_factory=list)
    max_retries: Optional[int] = None


@dataclass
class UsageRecord:
    role: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latency_ms: int
    attempt: int
    fell_back: bool
    trace_id: str


class ModelManager:
    """Role-based routing over one or more LLMProviderClient implementations,
    with exponential backoff retry, provider/model fallback chains, and
    cumulative token/cost tracking.

    Constructed with an explicit `clients` mapping (provider name ->
    LLMProviderClient) so tests inject a StubProviderClient without any
    monkeypatching of the anthropic SDK. Production wiring
    (sampark.llm.factory.build_default_reasoning_engine) constructs real
    clients from env vars.
    """

    def __init__(
        self,
        roles: dict[str, RoleConfig],
        clients: dict[str, LLMProviderClient],
        *,
        max_retries: int = 3,
        backoff_base_seconds: float = 0.5,
        backoff_multiplier: float = 2.0,
        backoff_max_seconds: float = 20.0,
        pricing: Optional[dict[str, dict[str, dict[str, float]]]] = None,
        sleep_fn: Callable[[float], None] = time.sleep,
    ) -> None:
        self._roles = roles
        self._clients = clients
        self._max_retries = max_retries
        self._backoff_base = backoff_base_seconds
        self._backoff_mult = backoff_multiplier
        self._backoff_max = backoff_max_seconds
        # pricing[provider][model] = {"input": usd_per_million, "output": usd_per_million}
        self._pricing = pricing or {}
        self._sleep = sleep_fn
        self._usage_log: list[UsageRecord] = []
        self._logger = get_logger("sampark.llm")

    @classmethod
    def from_yaml(cls, path: str, clients: dict[str, LLMProviderClient]) -> "ModelManager":
        import yaml

        with open(path, "r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)

        defaults = data.get("defaults", {})
        roles: dict[str, RoleConfig] = {}
        for role_name, role_data in data.get("roles", {}).items():
            roles[role_name] = RoleConfig(
                provider=role_data["provider"],
                model=role_data["model"],
                max_tokens=role_data.get("max_tokens", 1024),
                fallback=role_data.get("fallback", []),
                max_retries=role_data.get("max_retries"),
            )

        pricing = data.get("pricing_usd_per_million_tokens", {})

        return cls(
            roles=roles,
            clients=clients,
            max_retries=defaults.get("max_retries", 3),
            backoff_base_seconds=defaults.get("backoff_base_seconds", 0.5),
            backoff_multiplier=defaults.get("backoff_multiplier", 2.0),
            backoff_max_seconds=defaults.get("backoff_max_seconds", 20.0),
            pricing=pricing,
        )

    def complete(
        self,
        role: str,
        *,
        system: Optional[str],
        messages: list[dict[str, str]],
        trace_id: str,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        """Tries the role's primary (provider, model), then each fallback
        entry in order, retrying each hop with exponential backoff up to
        max_retries before moving to the next fallback. Raises
        LLMProviderError if every hop in the chain is exhausted. Every
        attempt -- success or failure -- is recorded in the usage log."""
        if role not in self._roles:
            raise LLMProviderError(f"Unknown role: {role}", retryable=False)

        role_config = self._roles[role]
        max_retries = role_config.max_retries or self._max_retries
        hops = [{"provider": role_config.provider, "model": role_config.model}] + list(
            role_config.fallback
        )

        last_error: Optional[Exception] = None
        for hop_index, hop in enumerate(hops):
            provider_name = hop["provider"]
            model = hop["model"]
            client = self._clients.get(provider_name)
            if client is None:
                log_event(
                    self._logger,
                    "info",
                    "llm_hop_skipped_provider_unconfigured",
                    role=role,
                    provider=provider_name,
                    trace_id=trace_id,
                )
                continue

            for attempt in range(1, max_retries + 1):
                start = time.monotonic()
                try:
                    response = client.complete(
                        model=model,
                        system=system,
                        messages=messages,
                        max_tokens=role_config.max_tokens,
                        tools=tools,
                    )
                except LLMProviderError as exc:
                    last_error = exc
                    self._record_usage(
                        UsageRecord(
                            role=role,
                            provider=provider_name,
                            model=model,
                            input_tokens=0,
                            output_tokens=0,
                            cost_usd=0.0,
                            latency_ms=int((time.monotonic() - start) * 1000),
                            attempt=attempt,
                            fell_back=hop_index > 0,
                            trace_id=trace_id,
                        )
                    )
                    if not exc.retryable:
                        break
                    if attempt < max_retries:
                        delay = min(
                            self._backoff_base * (self._backoff_mult ** (attempt - 1)),
                            self._backoff_max,
                        )
                        if exc.retry_after_seconds is not None:
                            # A real per-minute quota wall (e.g. Gemini's
                            # free tier) needs the server's own guidance,
                            # not our fixed 0.5/1/2s schedule -- honor it
                            # even if it's longer than backoff_max.
                            delay = max(delay, exc.retry_after_seconds)
                        self._sleep(delay)
                    continue

                cost = self._cost_usd(
                    provider_name, model, response.input_tokens, response.output_tokens
                )
                self._record_usage(
                    UsageRecord(
                        role=role,
                        provider=provider_name,
                        model=model,
                        input_tokens=response.input_tokens,
                        output_tokens=response.output_tokens,
                        cost_usd=cost,
                        latency_ms=response.latency_ms,
                        attempt=attempt,
                        fell_back=hop_index > 0,
                        trace_id=trace_id,
                    )
                )
                return response

        raise LLMProviderError(
            f"All providers/models exhausted for role '{role}': {last_error}",
            retryable=False,
        )

    def usage_summary(self) -> dict[str, Any]:
        total_cost = sum(record.cost_usd for record in self._usage_log)
        total_input = sum(record.input_tokens for record in self._usage_log)
        total_output = sum(record.output_tokens for record in self._usage_log)

        by_role: dict[str, dict[str, Any]] = {}
        by_provider: dict[str, dict[str, Any]] = {}
        for record in self._usage_log:
            role_bucket = by_role.setdefault(
                record.role, {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}
            )
            role_bucket["cost_usd"] += record.cost_usd
            role_bucket["input_tokens"] += record.input_tokens
            role_bucket["output_tokens"] += record.output_tokens
            role_bucket["calls"] += 1

            provider_bucket = by_provider.setdefault(
                record.provider, {"cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0, "calls": 0}
            )
            provider_bucket["cost_usd"] += record.cost_usd
            provider_bucket["input_tokens"] += record.input_tokens
            provider_bucket["output_tokens"] += record.output_tokens
            provider_bucket["calls"] += 1

        return {
            "total_cost_usd": round(total_cost, 6),
            "total_input_tokens": total_input,
            "total_output_tokens": total_output,
            "total_calls": len(self._usage_log),
            "by_role": by_role,
            "by_provider": by_provider,
        }

    def _record_usage(self, record: UsageRecord) -> None:
        self._usage_log.append(record)
        log_event(self._logger, "info", "llm_call", **record.__dict__)

    def _cost_usd(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> float:
        rates = self._pricing.get(provider, {}).get(model)
        if not rates:
            return 0.0
        return (input_tokens / 1_000_000) * rates.get("input", 0.0) + (
            output_tokens / 1_000_000
        ) * rates.get("output", 0.0)
