"""Deterministic agent-facing status answers for active SendSprint runs."""

from __future__ import annotations

from sendsprint.api.schemas import AgentRunSnapshot, AgentStatusAnswer

_ADAPTERS = {"claude", "codex", "hermes", "generic"}


def render_status_answer(
    snapshot: AgentRunSnapshot, *, adapter: str = "generic", question: str | None = None
) -> AgentStatusAnswer:
    """Render a compact answer from a snapshot without guessing missing state."""
    normalized_adapter = adapter.lower()
    if normalized_adapter not in _ADAPTERS:
        normalized_adapter = "generic"

    current_step = _current_step(snapshot)
    last_evidence = snapshot.evidence_paths[-1] if snapshot.evidence_paths else None
    blockers = list(snapshot.blockers)
    next_action = _next_action(snapshot)
    active_agents = _active_agents(snapshot)
    summary = _summary(snapshot, current_step=current_step, next_action=next_action)
    if question:
        summary = f"{summary} Question handled from snapshot only: {question.strip()[:160]}"

    return AgentStatusAnswer(
        run_id=snapshot.run_id,
        adapter=normalized_adapter,  # type: ignore[arg-type]
        state=snapshot.state,
        summary=summary,
        current_step=current_step,
        active_agents=active_agents,
        last_evidence=last_evidence,
        blockers=blockers,
        pr_url=snapshot.pr_url,
        next_action=next_action,
        constraints=[
            "read-only status answer",
            "do not claim unpublished actions",
            "use control-command queue for mutations",
            "report unknown state as unknown",
        ],
        details={
            "sprint_id": snapshot.sprint_id,
            "mode": snapshot.mode,
            "progress": snapshot.progress,
            "iteration": snapshot.iteration,
            "max_iterations": snapshot.max_iterations,
            "failed": snapshot.failed,
            "timeline_events": len(snapshot.timeline),
        },
    )


def _current_step(snapshot: AgentRunSnapshot) -> str:
    if snapshot.current_step is None and not snapshot.current_step_name:
        return "unknown"
    step = f"step {snapshot.current_step}" if snapshot.current_step is not None else "step unknown"
    name = snapshot.current_step_name or "unknown"
    status = snapshot.current_step_status or "unknown"
    return f"{step}: {name} ({status})"


def _active_agents(snapshot: AgentRunSnapshot) -> list[str]:
    agents = {"sendsprint"}
    for event in snapshot.timeline:
        if event.name and event.name.startswith("agent."):
            agents.add(event.name)
    return sorted(agents)


def _next_action(snapshot: AgentRunSnapshot) -> str:
    if snapshot.state == "queued":
        return "wait for worker to start"
    if snapshot.state == "running":
        if snapshot.blockers:
            return "resolve blocker or queue rework command"
        if snapshot.current_step_name:
            return f"continue {snapshot.current_step_name}"
        return "continue active run"
    if snapshot.state == "failed":
        return "inspect blockers and queue rework or cancel command"
    if snapshot.state == "done":
        if snapshot.pr_url:
            return "review published PR and monitor feedback"
        return "review evidence bundle and close out"
    return "unknown"


def _summary(snapshot: AgentRunSnapshot, *, current_step: str, next_action: str) -> str:
    if snapshot.state == "failed":
        first_blocker = snapshot.blockers[0] if snapshot.blockers else "unknown failure"
        return f"Run {snapshot.run_id} failed. Blocker: {first_blocker}. Next: {next_action}."
    if snapshot.state == "done":
        pr = f" PR: {snapshot.pr_url}." if snapshot.pr_url else ""
        return f"Run {snapshot.run_id} is done.{pr} Next: {next_action}."
    return (
        f"Run {snapshot.run_id} is {snapshot.state}. "
        f"Current: {current_step}. Next: {next_action}."
    )
