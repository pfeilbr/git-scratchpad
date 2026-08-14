"""Authorized Google API client: JSON, params, pagination, 401 retry, backoff."""
from __future__ import annotations

import json
import time
import urllib.parse

import gsuite.transport as transport_mod
from gsuite import oauth
from gsuite.config import ConfigStore
from gsuite.errors import APIError, CLIError

# Seam for tests: monkeypatch gsuite.api._sleep to observe delays without waiting.
_sleep = time.sleep

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3

# Which `gsuite auth login --services <name>` covers a given API host, so a
# scope error can name the one service to re-authorize. Keys are a host, or a
# host plus path prefix where one host fronts several APIs (www.googleapis.com
# serves both drive and calendar); the longest matching key wins.
SERVICE_BY_HOST = {
    "gmail.googleapis.com": "gmail",
    "sheets.googleapis.com": "sheets",
    "docs.googleapis.com": "docs",
    "slides.googleapis.com": "slides",
    "people.googleapis.com": "contacts",
    "tasks.googleapis.com": "tasks",
    "chat.googleapis.com": "chat",
    "keep.googleapis.com": "keep",
    "admin.googleapis.com": "admin",
    "forms.googleapis.com": "forms",
    "meet.googleapis.com": "meet",
    "searchconsole.googleapis.com": "searchconsole",
    "analyticsdata.googleapis.com": "analytics",
    "analyticsadmin.googleapis.com": "analytics",
    "www.googleapis.com/drive": "drive",
    "www.googleapis.com/upload/drive": "drive",
    "www.googleapis.com/calendar": "calendar",
}

# Substrings that identify the two 403s a user can actually act on.
SCOPE_MARKERS = ("insufficient authentication scopes",
                 "access_token_scope_insufficient")
API_DISABLED_MARKERS = ("accessnotconfigured", "has not been used in project")


def quote_id(value: str) -> str:
    """Percent-encode an id/email for safe use as a URL path segment."""
    return urllib.parse.quote(value, safe="")


class Client:
    def __init__(self, store: ConfigStore, email, readonly: bool = False):
        self.store = store
        self._email = email  # a string, or a callable resolved on first use
        self.readonly = readonly

    @property
    def email(self) -> str:
        """The acting account, resolved lazily.

        Resolution can fail ("no accounts configured"), so it must not happen
        until a request actually needs credentials — otherwise `--readonly`
        would report a missing account instead of refusing the mutation it
        was asked to guard against.
        """
        if callable(self._email):
            self._email = self._email()
        return self._email

    @classmethod
    def for_args(cls, args) -> "Client":
        store = ConfigStore()
        account = getattr(args, "account", None)
        # A caller who supplies $GSUITE_ACCESS_TOKEN needs no configured
        # account at all, so account resolution is skipped entirely.
        email = "" if oauth.env_access_token() else (
            lambda: store.resolve(account))
        return cls(store, email, readonly=getattr(args, "readonly", False))

    # -- core ----------------------------------------------------------------

    def request(self, method: str, url: str, params: dict | None = None,
                json_body=None, data: bytes | None = None,
                headers: dict | None = None, raw: bool = False):
        if self.readonly and method.upper() != "GET":
            raise CLIError(f"readonly mode: refusing {method} {url}")
        if params:
            sep = "&" if "?" in url else "?"
            url = f"{url}{sep}{urllib.parse.urlencode(params, doseq=True)}"
        hdrs = dict(headers or {})
        if json_body is not None:
            data = json.dumps(json_body).encode()
            hdrs.setdefault("Content-Type", "application/json")
        hdrs["Authorization"] = f"Bearer {oauth.get_access_token(self.store, self.email)}"

        for retry in range(MAX_RETRIES + 1):
            status, resp_headers, body = transport_mod.request(method, url,
                                                               headers=hdrs,
                                                               data=data)
            if status == 401:
                # Access token revoked or expired early: force a refresh and
                # retry once (does not count against the backoff budget).
                token = self.store.load_token(self.email) if self.email else None
                if token is not None:
                    token["expiry"] = 0
                    self.store.save_token(self.email, token)
                hdrs["Authorization"] = (
                    f"Bearer {oauth.get_access_token(self.store, self.email)}"
                )
                status, resp_headers, body = transport_mod.request(
                    method, url, headers=hdrs, data=data)
            if status not in RETRY_STATUSES or retry == MAX_RETRIES:
                break
            _sleep(_retry_delay(retry, resp_headers))
        if status >= 400:
            raise APIError(status,
                           _error_message(body) + _hint(status, body, url,
                                                        self.email))
        if raw:
            return body
        return json.loads(body) if body else {}

    def get(self, url, **kw):
        return self.request("GET", url, **kw)

    def post(self, url, **kw):
        return self.request("POST", url, **kw)

    def patch(self, url, **kw):
        return self.request("PATCH", url, **kw)

    def put(self, url, **kw):
        return self.request("PUT", url, **kw)

    def delete(self, url, **kw):
        return self.request("DELETE", url, **kw)

    # -- pagination ------------------------------------------------------------

    def paged(self, url: str, params: dict | None = None, key: str = "items",
              limit: int | None = None):
        """Yield items across pages, following nextPageToken, up to limit."""
        params = dict(params or {})
        count = 0
        while True:
            page = self.get(url, params=params)
            for item in page.get(key, []):
                yield item
                count += 1
                if limit is not None and count >= limit:
                    return
            token = page.get("nextPageToken")
            if not token:
                return
            params["pageToken"] = token


def _retry_delay(retry: int, headers: dict) -> int:
    """Seconds to wait before retry N (0-based): Retry-After wins, else 1/2/4."""
    for name, value in (headers or {}).items():
        if name.lower() == "retry-after":
            try:
                return int(value)
            except (TypeError, ValueError):
                break
    return 2 ** retry


def service_for_url(url: str) -> str:
    """The gsuite service name serving `url`, or "" if the host is unknown."""
    parts = urllib.parse.urlsplit(url)
    segments = parts.path.strip("/").split("/")
    # Try the most specific key first: host + full path, shortening a segment
    # at a time down to the bare host.
    for depth in range(len(segments), -1, -1):
        service = SERVICE_BY_HOST.get("/".join([parts.netloc, *segments[:depth]]))
        if service:
            return service
    return ""


def _login_command(email: str, service: str = "") -> str:
    """`gsuite auth login`, narrowed to the account/service when each is known."""
    parts = ["gsuite auth login"]
    if email:
        parts.append(email)
    if service:
        parts.append(f"--services {service}")
    return " ".join(parts)


def _hint(status: int, body: bytes, url: str, email: str) -> str:
    """The next step for errors a user can fix, appended to Google's own text.

    Google says what went wrong but never what to do about it: which of the
    services to re-authorize, or that a 403 can mean "API not enabled" rather
    than "wrong scopes". Statuses with no useful advice get nothing.
    """
    text = (body or b"").decode(errors="replace").lower()
    if status == 401:
        return (" — those credentials were rejected; run "
                f"`{_login_command(email)}` to sign in again")
    if status == 429:
        return (" — quota exceeded; the request was already retried with "
                "backoff, so wait before trying again or raise the quota in "
                "the Google Cloud console")
    if status == 403:
        if any(m in text for m in SCOPE_MARKERS):
            return (" — this token is missing the scopes for that call; "
                    f"re-authorize with "
                    f"`{_login_command(email, service_for_url(url))}`")
        if any(m in text for m in API_DISABLED_MARKERS):
            return (" — that API is not enabled for your project; enable it "
                    "in the Google Cloud console under APIs & Services")
    return ""


def _error_message(body: bytes) -> str:
    try:
        err = json.loads(body).get("error", {})
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)
    except (ValueError, AttributeError):
        return (body or b"")[:200].decode(errors="replace")
