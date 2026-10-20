"""A polite JSON client: one request at a time, spaced out, retried when the
server stumbles, and clear about it when a site starts asking for a login."""

from __future__ import annotations

import time
from collections.abc import Callable, Mapping
from typing import Any
from urllib.parse import urlsplit

import requests

from apographe._version import __version__
from apographe.core.source import LoginWall, SourceError

USER_AGENT = f"apographe/{__version__} (+https://github.com/aristidesz/apographe)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class PoliteClient:
    """Fetch JSON from one site, politely.

    Waits ``min_interval`` seconds between requests, retries 429 and 5xx answers
    with a growing pause, and raises ``LoginWall`` if the site asks for a login.
    """

    def __init__(
        self,
        base_url: str,
        *,
        min_interval: float = 3.0,
        timeout: float = 60.0,
        retries: int = 3,
        backoff: float = 10.0,
        session: requests.Session | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.min_interval = min_interval
        self.timeout = timeout
        self.retries = retries
        self.backoff = backoff
        self.session = session or requests.Session()
        self.session.headers.setdefault("User-Agent", USER_AGENT)
        self.session.headers["Accept"] = "application/json"
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None

    def get_json(self, path: str, params: Mapping[str, Any] | None = None) -> Any:
        """GET ``base_url + path`` and decode the JSON, retrying server errors.

        Raises LoginWall when the site answers 401/403 or redirects elsewhere
        (typically to a login page), and SourceError when retries run out.
        """
        url = f"{self.base_url}{path}"
        last_error = ""
        for attempt in range(self.retries + 1):
            if attempt:
                self._sleep(self.backoff * attempt)
            self._wait()
            try:
                resp = self.session.get(url, params=params, timeout=self.timeout)
            except (requests.ConnectionError, requests.Timeout) as exc:
                last_error = type(exc).__name__
                continue
            if resp.status_code in (401, 403) or _left_site(url, resp.url):
                raise LoginWall(f"{path} answered {resp.status_code} at {resp.url}")
            if resp.status_code in RETRY_STATUS:
                last_error = f"HTTP {resp.status_code}"
                continue
            if resp.status_code != 200:
                raise SourceError(f"{path} answered HTTP {resp.status_code}")
            try:
                return resp.json()
            except ValueError as exc:
                kind = resp.headers.get("Content-Type", "unknown content")
                raise SourceError(f"{path} did not return JSON ({kind})") from exc
        raise SourceError(f"{path} failed {self.retries + 1} times: {last_error}")

    def _wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            gap = self.min_interval - (now - self._last)
            if gap > 0:
                self._sleep(gap)
        self._last = self._clock()


def _left_site(requested: str, final: str | None) -> bool:
    if not final:
        return False
    return urlsplit(requested).netloc != urlsplit(final).netloc
