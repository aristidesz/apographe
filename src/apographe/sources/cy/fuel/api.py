"""The fuel observatory's official API, served through CY Connect.

One POST per fuel type returns every station's price. The request and the
answer are XML; the call needs an OAuth 2.0 access token (see core/oauth.py).

Tables written (one file per run, ``api/YYYY/prices_YYYY-MM-DD_HHMM.csv.gz``)::

    fetched_at, fuel_type_id, fuel_type, company_code, company, station_code,
    station_name, phone, city, district, address, price, price_changed_at,
    lat, lon, offline
"""

from __future__ import annotations

import os
import re
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from typing import Any

import requests
from defusedxml import ElementTree as ET

from apographe.core.oauth import USER_AGENT, ClientCredentials
from apographe.core.source import SourceError

FUEL_TYPES = {
    1: "Unleaded 95",
    2: "Unleaded 98",
    3: "Diesel",
    4: "Heating diesel",
    5: "Kerosene",
}
FIELDS = [
    "fetched_at",
    "fuel_type_id",
    "fuel_type",
    "company_code",
    "company",
    "station_code",
    "station_name",
    "phone",
    "city",
    "district",
    "address",
    "price",
    "price_changed_at",
    "lat",
    "lon",
    "offline",
]
RETRY_STATUS = {429, 500, 502, 503, 504}
NS = {"m": "http://gateway.gov/schema/mcit/v1"}
DMS = re.compile(r"(\d+)°\s*(\d+)'\s*([\d.]+)\"?\s*([NSEW])")


@dataclass(frozen=True)
class Environment:
    name: str
    token_url: str
    api_url: str

    @property
    def folder(self) -> str:
        # Sandbox answers are test data. Keep them away from the real tables.
        return "api" if self.name == "production" else f"api-{self.name}"


ENVIRONMENTS = {
    "sandbox": Environment(
        "sandbox",
        "https://sandbox-apis.cyconnect.cyprus.gov.cy/auth/oauth/v2/token",
        "https://sandbox-apis.cyconnect.cyprus.gov.cy"
        "/legacysubmission/request/PBL_MCIT_Petrol_PricesMob",
    ),
    "production": Environment(
        "production",
        "https://apis.cyconnect.cyprus.gov.cy/auth/oauth/v2/token",
        "https://apis.cyconnect.cyprus.gov.cy"
        "/legacysubmission/request/PBL_MCIT_Petrol_PricesMob",
    ),
}


def settings_from_env(
    env: Mapping[str, str] | None = None,
) -> tuple[Environment, str, str]:
    """Which environment to call, and the client id and secret to call it with.

    CYCONNECT_ENV is ``sandbox`` (the default) or ``production``.
    """
    env = os.environ if env is None else env
    name = env.get("CYCONNECT_ENV", "sandbox").strip().lower()
    if name not in ENVIRONMENTS:
        raise SourceError("CYCONNECT_ENV must be 'sandbox' or 'production'")
    client_id = env.get("CYCONNECT_CLIENT_ID", "").strip()
    secret = env.get("CYCONNECT_CLIENT_SECRET", "").strip()
    if not client_id or not secret:
        raise SourceError(
            "set CYCONNECT_CLIENT_ID and CYCONNECT_CLIENT_SECRET "
            "(the credentials of your CY Connect application)"
        )
    return ENVIRONMENTS[name], client_id, secret


def build_request(fuel_type: int) -> str:
    """The XML body asking for one fuel in every city."""
    return (
        '<Message Version="string" xmlns="http://gateway.gov/schema/common/v1">'
        "<Header><Vendor>apographe</Vendor></Header>"
        "<Body>"
        '<PetroleumPriceRequestMob xmlns="http://gateway.gov/schema/mcit/v1">'
        f"<PetroleumType>{int(fuel_type)}</PetroleumType>"
        "</PetroleumPriceRequestMob>"
        "</Body></Message>"
    )


class FuelApi:
    def __init__(
        self,
        environment: Environment,
        credentials: ClientCredentials,
        *,
        session: requests.Session | None = None,
        min_interval: float = 2.0,
        retries: int = 3,
        backoff: float = 10.0,
        timeout: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.environment = environment
        self.credentials = credentials
        self.session = session or requests.Session()
        self.min_interval = min_interval
        self.retries = retries
        self.backoff = backoff
        self.timeout = timeout
        self._sleep = sleep
        self._called = False

    def prices(self, fuel_type: int, fetched_at: str) -> list[dict[str, Any]]:
        """Every station's price for one fuel, as table rows."""
        return parse_response(
            self._post(build_request(fuel_type)), fetched_at, fuel_type
        )

    def _post(self, body: str) -> str:
        last = ""
        refreshed = False
        for attempt in range(self.retries + 1):
            if attempt:
                self._sleep(self.backoff * attempt)
            elif self._called:
                self._sleep(self.min_interval)
            self._called = True
            try:
                resp = self.session.post(
                    self.environment.api_url,
                    data=body.encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {self.credentials.token()}",
                        "Content-Type": "application/xml",
                        "Accept": "application/xml",
                        "User-Agent": USER_AGENT,
                    },
                    timeout=self.timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                last = type(exc).__name__
                continue
            if resp.status_code == 401 and not refreshed:
                # The token may have been revoked or expired early: ask once more.
                refreshed = True
                self.credentials.forget()
                last = "HTTP 401"
                continue
            if resp.status_code == 401:
                raise SourceError(
                    "the API refused a fresh token (HTTP 401): has CDS approved "
                    "this application for the fuel API in this environment?"
                )
            if resp.status_code in RETRY_STATUS:
                last = f"HTTP {resp.status_code}"
                continue
            if resp.status_code != 200:
                raise SourceError(f"the fuel API answered HTTP {resp.status_code}")
            return resp.text
        raise SourceError(f"the fuel API failed {self.retries + 1} times: {last}")


def parse_response(
    xml_text: str, fetched_at: str, fuel_type: int
) -> list[dict[str, Any]]:
    try:
        root = ET.fromstring(xml_text.lstrip("﻿").encode("utf-8"))
    except ET.ParseError as exc:
        raise SourceError("the fuel API did not return valid XML") from exc
    reply = root.find(".//m:PetroleumPriceResponseMob", NS)
    if reply is None:
        raise SourceError("the fuel API's answer has no PetroleumPriceResponseMob")
    if reply.get("Success", "").lower() != "true":
        raise SourceError(f"the fuel API reported an error (code {reply.get('Code')})")
    fuel_name = _text(reply, "PetroleumType")
    rows = []
    for item in reply.iterfind(".//m:PetroleumPriceDetails1", NS):
        lat, lon = coordinates(_text(item, "map_coordinates"))
        rows.append(
            {
                "fetched_at": fetched_at,
                "fuel_type_id": fuel_type,
                "fuel_type": fuel_name,
                "company_code": _text(item, "FuelCompanyCode"),
                "company": _text(item, "fuel_company_name"),
                "station_code": _text(item, "station_code"),
                "station_name": _text(item, "station_name").strip('"').strip(),
                "phone": _text(item, "station_tel_no"),
                "city": _text(item, "station_city"),
                "district": _text(item, "station_district"),
                "address": _text(item, "station_address1"),
                "price": _text(item, "Fuel_Price"),
                "price_changed_at": _text(item, "price_modification_date"),
                "lat": lat,
                "lon": lon,
                "offline": _text(item, "isOffLine").lower(),
            }
        )
    return rows


def coordinates(text: str) -> tuple[float | str, float | str]:
    """``"34.77,32.42"`` or ``34°39'13.5"N 32°58'26.3"E`` -> (lat, lon); else blanks."""
    if "°" in text:
        parts = DMS.findall(text)
        if len(parts) == 2:
            values = []
            for deg, minutes, seconds, hemi in parts:
                value = int(deg) + int(minutes) / 60 + float(seconds) / 3600
                values.append(round(-value if hemi in "SW" else value, 6))
            return values[0], values[1]
        return "", ""
    try:
        lat, lon = (float(part) for part in text.split(","))
    except ValueError:
        return "", ""
    return round(lat, 6), round(lon, 6)


def _text(parent: Any, tag: str) -> str:
    node = parent.find(f"m:{tag}", NS)
    if node is None or node.text is None:
        return ""
    return re.sub(r"\s+", " ", node.text).strip()


def collect(
    api: FuelApi,
    fuel_types: Iterable[int],
    fetched_at: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for fuel_type in fuel_types:
        rows.extend(api.prices(fuel_type, fetched_at))
    return rows
