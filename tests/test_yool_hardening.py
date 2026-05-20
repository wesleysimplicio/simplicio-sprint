"""Tests for yool runtime hardening: contracts, budgets, retries, cache, inspect (#98)."""

from __future__ import annotations

import time

import pytest

from sendsprint.yool.contracts import (
    BudgetEnforcer,
    BudgetEnforcerExceeded,
    ContractRegistry,
    ContractViolation,
    InputCache,
    InspectReport,
    RetryPolicy,
    RetryRecord,
    YoolContract,
    validate_payload,
)

# ---------------------------------------------------------------------------
# YoolContract
# ---------------------------------------------------------------------------


class TestYoolContract:
    def test_minimal_contract_defaults(self) -> None:
        c = YoolContract(yool_id="agent.codex.plan")
        assert c.input_schema == {"type": "object"}
        assert c.output_schema == {"type": "object"}
        assert c.timeout_s == 300
        assert c.cpu_quota_pct == 60
        assert c.disk_quota_mb == 100
        assert c.token_limit == 0
        assert c.max_retries == 0

    def test_has_budget_limits_true(self) -> None:
        c = YoolContract(yool_id="x", token_limit=1000)
        assert c.has_budget_limits() is True

    def test_has_budget_limits_all_zero(self) -> None:
        c = YoolContract(
            yool_id="x",
            token_limit=0,
            cost_limit_usd=0.0,
            timeout_s=0,
            cpu_quota_pct=0,
            disk_quota_mb=0,
        )
        assert c.has_budget_limits() is False

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValueError):  # ValidationError
            YoolContract(yool_id="x", unknown_field=True)

    def test_custom_schemas(self) -> None:
        c = YoolContract(
            yool_id="agent.dev.python",
            input_schema={
                "type": "object",
                "required": ["ticket"],
                "properties": {"ticket": {"type": "string"}},
            },
            output_schema={
                "type": "object",
                "properties": {"result": {"type": "string"}},
            },
        )
        assert "ticket" in c.input_schema.get("required", [])


# ---------------------------------------------------------------------------
# validate_payload
# ---------------------------------------------------------------------------


class TestValidatePayload:
    def test_valid_object(self) -> None:
        schema = {
            "type": "object",
            "required": ["name"],
            "properties": {"name": {"type": "string"}, "age": {"type": "integer"}},
        }
        assert validate_payload(schema, {"name": "alice", "age": 30}) == []

    def test_missing_required(self) -> None:
        schema = {"type": "object", "required": ["name"]}
        errors = validate_payload(schema, {"age": 30})
        assert len(errors) == 1
        assert "missing required field: name" in errors[0]

    def test_wrong_type_for_field(self) -> None:
        schema = {
            "type": "object",
            "properties": {"age": {"type": "integer"}},
        }
        errors = validate_payload(schema, {"age": "thirty"})
        assert len(errors) == 1
        assert "expected integer" in errors[0]

    def test_non_object_when_object_expected(self) -> None:
        schema = {"type": "object"}
        errors = validate_payload(schema, "not-an-object")
        assert len(errors) == 1

    def test_string_schema(self) -> None:
        assert validate_payload({"type": "string"}, "hello") == []
        assert len(validate_payload({"type": "string"}, 42)) == 1

    def test_integer_rejects_bool(self) -> None:
        errors = validate_payload({"type": "integer"}, True)
        assert len(errors) == 1

    def test_array_schema(self) -> None:
        assert validate_payload({"type": "array"}, [1, 2]) == []
        assert len(validate_payload({"type": "array"}, "nope")) == 1

    def test_empty_schema_passes_anything(self) -> None:
        assert validate_payload({}, {"any": "thing"}) == []


# ---------------------------------------------------------------------------
# BudgetEnforcer
# ---------------------------------------------------------------------------


class TestBudgetEnforcer:
    def test_unlimited_passes(self) -> None:
        be = BudgetEnforcer(
            token_limit=0, cost_limit_usd=0.0, timeout_s=0, cpu_quota_pct=0, disk_quota_mb=0
        )
        be.check_all(tokens=999999, cost_usd=999.0, wall_s=999.0, disk_mb=999.0)

    def test_token_limit_exceeded(self) -> None:
        be = BudgetEnforcer(token_limit=100)
        be.commit(tokens=90)
        with pytest.raises(BudgetEnforcerExceeded, match="tokens"):
            be.check_tokens(20)

    def test_cost_limit_exceeded(self) -> None:
        be = BudgetEnforcer(cost_limit_usd=1.0)
        be.commit(cost_usd=0.8)
        with pytest.raises(BudgetEnforcerExceeded, match="cost_usd"):
            be.check_cost(0.3)

    def test_timeout_exceeded(self) -> None:
        be = BudgetEnforcer(timeout_s=10)
        be.commit(wall_s=9.0)
        with pytest.raises(BudgetEnforcerExceeded, match="timeout_s"):
            be.check_timeout(2.0)

    def test_disk_exceeded(self) -> None:
        be = BudgetEnforcer(disk_quota_mb=50)
        be.commit(disk_mb=45.0)
        with pytest.raises(BudgetEnforcerExceeded, match="disk_mb"):
            be.check_disk(10.0)

    def test_check_all_raises_first_breach(self) -> None:
        be = BudgetEnforcer(token_limit=10, cost_limit_usd=0.5)
        with pytest.raises(BudgetEnforcerExceeded, match="tokens"):
            be.check_all(tokens=20)

    def test_remaining(self) -> None:
        be = BudgetEnforcer(
            token_limit=100, cost_limit_usd=1.0, timeout_s=0, cpu_quota_pct=0, disk_quota_mb=0
        )
        be.commit(tokens=40, cost_usd=0.3)
        rem = be.remaining()
        assert rem["tokens"] == 60
        assert abs(rem["cost_usd"] - 0.7) < 1e-9
        assert rem["timeout_s"] == float("inf")

    def test_from_contract(self) -> None:
        contract = YoolContract(
            yool_id="x",
            token_limit=500,
            cost_limit_usd=2.0,
            timeout_s=60,
            cpu_quota_pct=80,
            disk_quota_mb=200,
        )
        be = BudgetEnforcer.from_contract(contract)
        assert be.token_limit == 500
        assert be.cpu_quota_pct == 80

    def test_exception_attributes(self) -> None:
        exc = BudgetEnforcerExceeded("tokens", 150, 100)
        assert exc.dimension == "tokens"
        assert exc.used == 150
        assert exc.limit == 100


# ---------------------------------------------------------------------------
# RetryPolicy
# ---------------------------------------------------------------------------


class TestRetryPolicy:
    def test_default_retryable(self) -> None:
        rp = RetryPolicy()
        assert rp.is_retryable(TimeoutError("timeout"))
        assert rp.is_retryable(ConnectionError("conn"))
        assert rp.is_retryable(OSError("os"))
        assert not rp.is_retryable(ValueError("val"))

    def test_custom_retryable_errors(self) -> None:
        rp = RetryPolicy(retryable_errors=["ValueError", "KeyError"])
        assert rp.is_retryable(ValueError("v"))
        assert rp.is_retryable(KeyError("k"))
        assert not rp.is_retryable(TimeoutError("t"))

    def test_should_retry_respects_max(self) -> None:
        rp = RetryPolicy(max_retries=2)
        assert rp.should_retry(0, TimeoutError()) is True
        assert rp.should_retry(1, TimeoutError()) is True
        assert rp.should_retry(2, TimeoutError()) is False

    def test_should_retry_rejects_non_retryable(self) -> None:
        rp = RetryPolicy(max_retries=5)
        assert rp.should_retry(0, ValueError("nope")) is False

    def test_backoff_exponential(self) -> None:
        rp = RetryPolicy(backoff_base_s=1.0, backoff_factor=2.0, backoff_max_s=10.0)
        assert rp.delay_for_attempt(0) == 1.0
        assert rp.delay_for_attempt(1) == 2.0
        assert rp.delay_for_attempt(2) == 4.0
        assert rp.delay_for_attempt(3) == 8.0
        assert rp.delay_for_attempt(4) == 10.0  # capped

    def test_from_contract(self) -> None:
        contract = YoolContract(
            yool_id="x",
            max_retries=5,
            retryable_errors=["RuntimeError"],
        )
        rp = RetryPolicy.from_contract(contract)
        assert rp.max_retries == 5
        assert rp.retryable_errors == ["RuntimeError"]

    def test_from_contract_defaults_retryable(self) -> None:
        contract = YoolContract(yool_id="x", max_retries=2)
        rp = RetryPolicy.from_contract(contract)
        assert "TimeoutError" in rp.retryable_errors

    def test_mro_match(self) -> None:
        """Retry matches parent class names via MRO."""
        rp = RetryPolicy(retryable_errors=["OSError"])
        # ConnectionError is a subclass of OSError
        assert rp.is_retryable(ConnectionError("conn"))


# ---------------------------------------------------------------------------
# InputCache
# ---------------------------------------------------------------------------


class TestInputCache:
    def test_put_and_get_hit(self) -> None:
        cache = InputCache(ttl_s=60.0)
        cache.put("y.plan", {"task": 1}, {"result": "ok"})
        assert cache.get("y.plan", {"task": 1}) == {"result": "ok"}
        assert cache.total_hits == 1
        assert cache.total_misses == 0

    def test_miss(self) -> None:
        cache = InputCache()
        assert cache.get("y.plan", {"task": 2}) is None
        assert cache.total_misses == 1

    def test_different_payload_is_miss(self) -> None:
        cache = InputCache()
        cache.put("y.plan", {"task": 1}, "out1")
        assert cache.get("y.plan", {"task": 2}) is None

    def test_different_yool_is_miss(self) -> None:
        cache = InputCache()
        cache.put("y.plan", {"task": 1}, "out1")
        assert cache.get("y.review", {"task": 1}) is None

    def test_ttl_expiry(self) -> None:
        cache = InputCache(ttl_s=0.0)
        cache.put("y.plan", {"task": 1}, "out")
        # TTL=0 means immediate expiry on next access
        time.sleep(0.001)
        assert cache.get("y.plan", {"task": 1}) is None
        assert cache.total_misses == 1

    def test_invalidate(self) -> None:
        cache = InputCache()
        cache.put("y.plan", {"task": 1}, "out")
        assert cache.invalidate("y.plan", {"task": 1}) is True
        assert cache.get("y.plan", {"task": 1}) is None
        assert cache.invalidate("y.plan", {"task": 1}) is False

    def test_clear(self) -> None:
        cache = InputCache()
        cache.put("a", {}, "1")
        cache.put("b", {}, "2")
        assert cache.size == 2
        cache.clear()
        assert cache.size == 0

    def test_max_entries_evicts_oldest(self) -> None:
        cache = InputCache(ttl_s=60.0, max_entries=2)
        cache.put("a", {"n": 1}, "out1")
        cache.put("b", {"n": 2}, "out2")
        cache.put("c", {"n": 3}, "out3")
        # oldest ("a") should have been evicted
        assert cache.size == 2
        assert cache.get("a", {"n": 1}) is None

    def test_stats(self) -> None:
        cache = InputCache()
        cache.put("y", {"x": 1}, "out")
        cache.get("y", {"x": 1})  # hit
        cache.get("y", {"x": 2})  # miss
        stats = cache.stats()
        assert stats["total_hits"] == 1
        assert stats["total_misses"] == 1
        assert stats["hit_rate"] == 0.5
        assert stats["size"] == 1


# ---------------------------------------------------------------------------
# InspectReport
# ---------------------------------------------------------------------------


class TestInspectReport:
    def test_basic_report(self) -> None:
        report = InspectReport(
            yool_id="agent.codex.plan",
            run_id="run-1",
            total_cost_usd=0.25,
            total_tokens=500,
            total_wall_ms=1200,
            cache_hits=3,
            cache_misses=1,
            cache_hit_rate=0.75,
            budget_remaining={"tokens": 500, "cost_usd": 0.75},
        )
        assert report.yool_id == "agent.codex.plan"
        assert report.cache_hit_rate == 0.75
        assert report.status == "ok"
        assert report.contract_valid is True

    def test_report_with_retries(self) -> None:
        report = InspectReport(
            yool_id="x",
            retries=[
                RetryRecord(
                    attempt=0,
                    error_type="TimeoutError",
                    error_message="timed out",
                    delay_s=1.0,
                ),
                RetryRecord(
                    attempt=1,
                    error_type="TimeoutError",
                    error_message="timed out again",
                    delay_s=2.0,
                ),
            ],
            retry_count=2,
        )
        assert report.retry_count == 2
        assert len(report.retries) == 2

    def test_report_with_contract_errors(self) -> None:
        report = InspectReport(
            yool_id="x",
            contract_valid=False,
            contract_errors=["missing required field: ticket"],
        )
        assert report.contract_valid is False
        assert len(report.contract_errors) == 1


# ---------------------------------------------------------------------------
# ContractRegistry
# ---------------------------------------------------------------------------


class TestContractRegistry:
    def test_register_and_get(self) -> None:
        reg = ContractRegistry()
        c = YoolContract(yool_id="agent.codex.plan")
        reg.register(c)
        assert reg.get("agent.codex.plan") is not None
        assert reg.get("unknown") is None

    def test_require_raises_on_missing(self) -> None:
        reg = ContractRegistry()
        with pytest.raises(ContractViolation, match="no contract registered"):
            reg.require("missing.yool")

    def test_validate_input_pass(self) -> None:
        reg = ContractRegistry()
        reg.register(
            YoolContract(
                yool_id="x",
                input_schema={
                    "type": "object",
                    "required": ["ticket"],
                    "properties": {"ticket": {"type": "string"}},
                },
            )
        )
        assert reg.validate_input("x", {"ticket": "APP-1"}) == []

    def test_validate_input_fail(self) -> None:
        reg = ContractRegistry()
        reg.register(
            YoolContract(
                yool_id="x",
                input_schema={
                    "type": "object",
                    "required": ["ticket"],
                },
            )
        )
        errors = reg.validate_input("x", {"other": "stuff"})
        assert len(errors) == 1

    def test_validate_input_no_contract(self) -> None:
        reg = ContractRegistry()
        errors = reg.validate_input("unknown", {})
        assert len(errors) == 1
        assert "no contract" in errors[0]

    def test_validate_output(self) -> None:
        reg = ContractRegistry()
        reg.register(
            YoolContract(
                yool_id="x",
                output_schema={
                    "type": "object",
                    "required": ["result"],
                },
            )
        )
        assert reg.validate_output("x", {"result": "done"}) == []
        errors = reg.validate_output("x", {"wrong": "field"})
        assert len(errors) == 1

    def test_all_returns_copy(self) -> None:
        reg = ContractRegistry()
        reg.register(YoolContract(yool_id="a"))
        reg.register(YoolContract(yool_id="b"))
        all_contracts = reg.all()
        assert len(all_contracts) == 2
        assert "a" in all_contracts
        assert "b" in all_contracts


# ---------------------------------------------------------------------------
# ContractViolation
# ---------------------------------------------------------------------------


class TestContractViolation:
    def test_attributes(self) -> None:
        exc = ContractViolation("y.plan", "input", "missing field")
        assert exc.yool_id == "y.plan"
        assert exc.direction == "input"
        assert exc.reason == "missing field"
        assert "y.plan" in str(exc)
