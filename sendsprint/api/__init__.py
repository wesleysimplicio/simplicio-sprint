"""HTTP API for the SendSprint mobile flow.

Wraps the existing operators + SprintFlow behind a FastAPI server so a mobile
client can drive the pipeline (auth → list sprints → pick items → run → PR)
over HTTP + SSE.
"""

from sendsprint.api.server import app, create_app

__all__ = ["app", "create_app"]
