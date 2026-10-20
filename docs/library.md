# Using Apographe from Python

Everything the command line does is one function, `run`:

```python
from apographe import run

report = run("cy.ekalathi", out="data", limit=5)
print(report.rows)  # {"products": 5, ...}: rows written per table
print(report.files)  # the files written
```

`run` takes the same options as `apographe run`: `jobs`, `day` (a date or
`"2026-10-01"`), `limit`, `only`, `delay`, `inputs` and `force`. `help(run)`
lists them all. It raises `ValueError` for a job the source does not have,
`LoginWall` when the site now asks for a login, and `SourceError` for anything
else that goes wrong. It prints nothing.

## Your own source

Pass a `Source` (an instance or the class) instead of an id:

```python
from apographe import Report, Source, run


class Stations(Source):
    id = "xx.fuel"
    title = "Example fuel prices"
    country = "XX"
    homepage = "https://fuel.example.gov"
    jobs = {"prices": "every station's prices, now"}
    default_jobs = ("prices",)

    def run(self, job, out, options):
        rows = [{"station": "A", "price": 1.5}]  # fetch your data here
        path, count = out.write_csv(
            f"prices/{options.day}.csv", rows, ["station", "price"]
        )
        report = Report()
        report.add("prices", count, path)
        return report


run(Stations(), out="data")
```

[Adding a source](adding-a-source.md) shows a full one and the conventions.

## What you can import

| Name | What it is |
|---|---|
| `run` | Run a source |
| `Source`, `Options`, `Report` | Write a source: the class, its run settings, what it hands back |
| `Store` | The folder a source writes into: `write_csv`, `write_json`, `read_csv` |
| `PoliteClient` | A JSON client that waits between requests and retries |
| `ClientCredentials` | OAuth sign-in for sources behind an API gateway |
| `SourceError`, `LoginWall` | The errors above |
