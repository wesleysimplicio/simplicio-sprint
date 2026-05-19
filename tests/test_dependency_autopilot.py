from sendsprint.dependency_autopilot import detect_dependency_work


def test_detect_dependency_work_finds_python_and_node_manifests(tmp_path) -> None:
    (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n")
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / "package.json").write_text('{"name":"x"}')

    plan = detect_dependency_work(tmp_path)

    ecosystems = {finding.ecosystem for finding in plan.findings}
    assert ecosystems == {"python", "node"}
