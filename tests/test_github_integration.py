"""Tests for github_integration: duplicate detection, progress comments, CI monitoring, reviews.

All tests use mocked httpx transports -- zero network calls.
"""

from __future__ import annotations

from typing import Any

import httpx

from sendsprint.github_integration import (
    CIMonitor,
    CIStatus,
    DuplicateDetector,
    DuplicateResult,
    ProgressReporter,
    ReviewFeedback,
    ReviewReader,
)

REPO = "acme/widgets"


# ---------------------------------------------------------------------------
# httpx mock transport helper
# ---------------------------------------------------------------------------


class _MockTransport(httpx.BaseTransport):
    """Return canned JSON for any request, recording calls for assertions."""

    def __init__(self, responses: list[dict[str, Any]] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.calls.append(request)
        payload = self._responses.pop(0) if self._responses else {}
        return httpx.Response(200, json=payload)


def _client(responses: list[dict[str, Any]] | None = None) -> tuple[httpx.Client, _MockTransport]:
    transport = _MockTransport(responses)
    client = httpx.Client(transport=transport, base_url="https://api.github.com")
    return client, transport


# ---------------------------------------------------------------------------
# DuplicateDetector
# ---------------------------------------------------------------------------


class TestDuplicateDetector:
    def test_check_duplicate_issues_returns_items(self) -> None:
        items = [{"number": 10, "title": "Add widget"}]
        c, t = _client([{"total_count": 1, "items": items}])
        result = DuplicateDetector(REPO, client=c).check_duplicate_issues("Add widget")
        assert result == items
        assert "/search/issues" in str(t.calls[0].url)
        assert "is%3Aissue" in str(t.calls[0].url)

    def test_check_duplicate_issues_empty(self) -> None:
        c, _ = _client([{"total_count": 0, "items": []}])
        assert DuplicateDetector(REPO, client=c).check_duplicate_issues("nonexistent") == []

    def test_check_duplicate_prs_returns_items(self) -> None:
        items = [{"number": 22, "title": "fix: widget crash"}]
        c, t = _client([{"total_count": 1, "items": items}])
        result = DuplicateDetector(REPO, client=c).check_duplicate_prs("fix: widget crash")
        assert result == items
        assert "is%3Apr" in str(t.calls[0].url)

    def test_check_duplicate_prs_empty(self) -> None:
        c, _ = _client([{"total_count": 0, "items": []}])
        assert DuplicateDetector(REPO, client=c).check_duplicate_prs("nope") == []

    def test_check_concurrent_work_finds_matching_branch(self) -> None:
        prs = [
            {"number": 5, "head": {"ref": "feat/widget"}, "title": "feat: widget"},
            {"number": 6, "head": {"ref": "fix/other"}, "title": "fix: other"},
        ]
        c, _ = _client([prs])
        result = DuplicateDetector(REPO, client=c).check_concurrent_work("feat/widget")
        assert result.has_concurrent_work
        assert len(result.concurrent_prs) == 1
        assert result.concurrent_prs[0]["number"] == 5

    def test_check_concurrent_work_none_found(self) -> None:
        c, _ = _client([[]])
        result = DuplicateDetector(REPO, client=c).check_concurrent_work("feat/new")
        assert not result.has_concurrent_work
        assert result.concurrent_prs == []

    def test_check_duplicate_issues_respects_state_param(self) -> None:
        c, t = _client([{"total_count": 0, "items": []}])
        DuplicateDetector(REPO, client=c).check_duplicate_issues("test", state="closed")
        assert "is%3Aclosed" in str(t.calls[0].url)


# ---------------------------------------------------------------------------
# DuplicateResult dataclass
# ---------------------------------------------------------------------------


class TestDuplicateResult:
    def test_has_duplicates_true(self) -> None:
        r = DuplicateResult(duplicates=[{"number": 1}])
        assert r.has_duplicates

    def test_has_duplicates_false(self) -> None:
        assert not DuplicateResult().has_duplicates

    def test_has_concurrent_work_true(self) -> None:
        r = DuplicateResult(concurrent_prs=[{"number": 2}])
        assert r.has_concurrent_work

    def test_has_concurrent_work_false(self) -> None:
        assert not DuplicateResult().has_concurrent_work


# ---------------------------------------------------------------------------
# CIStatus dataclass
# ---------------------------------------------------------------------------


class TestCIStatus:
    def test_is_green(self) -> None:
        assert CIStatus(state="success").is_green
        assert not CIStatus(state="pending").is_green

    def test_is_red(self) -> None:
        assert CIStatus(state="failure").is_red
        assert CIStatus(state="error").is_red
        assert not CIStatus(state="pending").is_red
        assert not CIStatus(state="success").is_red


# ---------------------------------------------------------------------------
# ProgressReporter
# ---------------------------------------------------------------------------


class TestProgressReporter:
    def test_post_progress_comment(self) -> None:
        c, t = _client([{"id": 999, "body": "hello"}])
        result = ProgressReporter(REPO, client=c).post_progress_comment(7, "hello")
        assert result["id"] == 999
        req = t.calls[0]
        assert req.method == "POST"
        assert f"/repos/{REPO}/issues/7/comments" in str(req.url)

    def test_attach_evidence_summary_with_steps_and_artifacts(self) -> None:
        c, t = _client([{"id": 1000, "body": "..."}])
        result = ProgressReporter(REPO, client=c).attach_evidence_summary(
            10,
            steps_completed=["lint", "test"],
            artifacts=["coverage.xml"],
            status="done",
        )
        assert result["id"] == 1000
        # Verify the body was structured
        import json

        body = json.loads(t.calls[0].content)["body"]
        assert "## SendSprint Progress (done)" in body
        assert "- [x] lint" in body
        assert "- [x] test" in body
        assert "- coverage.xml" in body

    def test_attach_evidence_summary_minimal(self) -> None:
        c, t = _client([{"id": 1001, "body": "..."}])
        ProgressReporter(REPO, client=c).attach_evidence_summary(11)
        import json

        body = json.loads(t.calls[0].content)["body"]
        assert "## SendSprint Progress (in_progress)" in body


# ---------------------------------------------------------------------------
# CIMonitor
# ---------------------------------------------------------------------------


class TestCIMonitor:
    def test_check_ci_status_success(self) -> None:
        payload = {
            "state": "success",
            "statuses": [
                {"state": "success", "context": "ci/test"},
                {"state": "success", "context": "ci/lint"},
            ],
        }
        c, _ = _client([payload])
        status = CIMonitor(REPO, client=c).check_ci_status("abc123")
        assert status.is_green
        assert status.total == 2
        assert status.passed == 2
        assert status.failed == 0
        assert status.pending == 0

    def test_check_ci_status_failure(self) -> None:
        payload = {
            "state": "failure",
            "statuses": [
                {"state": "success", "context": "ci/lint"},
                {"state": "failure", "context": "ci/test"},
            ],
        }
        c, _ = _client([payload])
        status = CIMonitor(REPO, client=c).check_ci_status("def456")
        assert status.is_red
        assert status.passed == 1
        assert status.failed == 1

    def test_check_ci_status_pending(self) -> None:
        payload = {"state": "pending", "statuses": [{"state": "pending", "context": "ci/build"}]}
        c, _ = _client([payload])
        status = CIMonitor(REPO, client=c).check_ci_status("ghi789")
        assert not status.is_green
        assert not status.is_red
        assert status.pending == 1

    def test_check_ci_status_empty(self) -> None:
        c, _ = _client([{"state": "pending", "statuses": []}])
        status = CIMonitor(REPO, client=c).check_ci_status("empty")
        assert status.total == 0

    def test_wait_for_ci_returns_immediately_on_success(self) -> None:
        payload = {"state": "success", "statuses": [{"state": "success", "context": "ci"}]}
        c, _ = _client([payload])
        sleeps: list[float] = []
        status = CIMonitor(REPO, client=c, sleep_fn=sleeps.append).wait_for_ci("abc")
        assert status.is_green
        assert sleeps == []  # no sleep needed

    def test_wait_for_ci_polls_then_succeeds(self) -> None:
        pending = {"state": "pending", "statuses": [{"state": "pending", "context": "ci"}]}
        success = {"state": "success", "statuses": [{"state": "success", "context": "ci"}]}
        c, _ = _client([pending, success])
        sleeps: list[float] = []
        status = CIMonitor(REPO, client=c, sleep_fn=sleeps.append).wait_for_ci(
            "abc",
            poll_interval_s=5,
        )
        assert status.is_green
        assert len(sleeps) == 1
        assert sleeps[0] == 5

    def test_wait_for_ci_timeout(self) -> None:
        """When CI stays pending past timeout, return last status."""
        pending = {"state": "pending", "statuses": [{"state": "pending", "context": "ci"}]}
        # Provide enough responses for multiple polls
        c, _ = _client([pending, pending, pending, pending, pending])
        status = CIMonitor(REPO, client=c, sleep_fn=lambda _: None).wait_for_ci(
            "abc",
            timeout_s=0,
            poll_interval_s=1,
        )
        assert not status.is_green
        assert status.state == "pending"


# ---------------------------------------------------------------------------
# ReviewReader
# ---------------------------------------------------------------------------


class TestReviewReader:
    def test_read_reviews(self) -> None:
        reviews = [{"id": 1, "state": "APPROVED", "user": {"login": "alice"}, "body": "LGTM"}]
        c, t = _client([reviews])
        result = ReviewReader(REPO, client=c).read_reviews(42)
        assert result == reviews
        assert "/pulls/42/reviews" in str(t.calls[0].url)

    def test_read_review_comments(self) -> None:
        comments = [
            {"id": 2, "body": "nit: rename", "path": "foo.py", "line": 10, "user": {"login": "bob"}}
        ]
        c, t = _client([comments])
        result = ReviewReader(REPO, client=c).read_review_comments(42)
        assert result == comments
        assert "/pulls/42/comments" in str(t.calls[0].url)

    def test_extract_actionable_feedback_changes_requested(self) -> None:
        reviews = [
            {
                "state": "CHANGES_REQUESTED",
                "body": "Please fix the typo",
                "user": {"login": "carol"},
            },
            {"state": "APPROVED", "body": "Looks good", "user": {"login": "dave"}},
        ]
        comments: list[dict[str, Any]] = []
        c, _ = _client([reviews, comments])
        feedback = ReviewReader(REPO, client=c).extract_actionable_feedback(55)
        assert len(feedback) == 1
        assert feedback[0].reviewer == "carol"
        assert feedback[0].body == "Please fix the typo"
        assert feedback[0].state == "CHANGES_REQUESTED"

    def test_extract_actionable_feedback_inline_comments(self) -> None:
        reviews: list[dict[str, Any]] = []
        comments = [
            {
                "body": "Use snake_case here",
                "path": "main.py",
                "line": 42,
                "user": {"login": "eve"},
            },
            {
                "body": "",
                "path": "main.py",
                "line": 43,
                "user": {"login": "frank"},
            },  # empty body -> skipped
        ]
        c, _ = _client([reviews, comments])
        feedback = ReviewReader(REPO, client=c).extract_actionable_feedback(60)
        assert len(feedback) == 1
        assert feedback[0].path == "main.py"
        assert feedback[0].line == 42
        assert feedback[0].reviewer == "eve"

    def test_extract_actionable_feedback_mixed(self) -> None:
        reviews = [
            {"state": "CHANGES_REQUESTED", "body": "Needs refactor", "user": {"login": "gina"}},
        ]
        comments = [
            {"body": "Fix import order", "path": "lib.py", "line": 5, "user": {"login": "hank"}},
        ]
        c, _ = _client([reviews, comments])
        feedback = ReviewReader(REPO, client=c).extract_actionable_feedback(70)
        assert len(feedback) == 2
        assert feedback[0].state == "CHANGES_REQUESTED"
        assert feedback[1].state == "COMMENTED"

    def test_extract_actionable_feedback_empty(self) -> None:
        c, _ = _client([[], []])
        feedback = ReviewReader(REPO, client=c).extract_actionable_feedback(80)
        assert feedback == []

    def test_extract_uses_original_line_fallback(self) -> None:
        reviews: list[dict[str, Any]] = []
        comments = [
            {"body": "check this", "path": "a.py", "original_line": 99, "user": {"login": "ian"}},
        ]
        c, _ = _client([reviews, comments])
        feedback = ReviewReader(REPO, client=c).extract_actionable_feedback(90)
        assert feedback[0].line == 99


# ---------------------------------------------------------------------------
# ReviewFeedback dataclass
# ---------------------------------------------------------------------------


class TestReviewFeedback:
    def test_defaults(self) -> None:
        fb = ReviewFeedback(reviewer="x", body="y")
        assert fb.path is None
        assert fb.line is None
        assert fb.state == "COMMENTED"
