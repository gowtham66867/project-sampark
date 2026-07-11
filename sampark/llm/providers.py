from __future__ import annotations

import json
import re
import time
from typing import Any, Optional

from sampark.llm.model_manager import LLMProviderError, LLMResponse

_RETRY_DELAY_RE = re.compile(r"retryDelay['\"]?\s*:\s*['\"]?(\d+(?:\.\d+)?)s")


def _extract_retry_delay_seconds(error_text: str) -> Optional[float]:
    """Best-effort extraction of a server-suggested retry delay from a
    provider error's string representation (e.g. Gemini's structured
    RESOURCE_EXHAUSTED response embeds `'retryDelay': '5s'`). Returns None
    if no hint is found -- callers fall back to ModelManager's own
    exponential backoff schedule in that case."""
    match = _RETRY_DELAY_RE.search(error_text)
    return float(match.group(1)) if match else None

# Canonical, provider-neutral message shape used by ReasoningEngine and
# converted internally by each provider client:
#   {"role": "user", "content": "<text>"}
#   {"role": "assistant", "content": "<text>"}
#   {"role": "assistant", "tool_calls": [{"id":..., "name":..., "input": {...}}]}
#   {"role": "tool_result", "tool_use_id": "...", "name": "...", "content": <dict or str>}
# Keeping this provider-neutral (rather than leaking Anthropic's or
# Gemini's native wire format into ReasoningEngine) is what lets a single
# role fall over from Anthropic to Gemini mid-conversation -- including
# mid tool-use round-trip -- without ReasoningEngine knowing or caring
# which provider is actually handling a given hop.


def _classify_anthropic_error(exc: Exception) -> tuple[bool, Optional[float]]:
    """Returns (retryable, retry_after_seconds). Rate-limit responses carry
    a `retry-after` header the SDK exposes via exc.response -- honoring it
    is more reliable than a fixed backoff schedule."""
    import anthropic

    retryable = isinstance(
        exc,
        (
            anthropic.RateLimitError,
            anthropic.APIConnectionError,
            anthropic.APITimeoutError,
            anthropic.InternalServerError,
        ),
    )
    # Auth errors, bad requests, and permission errors are not retryable --
    # retrying them just wastes the backoff budget before falling back.
    retry_after = None
    if isinstance(exc, anthropic.RateLimitError):
        response = getattr(exc, "response", None)
        header_value = response.headers.get("retry-after") if response is not None else None
        if header_value:
            try:
                retry_after = float(header_value)
            except ValueError:
                retry_after = _extract_retry_delay_seconds(str(exc))
    return retryable, retry_after


def _to_anthropic_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    converted: list[dict[str, Any]] = []
    i = 0
    while i < len(messages):
        message = messages[i]
        role = message["role"]
        if role == "user":
            converted.append({"role": "user", "content": message["content"]})
            i += 1
        elif role == "assistant":
            tool_calls = message.get("tool_calls")
            if tool_calls:
                converted.append(
                    {
                        "role": "assistant",
                        "content": [
                            {"type": "tool_use", "id": tc["id"], "name": tc["name"], "input": tc["input"]}
                            for tc in tool_calls
                        ],
                    }
                )
            else:
                converted.append({"role": "assistant", "content": message.get("content", "")})
            i += 1
        elif role == "tool_result":
            blocks = []
            while i < len(messages) and messages[i]["role"] == "tool_result":
                turn = messages[i]
                content = turn["content"]
                blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": turn["tool_use_id"],
                        "content": content if isinstance(content, str) else json.dumps(content),
                    }
                )
                i += 1
            converted.append({"role": "user", "content": blocks})
        else:
            raise ValueError(f"Unknown message role: {role}")
    return converted


class AnthropicProviderClient:
    """Real Anthropic SDK client wrapper. Constructed only when
    ANTHROPIC_API_KEY is present -- see build_provider_clients() below.
    The `anthropic` package is imported here (module scope of this file,
    not of model_manager.py), so importing sampark.llm.model_manager or
    running its offline tests never requires the SDK to be installed.
    """

    provider_name = "anthropic"

    def __init__(self, api_key: str) -> None:
        import anthropic

        # max_retries=0: ModelManager owns all retry/backoff/fallback
        # decisions centrally so every attempt is visible in the usage log
        # and there is no double-backoff (SDK retrying internally, then
        # ModelManager retrying again on top).
        self._client = anthropic.Anthropic(api_key=api_key, max_retries=0)

    def complete(
        self,
        *,
        model: str,
        system: Optional[str],
        messages: list[dict[str, Any]],
        max_tokens: int,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        start = time.monotonic()
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": _to_anthropic_messages(messages),
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = tools

        try:
            response = self._client.messages.create(**kwargs)
        except Exception as exc:  # narrowed via anthropic's typed exceptions
            retryable, retry_after = _classify_anthropic_error(exc)
            raise LLMProviderError(str(exc), retryable=retryable, retry_after_seconds=retry_after) from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        tool_calls = [
            {"id": block.id, "name": block.name, "input": block.input}
            for block in response.content
            if getattr(block, "type", None) == "tool_use"
        ]
        return LLMResponse(
            text=text,
            provider=self.provider_name,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=latency_ms,
            raw=response.model_dump() if hasattr(response, "model_dump") else {},
            tool_calls=tool_calls,
        )


def _to_gemini_contents(messages: list[dict[str, Any]], types_module: Any) -> list[Any]:
    contents = []
    i = 0
    while i < len(messages):
        message = messages[i]
        role = message["role"]
        if role == "user":
            contents.append(
                types_module.Content(role="user", parts=[types_module.Part(text=message["content"])])
            )
            i += 1
        elif role == "assistant":
            tool_calls = message.get("tool_calls")
            if tool_calls:
                contents.append(
                    types_module.Content(
                        role="model",
                        parts=[
                            types_module.Part(
                                function_call=types_module.FunctionCall(name=tc["name"], args=tc["input"])
                            )
                            for tc in tool_calls
                        ],
                    )
                )
            else:
                contents.append(
                    types_module.Content(
                        role="model", parts=[types_module.Part(text=message.get("content", ""))]
                    )
                )
            i += 1
        elif role == "tool_result":
            parts = []
            while i < len(messages) and messages[i]["role"] == "tool_result":
                turn = messages[i]
                content = turn["content"]
                response_payload = content if isinstance(content, dict) else {"result": content}
                parts.append(
                    types_module.Part(
                        function_response=types_module.FunctionResponse(
                            name=turn["name"], response=response_payload
                        )
                    )
                )
                i += 1
            contents.append(types_module.Content(role="user", parts=parts))
        else:
            raise ValueError(f"Unknown message role: {role}")
    return contents


def _to_gemini_tools(tools: Optional[list[dict[str, Any]]], types_module: Any) -> Optional[list[Any]]:
    if not tools:
        return None
    return [
        types_module.Tool(
            function_declarations=[
                types_module.FunctionDeclaration(
                    name=tool["name"],
                    description=tool.get("description", ""),
                    parameters=tool["input_schema"],
                )
                for tool in tools
            ]
        )
    ]


class GeminiProviderClient:
    """Optional secondary (or, with no Anthropic key configured, primary)
    provider using Google's current `google-genai` SDK (the older
    `google-generativeai` package is end-of-life and intentionally not
    used here). Imported lazily inside __init__ so it is never a hard
    install requirement -- if GEMINI_API_KEY is unset, this class is
    simply never constructed and the import never happens."""

    provider_name = "gemini"

    def __init__(self, api_key: str) -> None:
        from google import genai

        self._client = genai.Client(api_key=api_key)

    def complete(
        self,
        *,
        model: str,
        system: Optional[str],
        messages: list[dict[str, Any]],
        max_tokens: int,
        tools: Optional[list[dict[str, Any]]] = None,
    ) -> LLMResponse:
        from google.genai import types

        start = time.monotonic()
        config_kwargs: dict[str, Any] = {"max_output_tokens": max_tokens}
        if system:
            config_kwargs["system_instruction"] = system
        gemini_tools = _to_gemini_tools(tools, types)
        if gemini_tools:
            config_kwargs["tools"] = gemini_tools

        try:
            response = self._client.models.generate_content(
                model=model,
                contents=_to_gemini_contents(messages, types),
                config=types.GenerateContentConfig(**config_kwargs),
            )
        except Exception as exc:
            # Gemini's RESOURCE_EXHAUSTED errors embed a structured
            # 'retryDelay': '5s' hint -- honoring it beats guessing against
            # a real per-minute free-tier quota wall.
            retry_after = _extract_retry_delay_seconds(str(exc))
            raise LLMProviderError(str(exc), retryable=True, retry_after_seconds=retry_after) from exc

        latency_ms = int((time.monotonic() - start) * 1000)
        text_parts: list[str] = []
        tool_calls: list[dict[str, Any]] = []
        if response.candidates:
            for index, part in enumerate(response.candidates[0].content.parts):
                if getattr(part, "text", None):
                    text_parts.append(part.text)
                function_call = getattr(part, "function_call", None)
                if function_call is not None:
                    tool_calls.append(
                        {
                            "id": f"gemini-call-{index}",
                            "name": function_call.name,
                            "input": dict(function_call.args or {}),
                        }
                    )

        usage = response.usage_metadata
        # Gemini 2.5's "thinking" tokens are billed as output tokens but
        # reported in a separate counter from candidates_token_count --
        # both must be summed for accurate cost tracking.
        output_tokens = (getattr(usage, "candidates_token_count", 0) or 0) + (
            getattr(usage, "thoughts_token_count", 0) or 0
        )
        return LLMResponse(
            text="".join(text_parts),
            provider=self.provider_name,
            model=model,
            input_tokens=getattr(usage, "prompt_token_count", 0) or 0,
            output_tokens=output_tokens,
            latency_ms=latency_ms,
            tool_calls=tool_calls,
        )


def build_provider_clients() -> dict[str, Any]:
    """Reads ANTHROPIC_API_KEY / GEMINI_API_KEY from os.environ and builds
    only the clients that have credentials. A missing GEMINI_API_KEY simply
    means the "gemini" key is absent from the returned dict -- ModelManager
    treats a missing provider client as "skip this fallback hop", not as an
    error. See sampark.llm.factory.build_default_reasoning_engine for how
    an empty dict (no provider configured at all) is turned into "LLM
    unavailable" rather than a silent rule-based-only fallback."""
    import os

    clients: dict[str, Any] = {}
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    if anthropic_key:
        clients["anthropic"] = AnthropicProviderClient(anthropic_key)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        clients["gemini"] = GeminiProviderClient(gemini_key)
    return clients
