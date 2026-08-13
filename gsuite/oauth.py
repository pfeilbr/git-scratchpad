"""OAuth 2.0 for installed apps: loopback flow, refresh, scope registry.

The pain point this tool exists to fix: `gsuite auth login` is one command —
browser opens, you approve, done. Multi-account, aliases, and automatic
token refresh come for free.
"""
from __future__ import annotations

import http.server
import json
import os
import secrets
import threading
import time
import urllib.parse
import webbrowser

import gsuite.transport as transport_mod
from gsuite.config import ConfigStore
from gsuite.errors import AuthError, CLIError

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
USERINFO_ENDPOINT = "https://openidconnect.googleapis.com/v1/userinfo"

# service name -> OAuth scopes (union of what gws and gog request per service)
SERVICE_SCOPES: dict[str, list[str]] = {
    "gmail": ["https://www.googleapis.com/auth/gmail.modify"],
    "calendar": ["https://www.googleapis.com/auth/calendar"],
    "drive": ["https://www.googleapis.com/auth/drive"],
    "docs": ["https://www.googleapis.com/auth/documents"],
    "sheets": ["https://www.googleapis.com/auth/spreadsheets"],
    "slides": ["https://www.googleapis.com/auth/presentations"],
    "contacts": ["https://www.googleapis.com/auth/contacts"],
    "tasks": ["https://www.googleapis.com/auth/tasks"],
    "chat": [
        "https://www.googleapis.com/auth/chat.messages",
        "https://www.googleapis.com/auth/chat.spaces",
    ],
    "keep": ["https://www.googleapis.com/auth/keep"],
    "admin": [
        "https://www.googleapis.com/auth/admin.directory.user",
        "https://www.googleapis.com/auth/admin.directory.group",
    ],
    "forms": [
        "https://www.googleapis.com/auth/forms.body",
        "https://www.googleapis.com/auth/forms.responses.readonly",
    ],
    "meet": [
        "https://www.googleapis.com/auth/meetings.space.created",
        "https://www.googleapis.com/auth/meetings.space.readonly",
    ],
}
IDENTITY_SCOPES = ["https://www.googleapis.com/auth/userinfo.email"]
DEFAULT_SERVICES = ["gmail", "calendar", "drive", "contacts"]
REFRESH_SLACK_SECONDS = 60


def scopes_for(services: list[str]) -> list[str]:
    scopes: set[str] = set(IDENTITY_SCOPES)
    for service in services:
        if service not in SERVICE_SCOPES:
            valid = ", ".join(sorted(SERVICE_SCOPES))
            raise CLIError(f"unknown service: {service} (valid: {valid})")
        scopes.update(SERVICE_SCOPES[service])
    return sorted(scopes)


def get_client(store: ConfigStore) -> dict:
    """OAuth client credentials: env vars win, then stored client.json."""
    env_id = os.environ.get("GSUITE_CLIENT_ID")
    env_secret = os.environ.get("GSUITE_CLIENT_SECRET")
    if env_id and env_secret:
        return {"client_id": env_id, "client_secret": env_secret}
    client = store.load_client()
    if client:
        return client
    raise AuthError(
        "no OAuth client configured — run `gsuite auth credentials set "
        "<client.json>` (Desktop-app client from the Google Cloud console) "
        "or set GSUITE_CLIENT_ID / GSUITE_CLIENT_SECRET"
    )


# -- flow building blocks -----------------------------------------------------

def build_auth_url(client: dict, scopes: list[str], redirect_uri: str,
                   state: str) -> str:
    params = {
        "client_id": client["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"


def parse_redirect(path: str) -> tuple[str, str]:
    """Extract (code, state) from the loopback redirect request path."""
    query = urllib.parse.parse_qs(urllib.parse.urlparse(path).query)
    if "error" in query:
        raise AuthError(f"authorization failed: {query['error'][0]}")
    if "code" not in query:
        raise AuthError("authorization redirect missing ?code=")
    return query["code"][0], query.get("state", [""])[0]


def _post_token(fields: dict) -> dict:
    body = urllib.parse.urlencode(fields).encode()
    status, _, raw = transport_mod.request(
        "POST", TOKEN_ENDPOINT, data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    payload = json.loads(raw or b"{}")
    if status != 200:
        detail = payload.get("error_description") or payload.get("error") or raw
        raise AuthError(f"token endpoint error (HTTP {status}): {detail}")
    return payload


def _with_expiry(payload: dict) -> dict:
    token = dict(payload)
    token["expiry"] = time.time() + float(payload.get("expires_in", 0))
    token.pop("expires_in", None)
    return token


def exchange_code(client: dict, code: str, redirect_uri: str) -> dict:
    payload = _post_token({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    })
    return _with_expiry(payload)


def refresh_access_token(client: dict, token: dict) -> dict:
    if not token.get("refresh_token"):
        raise AuthError("token has no refresh_token — run `gsuite auth login` again")
    payload = _post_token({
        "client_id": client["client_id"],
        "client_secret": client["client_secret"],
        "refresh_token": token["refresh_token"],
        "grant_type": "refresh_token",
    })
    new = _with_expiry(payload)
    new.setdefault("refresh_token", token["refresh_token"])
    for key in ("scopes",):
        if key in token and key not in new:
            new[key] = token[key]
    return new


# -- loopback browser flow ----------------------------------------------------

_SUCCESS_PAGE = (b"<html><body><h2>gsuite: authorization complete</h2>"
                 b"You can close this tab and return to the terminal.</body></html>")


def loopback_authorizer(client: dict, scopes: list[str]) -> tuple[str, str]:
    """Open the browser, catch the redirect on localhost, return (code, uri)."""
    state = secrets.token_urlsafe(16)
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802 (stdlib naming)
            try:
                result["code"], result["state"] = parse_redirect(self.path)
            except AuthError as exc:
                result["error"] = exc
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(_SUCCESS_PAGE)

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect_uri = f"http://127.0.0.1:{server.server_port}/"
    url = build_auth_url(client, scopes, redirect_uri, state)
    print("Opening browser for Google sign-in…\nIf it does not open, visit:")
    print(f"  {url}")
    threading.Thread(target=webbrowser.open, args=(url,), daemon=True).start()
    server.handle_request()
    server.server_close()
    if "error" in result:
        raise result["error"]
    if result.get("state") != state:
        raise AuthError("state mismatch in OAuth redirect — try again")
    return result["code"], redirect_uri


def login_flow(client: dict, scopes: list[str], authorizer=None) -> dict:
    authorizer = authorizer or loopback_authorizer
    code, redirect_uri = authorizer(client, scopes)
    token = exchange_code(client, code, redirect_uri)
    token["scopes"] = scopes
    return token


def fetch_email(token: dict) -> str:
    status, _, raw = transport_mod.request(
        "GET", USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {token['access_token']}"},
    )
    if status != 200:
        raise AuthError(f"could not determine account email (HTTP {status})")
    email = json.loads(raw).get("email")
    if not email:
        raise AuthError("userinfo response had no email")
    return email


# -- other credential sources: env token, Application Default Credentials -------

ACCESS_TOKEN_ENV = "GSUITE_ACCESS_TOKEN"
ADC_ENV = "GOOGLE_APPLICATION_CREDENTIALS"


def env_access_token() -> str | None:
    """A ready-made access token handed in by the environment, if any."""
    return os.environ.get(ACCESS_TOKEN_ENV) or None


def adc_path() -> str:
    """Where Application Default Credentials live (gcloud's own convention)."""
    return os.environ.get(ADC_ENV) or os.path.expanduser(
        "~/.config/gcloud/application_default_credentials.json")


def load_adc() -> dict | None:
    """Parse the ADC file: an authorized_user dict, or None if there is none.

    Service-account keys are recognised and rejected with an explanation:
    signing their JWT assertion needs RS256, which is out of reach for a
    zero-dependency (stdlib-only) tool.
    """
    path = adc_path()
    try:
        data = json.loads(open(path).read())
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as exc:
        raise AuthError(f"cannot read ADC file {path}: {exc}") from exc
    if data.get("type") == "service_account":
        raise AuthError(
            f"{path} is a service_account key — using one requires signing a "
            "JWT with RS256, which gsuite does not support (it is "
            "zero-dependency, stdlib only). Run `gsuite auth login`, or set "
            f"{ACCESS_TOKEN_ENV} to a token minted elsewhere (e.g. "
            "`gcloud auth print-access-token`)"
        )
    missing = [k for k in ("client_id", "client_secret", "refresh_token")
               if not data.get(k)]
    if missing:
        raise AuthError(
            f"{path} is not usable Application Default Credentials: missing "
            f"{', '.join(missing)} (expected an authorized_user file from "
            "`gcloud auth application-default login`)"
        )
    return data


def _adc_access_token(adc: dict) -> dict:
    """Mint an access token from ADC by reusing the ordinary refresh flow."""
    token = refresh_access_token(
        {"client_id": adc["client_id"], "client_secret": adc["client_secret"]},
        {"refresh_token": adc["refresh_token"]},
    )
    # Remembering the origin keeps a cached ADC token renewable: it must be
    # re-minted from ADC, not refreshed against this install's OAuth client.
    token["source"] = "adc"
    return token


def credential_source(store: ConfigStore, email: str | None) -> str:
    """Which credential the next API call would use (reported by `auth doctor`)."""
    if env_access_token():
        return f"{ACCESS_TOKEN_ENV} (env)"
    if email and store.load_token(email) is not None:
        return f"stored token ({email})"
    try:
        if load_adc() is not None:
            return f"ADC ({adc_path()})"
    except AuthError:
        return "none (ADC present but unusable — see `gsuite auth adc`)"
    return "none"


# -- token access for API calls ------------------------------------------------

def get_access_token(store: ConfigStore, email: str) -> str:
    """Resolve a bearer token: env var, then the stored token, then ADC."""
    env_token = env_access_token()
    if env_token:
        return env_token
    token = store.load_token(email) if email else None
    if token is not None:
        if token.get("expiry", 0) - REFRESH_SLACK_SECONDS > time.time():
            return token["access_token"]
        if token.get("source") != "adc":  # an ADC token is re-minted below
            new = refresh_access_token(get_client(store), token)
            store.save_token(email, new)
            return new["access_token"]
    adc = load_adc()
    if adc is not None:
        new = _adc_access_token(adc)
        if email:  # cache it like any other token for this account
            store.save_token(email, new)
        return new["access_token"]
    if email:
        raise AuthError(f"no credentials for {email} — run `gsuite auth login {email}`")
    raise AuthError(
        f"no credentials — run `gsuite auth login` or set {ACCESS_TOKEN_ENV}")
