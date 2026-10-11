"""The fuel observatory as an apographe source."""

from __future__ import annotations

import csv

from apographe.core.source import Options, Report, Source, SourceError
from apographe.core.storage import Store

INSTALL_HINT = "the cy.fuel source needs its extras: pip install 'apographe[cy-fuel]'"


class FuelSource(Source):
    id = "cy.fuel"
    title = "Cyprus fuel prices at every petrol station"
    country = "CY"
    homepage = "https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices"
    timezone = "Asia/Nicosia"
    jobs = {
        "prices": "every station's price for each fuel, right now (needs Chrome)",
        "pdf": "import the observatory page saved as PDFs (--input)",
    }
    default_jobs = ("prices",)

    def run(self, job: str, out: Store, options: Options) -> Report:
        report = Report()
        if job == "prices":
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
