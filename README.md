# Apographe

[![PyPI](https://img.shields.io/pypi/v/apographe)](https://pypi.org/project/apographe/)
[![Python](https://img.shields.io/pypi/pyversions/apographe)](https://pypi.org/project/apographe/)
[![CI](https://github.com/aristidesz/apographe/actions/workflows/ci.yml/badge.svg)](https://github.com/aristidesz/apographe/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](https://github.com/aristidesz/apographe/blob/main/LICENSE)

**Collect public data, day by day, into plain CSV files.**

Governments and public bodies publish data on websites and APIs, usually as
today's snapshot with no history. Apographe collects it on a schedule and saves
it as dated CSV files you can open in pandas, Excel or anything else. Run it
every day and you build your own history.

Prices are the first sources (supermarket products, petrol stations), not the
limit: a source is one small class, so any public dataset can be added.

*ἀπογραφή (apographḗ): a register, the official record of what was counted.*

## Getting started

```bash
pip install apographe

apographe list                                   # what you can collect
apographe run cy.ekalathi --limit 5 --out data   # try it: 5 products, about a minute
```

Among the files it writes:

```
data/cy/ekalathi/
├── products.csv                        what each product is
├── stores.csv                          each store, its chain and location
└── store_prices/2026/2026-10-12.csv.gz the price of each product in each store
```

Read it with pandas:

```python
import glob
import pandas as pd

files = glob.glob("data/cy/ekalathi/store_prices/*/*.csv.gz")
prices = pd.concat(map(pd.read_csv, files))
```

Leave out `--limit 5` to collect every product (about 45 minutes, since
Apographe waits a few seconds between requests).

Or from Python:

```python
from apographe import run

report = run("cy.ekalathi", out="data", limit=5)
print(report.rows)  # rows written per table
```

## Sources

| Source | What it collects | Install |
|---|---|---|
| `cy.ekalathi` | Cyprus supermarket prices: every product in every store, from [e-kalathi.gov.cy](https://www.e-kalathi.gov.cy) | `pip install apographe` |
| `cy.fuel` | Cyprus fuel prices at every petrol station. The default job scrapes the [Ministry's observatory](https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices) (needs Chrome, [caveats](https://github.com/aristidesz/apographe/blob/main/docs/sources/cy-fuel.md#caveats-of-the-default-prices-job)); the `api` job uses the official API (needs approval and credentials) | `pip install "apographe[cy-fuel]"` |

## Learn more

- [Commands and options](https://github.com/aristidesz/apographe/blob/main/docs/usage.md)
- [Using it from Python](https://github.com/aristidesz/apographe/blob/main/docs/library.md)
- [Collecting every day](https://github.com/aristidesz/apographe/blob/main/docs/scheduling.md)
- [What each source collects](https://github.com/aristidesz/apographe/tree/main/docs/sources)
- [Adding a source for your country](https://github.com/aristidesz/apographe/blob/main/docs/adding-a-source.md)
- [Contributing](https://github.com/aristidesz/apographe/blob/main/CONTRIBUTING.md)

Apographe makes one request at a time, waits between requests and identifies
itself to the sites it reads. It is an independent project, not affiliated with
any of them; check each site's terms before you collect from it.

## License

MIT. The data you collect belongs to its publishers.
