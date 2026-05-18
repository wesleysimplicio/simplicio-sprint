"""Executive sprint summary rendering."""

from __future__ import annotations

from sendsprint.evidence import EvidenceBundleManifest
from sendsprint.models.reports import RunReport


def render_executive_report(
    report: RunReport,
    *,
    evidence: EvidenceBundleManifest | None = None,
    next_actions: list[str] | None = None,
) -> str:
    """Render a concise manager-facing Markdown report."""
    delivered = len(report.prs)
    failed_steps = [step for step in report.steps if step.status == "failed"]
    validation_steps = [
        step for step in report.steps if step.name in {"lint", "unit-tests", "e2e-tests"}
    ]
    prs = (
        "\n".join(f"- {pr.title}: {pr.url or pr.number or 'created'}" for pr in report.prs)
        or "- No PRs created"
    )
    blockers = (
        "\n".join(f"- {step.name}: {step.message or 'failed'}" for step in failed_steps)
        or "- None"
    )
    evidence_line = (
        f"- Evidence bundle: `{evidence.root}`" if evidence else "- Evidence bundle: not generated"
    )
    actions = (
        "\n".join(f"- {item}" for item in next_actions or [])
        or "- Human review of PRs and evidence"
    )

    return f"""# Executive Sprint Summary

## Outcome

- Workspace: {report.workspace}
- Sprint: {report.sprint_name or report.sprint_id or "n/a"}
- Delivered PRs: {delivered}
- Failed: {report.failed}
- Summary: {report.summary or "n/a"}

## Pull Requests

{prs}

## Validation

- Validation steps recorded: {len(validation_steps)}
- Failed steps: {len(failed_steps)}
{evidence_line}

## Blockers and Risk

{blockers}

## Next Actions

{actions}
"""
