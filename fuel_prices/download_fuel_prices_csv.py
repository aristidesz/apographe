import io
import subprocess  # nosec B404
import tarfile
from pathlib import Path

DATA_BRANCH = "data"


def download_data(dest="data"):
    """Copy every scraped CSV from the `data` branch on origin into `dest`."""
    subprocess.run(["git", "fetch", "origin", DATA_BRANCH], check=True)  # nosec
    archive = subprocess.run(  # nosec
        ["git", "archive", "FETCH_HEAD"], check=True, capture_output=True
    ).stdout
    Path(dest).mkdir(exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
        tar.extractall(dest, filter="data")
    print(f"✅ Fuel price CSVs extracted to {dest}/")
