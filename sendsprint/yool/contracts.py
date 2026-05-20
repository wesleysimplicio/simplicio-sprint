"""Yool runtime contracts, budgets, retries, cache, and inspect (issue #98).

Pydantic models for hardened yool execution:
- ``YoolContract``: input/output schema + budget constraints per yool.
- ``BudgetEnforcer``: multi-dimension budget enforcement (tokens, cost, time, CPU, disk).
- ``RetryPolicy``: selective retry by error type with backoff.
- ``InputCache``: hash-based in-memory cache with TTL.
- ``InspectReport``: enriched inspect with cost, cache, retry info.
"""

from __future__ import annotations

import hashlib
import json
import time
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# YoolContract
# ---------------------------------------------------------------------------

class YoolContract(BaseModel):
    """Declares expected input/output schema and budget limits for a yool."""

    model_config = ConfigDict(extra="forbid")

    yool_id: str
    input_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object"},
        description="JSON Schema for valid input payloads.",
    )
    output_schema: dict[str, Any] = Field(
        default_factory=lambda: {"type": "object"},
        description="JSON Schema for expected output payloads.",
    )
    # Budget constraints (0 = unlimited)
    token_limit: int = Field(default=0, ge=0)
    cost_limit_usd: float = Field(default=0.0, ge=0.0)
    timeout_s: int = Field(default=300, ge=0)
    cpu_quota_pct: int = Field(default=60, ge=0, le=100)
    disk_quota_mb: int = Field(default=100, ge=0)
    # Retry
    max_retries: int = Field(default=0, ge=0)
    retryable_errors: list[str] = Field(default_factory=list)

    def has_budget_limits(self) -> bool:
        return any([
            self.token_limit > 0,
            self.cost_limit_usd > 0.0,
            self.timeout_s > 0,
            self.cpu_quota_pct > 0,
            self.disk_quota_mb > 0,
        ])


class ContractViolation(ValueError):
    """Raised when a yool payload violates its contract schema."""

    def __init__(self, yool_id: str, direction: str, reason: str) -> None:
        super().__init__(f"contract violation on {yool_id} ({direction}): {reason}")
        self.yool_id = yool_id
        self.direction = direction
        self.reason = reason


def validate_payload(schema: dict[str, Any], payload: Any) -> list[str]:
    """Minimal JSON-Schema-like validator (no external deps).

    Checks ``type``, ``required``, and ``properties`` keys only.
    Returns a list of error strings (empty = valid).
    """
    errors: list[str] = []
    expected_type = schema.get("type")
    if expected_type == "object":
        if not isinstance(payload, dict):
            errors.append(f"expected object, got {type(payload).__name__}")
            return errors
        for req in schema.get("required", []):
            if req not in payload:
                errors.append(f"missing required field: {req}")
        props = schema.get("properties", {})
        for key, prop_schema in props.items():
            if key in payload:
                prop_type = prop_schema.get("type")
                if prop_type and not _type_matches(prop_type, payload[key]):
                    errors.append(
                        f"field '{key}': expected {prop_type}, "
                        f"got {type(payload[key]).__name__}"
                    )
    elif expected_type == "string":
        if not isinstance(payload, str):
            errors.append(f"expected string, got {type(payload).__name__}")
    elif expected_type == "integer":
        if not isinstance(payload, int) or isinstance(payload, bool):
            errors.append(f"expected integer, got {type(payload).__name__}")
    elif expected_type == "number":
        if not isinstance(payload, (int, float)) or isinstance(payload, bool):
            errors.append(f"expected number, got {type(payload).__name__}")
    elif expected_type == "array":
        if not isinstance(payload, list):
            errors.append(f"expected array, got {type(payload).__name__}")
    elif expected_type == "boolean":
        if not isinstance(payload, bool):
            errors.append(f"expected boolean, got {type(payload).__name__}")
    return errors


def _type_matches(json_type: str, value: Any) -> bool:
    mapping: dict[str, type | tuple[type, ...]] = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    expected = mapping.get(json_type)
    if expected is None:
        return True  # unknown type, allow
    if json_type in ("integer", "number") and isinstance(value, bool):
        return False
    return isinstance(value, expected)


# ---------------------------------------------------------------------------
# BudgetEnforcer
# ---------------------------------------------------------------------------

class BudgetEnforcer(BaseModel):
    """Multi-dimension budget enforcement for a single dispatch."""

    model_config = ConfigDict(extra="forbid")

    token_limit: int = Field(default=0, ge=0)
    cost_limit_usd: float = Field(default=0.0, ge=0.0)
    timeout_s: int = Field(default=300, ge=0)
    cpu_quota_pct: int = Field(default=60, ge=0, le=100)
    disk_quota_mb: int = Field(default=100, ge=0)

    # Accumulators (mutable)
    tokens_used: int = 0
    cost_used_usd: float = 0.0
    wall_s_used: float = 0.0
    disk_mb_used: float = 0.0

    def check_tokens(self, additional: int = 0) -> None:
        if self.token_limit > 0 and (self.tokens_used + additional) > self.token_limit:
            raise BudgetEnforcerExceeded(
                "tokens", self.tokens_used + additional, self.token_limit
            )

    def check_cost(self, additional: float = 0.0) -> None:
        if self.cost_limit_usd > 0.0 and (self.cost_used_usd + additional) > self.cost_limit_usd:
            raise BudgetEnforcerExceeded(
                "cost_usd", self.cost_used_usd + additional, self.cost_limit_usd
            )

    def check_timeout(self, additional: float = 0.0) -> None:
        if self.timeout_s > 0 and (self.wall_s_used + additional) > self.timeout_s:
            raise BudgetEnforcerExceeded(
                "timeout_s", self.wall_s_used + additional, self.timeout_s
            )

    def check_disk(self, additional: float = 0.0) -> None:
        if self.disk_quota_mb > 0 and (self.disk_mb_used + additional) > self.disk_quota_mb:
            raise BudgetEnforcerExceeded(
                "disk_mb", self.disk_mb_used + additional, self.disk_quota_mb
            )

    def check_all(
        self,
        *,
        tokens: int = 0,
        cost_usd: float = 0.0,
        wall_s: float = 0.0,
        disk_mb: float = 0.0,
    ) -> None:
        self.check_tokens(tokens)
        self.check_cost(cost_usd)
        self.check_timeout(wall_s)
        self.check_disk(disk_mb)

    def commit(
        self,
        *,
        tokens: int = 0,
        cost_usd: float = 0.0,
        wall_s: float = 0.0,
        disk_mb: float = 0.0,
    ) -> None:
        self.tokens_used += tokens
        self.cost_used_usd += cost_usd
        self.wall_s_used += wall_s
        self.disk_mb_used += disk_mb

    def remaining(self) -> dict[str, float]:
        return {
            "tokens": max(0, self.token_limit - self.tokens_used)
            if self.token_limit > 0
            else float("inf"),
            "cost_usd": max(0.0, self.cost_limit_usd - self.cost_used_usd)
            if self.cost_limit_usd > 0.0
            else float("inf"),
            "timeout_s": max(0.0, self.timeout_s - self.wall_s_used)
            if self.timeout_s > 0
            else float("inf"),
            "disk_mb": max(0.0, self.disk_quota_mb - self.disk_mb_used)
            if self.disk_quota_mb > 0
            else float("inf"),
        }

    @classmethod
    def from_contract(cls, contract: YoolContract) -> BudgetEnforcer:
        return cls(
            token_limit=contract.token_limit,
            cost_limit_usd=contract.cost_limit_usd,
            timeout_s=contract.timeout_s,
            cpu_quota_pct=contract.cpu_quota_pct,
            disk_quota_mb=contract.disk_quota_mb,
        )


class BudgetEnforcerExceeded(RuntimeError):
    """Raised when a BudgetEnforcer dimension is breached."""

    def __init__(self, dimension: str, used: float, limit: float) -> None:
        super().__init__(
            f"budget enforcer exceeded on {dimension}: used={used} limit={limit}"
        )
        self.dimension = dimension
        self.used = used
        self.limit = limit


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------

class RetryPolicy(BaseModel):
    """Selective retry with exponential backoff."""

    model_config = ConfigDict(extra="forbid")

    max_retries: int = Field(default=3, ge=0)
    retryable_errors: list[str] = Field(
        default_factory=lambda: ["TimeoutError", "ConnectionError", "OSError"],
        description="Error class names eligible for retry.",
    )
    backoff_base_s: float = Field(default=1.0, ge=0.0)
    backoff_factor: float = Field(default=2.0, ge=1.0)
    backoff_max_s: float = Field(default=60.0, ge=0.0)

    def is_retryable(self, exc: BaseException) -> bool:
        for pattern in self.retryable_errors:
            for cls in type(exc).__mro__:
                if cls.__name__ == pattern:
                    return True
        return False

    def delay_for_attempt(self, attempt: int) -> float:
        """Compute backoff delay in seconds for the given attempt (0-indexed)."""
        delay = self.backoff_base_s * (self.backoff_factor ** attempt)
        return min(delay, self.backoff_max_s)

    def should_retry(self, attempt: int, exc: BaseException) -> bool:
        """True if we should retry: attempt < max_retries AND error is retryable."""
        if attempt >= self.max_retries:
            return False
        return self.is_retryable(exc)

    @classmethod
    def from_contract(cls, contract: YoolContract) -> RetryPolicy:
        return cls(
            max_retries=contract.max_retries,
            retryable_errors=contract.retryable_errors
            if contract.retryable_errors
            else ["TimeoutError", "ConnectionError", "OSError"],
        )


# ---------------------------------------------------------------------------
# InputCache
# ---------------------------------------------------------------------------

class CacheEntry(BaseModel):
    """One cached result."""

    model_config = ConfigDict(extra="forbid")

    input_hash: str
    output: Any = None
    created_at: float = Field(default_factory=time.monotonic)
    hits: int = 0


class InputCache:
    """Hash-based in-memory cache with TTL.

    Keys are ``sha256(canonical(yool_id + payload))``. Expired entries are
    evicted lazily on access.
    """

    def __init__(self, ttl_s: float = 300.0, max_entries: int = 1024) -> None:
        self.ttl_s = ttl_s
        self.max_entries = max_entries
        self._store: dict[str, CacheEntry] = {}
        self._total_hits: int = 0
        self._total_misses: int = 0

    @staticmethod
    def _make_key(yool_id: str, payload: Any) -> str:
        text = json.dumps(
            {"yool_id": yool_id, "payload": payload},
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        )
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def get(self, yool_id: str, payload: Any) -> Any | None:
        key = self._make_key(yool_id, payload)
        entry = self._store.get(key)
        if entry is None:
            self._total_misses += 1
            return None
        if (time.monotonic() - entry.created_at) > self.ttl_s:
            del self._store[key]
            self._total_misses += 1
            return None
        entry.hits += 1
        self._total_hits += 1
        return entry.output

    def put(self, yool_id: str, payload: Any, output: Any) -> None:
        key = self._make_key(yool_id, payload)
        if len(self._store) >= self.max_entries and key not in self._store:
            self._evict_oldest()
        self._store[key] = CacheEntry(
            input_hash=key,
            output=output,
            created_at=time.monotonic(),
        )

    def invalidate(self, yool_id: str, payload: Any) -> bool:
        key = self._make_key(yool_id, payload)
        if key in self._store:
            del self._store[key]
            return True
        return False

    def clear(self) -> None:
        self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)

    @property
    def total_hits(self) -> int:
        return self._total_hits

    @property
    def total_misses(self) -> int:
        return self._total_misses

    def stats(self) -> dict[str, int | float]:
        return {
            "size": self.size,
            "total_hits": self._total_hits,
            "total_misses": self._total_misses,
            "hit_rate": (
                self._total_hits / (self._total_hits + self._total_misses)
                if (self._total_hits + self._total_misses) > 0
                else 0.0
            ),
        }

    def _evict_oldest(self) -> None:
        if not self._store:
            return
        oldest_key = min(self._store, key=lambda k: self._store[k].created_at)
        del self._store[oldest_key]


# ---------------------------------------------------------------------------
# InspectReport
# ---------------------------------------------------------------------------

class RetryRecord(BaseModel):
    """One retry attempt record."""

    model_config = ConfigDict(extra="forbid")

    attempt: int
    error_type: str
    error_message: str
    delay_s: float


class InspectReport(BaseModel):
    """Enriched inspect output with cost, cache, retry info."""

    model_config = ConfigDict(extra="forbid")

    yool_id: str
    run_id: str = ""
    total_cost_usd: float = 0.0
    total_tokens: int = 0
    total_wall_ms: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    cache_hit_rate: float = 0.0
    retries: list[RetryRecord] = Field(default_factory=list)
    retry_count: int = 0
    budget_remaining: dict[str, float] = Field(default_factory=dict)
    status: str = "ok"
    contract_valid: bool = True
    contract_errors: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Contract registry helper
# ---------------------------------------------------------------------------

class ContractRegistry:
    """In-memory registry of YoolContract by yool_id."""

    def __init__(self) -> None:
        self._contracts: dict[str, YoolContract] = {}

    def register(self, contract: YoolContract) -> None:
        self._contracts[contract.yool_id] = contract

    def get(self, yool_id: str) -> YoolContract | None:
        return self._contracts.get(yool_id)

    def require(self, yool_id: str) -> YoolContract:
        contract = self.get(yool_id)
        if contract is None:
            raise ContractViolation(
                yool_id, "registry", f"no contract registered for {yool_id}"
            )
        return contract

    def validate_input(self, yool_id: str, payload: Any) -> list[str]:
        contract = self.get(yool_id)
        if contract is None:
            return [f"no contract registered for {yool_id}"]
        return validate_payload(contract.input_schema, payload)

    def validate_output(self, yool_id: str, payload: Any) -> list[str]:
        contract = self.get(yool_id)
        if contract is None:
            return [f"no contract registered for {yool_id}"]
        return validate_payload(contract.output_schema, payload)

    def all(self) -> dict[str, YoolContract]:
        return dict(self._contracts)
