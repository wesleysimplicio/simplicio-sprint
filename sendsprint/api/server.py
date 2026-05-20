"""FastAPI server entry point for the SendSprint web API."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sendsprint import __version__
from sendsprint.api.routes import auth as auth_routes
from sendsprint.api.routes import control_plane as cp_routes
from sendsprint.api.routes import dashboard as dashboard_routes
from sendsprint.api.routes import operator as op_routes
from sendsprint.api.routes import runs as run_routes
from sendsprint.api.routes import sprints as sprint_routes
from sendsprint.api.runs import events
from sendsprint.api.schemas import HealthResponse
from sendsprint.api.security import (
    LocalAuthMiddleware,
    OriginCheckMiddleware,
    generate_operator_token,
)


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    events.bind_loop(asyncio.get_running_loop())
    token = generate_operator_token()
    print(f"\n  Operator token: {token}\n")  # noqa: T201 — intentional console output
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="SendSprint Web API",
        version=__version__,
        description=(
            "HTTP + SSE API that lets the SendSprint web app drive the 10-step flow locally."
        ),
        lifespan=_lifespan,
    )
    # Security middlewares — order: origin check → auth → CORS.
    # Starlette applies middlewares in reverse add-order, so add CORS last
    # (processed first) to set response headers, then auth, then origin.
    app.add_middleware(OriginCheckMiddleware)
    app.add_middleware(LocalAuthMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1|\[::1\])(:\d+)?$",
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    @app.get("/health", response_model=HealthResponse, tags=["meta"])
    def health() -> HealthResponse:
        return HealthResponse(
            ok=True,
            version=__version__,
            providers_configured={
                "jira": bool(os.getenv("JIRA_BASE_URL") and os.getenv("JIRA_EMAIL")),
                "azuredevops": bool(
                    os.getenv("AZURE_DEVOPS_ORG") and os.getenv("AZURE_DEVOPS_PROJECT")
                ),
            },
        )

    app.include_router(auth_routes.router)
    app.include_router(sprint_routes.router)
    app.include_router(run_routes.router)
    app.include_router(cp_routes.router)
    app.include_router(op_routes.router)
    app.include_router(dashboard_routes.router)
    return app


app = create_app()


def main() -> None:
    """python -m sendsprint.api"""
    import uvicorn

    host = os.getenv("SENDSPRINT_API_HOST", "127.0.0.1")
    port = int(os.getenv("SENDSPRINT_API_PORT", "8765"))
    uvicorn.run("sendsprint.api.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
