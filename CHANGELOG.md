# Changelog

## 0.1.0 (unreleased)

First release as Apographe. The project began as `fuel_prices_retrieval`
(v0.2.0), a scraper for Cyprus fuel prices, and grew into a framework for
collecting public price data from many sources.

- Source framework: a `Source` interface, a polite HTTP client, atomic CSV and
  JSON storage, plug-in discovery through the `apographe.sources` entry point.
- `apographe list` and `apographe run` commands.
- `cy.ekalathi`: Cyprus supermarket prices, every product in every store, daily;
  cheapest-price history since September 2025.
- `cy.fuel`: Cyprus fuel prices per station, plus importing the observatory page
  saved as PDFs.
