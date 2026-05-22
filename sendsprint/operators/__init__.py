"""Sprint-source operators.

Each operator reads work items from a specific tracker (Jira, Azure DevOps,
GitHub, GitLab, …) and emits a uniform :class:`~sendsprint.models.Sprint`
that the v2 dispatcher fans out across provider adapters.

Status:
    * jira, azuredevops, github                — fully wired (REST + MCP/Playwright stubs)
    * gitlab, bitbucket, gitee, linear, clickup, trello, slack, hermes
                                               — auth pre-check wired, transport bodies
                                                 are "not yet wired" scaffolds until
                                                 the matching *-INGEST sub-issue lands.

Spec: ``.specs/v2/cloud-dispatcher.md`` (INGEST sub-issue + per-tracker
``*-INGEST`` follow-ups).
"""

from sendsprint.operators.azure_devops_operator import AzureDevopsOperator
from sendsprint.operators.base import BaseOperator, Transport, TransportUnavailable
from sendsprint.operators.bitbucket_operator import BitbucketOperator
from sendsprint.operators.clickup_operator import ClickUpOperator
from sendsprint.operators.gitee_operator import GiteeOperator
from sendsprint.operators.github_operator import GitHubOperator
from sendsprint.operators.gitlab_operator import GitLabOperator
from sendsprint.operators.hermes_operator import HermesOperator
from sendsprint.operators.jira_operator import JiraOperator
from sendsprint.operators.linear_operator import LinearOperator
from sendsprint.operators.slack_operator import SlackOperator
from sendsprint.operators.trello_operator import TrelloOperator

# Registry keyed by the canonical source name (matches Sprint.source).
OPERATOR_CLASSES: dict[str, type[BaseOperator]] = {
    "jira": JiraOperator,
    "azuredevops": AzureDevopsOperator,
    "github": GitHubOperator,
    "gitlab": GitLabOperator,
    "bitbucket": BitbucketOperator,
    "gitee": GiteeOperator,
    "linear": LinearOperator,
    "clickup": ClickUpOperator,
    "trello": TrelloOperator,
    "slack": SlackOperator,
    "hermes": HermesOperator,
}

__all__ = [
    "OPERATOR_CLASSES",
    "AzureDevopsOperator",
    "BaseOperator",
    "BitbucketOperator",
    "ClickUpOperator",
    "GiteeOperator",
    "GitHubOperator",
    "GitLabOperator",
    "HermesOperator",
    "JiraOperator",
    "LinearOperator",
    "SlackOperator",
    "Transport",
    "TransportUnavailable",
    "TrelloOperator",
]
