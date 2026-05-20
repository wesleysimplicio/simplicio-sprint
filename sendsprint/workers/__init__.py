"""Worker runtime package — Python fallback + optional Go accelerator.

Public API:
    resolve_worker() -> PythonWorker | GoWorkerProxy
    PythonWorker     — always-available asyncio-based worker
    GoWorkerProxy    — subprocess wrapper when Go binary is on PATH
"""

from sendsprint.workers.go_spec import GoWorkerProxy, GoWorkerSpec, detect_go_worker
from sendsprint.workers.python_worker import PythonWorker
from sendsprint.workers.resolver import resolve_worker

__all__ = [
    "PythonWorker",
    "GoWorkerProxy",
    "GoWorkerSpec",
    "detect_go_worker",
    "resolve_worker",
]
