"""Fan a task out across N real subagents via simplicio-prompt.

simplicio-prompt (https://github.com/wesleysimplicio/simplicio-prompt) ships a
Tuple-Space + Yool kernel that materializes real subagents through an
OpenAI-compatible provider. SendSprint uses it to brainstorm edge cases and a
plan for a card *before* simplicio-cli implements it. This wrapper is the single
boundary: it shells out to ``kernel/subagent_runtime.py`` (mirroring how
:class:`~sendsprint.executor.SimplicioExecutor` wraps simplicio-cli) and parses
the JSON :class:`FanoutReport`, degrading gracefully when the kernel is absent.
"""

from sendsprint.prompt.fanout import FanoutResult, PromptFanout

__all__ = ["FanoutResult", "PromptFanout"]
