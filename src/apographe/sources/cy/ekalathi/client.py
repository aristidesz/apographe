"""The e-kalathi website's own backend: the JSON requests its pages make.

It is not a published API, so it can change without notice. Every call here
was checked against the live site in October 2026; none needs a login.
Paged calls use Spring paging (``page`` from 0, ``size``, ``sort``) and wrap
their rows in ``{"content": [...], "last": bool, ...}``.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from apographe.core.http import PoliteClient
from apographe.core.source import SourceError

BASE_URL = "https://www.e-kalathi.gov.cy/ekalathi-website-server/api"
# Each store row repeats the chain's logo as base64 (~100 KB). Dropped on arrival.
HEAVY_FIELDS = ("companyPhotoFile", "companyPhotoFileName", "companyPhotoFileType")
# The site's own price charts start here; data actually begins on 2025-09-03.
HISTORY_START = date(2025, 6, 12)


class EkalathiClient:
    def __init__(self, http: PoliteClient | None = None, delay: float = 3.0) -> None:
        # The price history call takes ~30 s and the site's proxy gives up at
        # 30 s, so about half fail at first: retry generously.
        self.http = http or PoliteClient(
            BASE_URL, min_interval=delay, timeout=90, retries=4, backoff=10
        )

    def products(self) -> list[dict[str, Any]]:
        """Every product with its cheapest price in Cyprus today (~476, 5 pages)."""
        return self._pages("/fetch-product-list", {}, size=100)

    def store_prices(self, product_id: int | str) -> list[dict[str, Any]]:
        """Every store selling the product, with its price there today."""
        rows = self._pages(
            "/retail/fetch-retail-branch-list", {"productId": product_id}, size=200
        )
        for row in rows:
            for key in HEAVY_FIELDS:
                row.pop(key, None)
        return rows

    def price_history(
        self,
        product_id: int | str,
        start: date = HISTORY_START,
        end: date | None = None,
        chain_id: int | str | None = None,
        region_id: int | str | None = None,
    ) -> list[dict[str, Any]]:
        """Daily ``[{date, price}]``: the cheapest in Cyprus, or one chain/region."""
        params: dict[str, Any] = {
            "id": product_id,
            "from": start.isoformat(),
            "to": (end or date.today()).isoformat(),
        }
        if chain_id is not None:
            params["cId"] = chain_id
        if region_id is not None:
            params["rId"] = region_id
        series = self.http.get_json("/fetch-product-price-diagram", params)
        if not isinstance(series, list):
            raise SourceError("price history is not a list")
        return series

    def chains(self) -> list[dict[str, Any]]:
        return self._list("/fetch-companies")

    def regions(self) -> list[dict[str, Any]]:
        return self._list("/fetch-regions")

    def categories(self) -> list[dict[str, Any]]:
        return self._list("/fetch-product-categories")

    def _list(self, path: str) -> list[dict[str, Any]]:
        payload = self.http.get_json(path)
        if not isinstance(payload, list):
            raise SourceError(f"{path} is not a list")
        return payload

    def _pages(
        self, path: str, params: dict[str, Any], size: int
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        page = 0
        while True:
            payload = self.http.get_json(
                path, {**params, "page": page, "size": size, "sort": "DEFAULT,ASC"}
            )
            if not isinstance(payload, dict) or "content" not in payload:
                raise SourceError(f"{path} page {page} has no 'content'")
            rows.extend(payload["content"])
            if payload.get("last", True) or not payload["content"]:
                return rows
            page += 1
