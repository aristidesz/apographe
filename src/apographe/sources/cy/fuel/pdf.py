"""Turn PDF printouts of the fuel price observatory into the scraper's CSV.

When the scraper misses a day, the same page saved or printed as PDF from a
browser (one PDF per fuel type) can fill the gap. This writes one CSV for the
whole set, in exactly the scraper's format, so it sits on the data branch
like any other run:

    python -m apographe.sources.cy.fuel.pdf path/to/*.pdf --data-dir data
    python -m apographe.sources.cy.fuel.pdf ~/Downloads --data-dir data

Given a folder, it takes every observatory PDF in it and skips the rest;
PDFs saved more than 30 minutes apart become separate CSVs (one per day,
typically), and a CSV that already exists is left alone.

- Stations are matched to the scraper's own CSVs in --data-dir by brand and
  phone number (by brand, area and address when a station lists no phone),
  so each station's address and area are spelled exactly as in the rest of
  the data. A station the scraper has never seen stops the run.
- The fuel type is read from the page, not the file name.
- Every fuel's average, cheapest and most expensive price are checked
  against the figures printed at the top of its PDF.
- The time is when the PDFs were made, in UTC like the scraper's (the
  earliest of each snapshot); --stamp overrides it for a single snapshot.
"""

from __future__ import annotations

import argparse
import csv
import re
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

# The scraper's column order, and its fuel order (the site's dropdown).
COLUMNS = ["brand", "address", "area", "price", "fuel_type", "datetime"]
FUEL_TYPES = [
    "Αμόλυβδη 95",
    "Αμόλυβδη 98",
    "Κηροζίνη",
    "Πετρέλαιο Θέρμανσης",
    "Πετρέλαιο κίνησης",
]

PRICE = r"(\d,\d{3})"
PHONE = re.compile(r"^τηλ:\s*(\S+)")
HEADER = re.compile(r"\(Παγκύπρια\) (\d,\d{3})")


@dataclass(frozen=True)
class Station:
    brand: str
    text: str  # the address and area, run together on the page
    price: str  # as printed, e.g. "1,519"
    phone: str | None


Known = dict[tuple[str, str], tuple[str, str]]  # (brand, phone) -> (address, area)
# brand -> {(address, area): last file seen in}, for stations listing no phone
NoPhone = dict[str, dict[tuple[str, str], int]]


def canonical_fuel(name: str) -> str:
    """The scraper's spelling of a fuel type (the page varies the case)."""
    for fuel in FUEL_TYPES:
        if fuel.casefold() == name.strip().casefold():
            return fuel
    raise ValueError(f"unknown fuel type {name!r}")


def load_known(csv_paths: list[Path]) -> tuple[Known, NoPhone, set[str]]:
    """Every station the scraper has written, keyed the way the PDF shows it.

    Files are read oldest first, so a station whose text changed over the
    year ends up with its latest spelling."""
    known: Known = {}
    nophone: NoPhone = defaultdict(dict)
    brands: set[str] = set()
    for n, path in enumerate(sorted(csv_paths)):
        with path.open(encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                brands.add(row["brand"])
                found = re.search(r"τηλ:\s*(\S+)", row["address"])
                if found:
                    known[(row["brand"], found.group(1))] = (
                        row["address"],
                        row["area"],
                    )
                else:
                    nophone[row["brand"]][(row["address"], row["area"])] = n
    return known, nophone, brands


def parse_stations(lines: list[str], brands: set[str]) -> list[Station]:
    """Station rows from a page's text lines.

    A row is "BRAND <address> <area> 1,519", usually followed by
    "τηλ: <phone>". Two layouts wrap: a two-word brand ("TOTAL ... 1,578"
    then "PLUS τηλ: ..."), and a long address that takes one more line
    before the phone.
    """
    names = "|".join(sorted(map(re.escape, brands), key=len, reverse=True))
    row = re.compile(rf"^({names}) (.*) {PRICE}$")
    firsts = "|".join(
        sorted({re.escape(b.split(" ", 1)[0]) for b in brands if " " in b})
    )
    wrapped = re.compile(rf"^({firsts}) (.*) {PRICE}$") if firsts else None

    stations = []
    for i, raw in enumerate(lines):
        line = raw.strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ""
        m = row.match(line)
        if m:
            brand, text, price = m.groups()
        else:
            w = wrapped.match(line) if wrapped else None
            if not w:
                continue
            first, text, price = w.groups()
            brand = next(
                (
                    b
                    for b in brands
                    if b.split(" ", 1)[0] == first
                    and " " in b
                    and nxt.startswith(b.split(" ", 1)[1] + " ")
                ),
                "",
            )
            if not brand:
                continue
            nxt = nxt[len(brand.split(" ", 1)[1]) :].strip()
        phone = PHONE.match(nxt)
        if not phone and i + 2 < len(lines) and not row.match(nxt):
            phone = PHONE.match(lines[i + 2].strip())
        stations.append(Station(brand, text, price, phone.group(1) if phone else None))
    return stations


def match(station: Station, known: Known, nophone: NoPhone) -> tuple[str, str]:
    """The station's (address, area) exactly as the scraper wrote them."""
    if station.phone and (station.brand, station.phone) in known:
        return known[(station.brand, station.phone)]
    # No phone on the page: same brand, the area at the end of the text, and
    # the start of the known address in it.
    # If its text changed over the year, the latest spelling wins.
    candidates = {
        (address, area): -1
        for (brand, _), (address, area) in known.items()
        if brand == station.brand
    }
    candidates.update(nophone.get(station.brand, {}))
    found = {
        (address, area): seen
        for (address, area), seen in candidates.items()
        if station.text.endswith(area)
        and (address == "" or address.split("\n")[0][:20] in station.text)
    }
    if not found:
        raise LookupError(f"{station.brand} {station.text!r}: no matching station")
    latest = max(found.values())
    best = [k for k, seen in found.items() if seen == latest]
    if len(best) != 1:
        raise LookupError(
            f"{station.brand} {station.text!r}: {len(best)} matching stations"
        )
    return best[0]


def check_header(fuel: str, header: list[float], prices: list[float]) -> None:
    """The page's own average, cheapest and most expensive price must match."""
    ours = [round(statistics.mean(prices), 3), min(prices), max(prices)]
    if [round(h, 3) for h in header] != ours:
        raise ValueError(f"{fuel}: page says {header}, parsed {ours}")


def pdf_created(meta: dict) -> datetime | None:
    """A PDF's CreationDate ("D:20261002054901Z00'00'") as UTC."""
    raw = str(meta.get("CreationDate") or "")
    m = re.match(r"D:(\d{14})", raw)
    if not m:
        return None
    return datetime.strptime(m.group(1), "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


# PDFs saved more than this far apart are separate snapshots (separate CSVs).
SNAPSHOT_GAP = timedelta(minutes=30)


@dataclass(frozen=True)
class Page:
    path: Path
    fuel: str
    created: datetime | None
    text: str


def read_pdf(path: Path) -> Page | None:
    """The page's fuel type and text, or None if it isn't an observatory page."""
    import pdfplumber  # dev dependency, only needed here

    with pdfplumber.open(path) as pdf:
        text = "\n".join(page.extract_text() or "" for page in pdf.pages)
        created = pdf_created(pdf.metadata)
    criteria = re.search(r"Κριτήρια Αναζήτησης\n(.+)", text)
    if not criteria:
        return None
    return Page(path, canonical_fuel(criteria.group(1)), created, text)


def snapshots(pages: list[Page]) -> list[list[Page]]:
    """Group PDFs into snapshots: saved within SNAPSHOT_GAP of each other, and
    one PDF per fuel type. A folder holding several days' PDFs gives one
    group per day."""
    pages = sorted(pages, key=lambda p: (p.created is None, p.created or datetime.min))
    groups: list[list[Page]] = []
    for page in pages:
        last = groups[-1] if groups else None
        if (
            last
            and page.fuel not in {p.fuel for p in last}
            and (
                page.created is None
                or last[-1].created is None
                or page.created - last[-1].created <= SNAPSHOT_GAP
            )
        ):
            last.append(page)
        else:
            groups.append([page])
    return groups


def collect(paths: list[Path]) -> list[Page]:
    """PDFs named directly, plus every observatory PDF in folders named.
    Other PDFs in a folder (a Downloads folder has plenty) are skipped."""
    pages = []
    for path in paths:
        if path.is_dir():
            found = [read_pdf(p) for p in sorted(path.glob("*.pdf"))]
            pages += [p for p in found if p]
            print(f"{path}: {sum(1 for p in found if p)} observatory PDFs")
        else:
            page = read_pdf(path)
            if page is None:
                raise ValueError(f"{path.name}: not a fuel price observatory page")
            pages.append(page)
    return pages


def write_snapshot(
    group: list[Page],
    data_dir: Path,
    known: Known,
    nophone: NoPhone,
    brands: set[str],
    stamp: datetime | None,
    force: bool,
) -> Path | None:
    created = [p.created for p in group if p.created]
    stamp = stamp or (min(created) if created else None)
    if stamp is None:
        raise ValueError("no creation time in the PDFs: pass --stamp")
    out = data_dir / f"fuel_prices_{stamp:%Y-%m-%d_%H%M}.csv"
    if out.exists() and not force:
        print(f"{out.name}: already there, skipped (--force to rewrite)")
        return None
    missing = set(FUEL_TYPES) - {p.fuel for p in group}
    if missing:
        print(f"{out.name}: no PDF for {', '.join(sorted(missing))}")

    rows = []
    for page in group:
        stations = parse_stations(page.text.splitlines(), brands)
        prices = [float(s.price.replace(",", ".")) for s in stations]
        header = [float(h.replace(",", ".")) for h in HEADER.findall(page.text)]
        check_header(page.fuel, header, prices)
        for s in stations:
            address, area = match(s, known, nophone)
            rows.append([s.brand, address, area, s.price.replace(",", "."), page.fuel])
        print(f"  {page.fuel}: {len(stations)} stations ({page.path.name})")
    keys = [(r[0], r[1], r[4]) for r in rows]
    if len(keys) != len(set(keys)):
        raise ValueError("a station appears twice for one fuel")
    rows.sort(key=lambda r: FUEL_TYPES.index(r[4]))  # stations keep page order
    with out.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh, lineterminator="\n")
        writer.writerow(COLUMNS)
        for r in rows:
            writer.writerow([*r, f"{stamp:%Y-%m-%d %H:%M:%S}"])
    print(f"{len(rows)} rows -> {out}")
    return out


def convert(
    paths: list[Path],
    data_dir: Path,
    stamp: datetime | None = None,
    force: bool = False,
) -> list[Path]:
    known, nophone, brands = load_known(sorted(data_dir.glob("fuel_prices_*.csv")))
    if not known:
        raise SystemExit(f"no scraper CSVs in {data_dir}: fetch the fuel CSVs first")
    groups = snapshots(collect(paths))
    if not groups:
        raise SystemExit("no fuel price observatory PDFs found")
    if stamp and len(groups) > 1:
        raise SystemExit(f"--stamp needs one snapshot; these PDFs make {len(groups)}")
    written = []
    for group in groups:
        out = write_snapshot(group, data_dir, known, nophone, brands, stamp, force)
        if out:
            written.append(out)
    return written


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "pdfs",
        nargs="+",
        type=Path,
        help="the PDFs (one per fuel type), or a folder holding them",
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument(
        "--stamp",
        type=lambda s: datetime.strptime(s, "%Y-%m-%d %H:%M"),
        help='UTC time of the snapshot, "YYYY-MM-DD HH:MM"',
    )
    parser.add_argument(
        "--force", action="store_true", help="rewrite a CSV that already exists"
    )
    args = parser.parse_args(argv)
    try:
        convert(args.pdfs, args.data_dir, args.stamp, args.force)
    except (LookupError, ValueError) as exc:
        sys.exit(f"stopped: {exc}")


if __name__ == "__main__":
    main()
