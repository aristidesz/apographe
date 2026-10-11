"""Turn e-kalathi responses into table rows. Pure functions, no network.

Tables (ids join them):

    products        product_id, code, name, category, category_en, category_id
    catalogue       date, product_id, price, previous_price, store_count
    store_prices    date, product_id, store_id, price, price_before_offer, on_offer
    stores          store_id, name, chain_id, chain, phone, address, postcode,
                    region_id, lat, lon, last_seen
    chains          chain_id, name
    regions         region_id, name
    categories      category_id, code, name, name_en, parent_id
    history         date, product_id, price
"""

from __future__ import annotations

import html
import re
from collections.abc import Iterable
from typing import Any

PRODUCT_FIELDS = [
    "product_id",
    "code",
    "name",
    "category",
    "category_en",
    "category_id",
]
CATALOGUE_FIELDS = ["date", "product_id", "price", "previous_price", "store_count"]
STORE_PRICE_FIELDS = [
    "date",
    "product_id",
    "store_id",
    "price",
    "price_before_offer",
    "on_offer",
]
STORE_FIELDS = [
    "store_id",
    "name",
    "chain_id",
    "chain",
    "phone",
    "address",
    "postcode",
    "region_id",
    "lat",
    "lon",
    "last_seen",
]
CHAIN_FIELDS = ["chain_id", "name"]
REGION_FIELDS = ["region_id", "name"]
CATEGORY_FIELDS = ["category_id", "code", "name", "name_en", "parent_id"]
HISTORY_FIELDS = ["date", "product_id", "price"]

# Cyprus postcodes by first digit -> the site's region ids
# (1 Λευκωσία, 2 Λάρνακα, 3 Λεμεσός, 4 Πάφος, 5 Αμμόχωστος).
REGION_BY_POSTCODE = {"1": 1, "2": 1, "3": 3, "4": 3, "5": 5, "6": 2, "7": 2, "8": 4}
# For the few addresses without a postcode ("Μαρίνα Λεμεσού").
REGION_BY_TOWN = {
    "λευκωσ": 1,
    "κοκκινοτριμιθ": 1,
    "λάρνακ": 2,
    "λαρνακ": 2,
    "λεμεσ": 3,
    "πάφ": 4,
    "παφ": 4,
    "αμμόχωστ": 5,
    "παραλίμν": 5,
    "αγία νάπα": 5,
}
POSTCODE = re.compile(r"(?<!\d)(\d{4})(?!\d)")
DMS = re.compile(r"(\d+)°(\d+)'([\d.]+)\"?\s*([NSEW])")


def clean(text: Any) -> str:
    """Names arrive with HTML entities and stray spaces ("WOLT MARKET&nbsp;")."""
    if text is None:
        return ""
    text = html.unescape(str(text)).replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def product_rows(
    products: Iterable[dict[str, Any]], category_ids: dict[tuple[str, str], int]
) -> list[dict[str, Any]]:
    rows = []
    for p in products:
        key = (
            clean(p.get("productCategoryName")),
            clean(p.get("productCategoryNameEnglish")),
        )
        rows.append(
            {
                "product_id": p["productMasterId"],
                "code": p.get("code"),
                "name": clean(p.get("name")),
                "category": key[0],
                "category_en": key[1],
                "category_id": category_ids.get(key, ""),
            }
        )
    return rows


def catalogue_rows(
    day: str, products: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Today's cheapest price in Cyprus per product.

    ``store_count`` is the site's ``numberOfChains``, which in fact counts stores.
    """
    return [
        {
            "date": day,
            "product_id": p["productMasterId"],
            "price": p.get("startPrice"),
            "previous_price": p.get("previousPrice"),
            "store_count": p.get("numberOfChains"),
        }
        for p in products
    ]


def chain_rows(chains: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{"chain_id": c["id"], "name": clean(c.get("name"))} for c in chains]


def region_rows(regions: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        ({"region_id": r["id"], "name": clean(r.get("name"))} for r in regions),
        key=lambda r: r["region_id"],
    )


def category_rows(groups: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Groups and their sub-categories in one table; sub-categories point up."""
    rows = []
    for g in groups:
        rows.append(_category(g, parent=""))
        for sub in g.get("productCategoryResponses") or []:
            rows.append(_category(sub, parent=g["id"]))
    return rows


def _category(c: dict[str, Any], parent: Any) -> dict[str, Any]:
    return {
        "category_id": c["id"],
        "code": c.get("code"),
        "name": clean(c.get("name")),
        "name_en": clean(c.get("nameEnglish")),
        "parent_id": parent,
    }


def category_lookup(rows: Iterable[dict[str, Any]]) -> dict[tuple[str, str], int]:
    """(Greek name, English name) -> id. Products name their category, not its id.

    Sub-categories win over a group with the same names, since products sit in
    sub-categories.
    """
    lookup: dict[tuple[str, str], int] = {}
    for row in sorted(rows, key=lambda r: r["parent_id"] != ""):
        lookup[(row["name"], row["name_en"])] = row["category_id"]
    return lookup


def chain_lookup(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Chain name -> id. Store rows give the chain by name only."""
    return {row["name"].casefold(): row["chain_id"] for row in rows}


def postcode(address: str) -> str:
    """The last four-digit number in an address, or "" when it has none."""
    found = POSTCODE.findall(address or "")
    return found[-1] if found else ""


def region_for(code: str, address: str = "") -> int | str:
    """Region id from the postcode, else from a town named in the address."""
    if code:
        return REGION_BY_POSTCODE.get(code[:1], "")
    lowered = address.casefold()
    for stem, region in REGION_BY_TOWN.items():
        if stem in lowered:
            return region
    return ""


def dms_to_decimal(text: str | None) -> float | str:
    """34°38'39.0"N -> 34.6442. Returns "" when the text is not in that form."""
    m = DMS.search(text or "")
    if not m:
        return ""
    value = int(m[1]) + int(m[2]) / 60 + float(m[3]) / 3600
    return round(-value if m[4] in "SW" else value, 6)


def store_rows(
    day: str, branches: Iterable[dict[str, Any]], chain_ids: dict[str, Any]
) -> list[dict[str, Any]]:
    rows = []
    for b in branches:
        chain = clean(b.get("companyName"))
        address = clean(b.get("postalAddress"))
        code = postcode(address)
        rows.append(
            {
                "store_id": b["id"],
                "name": clean(b.get("name")),
                "chain_id": chain_ids.get(chain.casefold(), ""),
                "chain": chain,
                "phone": clean(b.get("landPhone")),
                "address": address,
                "postcode": code,
                "region_id": region_for(code, address),
                "lat": dms_to_decimal(b.get("branchLatitude")),
                "lon": dms_to_decimal(b.get("branchLongitude")),
                "last_seen": day,
            }
        )
    return rows


def store_price_rows(
    day: str, product_id: Any, branches: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {
            "date": day,
            "product_id": product_id,
            "store_id": b["id"],
            "price": b.get("retailerProductPrice"),
            "price_before_offer": b.get("retailerInitialProductPrice"),
            "on_offer": bool(b.get("isInOfferOrDiscount")),
        }
        for b in branches
    ]


def history_rows(
    product_id: Any, series: Iterable[dict[str, Any]]
) -> list[dict[str, Any]]:
    return [
        {"date": point["date"], "product_id": product_id, "price": point["price"]}
        for point in series
        if point.get("date") and point.get("price") is not None
    ]
