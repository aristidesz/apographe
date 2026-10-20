# Commands and options

```bash
apographe list                       # every source and its jobs (* = runs by default)
apographe run SOURCE [options]       # run a source's jobs
apographe --version
```

## `apographe run`

```bash
apographe run cy.ekalathi --out data                  # the source's default jobs
apographe run cy.ekalathi --job history --out data    # one particular job
apographe run cy.fuel --job pdf --input ~/Downloads --out data
```

| Option | What it does |
|---|---|
| `--out DIR` | Folder to write into (default `data`). Each source writes under `DIR/<country>/<source>/`. |
| `--job NAME` | Run this job instead of the defaults. Repeat it to run several. |
| `--date YYYY-MM-DD` | File the data under this day instead of today (today is taken in the source's own time zone). |
| `--limit N` | Only the first N items, for a quick trial. |
| `--only ID,ID` | Only these items, e.g. `--only 2074,1906`. |
| `--delay SECONDS` | Seconds between requests (default 3). Please don't go lower. |
| `--input PATH` | A file or folder for jobs that import, such as the fuel PDFs. Repeatable. |
| `--force` | Redo work that already exists, such as a day already collected. |

A long run that stops part way can simply be run again: it carries on where it
stopped.

## Environment variables

Some jobs need credentials. `apographe info <source>` lists each job with the
variables it needs, and `apographe list` marks those jobs `[needs env]`. A job
whose variables are missing stops before it does anything, naming the
variables (never their values).

| Source | Job | Variables | Where to get them |
|---|---|---|---|
| `cy.fuel` | `api` | `CYCONNECT_CLIENT_ID`, `CYCONNECT_CLIENT_SECRET` | CDS Support, see [cy.fuel](sources/cy-fuel.md#getting-access) |

Set them in your shell, or put `KEY=VALUE` lines in a file and pass it:

```bash
apographe run cy.fuel --job api --env-file .env.production
```

`--env-file` skips blank lines and `#` comments and strips quotes around values.
It applies to that run only, and a variable already set in your shell wins over
the file. Keep the file out of git.

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Done. |
| `2` | The site now asks for a login, so nothing was collected. Schedulers can treat this as a warning. |
| `1` | Anything else went wrong; the message says what. |

## Output

Everything is plain CSV (gzipped for the daily files) with ids in every row, so
tables join: a store price points to a product and a store, and a store to its
chain and region. Each source's page in [sources](sources/) lists its tables and
columns with real example rows.
