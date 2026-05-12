"""FastAPI server entry point for the SendSprint web API."""

from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from sendsprint import __version__
from sendsprint.api.routes import auth as auth_routes
from sendsprint.api.routes import runs as run_routes
from sendsprint.api.routes import sprints as sprint_routes
from sendsprint.api.runs import events
from sendsprint.api.schemas import HealthResponse


@asynccontextmanager
async def _lifespan(_app: FastAPI):
    events.bind_loop(asyncio.get_running_loop())
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
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
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
    return app


app = create_app()


def main() -> None:
    """python -m sendsprint.api"""
    import uvicorn

    host = os.getenv("SENDSPRINT_API_HOST", "0.0.0.0")
    port = int(os.getenv("SENDSPRINT_API_PORT", "8765"))
    uvicorn.run("sendsprint.api.server:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()
