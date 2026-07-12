import argparse
from unittest import mock

import main


def test_download_flag_triggers_artifact_download():
    with mock.patch("main.download_github_artifacts") as download, mock.patch(
        "main.retrieve_fuel_data_run"
    ) as retrieve:
        main.run(argparse.Namespace(download=True))

    download.assert_called_once()
    retrieve.assert_not_called()


def test_no_flag_triggers_scrape():
    with mock.patch("main.download_github_artifacts") as download, mock.patch(
        "main.retrieve_fuel_data_run"
    ) as retrieve:
        main.run(argparse.Namespace(download=False))

    retrieve.assert_called_once()
    download.assert_not_called()
