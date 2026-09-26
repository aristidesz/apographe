import subprocess  # nosec B404

from fuel_prices.download_fuel_prices_csv import download_data


def git(*args, cwd):
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_download_data_extracts_csvs_from_data_branch(tmp_path, monkeypatch):
    # A local "origin" repo whose data branch holds one CSV.
    origin = tmp_path / "origin"
    origin.mkdir()
    git("init", "-q", "-b", "data", cwd=origin)
    (origin / "fuel_prices_2026-09-26_0600.csv").write_text("brand,price\nESSO,1.4\n")
    git("add", ".", cwd=origin)
    git(
        "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "csv",
        "--no-verify", cwd=origin,
    )  # fmt: skip

    work = tmp_path / "work"
    work.mkdir()
    git("init", "-q", cwd=work)
    git("remote", "add", "origin", str(origin), cwd=work)
    monkeypatch.chdir(work)

    download_data()

    extracted = work / "data" / "fuel_prices_2026-09-26_0600.csv"
    assert extracted.read_text() == "brand,price\nESSO,1.4\n"
