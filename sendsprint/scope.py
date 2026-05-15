"""Sprint scope filtering: scope mode + status whitelist + explicit task keys."""

from __future__ import annotations

from .models.sprint import Sprint, SprintItem
from .models.workspace import DEFAULT_DEVELOPABLE_STATUSES, ScopeConfig


def _matches_user(item: SprintItem, scope: ScopeConfig) -> bool:
    """True if item assignee matches the configured user identity."""
    if scope.user_account_id and item.assignee_account_id == scope.user_account_id:
        return True
    if scope.user_descriptor and item.assignee_descriptor == scope.user_descriptor:
        return True
    if (
        scope.user_email
        and item.assignee_email
        and (item.assignee_email.lower() == scope.user_email.lower())
    ):
        return True
    return bool(
        scope.user_display_name
        and item.assignee
        and (item.assignee.strip().lower() == scope.user_display_name.strip().lower())
    )


def _norm(s: str | None) -> str:
    return (s or "").strip().lower()


def _matches_status(item: SprintItem, allowed: list[str]) -> bool:
    """Case-insensitive status whitelist match. Empty list = pass-through."""
    if not allowed:
        return True
    haystack = {_norm(s) for s in allowed}
    return _norm(item.status) in haystack


def _matches_key(item: SprintItem, keys: list[str]) -> bool:
    """Case-insensitive match against explicit task keys/ids."""
    haystack = {_norm(k) for k in keys}
    return _norm(item.key) in haystack or _norm(item.id) in haystack


def apply_scope(sprint: Sprint, scope: ScopeConfig) -> Sprint:
    """Return a new Sprint with items filtered per scope rules.

    Precedence:
      1. explicit ``task_keys`` (overrides mode + status filter)
      2. ``mode='mine'`` (filter by assignee) then status whitelist
      3. ``mode='all'`` then status whitelist
    """
    items: list[SprintItem] = list(sprint.items)

    if scope.task_keys:
        filtered = [i for i in items if _matches_key(i, scope.task_keys)]
        return sprint.model_copy(update={"items": filtered})

    if scope.mode == "mine":
        items = [i for i in items if _matches_user(i, scope)]

    items = [i for i in items if _matches_status(i, scope.allowed_statuses)]
    return sprint.model_copy(update={"items": items})


def build_scope(
    mode: str = "all",
    user_email: str | None = None,
    user_account_id: str | None = None,
    user_descriptor: str | None = None,
    user_display_name: str | None = None,
    allowed_statuses: list[str] | None = None,
    task_keys: list[str] | None = None,
) -> ScopeConfig:
    """Build a ScopeConfig from CLI/programmatic args.

    ``allowed_statuses=None`` -> default developable set (new/active/todo/open/in progress/...).
    ``task_keys`` (when set) bypasses both mode and status filter.
    """
    if mode not in ("all", "mine"):
        raise ValueError(f"scope mode must be 'all' or 'mine', got {mode!r}")
    statuses = (
        list(allowed_statuses)
        if allowed_statuses is not None
        else list(DEFAULT_DEVELOPABLE_STATUSES)
    )
    keys = [k.strip() for k in task_keys if k and k.strip()] if task_keys else None
    return ScopeConfig(
        mode=mode,  # type: ignore[arg-type]
        user_email=user_email,
        user_account_id=user_account_id,
        user_descriptor=user_descriptor,
        user_display_name=user_display_name,
        allowed_statuses=statuses,
        task_keys=keys,
    )
