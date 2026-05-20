import json

from sendsprint.runtime_baseline import run_runtime_baseline


def test_runtime_baseline_writes_evidence(tmp_path) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "pyproject.toml").write_text("[project]\nname='demo'\n", encoding="utf-8")
    output = tmp_path / "evidence" / "baseline.json"

    report = run_runtime_baseline(repo, output=output, max_files=20)

    assert output.exists()
    assert report.evidence_path == str(output)
    names = {case.name for case in report.cases}
    assert {"scan.files", "dedupe.hash", "scheduling.fanout", "validation.selection"} <= names
    data = json.loads(output.read_text(encoding="utf-8"))
    assert data["thresholds"]["rust_accelerator"]
