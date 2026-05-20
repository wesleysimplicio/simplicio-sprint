"""Localhost control-plane security hardening.

Provides lightweight authorization, origin checking, destructive-action
confirmation, and audit logging for the local web API.  Read-only (GET)
endpoints stay open for easy dashboard polling; mutating endpoints
(POST/PUT/DELETE/PATCH) require a Bearer token generated once at startup.

Issue: #117
"""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import JSONResponse

from sendsprint.audit import AuditEntry, audit_log

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Operator token — generated once at startup, printed to console
# ---------------------------------------------------------------------------

_operator_token: str | None = None

# HTTP methods that are considered read-only (no auth required).
READ_ONLY_METHODS: frozenset[str] = frozenset({"GET", "HEAD", "OPTIONS"})

# Paths that are always open regardless of method (health, SSE streams).
OPEN_PATHS: tuple[str, ...] = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
)

# Allowed origins for browser requests.  Localhost variants only.
ALLOWED_ORIGINS: frozenset[str] = frozenset(
    {
        "http://localhost",
        "https://localhost",
        "http://127.0.0.1",
        "https://127.0.0.1",
        "http://[::1]",
        "https://[::1]",
    }
)


def generate_operator_token() -> str:
    """Generate a cryptographically random operator token for this session.

    Called once at app startup.  The token is printed to the console so the
    local operator (or UI) can capture it.  Never persisted to disk.
    """
    global _operator_token
    _operator_token = secrets.token_urlsafe(32)
    logger.info(
        "Operator token generated — pass as 'Authorization: Bearer <token>' for mutating requests."
    )
    return _operator_token


def get_operator_token() -> str | None:
    """Return the current operator token (None if not yet generated)."""
    return _operator_token


def _reset_token() -> None:
    """Test helper: clear the token so tests can re-generate."""
    global _operator_token
    _operator_token = None


def _is_origin_allowed(origin: str) -> bool:
    """Check if *origin* matches an allowed localhost variant.

    Accepts bare origins (``http://localhost``) and origins with a port
    suffix (``http://localhost:5173``).
    """
    if not origin:
        return False
    # Exact match (no port).
    if origin in ALLOWED_ORIGINS:
        return True
    # Match with port — strip ``:<port>`` and check the base.
    return any(origin.startswith(allowed + ":") for allowed in ALLOWED_ORIGINS)


# ---------------------------------------------------------------------------
# Middlewares
# ---------------------------------------------------------------------------


class LocalAuthMiddleware(BaseHTTPMiddleware):
    """Require Bearer token for mutating (non-GET) endpoints.

    Read-only requests and explicitly open paths pass through without auth.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Always allow read-only methods.
        if request.method in READ_ONLY_METHODS:
            return await call_next(request)

        # Always allow explicitly open paths.
        path = request.url.path.rstrip("/")
        for open_path in OPEN_PATHS:
            if path == open_path or path.startswith(open_path + "/"):
                return await call_next(request)

        # Mutating request — require valid Bearer token.
        token = _operator_token
        if token is None:
            # Token not generated yet — reject.
            return JSONResponse(
                status_code=503,
                content={"detail": "operator token not initialized"},
            )

        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            _audit_rejected(request, "missing_token")
            return JSONResponse(
                status_code=401,
                content={"detail": "Bearer token required for mutating endpoints"},
            )

        provided = auth_header[7:]  # len("Bearer ") == 7
        if not secrets.compare_digest(provided, token):
            _audit_rejected(request, "invalid_token")
            return JSONResponse(
                status_code=403,
                content={"detail": "invalid operator token"},
            )

        return await call_next(request)


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """Validate the Origin header on browser-originated mutating requests.

    Requests without an Origin header are assumed to be non-browser (curl,
    SDK) and pass through.  Requests WITH an Origin header must match a
    localhost variant.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Only enforce on mutating methods.
        if request.method in READ_ONLY_METHODS:
            return await call_next(request)

        origin = request.headers.get("origin")
        if origin is not None and not _is_origin_allowed(origin):
            _audit_rejected(request, "origin_blocked", detail={"origin": origin})
            return JSONResponse(
                status_code=403,
                content={
                    "detail": f"origin '{origin}' is not allowed",
                },
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Destructive-action guard (dependency, not middleware)
# ---------------------------------------------------------------------------


class DestructiveActionGuard:
    """Verify that destructive operations carry a ``confirmed`` flag.

    Used as a utility by route handlers — not a middleware — because it
    needs access to the parsed request body.
    """

    #: Actions that require ``confirmed=true`` in the request body.
    DESTRUCTIVE_ACTIONS: frozenset[str] = frozenset({"cancel", "delete", "purge"})

    @classmethod
    def check(cls, action: str, body: dict[str, Any]) -> str | None:
        """Return an error message if the action is destructive and not confirmed.

        Returns ``None`` when the request is acceptable.
        """
        if action not in cls.DESTRUCTIVE_ACTIONS:
            return None
        if body.get("confirmed") is True:
            return None
        return f"action '{action}' is destructive — set confirmed=true to proceed"


# ---------------------------------------------------------------------------
# Audit helpers
# ---------------------------------------------------------------------------


def audit_operator_action(
    *,
    action: str,
    run_id: str,
    operator: str = "web-ui",
    result: str = "ok",
    detail: dict[str, Any] | None = None,
) -> AuditEntry:
    """Record an operator action to the global audit log.

    Convenience wrapper used by route handlers after successful mutations.
    """
    entry = AuditEntry(
        operator=operator,
        action=action,  # type: ignore[arg-type]
        run_id=run_id,
        result=result,
        detail=detail or {},
    )
    audit_log.append(entry)
    return entry


def _audit_rejected(
    request: Request,
    reason: str,
    *,
    detail: dict[str, Any] | None = None,
) -> None:
    """Log a rejected request to the audit trail for observability."""
    info: dict[str, Any] = {
        "reason": reason,
        "method": request.method,
        "path": str(request.url.path),
        "timestamp": datetime.now(UTC).isoformat(),
    }
    if detail:
        info.update(detail)
    logger.warning("request rejected: %s %s — %s", request.method, request.url.path, reason)
    # Record to audit log with a synthetic run_id so it shows up in queries.
    entry = AuditEntry(
        operator="unknown",
        # Reuse the closest valid audit action for security rejections.
        action="pause",  # type: ignore[arg-type]
        run_id="__security__",
        result="rejected",
        detail=info,
    )
    audit_log.append(entry)
