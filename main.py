import argparse

from src.download_fuel_prices_csv import download_github_artifacts
from src.retrieve_fuel_data import run as retrieve_fuel_data_run


def run(args):

    if args.download:
        download_github_artifacts()
    else:
        retrieve_fuel_data_run()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--download", type=bool, help="True or False to download artifacts"
    )
    args = parser.parse_args()
    run(args)
