"""Cyprus supermarket prices from e-kalathi.gov.cy, the government's price
comparison site: every product, in every store, every day.

Files written (under ``cy/ekalathi/``)::

    chains.csv  regions.csv  categories.csv        lookups, refreshed by `lookups`
    products.csv                                   latest product list
    catalogue/YYYY/YYYY-MM-DD.csv.gz               cheapest price per product
    raw/catalogue/YYYY/YYYY-MM-DD.json.gz          the untouched product list
    store_prices/YYYY/YYYY-MM-DD.csv.gz            price per product per store
    stores.csv                                     every store seen, with its chain
    history/<product_id>.csv                       daily cheapest since Sep 2025
"""

from __future__ import annotations

from typing import Any

from apographe.core.source import Options, Report, Source, SourceError
from apographe.core.storage import Store
from apographe.sources.cy.ekalathi import parse
from apographe.sources.cy.ekalathi.client import EkalathiClient

PROGRESS_EVERY = 50


class EkalathiSource(Source):
    id = "cy.ekalathi"
    title = "Cyprus supermarket prices in every store (e-kalathi.gov.cy)"
    country = "CY"
    homepage = "https://www.e-kalathi.gov.cy"
    timezone = "Asia/Nicosia"
    jobs = {
        "lookups": "chains, regions and categories (3 requests)",
        "catalogue": "every product with its cheapest price today (~5 requests)",
        "store-prices": "every store's price for every product (1 request each)",
        "history": "daily cheapest price per product since Sep 2025 (resumable)",
    }
    default_jobs = ("lookups", "catalogue", "store-prices")

    def __init__(self, client: EkalathiClient | None = None) -> None:
        self._client = client

    def client(self, options: Options) -> EkalathiClient:
        if self._client is None:
            self._client = EkalathiClient(
                delay=3.0 if options.delay is None else options.delay
            )
        return self._client

    def run(self, job: str, out: Store, options: Options) -> Report:
        handler = {
            "lookups": self._lookups,
            "catalogue": self._catalogue,
            "store-prices": self._store_prices,
            "history": self._history,
        }[job]
        return handler(self.client(options), out, options)

    # -- jobs --------------------------------------------------------------

    def _lookups(self, client: EkalathiClient, out: Store, options: Options) -> Report:
        report = Report()
        for table, rows, fields in (
            ("chains", parse.chain_rows(client.chains()), parse.CHAIN_FIELDS),
            ("regions", parse.region_rows(client.regions()), parse.REGION_FIELDS),
            (
                "categories",
                parse.category_rows(client.categories()),
                parse.CATEGORY_FIELDS,
            ),
        ):
            path, count = out.write_csv(f"{table}.csv", rows, fields)
            report.add(table, count, path)
        return report

    def _catalogue(
        self, client: EkalathiClient, out: Store, options: Options
    ) -> Report:
        day = options.day.isoformat()
        year = day[:4]
        products = client.products()
        if not products:
            raise SourceError("the product list came back empty")
        report = Report()
        report.files.append(
            out.write_json(f"raw/catalogue/{year}/{day}.json.gz", products)
        )
        path, count = out.write_csv(
            f"catalogue/{year}/{day}.csv.gz",
            parse.catalogue_rows(day, products),
            parse.CATALOGUE_FIELDS,
        )
        report.add("catalogue", count, path)
        categories = out.read_csv("categories.csv") or parse.category_rows(
            client.categories()
        )
        path, count = out.write_csv(
            "products.csv",
            parse.product_rows(products, parse.category_lookup(categories)),
            parse.PRODUCT_FIELDS,
        )
        report.add("products", count, path)
        return report

    def _store_prices(
        self, client: EkalathiClient, out: Store, options: Options
    ) -> Report:
        day = options.day.isoformat()
        final = f"store_prices/{day[:4]}/{day}.csv.gz"
        partial = f"store_prices/{day[:4]}/{day}.partial.csv"
        report = Report()
        if out.exists(final) and not options.force:
            print(f"store-prices: {day} is already collected (use --force to redo)")
            return report
        if options.force:
            out.path(partial).unlink(missing_ok=True)

        done = {row["product_id"] for row in out.read_csv(partial)}
        ids = self._product_ids(client, out, options)
        chains = out.read_csv("chains.csv") or parse.chain_rows(client.chains())
        chain_ids = parse.chain_lookup(chains)
        stores: dict[str, dict[str, Any]] = {
            r["store_id"]: r for r in out.read_csv("stores.csv")
        }

        todo = [pid for pid in ids if pid not in done]
        if done:
            print(f"store-prices: resuming, {len(done)} products already done")
        for i, pid in enumerate(todo, 1):
            branches = client.store_prices(pid)
            out.append_csv(
                partial,
                parse.store_price_rows(day, pid, branches),
                parse.STORE_PRICE_FIELDS,
            )
            for row in parse.store_rows(day, branches, chain_ids):
                stores[str(row["store_id"])] = row
            if i % PROGRESS_EVERY == 0:
                print(f"store-prices: {i}/{len(todo)} products", flush=True)
                _write_stores(out, stores)

        path, count = out.write_csv(
            final, out.read_csv(partial), parse.STORE_PRICE_FIELDS
        )
        out.path(partial).unlink(missing_ok=True)
        report.add("store_prices", count, path)
        report.add("stores", len(stores), _write_stores(out, stores))
        return report

    def _history(self, client: EkalathiClient, out: Store, options: Options) -> Report:
        report = Report()
        ids = self._product_ids(client, out, options)
        failed = []
        for i, pid in enumerate(ids, 1):
            rel = f"history/{pid}.csv"
            if out.exists(rel) and not options.force:
                continue
            try:
                series = client.price_history(pid, end=options.day)
            except SourceError:
                failed.append(pid)
                continue
            path, count = out.write_csv(
                rel, parse.history_rows(pid, series), parse.HISTORY_FIELDS
            )
            report.add("history", count, path)
            if i % PROGRESS_EVERY == 0:
                print(f"history: {i}/{len(ids)} products", flush=True)
        if failed:
            raise SourceError(
                f"history: {len(failed)} of {len(ids)} products failed; "
                "run the job again to fetch the rest"
            )
        return report

    # -- helpers -----------------------------------------------------------

    def _product_ids(
        self, client: EkalathiClient, out: Store, options: Options
    ) -> list[str]:
        """Product ids to work on: --only, else today's catalogue (or the live list)."""
        if options.only:
            ids = list(options.only)
        else:
            day = options.day.isoformat()
            rows = out.read_csv(f"catalogue/{day[:4]}/{day}.csv.gz")
            ids = [r["product_id"] for r in rows] or [
                str(p["productMasterId"]) for p in client.products()
            ]
        return ids[: options.limit] if options.limit else ids


def _write_stores(out: Store, stores: dict[str, dict[str, Any]]):
    rows = sorted(stores.values(), key=lambda r: int(r["store_id"]))
    path, _ = out.write_csv("stores.csv", rows, parse.STORE_FIELDS)
    return path
