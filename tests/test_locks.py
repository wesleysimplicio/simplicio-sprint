from sendsprint.locks import LockClaim, LockRegistry


def test_lock_registry_rejects_conflicting_file_patterns() -> None:
    registry = LockRegistry()
    registry.acquire(
        LockClaim(
            owner="agent-a", repo="repo", kind="files", key="src/*", file_patterns=["src/*.py"]
        )
    )
    try:
        registry.acquire(
            LockClaim(
                owner="agent-b", repo="repo", kind="files", key="src/*", file_patterns=["src/*.py"]
            )
        )
    except ValueError as exc:
        assert "lock conflict" in str(exc)
    else:
        raise AssertionError("expected a lock conflict")


def test_lock_registry_allows_non_overlapping_claims() -> None:
    registry = LockRegistry()
    registry.acquire(
        LockClaim(
            owner="agent-a", repo="repo", kind="files", key="src/*", file_patterns=["src/*.py"]
        )
    )
    registry.acquire(
        LockClaim(
            owner="agent-b", repo="repo", kind="files", key="docs/*", file_patterns=["docs/*.md"]
        )
    )
    assert len(registry.claims) == 2
