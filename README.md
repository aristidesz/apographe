# Apographe

*ἀπογραφή (apographḗ): a register, the official record of what was counted.*

Apographe collects public price data, source by source and day by day, and
writes it as plain CSV you can analyse with anything. Each source is a small
plug-in; the framework handles the polite fetching, retries, resumable runs and
tidy files.

```console
$ pip install apographe
$ apographe run cy.ekalathi --out data --limit 2
cy.ekalathi lookups: 48 rows -> chains
cy.ekalathi lookups: 5 rows -> regions
cy.ekalathi lookups: 62 rows -> categories
cy.ekalathi catalogue: 476 rows -> catalogue
cy.ekalathi catalogue: 476 rows -> products
cy.ekalathi store-prices: 254 rows -> store_prices
cy.ekalathi store-prices: 143 rows -> stores
```

## Sources

| Source | What it collects | Granularity |
|---|---|---|
| `cy.ekalathi` | Cyprus supermarket prices from [e-kalathi.gov.cy](https://www.e-kalathi.gov.cy): every product, in every store | daily, per store; cheapest-price history since Sep 2025 |
| `cy.fuel` | Cyprus fuel prices at every petrol station, from the Ministry's [fuel price observatory](https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices) | per station, as often as you run it |

Want your country here? See [Adding a source](docs/adding-a-source.md): a
source is one class with a few jobs.

## Quick start

```bash
pip install apographe                 # core + e-kalathi
pip install "apographe[cy-fuel]"      # adds the browser the fuel source needs

apographe list                        # sources and their jobs
apographe run cy.ekalathi --out data --limit 5     # a quick trial: 5 products
apographe run cy.ekalathi --out data               # the full daily collection
apographe run cy.ekalathi --job history --out data # backfill, resumable
apographe run cy.fuel --out data
```

Useful options: `--job` (repeatable), `--date` (file the run under another
day), `--only 2074,1906` (just these items), `--limit N`, `--delay SECONDS`,
`--force` (redo what exists).

Exit codes: `0` done, `2` the site now asks for a login (nothing collected),
`1` anything else.

## What you get

Everything a source writes goes under `<out>/<country>/<source>/`:

```
data/cy/ekalathi/
├── chains.csv  regions.csv  categories.csv  products.csv  stores.csv
├── catalogue/2026/2026-10-11.csv.gz        date, product_id, price, previous_price, store_count
├── store_prices/2026/2026-10-11.csv.gz     date, product_id, store_id, price, price_before_offer, on_offer
├── history/2074.csv                        date, product_id, price
└── raw/catalogue/2026/2026-10-11.json.gz   the untouched response, for rebuilding
```

Tables join on their ids: a store price points to a product and a store, a
store to its chain and region. The e-kalathi page in
[docs/sources](docs/sources/cy-ekalathi.md) shows each table with real rows.

## Collecting every day

Apographe is a command, so any scheduler works: cron, GitHub Actions, a
container on a timer. A minimal GitHub Actions job that commits each day's
data to the repository it runs in:

```yaml
on:
  schedule: [{ cron: "30 4 * * *" }]   # 07:30 in Cyprus
jobs:
  collect:
    runs-on: ubuntu-latest
    permissions: { contents: write }
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.12" }
      - run: pip install apographe
      - run: apographe run cy.ekalathi --out .
      - run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add cy && git commit -m "e-kalathi $(date -u +%F)" && git push
```

## Being a good guest

Sources are public websites, not services built for bulk use, so Apographe
makes one request at a time, waits at least 3 seconds between requests by
default, identifies itself with a `User-Agent` that links back here, and stops
when a site starts asking for a login. Check each site's terms before you
collect from it, and keep the delays.

Apographe is an independent project, not affiliated with any of the sites it
reads.

## Development

```bash
poetry install --all-extras
pre-commit install
poetry run pytest
```

Tests run offline, against trimmed copies of real responses in
`tests/fixtures`.

## Licence

MIT. The data you collect belongs to its publishers and is subject to their
terms.
