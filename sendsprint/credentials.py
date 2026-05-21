"""Persistent credential store backed by the OS keyring.

First call to :func:`get_or_prompt` asks the user once; the value is then
stored in macOS Keychain / Linux Secret Service / Windows Credential Manager
via the ``keyring`` library and returned silently on subsequent calls.

No secret ever touches disk in plaintext. Profile metadata (non-secret prefs
like default provider / sprint id) lives in :mod:`sendsprint.profile`.
"""

from __future__ import annotations

import contextlib
import logging
import os
from typing import Literal

logger = logging.getLogger(__name__)

SERVICE = "sendsprint"
Provider = Literal["jira", "azuredevops"]
_VOLATILE_SECRETS: dict[str, str] = {}


class CredentialError(RuntimeError):
    """Raised when credentials cannot be read or written."""


def _keyring():
    try:
        import keyring  # type: ignore[import-not-found]
    except ImportError as exc:
        raise CredentialError(
            "keyring not installed. run: pip install 'sendsprint[keyring]'"
        ) from exc
    return keyring


def _username(provider: Provider, account: str) -> str:
    return f"{provider}:{account}"


def _cache_key(provider: Provider, account: str) -> str:
    return _username(provider, account.strip())


def get_secret(provider: Provider, account: str) -> str | None:
    """Return the stored secret for ``provider:account`` or ``None``."""
    normalized = account.strip()
    if not normalized:
        return None
    kr = _keyring()
    try:
        secret = kr.get_password(SERVICE, _username(provider, normalized))
    except Exception as exc:  # pragma: no cover - keyring backend errors
        logger.warning("keyring read failed: %s", exc)
        secret = None
    if secret:
        _VOLATILE_SECRETS[_cache_key(provider, normalized)] = secret
        return secret
    return _VOLATILE_SECRETS.get(_cache_key(provider, normalized))


def set_secret(provider: Provider, account: str, secret: str) -> None:
    """Persist ``secret`` for ``provider:account`` in the OS keyring."""
    normalized = account.strip()
    if not normalized:
        raise CredentialError("account is required")
    _VOLATILE_SECRETS[_cache_key(provider, normalized)] = secret
    kr = _keyring()
    try:
        kr.set_password(SERVICE, _username(provider, normalized), secret)
    except Exception as exc:
        raise CredentialError(f"keyring write failed: {exc}") from exc


def delete_secret(provider: Provider, account: str) -> None:
    """Remove the stored secret. No-op if absent."""
    normalized = account.strip()
    if normalized:
        _VOLATILE_SECRETS.pop(_cache_key(provider, normalized), None)
    kr = _keyring()
    with contextlib.suppress(Exception):  # pragma: no cover - already gone
        kr.delete_password(SERVICE, _username(provider, normalized))


def get_or_prompt(
    provider: Provider,
    account_env: str,
    secret_env: str,
    *,
    account_label: str = "email/org",
    secret_label: str = "API token",
    interactive: bool = True,
) -> tuple[str, str]:
    """Resolve ``(account, secret)`` from env, then keyring, then prompt.

    Lookup order:
      1. ``os.environ[account_env]`` + ``os.environ[secret_env]`` - used as-is,
         and (if both present) persisted to keyring for next time.
      2. Keyring entry for ``provider`` keyed by the env-var account.
      3. Interactive prompt (only when ``interactive`` is true). Both values
         are written to keyring on success.

    Raises :class:`CredentialError` when non-interactive and nothing found.
    """
    account = os.environ.get(account_env)
    secret_from_env = os.environ.get(secret_env)

    if account and secret_from_env:
        set_secret(provider, account, secret_from_env)
        return account, secret_from_env

    if account:
        stored = get_secret(provider, account)
        if stored:
            return account, stored

    if not interactive:
        raise CredentialError(
            f"missing credentials for {provider}: set {account_env} + {secret_env}"
            f" or run 'sendsprint login {provider}' once."
        )

    import typer

    if not account:
        account = typer.prompt(f"{provider} {account_label}")
    secret = typer.prompt(f"{provider} {secret_label}", hide_input=True)
    set_secret(provider, account, secret)
    typer.echo(f"saved {provider} credentials to keyring (account={account})")
    return account, secret
