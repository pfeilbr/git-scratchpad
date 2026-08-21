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

SERVER_ERROR_STATUSES = {500, 502, 503, 504}
RETRY_STATUSES = {429, *SERVER_ERROR_STATUSES}
MAX_RETRIES = 3

# Methods that are idempotent by definition: sending one twice leaves the same
# state behind as sending it once, so a reply lost in transit costs only a
# second round trip. POST and PATCH are deliberately absent.
IDEMPOTENT_METHODS = {"GET", "HEAD", "PUT", "DELETE"}

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
    "classroom.googleapis.com": "classroom",
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
            if not _should_retry(method, status) or retry == MAX_RETRIES:
                break
            _sleep(_retry_delay(retry, resp_headers))
        if status >= 400:
            raise APIError(status,
                           _error_message(body) + _hint(status, body, url,
                                                        self.email, method))
        if raw:
            return body
        return _parse_json(body, status, url)

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


def _should_retry(method: str, status: int) -> bool:
    """Whether a failed request may be sent again.

    Splitting 429 from 5xx is deliberate — please do not "simplify" it back
    into one status set. The two say opposite things about what the server
    already did:

    * 429 is a *rejection*. Google refused the request before running any of
      it, so nothing happened and replaying it cannot duplicate anything.
      Retrying with backoff is safe for every method, and is exactly what
      Google's own rate-limit guidance asks clients to do.
    * 5xx is *unknown*. The request may well have been applied and only the
      response lost on the way back. Replaying a non-idempotent method then
      sends the same mail a second time, creates a duplicate calendar event,
      or adds a group member twice — silent damage the user never asked for.
      So a 5xx is retried only for methods that are idempotent by definition.

    A 401 is neither: it is handled separately in `Client.request`, which
    refreshes the token and retries once for every method, because rejected
    credentials mean the request never reached the handler at all.
    """
    if status == 429:
        return True
    return (status in SERVER_ERROR_STATUSES
            and method.upper() in IDEMPOTENT_METHODS)


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


def _hint(status: int, body: bytes, url: str, email: str,
          method: str = "GET") -> str:
    """The next step for errors a user can fix, appended to Google's own text.

    Google says what went wrong but never what to do about it: which of the
    services to re-authorize, or that a 403 can mean "API not enabled" rather
    than "wrong scopes". Statuses with no useful advice get nothing.
    """
    text = (body or b"").decode(errors="replace").lower()
    if status in SERVER_ERROR_STATUSES and not _should_retry(method, status):
        # The one case where the client's *inaction* needs explaining: the
        # user must decide whether to re-run it, and only they know whether a
        # duplicate would matter.
        return (f" — the request was not retried because replaying a "
                f"{method.upper()} could duplicate the operation; it may or "
                "may not have been applied, so check before sending it again")
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


def _parse_json(body: bytes, status: int, url: str):
    """The response body as a dict — or a CLIError naming what arrived instead.

    Every typed command reads fields off this dict, so it has to be JSON. But
    a 2xx is no guarantee that it is: a captive portal answers any URL with a
    sign-in page, a corporate proxy substitutes a block notice, a load
    balancer in front of a dead backend replies `ok` in plain text. Each of
    those is a 200 whose body `json.loads` cannot read, and the bare call
    raised JSONDecodeError past main()'s handler as a traceback.

    The excerpt matters as much as the message. "Expected JSON" alone leaves
    the user guessing between a Google outage and their own network; the
    first line of the body usually says which, because a captive portal
    signs its work.
    """
    if not body:
        return {}
    try:
        return json.loads(body)
    except ValueError as exc:
        raise CLIError(
            f"{status} response from {urllib.parse.urlsplit(url).netloc} was "
            f"not JSON: {_excerpt(body)} — this is usually a proxy or captive "
            "portal answering instead of Google") from exc


def _excerpt(body: bytes, limit: int = 200) -> str:
    """A one-line, printable sample of a body that is not what we expected."""
    text = body[:limit].decode(errors="replace")
    return " ".join(text.split()) + ("…" if len(body) > limit else "")


def _error_message(body: bytes) -> str:
    try:
        err = json.loads(body).get("error", {})
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)
    except (ValueError, AttributeError):
        return (body or b"")[:200].decode(errors="replace")
