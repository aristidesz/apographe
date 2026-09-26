import argparse

from fuel_prices.download_fuel_prices_csv import download_github_artifacts
from fuel_prices.retrieve_fuel_data import run as retrieve_fuel_data_run


def run(args):

    if args.download:
        download_github_artifacts()
    else:
        retrieve_fuel_data_run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--download",
        action="store_true",
        help="Download previously retrieved fuel price artifacts instead of scraping",
    )
    args = parser.parse_args()
    run(args)
