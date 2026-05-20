"""Authenticated TestClient helpers for the localhost API."""

from __future__ import annotations

from typing import Any

from fastapi.testclient import TestClient

from sendsprint.api.security import generate_operator_token, get_operator_token

_READ_ONLY_METHODS = {"GET", "HEAD", "OPTIONS"}


class AuthenticatedTestClient(TestClient):
    """Inject the current operator token into mutating test requests."""

    def request(self, method: str, url: str, **kwargs: Any):
        headers = dict(kwargs.pop("headers", {}) or {})
        if method.upper() not in _READ_ONLY_METHODS and not _has_authorization(headers):
            token = get_operator_token() or generate_operator_token()
            headers["Authorization"] = f"Bearer {token}"
        return super().request(method, url, headers=headers, **kwargs)


def _has_authorization(headers: dict[str, Any]) -> bool:
    return any(str(name).lower() == "authorization" for name in headers)
