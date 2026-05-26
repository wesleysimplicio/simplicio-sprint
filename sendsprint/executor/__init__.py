"""Task execution backend.

SendSprint is the agent (the brain): it reads sprints, organizes tasks,
collects evidence, commits, opens PRs and drives the review loop. The actual
code edit is delegated to ``simplicio-cli`` — a stateless task executor that
turns one normalized task into an applied diff.

See :mod:`sendsprint.executor.simplicio`.
"""

from sendsprint.executor.simplicio import (
    SimplicioExecutor,
    SimplicioNotInstalled,
    SimplicioResult,
    SimplicioTask,
)

__all__ = [
    "SimplicioExecutor",
    "SimplicioNotInstalled",
    "SimplicioResult",
    "SimplicioTask",
]
