"""Tests for sendsprint.diff_verifier (#99)."""

from __future__ import annotations

import pytest

from sendsprint.diff_verifier import (
    DiffFinding,
    DiffReport,
    DiffVerdict,
    DiffVerifier,
    FindingSeverity,
    FindingType,
    _count_added_lines_per_file,
    _is_source_file,
    _is_test_file,
    _parse_changed_files,
)
from sendsprint.plan_verifier import VerifiablePlan


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CLEAN_DIFF = """\
diff --git a/sendsprint/foo.py b/sendsprint/foo.py
--- a/sendsprint/foo.py
+++ b/sendsprint/foo.py
@@ -1,3 +1,5 @@
 import os
+import sys
+
 def main():
     pass
diff --git a/tests/test_foo.py b/tests/test_foo.py
--- a/tests/test_foo.py
+++ b/tests/test_foo.py
@@ -1,2 +1,4 @@
 def test_main():
     pass
+def test_new():
+    assert True
"""

NO_TEST_DIFF = """\
diff --git a/sendsprint/bar.py b/sendsprint/bar.py
--- a/sendsprint/bar.py
+++ b/sendsprint/bar.py
@@ -1,2 +1,4 @@
 def bar():
     pass
+def baz():
+    return 42
"""

LARGE_DIFF_LINES = "\n".join(
    [
        "diff --git a/sendsprint/big.py b/sendsprint/big.py",
        "--- a/sendsprint/big.py",
        "+++ b/sendsprint/big.py",
        "@@ -0,0 +1,350 @@",
    ]
    + [f"+line {i}" for i in range(350)]
)

GENERATED_DIFF = """\
diff --git a/dist/bundle.min.js b/dist/bundle.min.js
--- /dev/null
+++ b/dist/bundle.min.js
@@ -0,0 +1 @@
+minified
diff --git a/sendsprint/ok.py b/sendsprint/ok.py
--- a/sendsprint/ok.py
+++ b/sendsprint/ok.py
@@ -1 +1,2 @@
 x = 1
+y = 2
"""


# ---------------------------------------------------------------------------
# Model basics
# ---------------------------------------------------------------------------


class TestModels:
    def test_diff_verdict_values(self):
        assert DiffVerdict.passed.value == "pass"
        assert DiffVerdict.warn.value == "warn"
        assert DiffVerdict.block.value == "block"

    def test_finding_type_values(self):
        assert FindingType.unexpected_file.value == "unexpected_file"
        assert FindingType.large_change.value == "large_change"
        assert FindingType.missing_test.value == "missing_test"
        assert FindingType.generated_artifact.value == "generated_artifact"

    def test_finding_severity_values(self):
        assert FindingSeverity.info.value == "info"
        assert FindingSeverity.warning.value == "warning"
        assert FindingSeverity.blocking.value == "blocking"

    def test_diff_finding_frozen(self):
        f = DiffFinding(
            file_path="a.py",
            finding_type=FindingType.large_change,
            severity=FindingSeverity.warning,
            message="big",
        )
        with pytest.raises(Exception):
            f.file_path = "b.py"  # type: ignore[misc]

    def test_diff_report_serialization(self):
        report = DiffReport(
            verdict=DiffVerdict.warn,
            findings=[
                DiffFinding(
                    file_path="x.py",
                    finding_type=FindingType.large_change,
                    severity=FindingSeverity.warning,
                    message="too big",
                )
            ],
            summary="1 finding(s): 1 large_change",
        )
        data = report.model_dump()
        assert data["verdict"] == "warn"
        assert len(data["findings"]) == 1
        roundtrip = DiffReport.model_validate(data)
        assert roundtrip.verdict == DiffVerdict.warn


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


class TestParsingHelpers:
    def test_parse_changed_files(self):
        files = _parse_changed_files(CLEAN_DIFF)
        assert files == ["sendsprint/foo.py", "tests/test_foo.py"]

    def test_parse_changed_files_dedup(self):
        double_diff = CLEAN_DIFF + "\n" + CLEAN_DIFF
        files = _parse_changed_files(double_diff)
        assert files == ["sendsprint/foo.py", "tests/test_foo.py"]

    def test_count_added_lines(self):
        counts = _count_added_lines_per_file(CLEAN_DIFF)
        assert counts["sendsprint/foo.py"] == 2
        assert counts["tests/test_foo.py"] == 2

    def test_count_added_lines_large(self):
        counts = _count_added_lines_per_file(LARGE_DIFF_LINES)
        assert counts["sendsprint/big.py"] == 350

    def test_is_test_file_positive(self):
        assert _is_test_file("tests/test_foo.py")
        assert _is_test_file("test/test_bar.py")
        assert _is_test_file("src/__tests__/foo.test.js")
        assert _is_test_file("foo_test.go")

    def test_is_test_file_negative(self):
        assert not _is_test_file("sendsprint/foo.py")
        assert not _is_test_file("README.md")

    def test_is_source_file(self):
        assert _is_source_file("foo.py")
        assert _is_source_file("bar.ts")
        assert _is_source_file("baz.go")
        assert not _is_source_file("README.md")
        assert not _is_source_file("config.yaml")
        assert not _is_source_file("Makefile")


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


class TestCheckUnexpectedFiles:
    def test_no_plan_returns_empty(self):
        v = DiffVerifier()
        assert v.check_unexpected_files(["a.py", "b.py"], plan=None) == []

    def test_empty_target_files_returns_empty(self):
        plan = VerifiablePlan(task_summary="t", target_files=[])
        v = DiffVerifier()
        assert v.check_unexpected_files(["a.py"], plan=plan) == []

    def test_all_files_expected(self):
        plan = VerifiablePlan(
            task_summary="t",
            target_files=["sendsprint/foo.py", "tests/test_foo.py"],
        )
        v = DiffVerifier()
        findings = v.check_unexpected_files(
            ["sendsprint/foo.py", "tests/test_foo.py"], plan=plan
        )
        assert findings == []

    def test_unexpected_file_flagged(self):
        plan = VerifiablePlan(
            task_summary="t", target_files=["sendsprint/foo.py"]
        )
        v = DiffVerifier()
        findings = v.check_unexpected_files(
            ["sendsprint/foo.py", "sendsprint/surprise.py"], plan=plan
        )
        assert len(findings) == 1
        assert findings[0].finding_type == FindingType.unexpected_file
        assert findings[0].severity == FindingSeverity.warning
        assert "surprise.py" in findings[0].message

    def test_partial_path_match(self):
        """Plan says 'sendsprint/' and actual file is 'sendsprint/foo.py'."""
        plan = VerifiablePlan(
            task_summary="t", target_files=["sendsprint/"]
        )
        v = DiffVerifier()
        findings = v.check_unexpected_files(["sendsprint/foo.py"], plan=plan)
        assert findings == []


class TestCheckLargeChanges:
    def test_small_change_no_finding(self):
        v = DiffVerifier()
        findings = v.check_large_changes(CLEAN_DIFF)
        assert findings == []

    def test_large_change_flagged(self):
        v = DiffVerifier(large_change_threshold=300)
        findings = v.check_large_changes(LARGE_DIFF_LINES)
        assert len(findings) == 1
        assert findings[0].finding_type == FindingType.large_change
        assert "350" in findings[0].message

    def test_custom_threshold(self):
        v = DiffVerifier(large_change_threshold=1)
        findings = v.check_large_changes(CLEAN_DIFF)
        assert len(findings) == 2  # both files have 2 added lines > 1


class TestCheckMissingTests:
    def test_source_with_test_ok(self):
        v = DiffVerifier()
        findings = v.check_missing_tests(
            ["sendsprint/foo.py", "tests/test_foo.py"]
        )
        assert findings == []

    def test_source_without_test_blocked(self):
        v = DiffVerifier()
        findings = v.check_missing_tests(["sendsprint/bar.py"])
        assert len(findings) == 1
        assert findings[0].finding_type == FindingType.missing_test
        assert findings[0].severity == FindingSeverity.blocking

    def test_only_test_files_ok(self):
        v = DiffVerifier()
        findings = v.check_missing_tests(["tests/test_x.py"])
        assert findings == []

    def test_non_source_files_ignored(self):
        v = DiffVerifier()
        findings = v.check_missing_tests(["README.md", "config.yaml"])
        assert findings == []

    def test_multiple_source_no_test(self):
        v = DiffVerifier()
        findings = v.check_missing_tests(["src/a.py", "src/b.ts"])
        assert len(findings) == 2


class TestCheckGeneratedArtifacts:
    def test_no_artifacts(self):
        v = DiffVerifier()
        findings = v.check_generated_artifacts(["sendsprint/foo.py"])
        assert findings == []

    def test_generated_flagged(self):
        v = DiffVerifier()
        findings = v.check_generated_artifacts(
            ["dist/bundle.min.js", "node_modules/pkg/index.js", "sendsprint/ok.py"]
        )
        assert len(findings) == 2
        types = {f.file_path for f in findings}
        assert "dist/bundle.min.js" in types
        assert "node_modules/pkg/index.js" in types

    def test_lockfile_flagged(self):
        v = DiffVerifier()
        findings = v.check_generated_artifacts(["package-lock.json"])
        assert len(findings) == 1
        assert findings[0].finding_type == FindingType.generated_artifact


# ---------------------------------------------------------------------------
# Full verify
# ---------------------------------------------------------------------------


class TestVerify:
    def test_clean_diff_passes(self):
        v = DiffVerifier()
        report = v.verify(CLEAN_DIFF)
        assert report.verdict == DiffVerdict.passed
        assert report.findings == []
        assert "2 file(s) changed" in report.summary

    def test_clean_diff_with_matching_plan(self):
        plan = VerifiablePlan(
            task_summary="add foo",
            target_files=["sendsprint/foo.py", "tests/test_foo.py"],
        )
        v = DiffVerifier()
        report = v.verify(CLEAN_DIFF, plan=plan)
        assert report.verdict == DiffVerdict.passed

    def test_missing_test_blocks(self):
        v = DiffVerifier()
        report = v.verify(NO_TEST_DIFF)
        assert report.verdict == DiffVerdict.block
        assert any(
            f.finding_type == FindingType.missing_test for f in report.findings
        )

    def test_large_change_warns(self):
        # Use a diff with large changes but include a test file to avoid block
        large_with_test = LARGE_DIFF_LINES + "\n" + """\
diff --git a/tests/test_big.py b/tests/test_big.py
--- /dev/null
+++ b/tests/test_big.py
@@ -0,0 +1 @@
+def test_big(): pass
"""
        v = DiffVerifier(large_change_threshold=300)
        report = v.verify(large_with_test)
        assert report.verdict == DiffVerdict.warn
        assert any(
            f.finding_type == FindingType.large_change for f in report.findings
        )

    def test_generated_artifact_warns(self):
        v = DiffVerifier()
        report = v.verify(GENERATED_DIFF)
        # generated artifact = warn, source without test = block
        # block wins over warn
        assert report.verdict in (DiffVerdict.warn, DiffVerdict.block)
        assert any(
            f.finding_type == FindingType.generated_artifact
            for f in report.findings
        )

    def test_unexpected_file_with_plan_warns(self):
        plan = VerifiablePlan(
            task_summary="only foo",
            target_files=["sendsprint/foo.py"],
        )
        v = DiffVerifier()
        report = v.verify(CLEAN_DIFF, plan=plan)
        # tests/test_foo.py is unexpected per plan -> warn
        assert report.verdict == DiffVerdict.warn
        assert any(
            f.finding_type == FindingType.unexpected_file for f in report.findings
        )

    def test_empty_diff_passes(self):
        v = DiffVerifier()
        report = v.verify("")
        assert report.verdict == DiffVerdict.passed
        assert report.findings == []

    def test_summary_counts(self):
        v = DiffVerifier()
        report = v.verify(NO_TEST_DIFF)
        assert "finding(s)" in report.summary

    def test_block_beats_warn(self):
        """When both blocking and warning findings exist, verdict is block."""
        plan = VerifiablePlan(
            task_summary="t", target_files=["nonexistent.py"]
        )
        v = DiffVerifier()
        report = v.verify(NO_TEST_DIFF, plan=plan)
        # unexpected_file (warn) + missing_test (block) -> block
        assert report.verdict == DiffVerdict.block
