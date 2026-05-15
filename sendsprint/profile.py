"""Persistent non-secret profile stored at ``~/.config/sendsprint/profile.yaml``.

Holds remembered defaults so the user only has to answer onboarding
questions once: provider, base URLs, default sprint/iteration, default
workspace, default repo, LLM choice. Secrets stay in :mod:`sendsprint.credentials`.
"""

from __future__ import annotations

import contextlib
import datetime
import logging
import os
import stat
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)

CONFIG_DIR = Path(os.environ.get("SENDSPRINT_CONFIG_DIR", "~/.config/sendsprint")).expanduser()
PROFILE_PATH = CONFIG_DIR / "profile.yaml"


class JiraProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    base_url: str | None = None
    email: str | None = None
    default_sprint_id: int | None = None


class AzureDevopsProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    organization: str | None = None
    project: str | None = None
    team: str | None = None
    default_iteration: str | None = None


class LlmProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str = "anthropic"
    model: str = "claude-opus-4-7"


class Profile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_provider: str | None = None  # "jira" | "azuredevops"
    default_repo_path: str | None = None
    default_workspace: str | None = None
    default_scope: str = "mine"  # "mine" | "all"
    jira: JiraProfile = Field(default_factory=JiraProfile)
    azuredevops: AzureDevopsProfile = Field(default_factory=AzureDevopsProfile)
    llm: LlmProfile = Field(default_factory=LlmProfile)
    updated_at: str | None = None  # ISO 8601 UTC


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with contextlib.suppress(OSError):  # pragma: no cover — Windows
        os.chmod(CONFIG_DIR, stat.S_IRWXU)  # 700


def load() -> Profile:
    """Read profile.yaml, returning an empty :class:`Profile` if absent."""
    if not PROFILE_PATH.exists():
        return Profile()
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover — pyyaml is a hard dep
        raise RuntimeError("pyyaml required to read profile") from exc
    raw: dict[str, Any] = yaml.safe_load(PROFILE_PATH.read_text()) or {}
    return Profile.model_validate(raw)


def save(profile: Profile) -> None:
    """Write profile.yaml with secure permissions and an updated timestamp."""
    try:
        import yaml
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pyyaml required to save profile") from exc
    _ensure_dir()
    profile.updated_at = datetime.datetime.now(datetime.UTC).isoformat()
    PROFILE_PATH.write_text(yaml.safe_dump(profile.model_dump(mode="json"), sort_keys=False))
    with contextlib.suppress(OSError):  # pragma: no cover — Windows
        os.chmod(PROFILE_PATH, stat.S_IRUSR | stat.S_IWUSR)  # 600


def update(**fields: Any) -> Profile:
    """Patch the on-disk profile with ``fields`` and return the new state.

    Nested keys use dotted notation: ``update(jira__base_url=...)`` is not
    supported because ``__`` is reserved by Pydantic; pass ``"jira.base_url"``
    instead via ``**{"jira.base_url": "..."}``.
    """
    p = load()
    data = p.model_dump()
    for key, value in fields.items():
        if "." in key:
            head, tail = key.split(".", 1)
            sub = data.setdefault(head, {})
            sub[tail] = value
        else:
            data[key] = value
    new = Profile.model_validate(data)
    save(new)
    return new
