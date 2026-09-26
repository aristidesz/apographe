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

## Layout

```
fuel_prices/   scraper and artifact downloader
tests/         pytest suite
notebooks/     prototype and price analysis (outputs stripped on commit)
main.py        CLI entry point
```

## Development

```bash
pytest
pre-commit run --all-files
```
