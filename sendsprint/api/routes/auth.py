"""Auth endpoints: persist Jira / Azure DevOps credentials in the OS keyring."""

from __future__ import annotations

import contextlib
import subprocess
from typing import cast

import httpx
from fastapi import APIRouter, HTTPException

from sendsprint import credentials
from sendsprint import profile as profile_mod
from sendsprint.api.schemas import AuthResponse, AzureAuthRequest, JiraAuthRequest
from sendsprint.azure_devops_urls import parse_azure_sprint_url
from sendsprint.credentials import Provider as CredentialProvider

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/jira", response_model=AuthResponse)
def auth_jira(req: JiraAuthRequest) -> AuthResponse:
    base = req.base_url.rstrip("/")
    try:
        with httpx.Client(timeout=15.0, auth=(req.email, req.api_token)) as client:
            resp = client.get(f"{base}/rest/api/3/myself")
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Jira auth failed: {exc.response.status_code} {exc.response.reason_phrase}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"Jira unreachable: {exc}") from exc

    # Keyring may be unavailable in some envs; auth still validated.
    with contextlib.suppress(credentials.CredentialError):
        credentials.set_secret("jira", req.email, req.api_token)

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
        raise HTTPException(
            status_code=401,
            detail=f"Azure DevOps auth failed: {exc.response.status_code}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=502, detail=f"ADO unreachable: {exc}") from exc

    account = f"{org}/{project}"
    with contextlib.suppress(credentials.CredentialError):
        credentials.set_secret("azuredevops", org, pat)
        credentials.set_secret("azuredevops", account, pat)
    profile_mod.update(
        default_provider="azuredevops",
        **{
            "azuredevops.organization": org,
            "azuredevops.project": project,
            "azuredevops.team": parsed.team if parsed else None,
            "azuredevops.default_iteration": parsed.iteration_path if parsed else None,
        },
    )

    return AuthResponse(
        provider="azuredevops",
        account=account,
        ok=True,
        user_display_name=data.get("name"),
        ado_team_path=parsed.team_path if parsed else f"{org}/{project}",
        ado_iteration_path=parsed.iteration_path if parsed else None,
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
