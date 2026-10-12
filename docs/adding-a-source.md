# Adding a source

A source is one class. It names its jobs, and each job writes tables through the
`Store` it is given. The framework does the rest: the command line, the day the
run belongs to, the output folder, the report.

```python
from apographe.core.http import PoliteClient
from apographe.core.source import Options, Report, Source
from apographe.core.storage import Store


class ExampleFuelSource(Source):
    id = "xx.fuel"  # country code, then a short name
    title = "Example fuel prices"
    country = "XX"  # ISO 3166-1 alpha-2
    homepage = "https://fuel.example.gov"
    timezone = "Europe/Athens"  # "today" is taken here
    jobs = {"prices": "every station's prices, now"}
    default_jobs = ("prices",)

    def run(self, job: str, out: Store, options: Options) -> Report:
        http = PoliteClient(
            "https://fuel.example.gov/api", min_interval=options.delay or 3
        )
        stations = http.get_json("/stations")
        day = options.day.isoformat()
        rows = [
            {"date": day, "station_id": s["id"], "fuel": s["fuel"], "price": s["price"]}
            for s in stations
        ]
        report = Report()
        path, count = out.write_csv(
            f"prices/{day[:4]}/{day}.csv.gz",
            rows,
            ["date", "station_id", "fuel", "price"],
        )
        report.add("prices", count, path)
        return report
```

## Shipping it

Put the module under `src/apographe/sources/<country>/`, add it to `BUILT_IN`
in `src/apographe/core/registry.py`, add tests with a few trimmed real responses
under `tests/fixtures/`, and open a pull request.

## Conventions

- **One file per day** for anything collected daily: `<table>/YYYY/YYYY-MM-DD.csv.gz`.
  Lookups that change slowly (stores, chains) are one CSV, rewritten.
- **Ids in every row** so tables join: `product_id`, `store_id`, `chain_id`.
- **Keep the raw response** when it is small, under `raw/`, so a parsing fix can
  rebuild the tables.
- **Be polite:** one request at a time, a few seconds apart; never parallelise
  requests to a public site.
- **Raise `LoginWall`** (the `PoliteClient` does this for you) when a site starts
  asking for a login, so scheduled runs end cleanly instead of failing.
- **Print counts, never data:** logs of scheduled runs are often public.
