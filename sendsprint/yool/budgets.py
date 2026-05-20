"""``agent_terms`` budget enforcement (spec §10, issue #87)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from .receipts import ReceiptCost
from .tuples import AgentTerms


class BudgetExceeded(RuntimeError):
    """Raised when a worker's external call would breach ``agent_terms``."""

    def __init__(self, dimension: str, used: float, limit: float) -> None:
        super().__init__(f"budget exceeded on {dimension}: used={used} limit={limit}")
        self.dimension = dimension
        self.used = used
        self.limit = limit


@dataclass
class BudgetGuard:
    """Tracks one tuple's cumulative usage against its ``agent_terms``."""

    terms: AgentTerms
    tokens_used: int = 0
    wall_ms_used: int = 0
    usd_used: float = 0.0

    def check(self, *, tokens: int = 0, wall_ms: int = 0, usd: float = 0.0) -> None:
        next_tokens = self.tokens_used + tokens
        next_wall = self.wall_ms_used + wall_ms
        next_usd = self.usd_used + usd
        if self.terms.max_tokens and next_tokens > self.terms.max_tokens:
            raise BudgetExceeded("tokens", next_tokens, self.terms.max_tokens)
        if self.terms.max_wall_ms and next_wall > self.terms.max_wall_ms:
            raise BudgetExceeded("wall_ms", next_wall, self.terms.max_wall_ms)
        if self.terms.max_cost_usd and next_usd > self.terms.max_cost_usd:
            raise BudgetExceeded("cost_usd", next_usd, self.terms.max_cost_usd)

    def commit(self, *, tokens: int = 0, wall_ms: int = 0, usd: float = 0.0) -> None:
        self.tokens_used += tokens
        self.wall_ms_used += wall_ms
        self.usd_used += usd

    def remaining(self) -> dict[str, float]:
        return {
            "tokens": max(0, self.terms.max_tokens - self.tokens_used)
            if self.terms.max_tokens
            else float("inf"),
            "wall_ms": max(0, self.terms.max_wall_ms - self.wall_ms_used)
            if self.terms.max_wall_ms
            else float("inf"),
            "usd": max(0.0, self.terms.max_cost_usd - self.usd_used)
            if self.terms.max_cost_usd
            else float("inf"),
        }


class BudgetLedger:
    """Aggregates cost per-yool across a whole sprint run."""

    def __init__(self) -> None:
        self._per_yool: dict[str, ReceiptCost] = defaultdict(ReceiptCost)

    def record(self, yool_id: str, cost: ReceiptCost) -> None:
        cur = self._per_yool[yool_id]
        cur.tokens_in += cost.tokens_in
        cur.tokens_out += cost.tokens_out
        cur.wall_ms += cost.wall_ms
        cur.usd += cost.usd

    def per_yool(self) -> dict[str, ReceiptCost]:
        return dict(self._per_yool)

    def total(self) -> ReceiptCost:
        total = ReceiptCost()
        for cost in self._per_yool.values():
            total.tokens_in += cost.tokens_in
            total.tokens_out += cost.tokens_out
            total.wall_ms += cost.wall_ms
            total.usd += cost.usd
        return total

    def to_dict(self) -> dict[str, Any]:
        return {
            "per_yool": {k: v.to_dict() for k, v in self._per_yool.items()},
            "total": self.total().to_dict(),
        }
