# Fuel prices retrieval

Scrapes daily fuel prices per station from the Cyprus petroleum prices site and
saves them as CSV (`data/fuel_prices_<date>.csv`). A GitHub Action runs the
scraper twice a day and uploads the CSVs as artifacts.

## Setup

```bash
poetry install
pre-commit install
```

## Usage

```bash
python main.py              # scrape today's prices into data/
GITHUB_TOKEN=... python main.py --download   # fetch past CSVs from GitHub artifacts
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
