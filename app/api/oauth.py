"""
OAuth endpoints for OpenEMR authorization code flow.
Redirect, launch, and logout URIs for app registration.
"""
# AI-generated: OAuth redirect, launch, and logout endpoints for OpenEMR

import os  # AI-generated
import re
import secrets
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Query
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/oauth", tags=["oauth"])

# AI-generated
OAUTH_CLIENT_ID = os.getenv("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET = os.getenv("OAUTH_CLIENT_SECRET", "")
OAUTH_REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE", "http://localhost:8000")
APP_BASE_URL = os.getenv("APP_BASE_URL", "http://localhost:3000")
# End AI-generated


@router.get("/callback", response_class=RedirectResponse, response_model=None)
async def oauth_callback(
    code: str | None = Query(None),
    state: str | None = Query(None),
) -> RedirectResponse | HTMLResponse:
    """
    OAuth redirect URI. OpenEMR redirects here with code and state after user approval.
    Exchanges code for tokens and redirects to the app.
    """
    if not code:
        return HTMLResponse(
            content=_error_html("No authorization code received. Authorization may have been denied or expired."),
            status_code=400,
        )

    if not OAUTH_CLIENT_ID or not OAUTH_CLIENT_SECRET:
        return HTMLResponse(
            content=_error_html(
                "OAuth not configured. Set OAUTH_CLIENT_ID and OAUTH_CLIENT_SECRET for authorization code flow."
            ),
            status_code=500,
        )

    redirect_uri = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/oauth/callback"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            os.getenv("OPENEMR_TOKEN_URL", "http://openemr/oauth2/default/token"),  # AI-generated
            data={
                "grant_type": "authorization_code",
                "client_id": OAUTH_CLIENT_ID,
                "client_secret": OAUTH_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

    if resp.status_code != 200:
        return HTMLResponse(
            content=_error_html(f"Token exchange failed: {resp.text[:300]}"),
            status_code=resp.status_code,
        )

    data = resp.json()
    patient_id = data.get("patient")
    redirect_path = "/patient" if patient_id else "/staff"
    redirect_url = f"{APP_BASE_URL.rstrip('/')}{redirect_path}"
    # TODO: Store tokens in session/cookie; pass to app for API calls

    return RedirectResponse(url=redirect_url, status_code=302)


@router.get("/launch", response_class=RedirectResponse, response_model=None)
async def oauth_launch(
    iss: str | None = Query(None),
    launch: str | None = Query(None),
) -> RedirectResponse | HTMLResponse:
    """
    OAuth launch URI (EHR launch). OpenEMR redirects here with iss and launch.
    Redirects user to OpenEMR authorize endpoint with launch token.
    """
    if not iss or not launch:
        return HTMLResponse(
            content=_error_html("Missing iss or launch parameters. This page should be opened from OpenEMR."),
            status_code=400,
        )

    if not OAUTH_CLIENT_ID:
        return HTMLResponse(
            content=_error_html("Set OAUTH_CLIENT_ID to enable EHR launch."),
            status_code=500,
        )

    oauth_base = re.sub(r"/apis/[^/]+/fhir/?$", "", iss) + "/oauth2/default"
    authorize_url = f"{oauth_base}/authorize"

    redirect_uri = f"{OAUTH_REDIRECT_BASE.rstrip('/')}/oauth/callback"
    scope = (
        "openid fhirUser launch launch/patient "
        "patient/Patient.read patient/Observation.read "
        "patient/Appointment.read patient/Appointment.write"
    )
    state = secrets.token_urlsafe(32)

    params = {
        "response_type": "code",
        "client_id": OAUTH_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "aud": iss,
        "launch": launch,
    }

    return RedirectResponse(url=f"{authorize_url}?{urlencode(params)}", status_code=302)


@router.get("/logout", response_class=HTMLResponse)
async def oauth_logout() -> HTMLResponse:
    """
    OAuth logout URI. OpenEMR redirects here after user logs out.
    """
    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Signed Out - OpenEMR AI Assistant</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f8fafc; }}
    .card {{ background: white; border-radius: 1rem; padding: 2rem; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,.1); }}
    h1 {{ font-size: 1.25rem; margin: 0 0 .5rem; color: #0f172a; }}
    p {{ color: #64748b; font-size: .875rem; margin: 0 0 1.5rem; }}
    a {{ display: inline-block; background: #059669; color: white; padding: .5rem 1.5rem; border-radius: .5rem; text-decoration: none; font-size: .875rem; }}
    a:hover {{ background: #047857; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>You have been signed out</h1>
    <p>Your session has ended. Sign in again to continue.</p>
    <a href="{APP_BASE_URL.rstrip('/')}/">Return to home</a>
  </div>
</body>
</html>
"""
    return HTMLResponse(content=html)


def _error_html(message: str) -> str:
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Error - OpenEMR AI Assistant</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ font-family: system-ui, sans-serif; margin: 0; min-height: 100vh; display: flex; align-items: center; justify-content: center; background: #f8fafc; }}
    .card {{ background: white; border: 1px solid #fecaca; border-radius: 1rem; padding: 2rem; text-align: center; max-width: 28rem; }}
    h1 {{ font-size: 1.125rem; margin: 0 0 .5rem; color: #b91c1c; }}
    p {{ color: #64748b; font-size: .875rem; margin: 0 0 1.5rem; }}
    a {{ display: inline-block; background: #059669; color: white; padding: .5rem 1.5rem; border-radius: .5rem; text-decoration: none; font-size: .875rem; }}
    a:hover {{ background: #047857; }}
  </style>
</head>
<body>
  <div class="card">
    <h1>Sign-in failed</h1>
    <p>{message}</p>
    <a href="{APP_BASE_URL.rstrip('/')}/">Return to home</a>
  </div>
</body>
</html>
"""
# End AI-generated code
