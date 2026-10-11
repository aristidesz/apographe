# cy.ekalathi: Cyprus supermarket prices

[e-kalathi.gov.cy](https://www.e-kalathi.gov.cy) is the Cypriot government's
supermarket price comparison site. It lists about 476 everyday products and their
price in each of more than 140 stores, listed under 48 chains.

## Jobs

| Job | Requests | Writes |
|---|---|---|
| `lookups` | 3 | `chains.csv`, `regions.csv`, `categories.csv` |
| `catalogue` | ~5 | `catalogue/YYYY/DATE.csv.gz` (cheapest price per product), `products.csv`, the raw response |
| `store-prices` | 1 per product (~476) | `store_prices/YYYY/DATE.csv.gz`, `stores.csv` |
| `history` | 1 per product | `history/<product_id>.csv`: daily cheapest price since 3 Sep 2025 |

`apographe run cy.ekalathi` runs the first three. A full day takes about 45
minutes at the default 3 seconds between requests. If it stops part way, the
next run on the same day carries on where it left off.

## Tables

| Table | Key | Columns |
|---|---|---|
| products | product_id | code, name, category, category_en, category_id |
| catalogue | date, product_id | price (cheapest in Cyprus), previous_price, store_count |
| store_prices | date, product_id, store_id | price, price_before_offer, on_offer |
| stores | store_id | name, chain_id, chain, phone, address, postcode, region_id, lat, lon, last_seen |
| chains | chain_id | name |
| regions | region_id | name |
| categories | category_id | code, name, name_en, parent_id |
| history | date, product_id | price |

Example, Kykkos water 500 ml on 9 Oct 2026:

```
catalogue:     2026-10-09, 2074, 0.25, 0.23, 115
store_prices:  2026-10-09, 2074, 539, 0.25, 0.25, False
stores:        539, ALPHA SIGMA SUPERMARKET Περιοχή Φασούρι, 452, ALPHA SIGMA, …, 4640, 3, 34.644167, 32.944778
chains:        452, ALPHA SIGMA
regions:       3, ΛΕΜΕΣΟΣ
```

## Things to know

- **Ids are per table.** Chain 539 (ΣΥΠΑΛ - ΛΙΜΝΙΑ) and store 539 (ALPHA SIGMA
  Φασούρι) are unrelated.
- **Some "chains" are single shops,** such as each SMART DISCOUNT SHOP branch.
- **`store_count` counts stores, not chains,** although the site calls it
  `numberOfChains`.
- **Region comes from the postcode** (1xxx-2xxx Nicosia, 3xxx-4xxx Limassol,
  5xxx Famagusta, 6xxx-7xxx Larnaca, 8xxx Paphos), or from the town named in the
  address when there is no postcode; store rows carry no region of their own.
- **Past prices exist only as the cheapest per product.** Per-store prices can
  be collected from the day you start.

## The site's API

The site's pages call a JSON backend at
`https://www.e-kalathi.gov.cy/ekalathi-website-server/api`. It is not a
published API and may change without notice. None of these calls needs a login.

| Path | Arguments | Returns | Time |
|---|---|---|---|
| `/fetch-product-list` | `page`, `size`, `sort=DEFAULT,ASC`; optional `categoryIds`, `productName` | Paged products: `productMasterId`, `code`, `name`, `startPrice` (cheapest today), `previousPrice`, `productCategoryName(English)`, `numberOfChains` | ~1 s per page |
| `/retail/fetch-retail-branch-list` | `productId`, `page`, `size`, `sort` | Paged store rows: `id`, `name`, `companyName`, `landPhone`, `postalAddress`, `branchLatitude/Longitude` (degrees-minutes-seconds), `retailerProductPrice`, `retailerInitialProductPrice`, `isInOfferOrDiscount`, and the chain logo as base64 (`companyPhotoFile`, ~100 KB per row) | ~4 s, ~11 MB |
| `/fetch-product-price-diagram` | `id`, `from`, `to` (YYYY-MM-DD); optional `cId` (chain), `rId` (region) | `[{date, price}]`, the cheapest in Cyprus each day, or one chain's/region's | ~30 s; often times out, so retried |
| `/fetch-product?id=` | product id | Product details, no prices | ~1 s |
| `/fetch-companies`, `/fetch-regions`, `/fetch-product-categories` | none | Lookup lists | ~1 s |

Paged calls answer `{"content": [...], "last": bool, "totalPages": n, ...}`.
`/fetch-retail-branches`, `/fetch-basket-types` and `/fetch-company-offers` need
a login (HTTP 401).
