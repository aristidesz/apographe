# Fuel prices retrieval

Scrapes daily fuel prices per station from the Cyprus petroleum prices site and
saves them as CSV (`data/fuel_prices_<date>_<HHMM>.csv`, UTC). A GitHub Action runs
the scraper twice a day and commits each CSV to the `data` branch.

## Setup

```bash
poetry install
pre-commit install
```

## Usage

```bash
python main.py              # scrape today's prices into data/
python main.py --download   # copy all CSVs from the data branch into data/
```

### Filling a missed day from saved PDFs

If the scraper misses a day, save the observatory page as PDF from a browser,
once per fuel type, then convert the set into one CSV in the scraper's format:

```bash
python main.py --download                                  # stations to match against
python -m fuel_prices.pdf_to_csv ~/Downloads/*.pdf --data-dir data
```

Each station is matched to its existing spelling, and each fuel's average,
cheapest and most expensive price are checked against the figures printed on
its PDF. Commit the new CSV to the `data` branch.

## Layout

```
fuel_prices/   scraper, data-branch downloader, PDF-to-CSV converter
tests/         pytest suite
notebooks/     prototype and price analysis (outputs stripped on commit)
main.py        CLI entry point
```

## Development

```bash
pytest
pre-commit run --all-files
```
