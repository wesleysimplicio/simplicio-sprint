"""Auth endpoints: persist Jira / Azure DevOps credentials in the OS keyring."""

from __future__ import annotations

import contextlib
import os
import subprocess
from typing import cast

import httpx
from fastapi import APIRouter, HTTPException

from sendsprint import credentials
from sendsprint import profile as profile_mod
from sendsprint.api.schemas import (
    AppLoginRequest,
    AppLoginResponse,
    AuthBootstrapResponse,
    AuthResponse,
    AzureAuthRequest,
    JiraAuthRequest,
)
from sendsprint.api.security import get_operator_token
from sendsprint.azure_devops_urls import parse_azure_sprint_url
from sendsprint.credentials import Provider as CredentialProvider
from sendsprint.operators import AzureDevopsOperator, JiraOperator

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/bootstrap", response_model=AuthBootstrapResponse)
def bootstrap() -> AuthBootstrapResponse:
    token = get_operator_token()
    if not token:
        raise HTTPException(status_code=503, detail="operator token not initialized")
    status_payload = status()
    return AuthBootstrapResponse(operator_token=token, **status_payload)


@router.post("/app-login", response_model=AppLoginResponse)
def app_login(req: AppLoginRequest) -> AppLoginResponse:
    email = req.email.strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required.")
    if not req.password.strip():
        raise HTTPException(status_code=400, detail="Password is required.")
    display_name = email.split("@", 1)[0].replace(".", " ").replace("_", " ").title()
    return AppLoginResponse(
        email=email,
        active=True,
        display_name=display_name,
        permissions={"can_run_all_backlog": _can_run_all_backlog(email)},
    )


@router.post("/jira", response_model=AuthResponse)
def auth_jira(req: JiraAuthRequest) -> AuthResponse:
    base = req.base_url.rstrip("/")
    try:
        with httpx.Client(timeout=15.0, auth=(req.email, req.api_token)) as client:
            resp = client.get(f"{base}/rest/api/3/myself")
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401 and req.sprint_url:
            fallback = _capture_jira_with_browser_fallback(
                base_url=base,
                email=req.email,
                sprint_id=req.sprint_id or "browser-captured",
                sprint_url=req.sprint_url,
                original_error=(
                    f"Jira auth failed: {exc.response.status_code} {exc.response.reason_phrase}"
                ),
            )
            profile_mod.update(
                default_provider="jira",
                **{
                    "jira.base_url": base,
                    "jira.email": req.email,
                    "jira.last_sprint_url": req.sprint_url or None,
                    "jira.default_sprint_id": (
                        int(req.sprint_id)
                        if req.sprint_id and req.sprint_id.isdigit()
                        else None
                    ),
                },
            )
            return AuthResponse(
                provider="jira",
                account=req.email,
                ok=True,
                user_display_name=req.email,
                fallback_used=True,
                capture_transport=fallback["capture_transport"],
            )
        raise HTTPException(
            status_code=401,
            detail=f"Jira auth failed: {exc.response.status_code} {exc.response.reason_phrase}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Jira unreachable: {exc}") from exc

    # Keyring may be unavailable in some envs; auth still validated.
    with contextlib.suppress(credentials.CredentialError):
        credentials.set_secret("jira", req.email, req.api_token)
    profile_mod.update(
        default_provider="jira",
        **{
            "jira.base_url": base,
            "jira.email": req.email,
            "jira.last_sprint_url": req.sprint_url or None,
            "jira.default_sprint_id": (
                int(req.sprint_id) if req.sprint_id and req.sprint_id.isdigit() else None
            ),
        },
    )

    return AuthResponse(
        provider="jira",
        account=req.email,
        ok=True,
        user_display_name=data.get("displayName"),
    )


@router.post("/azuredevops", response_model=AuthResponse)
def auth_azure(req: AzureAuthRequest) -> AuthResponse:
    parsed = parse_azure_sprint_url(req.sprint_url) if req.sprint_url else None
    org = (req.organization or (parsed.organization if parsed else "")).strip("/")
    project = (req.project or (parsed.project if parsed else "")).strip("/")
    team = (req.team or (parsed.team if parsed else "")).strip("/") or None
    account = f"{org}/{project}" if org and project else ""
    pat = (req.pat or "").strip()
    if not org or not project:
        raise HTTPException(
            status_code=400,
            detail="Provide a sprint URL or explicit organization/project for Azure DevOps auth.",
        )
    if not pat:
        pat = credentials.get_secret("azuredevops", org) or ""
    if not pat:
        raise HTTPException(status_code=400, detail="Azure DevOps PAT is required.")

    url = f"https://dev.azure.com/{org}/_apis/projects/{project}?api-version=7.1"
    try:
        with httpx.Client(timeout=15.0, auth=("", pat)) as client:
            resp = client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 401 and parsed and req.sprint_url:
            fallback = _capture_ado_with_browser_fallback(
                organization=org,
                project=project,
                team=team,
                iteration_path=(
                    "\\".join(part for part in (project, team, parsed.iteration_name) if part)
                    if parsed and parsed.iteration_name
                    else None
                ),
                sprint_url=req.sprint_url,
                original_error=f"Azure DevOps auth failed: {exc.response.status_code}",
            )
            with contextlib.suppress(credentials.CredentialError):
                credentials.delete_secret("azuredevops", org)
                credentials.delete_secret("azuredevops", account)
            profile_mod.update(
                default_provider="azuredevops",
                **{
                    "azuredevops.organization": org,
                    "azuredevops.project": project,
                    "azuredevops.team": team,
                    "azuredevops.last_sprint_url": req.sprint_url or None,
                    "azuredevops.default_iteration": fallback["iteration_path"],
                },
            )
            return AuthResponse(
                provider="azuredevops",
                account=account,
                ok=True,
                user_display_name=project,
                ado_team_path="/".join(part for part in (org, project, team) if part),
                ado_iteration_path=fallback["iteration_path"],
                fallback_used=True,
                capture_transport=fallback["capture_transport"],
            )
        raise HTTPException(
            status_code=401,
            detail=f"Azure DevOps auth failed: {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"ADO unreachable: {exc}") from exc

    with contextlib.suppress(credentials.CredentialError):
        credentials.set_secret("azuredevops", org, pat)
        credentials.set_secret("azuredevops", account, pat)
    profile_mod.update(
        default_provider="azuredevops",
        **{
            "azuredevops.organization": org,
            "azuredevops.project": project,
            "azuredevops.team": team,
            "azuredevops.last_sprint_url": req.sprint_url or None,
            "azuredevops.default_iteration": (
                "\\".join(part for part in (project, team, parsed.iteration_name) if part)
                if parsed and parsed.iteration_name
                else None
            ),
        },
    )

    return AuthResponse(
        provider="azuredevops",
        account=account,
        ok=True,
        user_display_name=data.get("name"),
        ado_team_path="/".join(part for part in (org, project, team) if part),
        ado_iteration_path=(
            "\\".join(part for part in (project, team, parsed.iteration_name) if part)
            if parsed and parsed.iteration_name
            else None
        ),
    )


@router.get("/status", response_model=dict)
def status() -> dict:
    """Tell the web app which providers already have stored creds."""
    profile = profile_mod.load()
    ado_org = profile.azuredevops.organization or ""
    ado_project = profile.azuredevops.project or ""
    ado_team = profile.azuredevops.team or ""
    jira_account = profile.jira.email or ""
    return {
        "default_provider": profile.default_provider,
        "jira_configured": _has_any("jira", jira_account),
        "azuredevops_configured": _has_any("azuredevops", ado_org),
        "providers": {
            "jira": {
                "configured": _has_any("jira", jira_account),
                "account": jira_account or None,
            },
            "azuredevops": {
                "configured": _has_any("azuredevops", ado_org),
                "account": f"{ado_org}/{ado_project}" if ado_org and ado_project else None,
                "team_path": "/".join(part for part in (ado_org, ado_project, ado_team) if part)
                or None,
                "iteration_path": profile.azuredevops.default_iteration,
            },
            "github": {
                "configured": _github_cli_authenticated(),
            },
        },
    }


def _has_any(provider: str, account: str) -> bool:
    if provider not in ("jira", "azuredevops"):
        return False
    if not account:
        return False
    try:
        return bool(credentials.get_secret(cast(CredentialProvider, provider), account))
    except credentials.CredentialError:
        return False


def _can_run_all_backlog(email: str) -> bool:
    allowlist = os.getenv("SENDSPRINT_RUN_ALL_BACKLOG_EMAILS", "").strip()
    if not allowlist:
        return True
    allowed = {item.strip().lower() for item in allowlist.split(",") if item.strip()}
    return email.strip().lower() in allowed


def _github_cli_authenticated() -> bool:
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return False
    return result.returncode == 0


def _capture_ado_with_browser_fallback(
    *,
    organization: str,
    project: str,
    team: str | None,
    iteration_path: str | None,
    sprint_url: str,
    original_error: str,
) -> dict[str, str]:
    if not iteration_path:
        raise HTTPException(status_code=401, detail=original_error)
    operator = AzureDevopsOperator(
        organization=organization,
        project=project,
        team=team,
        transport="playwright",
    )
    try:
        sprint = operator.read_sprint(iteration_path=iteration_path, sprint_url=sprint_url)
    except Exception as exc:  # pragma: no cover - exercised through API integration tests
        raise HTTPException(
            status_code=401,
            detail=f"{original_error}; browser fallback failed: {exc}",
        ) from exc
    return {
        "iteration_path": iteration_path,
        "capture_transport": sprint.transport,
    }


def _capture_jira_with_browser_fallback(
    *,
    base_url: str,
    email: str,
    sprint_id: str,
    sprint_url: str,
    original_error: str,
) -> dict[str, str]:
    operator = JiraOperator(
        base_url=base_url,
        email=email,
        transport="playwright",
    )
    try:
        sprint = operator.read_sprint(sprint_id=sprint_id, sprint_url=sprint_url)
    except Exception as exc:  # pragma: no cover - exercised through API integration tests
        raise HTTPException(
            status_code=401,
            detail=f"{original_error}; browser fallback failed: {exc}",
        ) from exc
    return {
        "sprint_id": sprint_id,
        "capture_transport": sprint.transport,
    }
