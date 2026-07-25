"""Per-campaign LLM token accounting.

Token counts are the only spend figure we can state exactly — they come back on every API
response. Dollar cost is derived from them **only when the operator has configured their own
rates** (`LLM_COST_PER_MTOK_INPUT` / `_OUTPUT`); we never guess at pricing, because a
fabricated cost figure in a revenue report is worse than an absent one.

Scoped with a `ContextVar` so a campaign running in a background task accumulates its own
usage rather than sharing a global counter.
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import asdict, dataclass

from src.runtime_config import get_setting

TOKENS_PER_MILLION = 1_000_000


@dataclass
class Usage:
    """Token counts for one unit of work."""

    input_tokens: int = 0
    output_tokens: int = 0
    calls: int = 0

    def add(self, *, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.calls += 1

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


_current: ContextVar[Usage | None] = ContextVar("llm_usage", default=None)


def start() -> Usage:
    """Begin a fresh accounting scope and return its accumulator."""
    usage = Usage()
    _current.set(usage)
    return usage


def record(input_tokens: int, output_tokens: int) -> None:
    """Add one call's tokens to the active scope. A no-op outside any scope."""
    usage = _current.get()
    if usage is not None:
        usage.add(input_tokens=input_tokens, output_tokens=output_tokens)


def _rate(key: str) -> float | None:
    """Configured price per million tokens, or None when the operator has not set one."""
    raw = get_setting(key)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def estimate_cost(usage: Usage) -> float | None:
    """Dollar cost for `usage`, or None when rates are not configured.

    Returning None rather than 0.0 matters: zero would read as "this was free".
    """
    input_rate = _rate("LLM_COST_PER_MTOK_INPUT")
    output_rate = _rate("LLM_COST_PER_MTOK_OUTPUT")
    if input_rate is None and output_rate is None:
        return None
    cost = (usage.input_tokens / TOKENS_PER_MILLION) * (input_rate or 0.0) + (
        usage.output_tokens / TOKENS_PER_MILLION
    ) * (output_rate or 0.0)
    return round(cost, 6)


def snapshot() -> dict[str, object]:
    """Serialisable view of the active scope, including cost when it can be priced."""
    usage = _current.get() or Usage()
    return {
        **asdict(usage),
        "total_tokens": usage.total_tokens,
        "estimated_cost_usd": estimate_cost(usage),
    }


_COUNTERS = ("input_tokens", "output_tokens", "calls", "total_tokens")


def merge(previous: dict[str, object], current: dict[str, object]) -> dict[str, object]:
    """Sum two usage snapshots, so a re-run reports cumulative campaign spend.

    Cost stays None unless at least one side priced it — summing an unpriced snapshot as 0
    would understate the total and read as "partly free".
    """
    merged: dict[str, object] = {
        key: int(previous.get(key, 0) or 0) + int(current.get(key, 0) or 0) for key in _COUNTERS
    }
    costs = [
        side.get("estimated_cost_usd")
        for side in (previous, current)
        if side.get("estimated_cost_usd") is not None
    ]
    merged["estimated_cost_usd"] = round(sum(costs), 6) if costs else None
    return merged
