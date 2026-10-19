"""The fuel observatory as an apographe source."""

from __future__ import annotations

import csv
from collections.abc import Callable
from datetime import datetime
from zoneinfo import ZoneInfo

from apographe.core.oauth import ClientCredentials
from apographe.core.source import Options, Report, Source, SourceError
from apographe.core.storage import Store
from apographe.sources.cy.fuel import api

INSTALL_HINT = "the cy.fuel source needs its extras: pip install 'apographe[cy-fuel]'"


class FuelSource(Source):
    id = "cy.fuel"
    title = "Cyprus fuel prices at every petrol station"
    country = "CY"
    homepage = "https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices"
    timezone = "Asia/Nicosia"
    jobs = {
        "prices": "every station's price for each fuel, right now (needs Chrome)",
        "api": "the same from the official API (needs CYCONNECT_* variables)",
        "pdf": "import the observatory page saved as PDFs (--input)",
    }
    default_jobs = ("prices",)

    def __init__(
        self,
        fuel_api: api.FuelApi | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._api = fuel_api
        self._clock = clock or (lambda: datetime.now(ZoneInfo(self.timezone)))

    def run(self, job: str, out: Store, options: Options) -> Report:
        report = Report()
        if job == "api":
            self._run_api(out, options, report)
        elif job == "prices":
            try:
                from apographe.sources.cy.fuel import scraper
            except ImportError as exc:
                raise SourceError(INSTALL_HINT) from exc
            path, count = scraper.run(out.root)
            report.add("prices", count, path)
        elif job == "pdf":
            if not options.inputs:
                raise SourceError("the pdf job needs --input: the PDFs or their folder")
            try:
                import pdfplumber  # noqa: F401  (checked here for a clear message)
            except ImportError as exc:
                raise SourceError(INSTALL_HINT) from exc
            from apographe.sources.cy.fuel import pdf

            try:
                written = pdf.convert(options.inputs, out.root, force=options.force)
            except (LookupError, ValueError) as exc:
                raise SourceError(str(exc)) from exc
            for path in written:
                with open(path, encoding="utf-8") as fh:
                    report.add("prices", sum(1 for _ in csv.DictReader(fh)), path)
        return report

    def _run_api(self, out: Store, options: Options, report: Report) -> None:
        fuel_api = self._api or self._connect(options)
        wanted = _fuel_types(options.only)
        now = self._clock()
        rows = api.collect(fuel_api, wanted, now.isoformat(timespec="seconds"))
        if not rows:
            raise SourceError("the fuel API returned no stations")
        stamp = now.strftime("%Y-%m-%d_%H%M")
        rel = f"{fuel_api.environment.folder}/{stamp[:4]}/prices_{stamp}.csv.gz"
        path, count = out.write_csv(rel, rows, api.FIELDS)
        report.add("prices", count, path)

    def _connect(self, options: Options) -> api.FuelApi:
        environment, client_id, secret = api.settings_from_env()
        credentials = ClientCredentials(environment.token_url, client_id, secret)
        interval = 2.0 if options.delay is None else options.delay
        return api.FuelApi(environment, credentials, min_interval=interval)


def _fuel_types(only: list[str]) -> list[int]:
    if not only:
        return list(api.FUEL_TYPES)
    try:
        chosen = [int(item) for item in only]
    except ValueError as exc:
        raise SourceError("--only takes fuel type numbers, 1 to 5") from exc
    bad = [n for n in chosen if n not in api.FUEL_TYPES]
    if bad:
        raise SourceError(f"unknown fuel type {bad}; the types are 1 to 5")
    return chosen
