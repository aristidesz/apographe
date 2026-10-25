# Changelog

## 0.1.0 - 2026-10-25

First public release. The project began as `fuel_prices_retrieval` (v0.2.0), a
scraper for Cyprus fuel prices, and grew into a way to collect public data from
many sources into dated plain files.

- Source framework: a `Source` interface, a polite HTTP client, OAuth client
  credentials, atomic CSV and JSON storage.
- Use it from Python: `from apographe import run` collects a source into dated
  files, and the main classes (`Source`, `Store`, `PoliteClient`, ...) are
  exported.
- `apographe list`, `apographe info SOURCE` and `apographe run`. `info` shows a
  source's jobs and the environment variables and extras each needs; a job with
  a missing variable stops early and names it. `run --env-file PATH` reads
  `KEY=VALUE` lines for one run.
- `cy.ekalathi`: Cyprus supermarket prices, every product in every store, daily;
  cheapest-price history since September 2025.
- `cy.fuel`: Cyprus fuel prices per station.
  - `prices` (default): scrapes the Ministry's website with Chrome. Chrome's
    sandbox stays on except in CI.
  - `api`: the official CY Connect API (OAuth 2.0 client credentials). The
    endpoints and credentials come from environment variables
    (`CYCONNECT_TOKEN_URL`, `CYCONNECT_API_URL`, `CYCONNECT_CLIENT_ID`,
    `CYCONNECT_CLIENT_SECRET`). Sandbox answers go to their own folder.
  - `pdf`: import the observatory page saved as PDFs.
