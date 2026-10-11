"""e-kalathi source, offline: fixtures are trimmed copies of real responses
(October 2026), with the chain logos cut down to a placeholder."""

import gzip
import json
from datetime import date
from pathlib import Path

import pytest

from apographe.core.source import Options, SourceError
from apographe.core.storage import Store
from apographe.sources.cy.ekalathi import EkalathiSource, parse
from apographe.sources.cy.ekalathi.client import EkalathiClient

FIXTURES = Path(__file__).parents[2] / "fixtures" / "ekalathi"
DAY = date(2026, 10, 9)


def fixture(name):
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


class FakeHTTP:
    """Answers like the site, from fixtures, and records every call."""

    def __init__(self, fail_history_for=()):
        self.calls = []
        self.fail_history_for = {str(x) for x in fail_history_for}

    def get_json(self, path, params=None):
        params = params or {}
        self.calls.append((path, dict(params)))
        if path == "/fetch-product-list":
            return fixture(f"product_list_page{params['page']}")
        if path == "/retail/fetch-retail-branch-list":
            # Every product is "sold" in the same stores; enough for these tests.
            return fixture("store_prices_2074")
        if path == "/fetch-product-price-diagram":
            if str(params["id"]) in self.fail_history_for:
                raise SourceError("HTTP 502")
            return fixture("history_2074")
        return fixture(
            {
                "/fetch-companies": "companies",
                "/fetch-regions": "regions",
                "/fetch-product-categories": "categories",
            }[path]
        )

    def count(self, path):
        return sum(1 for p, _ in self.calls if p == path)


@pytest.fixture
def http():
    return FakeHTTP()


@pytest.fixture
def source(http):
    return EkalathiSource(client=EkalathiClient(http=http))


@pytest.fixture
def out(tmp_path):
    return Store(tmp_path).scope("cy/ekalathi")


def read_gz_csv(path):
    with gzip.open(path, "rt", encoding="utf-8") as fh:
        return fh.read().splitlines()


# -- client ---------------------------------------------------------------


def test_product_list_follows_every_page(http):
    products = EkalathiClient(http=http).products()
    assert [p["productMasterId"] for p in products] == [2074, 1906, 26]
    assert http.count("/fetch-product-list") == 2


def test_store_prices_drop_the_logo(http):
    rows = EkalathiClient(http=http).store_prices(2074)
    assert rows and all("companyPhotoFile" not in r for r in rows)
    assert all("retailerProductPrice" in r for r in rows)


# -- parsing --------------------------------------------------------------


@pytest.mark.parametrize(
    "address, code, region",
    [
        ("Δρόμος Ακρωτήρι, 4640 Κολόσσι", "4640", 3),
        ("Τζων Κέννεντυ 26,1046 Παλουριώτισσα", "1046", 1),
        ("Αρχιεπισκόπου Μακαρίου 233Β, 3105 Λεμεσός", "3105", 3),
        ("Βαρωσίων 101 5522 Αμμόχωστος ", "5522", 5),
        ("12ο  χιλιόμετρο Κοκκινοτριμιθιάς", "", 1),
        ("Μαρίνα Λεμεσού", "", 3),
        ("Somewhere", "", ""),
    ],
)
def test_region_comes_from_the_postcode_or_the_town(address, code, region):
    assert parse.postcode(address) == code
    assert parse.region_for(code, address) == region


def test_coordinates_turn_into_decimals():
    assert parse.dms_to_decimal("34°38'39.0\"N") == pytest.approx(34.644167)
    assert parse.dms_to_decimal("32°56'41.2\"E") == pytest.approx(32.944778)
    assert parse.dms_to_decimal("") == ""


def test_names_lose_html_entities_and_stray_spaces():
    assert parse.clean("WOLT MARKET&nbsp;") == "WOLT MARKET"
    assert parse.clean("ΠΑΦΟΣ ") == "ΠΑΦΟΣ"


def test_products_get_their_sub_category_id():
    lookup = parse.category_lookup(parse.category_rows(fixture("categories")))
    products = fixture("product_list_page0")["content"][:1]
    (row,) = parse.product_rows(products, lookup)
    assert (row["product_id"], row["name"], row["category_id"]) == (
        2074,
        "Kykkos 500ml",
        87,  # ΝΕΡΟ, under ΜΗ ΑΛΚΟΛΟΥΧΑ ΠΟΤΑ (86)
    )


# -- jobs -----------------------------------------------------------------


def run(source, out, job, **kw):
    return source.run(job, out, Options(day=DAY, **kw))


def test_daily_jobs_write_every_table(source, out, http):
    for job in source.default_jobs:
        run(source, out, job)

    catalogue = read_gz_csv(out.path("catalogue/2026/2026-10-09.csv.gz"))
    assert catalogue[0] == "date,product_id,price,previous_price,store_count"
    assert "2026-10-09,2074,0.25,0.23,115" in catalogue

    prices = read_gz_csv(out.path("store_prices/2026/2026-10-09.csv.gz"))
    assert len(prices) == 1 + 3 * 5  # header + 3 products x 5 stores
    assert "2026-10-09,2074,539,0.25,0.25,False" in prices
    assert not out.exists("store_prices/2026/2026-10-09.partial.csv")

    stores = {r["store_id"]: r for r in out.read_csv("stores.csv")}
    assert stores["539"]["chain"] == "ALPHA SIGMA"
    assert stores["539"]["chain_id"] == "452"
    assert stores["539"]["region_id"] == "3"
    assert stores["562"]["chain_id"] == "452"  # LITSA'S, listed under ALPHA SIGMA
    assert stores["686"]["region_id"] == "1"  # no postcode; the town says Nicosia

    assert out.exists("raw/catalogue/2026/2026-10-09.json.gz")
    assert {r["name"] for r in out.read_csv("chains.csv")} >= {"WOLT MARKET"}
    # The store prices reuse today's catalogue instead of asking again.
    assert http.count("/fetch-product-list") == 2


def test_store_prices_resume_where_they_stopped(source, out, http):
    run(source, out, "catalogue")
    out.append_csv(
        "store_prices/2026/2026-10-09.partial.csv",
        [{"date": "2026-10-09", "product_id": "26", "store_id": "1", "price": 1}],
        parse.STORE_PRICE_FIELDS,
    )
    run(source, out, "store-prices")
    fetched = [p["productId"] for path, p in http.calls if "branch-list" in path]
    assert fetched == ["2074", "1906"]


def test_a_collected_day_is_not_fetched_twice(source, out, http):
    run(source, out, "catalogue")
    run(source, out, "store-prices", limit=1)
    run(source, out, "store-prices")
    assert http.count("/retail/fetch-retail-branch-list") == 1


def test_history_keeps_what_worked_and_reports_the_rest(out):
    http = FakeHTTP(fail_history_for=[1906])
    source = EkalathiSource(client=EkalathiClient(http=http))
    with pytest.raises(SourceError, match="1 of 3 products failed"):
        run(source, out, "history")
    assert out.exists("history/2074.csv") and out.exists("history/26.csv")
    assert not out.exists("history/1906.csv")

    http.fail_history_for.clear()
    run(source, out, "history")
    assert http.count("/fetch-product-price-diagram") == 4  # 3, then only 1906
    rows = out.read_csv("history/1906.csv")
    assert rows[-1] == {"date": "2026-10-10", "product_id": "1906", "price": "0.25"}
