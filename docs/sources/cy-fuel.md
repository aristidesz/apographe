# cy.fuel: Cyprus fuel prices

The Ministry's [fuel price observatory](https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices)
lists every petrol station's price for five fuels. The page is a form, so this
source drives a headless Chrome: install it with `pip install "apographe[cy-fuel]"`.

## Jobs

| Job | Writes |
|---|---|
| `prices` | `fuel_prices_YYYY-MM-DD_HHMM.csv` (UTC), one row per station and fuel |
| `pdf` | the same file, from the page saved as PDFs (`--input`) |

Columns: `brand, address, area, price, fuel_type, datetime`. The address holds
the street and the phone number (`"X\n τηλ: Y"`).

## Filling a missed day from saved PDFs

If a run is missed, save the observatory page as PDF from a browser, once per
fuel type, then import the set into the folder that already holds the
collected CSVs (it matches each station to its existing spelling):

```bash
apographe run cy.fuel --job pdf --input ~/Downloads --out data
```

Given a folder, it takes only the observatory PDFs in it and writes one CSV per
snapshot (PDFs saved more than 30 minutes apart are separate snapshots). A CSV
that already exists is left alone unless you add `--force`. Each fuel's average,
cheapest and most expensive price are checked against the figures printed on its
PDF.
