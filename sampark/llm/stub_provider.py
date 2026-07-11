from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sampark.llm.model_manager import LLMResponse


@dataclass
class StubProviderClient:
    """Fake LLMProviderClient for offline tests. `script` is a list of
    canned LLMResponse | Exception objects consumed in order across
    successive .complete() calls; when exhausted, the last entry repeats.
    A hostile/hallucinating test can inject an LLMResponse whose .text
    claims a blocked action is safe -- see
    tests/test_guardrails_cannot_be_bypassed_by_llm.py, which uses exactly
    this to prove verify_before_submit still wins regardless.
    """

    provider_name: str = "stub"
    script: list[Any] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    _index: int = 0

    def complete(
        self,
        *,
        model: str,
        system: Optional[str],
        messages: list[dict[str, str]],
        max_tokens: int,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        self.calls.append(
            {"model": model, "system": system, "messages": messages, "tools": tools}
        )
        if not self.script:
            return LLMResponse(
                text="stub response",
                provider=self.provider_name,
                model=model,
                input_tokens=10,
                output_tokens=10,
                latency_ms=1,
            )
        item = self.script[min(self._index, len(self.script) - 1)]
        self._index += 1
        if isinstance(item, Exception):
            raise item
        return item
