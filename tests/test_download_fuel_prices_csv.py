import io
import zipfile
from unittest import mock

import pytest

import src.download_fuel_prices_csv as dl


def test_missing_token_raises(monkeypatch):
    # TOKEN is captured as a module global at import time, so patch it there.
    monkeypatch.setattr(dl, "TOKEN", None)

    with pytest.raises(EnvironmentError, match="GITHUB_TOKEN"):
        dl.download_github_artifacts()


def _zip_bytes(filename, content):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(filename, content)
    return buf.getvalue()


def test_skips_expired_and_extracts_only_fuel_outputs(monkeypatch, tmp_path):
    monkeypatch.setattr(dl, "TOKEN", "fake-token")
    monkeypatch.chdir(tmp_path)  # so Path("data") is created under tmp_path

    list_resp = mock.Mock()
    list_resp.json.return_value = {
        "artifacts": [
            {
                "id": 1,
                "name": "fuel_prices_outputs",
                "expired": False,
                "size_in_bytes": 1000,
            },
            {
                "id": 2,
                "name": "fuel_prices_outputs",
                "expired": True,
                "size_in_bytes": 1000,
            },
        ]
    }
    list_resp.links = {}  # no pagination

    zip_resp = mock.Mock()
    zip_resp.content = _zip_bytes(
        "fuel_prices_2025-11-01.csv", "brand,price\nESSO,1.4\n"
    )

    session = mock.Mock()
    session.headers = {}  # real dict: code assigns the Authorization header
    # first .get is the artifact listing, subsequent ones are zip downloads
    session.get.side_effect = [list_resp, zip_resp]
    monkeypatch.setattr(dl.requests, "Session", lambda: session)

    dl.download_github_artifacts()

    # Only the non-expired artifact was downloaded (1 list + 1 zip = 2 gets).
    assert session.get.call_count == 2
    extracted = tmp_path / "data" / "fuel_prices_2025-11-01.csv"
    assert extracted.exists()
