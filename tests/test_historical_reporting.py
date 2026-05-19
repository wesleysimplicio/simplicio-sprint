from sendsprint.historical_reporting import HistoricalRun, build_historical_report


def test_build_historical_report_groups_runs_by_status_and_provider() -> None:
    report = build_historical_report(
        [
            HistoricalRun(repo="repo-a", provider="codex", status="done"),
            HistoricalRun(repo="repo-b", provider="codex", status="failed"),
            HistoricalRun(repo="repo-c", provider="claude", status="done"),
        ]
    )
    assert report.totals_by_status == {"done": 2, "failed": 1}
    assert report.totals_by_provider == {"codex": 2, "claude": 1}
