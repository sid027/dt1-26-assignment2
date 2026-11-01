"""Cost and speed of the queries. A query is one request to the model; a turn has one or more.

The two averages of a turn are the KPIs of the assignment.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ModelCall:
    """One query: one request to the model."""

    input_tokens: int
    output_tokens: int
    cost: float  # USD
    seconds: float  # from sending the request until the complete answer arrived

    @property
    def tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    @property
    def speed(self) -> float:
        """Output tokens per second."""
        return self.output_tokens / self.seconds if self.seconds > 0 else 0.0


@dataclass
class Usage:
    """The queries of one turn, or of a whole conversation."""

    calls: list[ModelCall] = field(default_factory=list)

    @property
    def current(self) -> ModelCall | None:
        return self.calls[-1] if self.calls else None

    @property
    def tokens(self) -> int:
        return sum(call.tokens for call in self.calls)

    @property
    def cost(self) -> float:
        return sum(call.cost for call in self.calls)

    @property
    def average_cost(self) -> float:
        """KPI: the mean cost of the queries, in USD."""
        return self.cost / len(self.calls) if self.calls else 0.0

    @property
    def average_speed(self) -> float:
        """KPI: the mean of the speeds of the queries, in output tokens per second."""
        return sum(call.speed for call in self.calls) / len(self.calls) if self.calls else 0.0


class Pricing:
    """The model's price per token, from OpenRouter's public model list."""

    def __init__(self, llm: Any, model: str) -> None:
        self.input: float | None = None
        self.output: float | None = None
        try:
            for listed in llm.models.list():
                if listed.id == model:
                    prices = (listed.model_extra or {})["pricing"]
                    self.input, self.output = float(prices["prompt"]), float(prices["completion"])
                    break
        except Exception:
            pass  # the cost then comes only from what OpenRouter reports for each call

    def measure(self, usage: Any, seconds: float) -> ModelCall:
        input_tokens = getattr(usage, "prompt_tokens", 0) or 0
        output_tokens = getattr(usage, "completion_tokens", 0) or 0
        reported = (getattr(usage, "model_extra", None) or {}).get("cost")
        if reported is not None:
            cost = float(reported)  # exact: what OpenRouter charged for this call
        elif self.input is not None and self.output is not None:
            cost = input_tokens * self.input + output_tokens * self.output
        else:
            cost = 0.0
        return ModelCall(input_tokens, output_tokens, cost, seconds)
