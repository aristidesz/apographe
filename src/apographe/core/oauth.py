"""OAuth 2.0 client-credentials sign-in, for sources that sit behind a gateway.

The client id and secret identify a program, not a person. They are exchanged
for a short-lived access token, which is kept and reused until it is about to
expire (gateways ask clients not to fetch a new token for every call).
"""

from __future__ import annotations

import time
from collections.abc import Callable

import requests

from apographe import __version__
from apographe.core.source import SourceError

USER_AGENT = f"apographe/{__version__} (+https://github.com/aristidesz/apographe)"
EARLY = 60.0  # seconds before expiry at which a token is replaced


class ClientCredentials:
    def __init__(
        self,
        token_url: str,
        client_id: str,
        client_secret: str,
        *,
        session: requests.Session | None = None,
        clock: Callable[[], float] = time.monotonic,
        timeout: float = 30.0,
    ) -> None:
        self.token_url = token_url
        self._id = client_id
        self._secret = client_secret
        self.session = session or requests.Session()
        self._clock = clock
        self.timeout = timeout
        self._token: str | None = None
        self._expires = 0.0

    def __repr__(self) -> str:
        # Never show the secret, even in a traceback or a log line.
        return f"ClientCredentials(token_url={self.token_url!r}, client_id=...)"

    def token(self) -> str:
        """The current access token, fetched only when there is none or it expired."""
        if self._token is None or self._clock() >= self._expires:
            self._token = self._fetch()
        return self._token

    def forget(self) -> None:
        """Drop the token, e.g. after the API refused it."""
        self._token = None

    def _fetch(self) -> str:
        try:
            resp = self.session.post(
                self.token_url,
                data={"grant_type": "client_credentials"},
                auth=(self._id, self._secret),
                headers={"Accept": "application/json", "User-Agent": USER_AGENT},
                timeout=self.timeout,
            )
        except (requests.ConnectionError, requests.Timeout) as exc:
            raise SourceError(f"the token server was unreachable: {exc!r}") from exc
        if resp.status_code in (400, 401):
            raise SourceError(
                f"the token server refused the client id and secret "
                f"(HTTP {resp.status_code}); check them and the environment"
            )
        if resp.status_code != 200:
            raise SourceError(f"the token server answered HTTP {resp.status_code}")
        try:
            body = resp.json()
            token = str(body["access_token"])
            lifetime = float(body.get("expires_in", 3600))
        except (ValueError, KeyError, TypeError) as exc:
            raise SourceError("the token server's answer had no access_token") from exc
        self._expires = self._clock() + max(lifetime - EARLY, 0.0)
        return token
