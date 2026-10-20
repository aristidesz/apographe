# Changelog

## Unreleased

- Use it from Python: `from apographe import run` collects a source into dated
  files, and the main classes (`Source`, `Store`, `PoliteClient`, ...) are
  exported. `apographe run` now calls it.
- Wording and README: Apographe collects public data in general, not only prices.
  `cy.fuel` docs list the caveats of the scraping job.
- `cy.fuel`: new `api` job, reading every station's price from the official
  CY Connect API (OAuth 2.0 client credentials from environment variables).
  Sandbox answers go to their own folder.
- `defusedxml` is now a dependency, for reading the API's XML.

## 0.1.0

First release as Apographe. The project began as `fuel_prices_retrieval`
(v0.2.0), a scraper for Cyprus fuel prices, and grew into a framework for
collecting public price data from many sources.

- Source framework: a `Source` interface, a polite HTTP client, atomic CSV and
  JSON storage.
- `apographe list` and `apographe run` commands.
- `cy.ekalathi`: Cyprus supermarket prices, every product in every store, daily;
  cheapest-price history since September 2025.
- `cy.fuel`: Cyprus fuel prices per station, plus importing the observatory page
  saved as PDFs.
