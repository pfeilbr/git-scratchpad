"""Authorized Google API client: JSON, params, pagination, 401 retry, backoff."""
from __future__ import annotations

import json
import time
import urllib.parse

import gsuite.transport as transport_mod
from gsuite import oauth
from gsuite.config import ConfigStore
from gsuite.errors import APIError

# Seam for tests: monkeypatch gsuite.api._sleep to observe delays without waiting.
_sleep = time.sleep

RETRY_STATUSES = {429, 500, 502, 503, 504}
MAX_RETRIES = 3


def quote_id(value: str) -> str:
    """Percent-encode an id/email for safe use as a URL path segment."""
    return urllib.parse.quote(value, safe="")


class Client:
    def __init__(self, store: ConfigStore, email: str):
        self.store = store
        self.email = email

    @classmethod
    def for_args(cls, args) -> "Client":
        store = ConfigStore()
        return cls(store, store.resolve(getattr(args, "account", None)))

    # -- core ----------------------------------------------------------------

    def request(self, method: str, url: str, params: dict | None = None,
                json_body=None, data: bytes | None = None,
                headers: dict | None = None, raw: bool = False):
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
                token = self.store.load_token(self.email) or {}
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
            raise APIError(status, _error_message(body))
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


def _error_message(body: bytes) -> str:
    try:
        err = json.loads(body).get("error", {})
        if isinstance(err, dict):
            return err.get("message") or str(err)
        return str(err)
    except (ValueError, AttributeError):
        return (body or b"")[:200].decode(errors="replace")
