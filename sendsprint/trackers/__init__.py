"""Tracker integrations beyond Jira and Azure DevOps."""

from __future__ import annotations

from .github_issues import GitHubIssue, GitHubIssuesTracker

__all__ = ["GitHubIssue", "GitHubIssuesTracker"]
