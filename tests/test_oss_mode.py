from sendsprint.oss_mode import detect_oss_mode


def test_detect_oss_mode_reads_common_repo_conventions(tmp_path) -> None:
    (tmp_path / "CONTRIBUTING.md").write_text("rules")
    (tmp_path / "CODE_OF_CONDUCT.md").write_text("rules")
    (tmp_path / "SECURITY.md").write_text("rules")
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "PULL_REQUEST_TEMPLATE.md").write_text("template")

    mode = detect_oss_mode(tmp_path)

    assert mode.has_contributing is True
    assert mode.has_pr_template is True
