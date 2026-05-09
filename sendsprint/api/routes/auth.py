"""Auth endpoints: persist Jira / Azure DevOps credentials in the OS keyring."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from sendsprint import credentials
from sendsprint.api.schemas import AuthResponse, AzureAuthRequest, JiraAuthRequest

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

    try:
        credentials.set_secret("jira", req.email, req.api_token)
    except credentials.CredentialError:
        # Keyring may be unavailable in some envs; auth still validated.
        pass

    return AuthResponse(
        provider="jira",
        account=req.email,
        ok=True,
        user_display_name=data.get("displayName"),
    )


@router.post("/azuredevops", response_model=AuthResponse)
def auth_azure(req: AzureAuthRequest) -> AuthResponse:
    org = req.organization.strip("/")
    url = f"https://dev.azure.com/{org}/_apis/projects/{req.project}?api-version=7.1"
    try:
        with httpx.Client(timeout=15.0, auth=("", req.pat)) as client:
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

    account = f"{org}/{req.project}"
    try:
        credentials.set_secret("azuredevops", account, req.pat)
    except credentials.CredentialError:
        pass

    return AuthResponse(
        provider="azuredevops",
        account=account,
        ok=True,
        user_display_name=data.get("name"),
    )


@router.get("/status", response_model=dict)
def status() -> dict:
    """Tell the mobile app which providers already have stored creds."""
    return {
        "jira_configured": _has_any("jira"),
        "azuredevops_configured": _has_any("azuredevops"),
    }


def _has_any(provider: str) -> bool:
    try:
        return bool(credentials.get_secret(provider, "default"))
    except credentials.CredentialError:
        return False
