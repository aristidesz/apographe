import io
import os
import zipfile
from pathlib import Path

import requests

# --- Configuration ---

OWNER = "aristidesz"
REPO = "fuel_prices_retrieval"
TOKEN = os.getenv("GITHUB_TOKEN")


def download_github_artifacts():
    # --- Check token ---
    if not TOKEN:
        raise EnvironmentError("Missing GITHUB_TOKEN environment variable")

    # --- Setup session ---
    session = requests.Session()
    session.headers["Authorization"] = f"token {TOKEN}"

    # --- Create downloads folder ---
    Path("data").mkdir(exist_ok=True)

    # --- Fetch all artifacts (handle pagination) ---
    artifacts = []
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/artifacts?per_page=100"

    while url:
        r = session.get(url)
        r.raise_for_status()
        data = r.json()
        artifacts.extend(data["artifacts"])
        url = r.links.get("next", {}).get("url")  # next page if exists

    print(f"🗂️ Found {len(artifacts)} artifacts")

    # --- Download each artifact ZIP ---
    for art in artifacts:
        if art["expired"]:
            print(f"⚠️ Skipping expired artifact: {art['name']}")
            continue

        print(f"⬇️ Downloading {art['name']} ({art['size_in_bytes'] / 1e6:.2f} MB)")
        dl_url = f"https://api.github.com/repos/{OWNER}/{REPO}/actions/artifacts/{art['id']}/zip"  # noqa: E501
        resp = session.get(dl_url)
        resp.raise_for_status()

        # Extract into folder
        with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
            if art["name"] == "fuel_prices_outputs":
                extract_path = Path("data")
                extract_path.mkdir(exist_ok=True)
                z.extractall(extract_path)

    print("✅ All available artifacts downloaded and extracted to ./artifacts/")
