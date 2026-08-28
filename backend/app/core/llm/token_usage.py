"""LLM token usage collection and estimated cost calculation."""

from __future__ import annotations

from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, AsyncIterator

from langchain_core.callbacks import BaseCallbackHandler


@dataclass
class ModelTokenUsage:
    """Aggregated token usage for one model inside one business run."""

    model: str
    provider: str | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: Decimal = Decimal("0")

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_key": self.model,
            "provider": self.provider,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
            "estimated_cost": str(self.estimated_cost),
        }


@dataclass
class TokenUsageCollector:
    """Collects usage only while an explicit context is active."""

    scene: str | None = None
    run_id: str | None = None
    models: dict[str, ModelTokenUsage] = field(default_factory=dict)

    def record(
        self,
        *,
        model: str,
        provider: str | None = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int | None = None,
        input_price: Decimal | float = Decimal("0"),
        output_price: Decimal | float = Decimal("0"),
    ) -> None:
        input_tokens = max(0, int(input_tokens or 0))
        output_tokens = max(0, int(output_tokens or 0))
        total_tokens = max(
            0,
            int(total_tokens)
            if total_tokens is not None
            else input_tokens + output_tokens,
        )
        model_usage = self.models.setdefault(
            model,
            ModelTokenUsage(model=model, provider=provider),
        )
        model_usage.input_tokens += input_tokens
        model_usage.output_tokens += output_tokens
        model_usage.total_tokens += total_tokens
        model_usage.estimated_cost += calculate_cost(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_price=input_price,
            output_price=output_price,
        )

    @property
    def input_tokens(self) -> int:
        return sum(item.input_tokens for item in self.models.values())

    @property
    def output_tokens(self) -> int:
        return sum(item.output_tokens for item in self.models.values())

    @property
    def total_tokens(self) -> int:
        return sum(item.total_tokens for item in self.models.values())

    @property
    def estimated_cost(self) -> Decimal:
        return sum((item.estimated_cost for item in self.models.values()), Decimal("0"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "currency": "CNY",
            "models": {
                item.model: item.as_dict() for item in self.models.values()
            },
        }


def calculate_cost(
    *,
    input_tokens: int,
    output_tokens: int,
    input_price: Decimal | float,
    output_price: Decimal | float,
) -> Decimal:
    """Calculate CNY cost from prices expressed as yuan per million tokens."""

    input_rate = Decimal(str(input_price or 0))
    output_rate = Decimal(str(output_price or 0))
    return (
        Decimal(max(0, int(input_tokens or 0))) * input_rate
        + Decimal(max(0, int(output_tokens or 0))) * output_rate
    ) / Decimal("1000000")


_active_collector: ContextVar[TokenUsageCollector | None] = ContextVar(
    "active_token_usage_collector",
    default=None,
)


def get_active_token_usage_collector() -> TokenUsageCollector | None:
    return _active_collector.get()


def summarize_token_usage(collector: TokenUsageCollector) -> dict[str, Any]:
    """Return nullable business-record fields plus per-model usage details."""

    if not collector.models:
        return {
            "input_tokens": None,
            "output_tokens": None,
            "total_tokens": None,
            "estimated_cost": None,
            "token_usage": None,
        }
    return {
        "input_tokens": collector.input_tokens,
        "output_tokens": collector.output_tokens,
        "total_tokens": collector.total_tokens,
        "estimated_cost": collector.estimated_cost,
        "token_usage": collector.as_dict(),
    }


@asynccontextmanager
async def token_usage_context(
    *,
    scene: str | None = None,
    run_id: str | None = None,
) -> AsyncIterator[TokenUsageCollector]:
    """Collect LLM usage for one business execution."""

    existing = _active_collector.get()
    if existing is not None:
        yield existing
        return

    collector = TokenUsageCollector(scene=scene, run_id=run_id)
    token = _active_collector.set(collector)
    try:
        yield collector
    finally:
        _active_collector.reset(token)


def _read_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _extract_usage(response: Any) -> tuple[int, int, int]:
    """Read usage from common LangChain/OpenAI-compatible response shapes."""

    candidates: list[dict[str, Any]] = []
    llm_output = getattr(response, "llm_output", None) or {}
    if isinstance(llm_output, dict):
        for key in ("token_usage", "usage"):
            value = llm_output.get(key)
            if isinstance(value, dict):
                candidates.append(value)

    for generation_group in getattr(response, "generations", None) or []:
        for generation in generation_group or []:
            message = getattr(generation, "message", None)
            for source in (
                getattr(message, "usage_metadata", None),
                getattr(message, "response_metadata", None),
                getattr(generation, "generation_info", None),
            ):
                if isinstance(source, dict):
                    candidates.append(source.get("token_usage", source))

    for usage in candidates:
        input_tokens = _read_int(usage.get("input_tokens", usage.get("prompt_tokens")))
        output_tokens = _read_int(
            usage.get("output_tokens", usage.get("completion_tokens"))
        )
        total_tokens = _read_int(usage.get("total_tokens"))
        if input_tokens or output_tokens or total_tokens:
            return input_tokens, output_tokens, total_tokens or input_tokens + output_tokens
    return 0, 0, 0


class TokenUsageCallbackHandler(BaseCallbackHandler):
    """LangChain callback that records usage when a collector is active."""

    def __init__(
        self,
        *,
        model: str,
        provider: str | None = None,
        input_price: Decimal | float = Decimal("0"),
        output_price: Decimal | float = Decimal("0"),
    ) -> None:
        super().__init__()
        self.model = model
        self.provider = provider
        self.input_price = input_price
        self.output_price = output_price

    def on_llm_end(self, response: Any, **_: Any) -> None:
        collector = get_active_token_usage_collector()
        if collector is None:
            return
        input_tokens, output_tokens, total_tokens = _extract_usage(response)
        if not (input_tokens or output_tokens or total_tokens):
            return
        collector.record(
            model=self.model,
            provider=self.provider,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
            input_price=self.input_price,
            output_price=self.output_price,
        )


__all__ = [
    "ModelTokenUsage",
    "TokenUsageCollector",
    "TokenUsageCallbackHandler",
    "calculate_cost",
    "get_active_token_usage_collector",
    "summarize_token_usage",
    "token_usage_context",
]
