# cy.fuel: Cyprus fuel prices

The Ministry's [fuel price observatory](https://eforms.eservices.cyprus.gov.cy/MCIT/MCIT/PetroleumPrices)
lists every petrol station's price for five fuels. The page is a form, so this
source drives a headless Chrome: install it with `pip install "apographe[cy-fuel]"`.

## Jobs

| Job | Writes |
|---|---|
| `prices` | `fuel_prices_YYYY-MM-DD_HHMM.csv` (UTC), one row per station and fuel |
| `api` | `api/YYYY/prices_YYYY-MM-DD_HHMM.csv.gz`, from the official API (below) |
| `pdf` | the same file, from the page saved as PDFs (`--input`) |

Columns: `brand, address, area, price, fuel_type, datetime`. The address holds
the street and the phone number (`"X\n τηλ: Y"`).

## Caveats of the default (`prices`) job

- It needs Chrome and the `cy-fuel` extras (`pip install "apographe[cy-fuel]"`).
- It reads the page's layout, so a redesign of the site breaks it.
- The site once started redirecting to CY Login. The run then exits with code 2
  and collects nothing.
- File names are in UTC.
- It is slower and heavier than the API.

The `api` job avoids all of these, but needs approval (below).

## The official API

The Ministry also offers the data as an API through CY Connect, the government's
API gateway. It needs no browser and reports when each station last changed its
price. Access is by approval; see the steps below.

```bash
export CYCONNECT_CLIENT_ID=...
export CYCONNECT_CLIENT_SECRET=...
export CYCONNECT_TOKEN_URL=...
export CYCONNECT_API_URL=...
export CYCONNECT_ENV=sandbox        # or production
apographe run cy.fuel --job api --out data
```

| Variable | |
|---|---|
| `CYCONNECT_CLIENT_ID` | Required. Your application's client id. |
| `CYCONNECT_CLIENT_SECRET` | Required. Your application's client secret. |
| `CYCONNECT_TOKEN_URL` | Required. The sign-in address, from the CY Connect onboarding package. |
| `CYCONNECT_API_URL` | Required. The fuel API address, from the same package. |
| `CYCONNECT_ENV` | `sandbox` (default) or `production`. Only chooses the output folder. |

Instead of `export`, you can keep them in a file and use
`--env-file .env.production`. `--only 1 3` asks for some fuels only (1 Unleaded
95, 2 Unleaded 98, 3 Diesel, 4 Heating diesel, 5 Kerosene). The credentials come
from the environment and are never written to disk or printed. One run signs in
once and makes five calls.

Columns: `fetched_at, fuel_type_id, fuel_type, company_code, company,
station_code, station_name, phone, city, district, address, price,
price_changed_at, lat, lon, offline`.

**The sandbox returns test data**, not real prices, so it is written to
`api-sandbox/`. Never mix that folder into a dataset.

### Getting access

Apographe does not include the API's addresses or sample data: they belong to
the government's API gateway (CY Connect) and come with your approval.

1. Ask the Consumer Protection Service, who own the data, for approval.
2. Apply to CDS Support, the CY Connect support team. Individuals can apply too.
3. Once you are approved, activate your Developer Portal account and add the
   fuel prices API to your application in the API Hub.
4. Test in the sandbox, then ask for a separate production application.

The terms forbid redistributing what the API returns, so keep collected data
private.

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
