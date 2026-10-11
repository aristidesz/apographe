"""Write tables to a folder: CSV (optionally gzipped) and raw JSON responses.

Every write goes to a temporary file first and is renamed into place, so a run
that dies half way never leaves a truncated file behind.
"""

from __future__ import annotations

import csv
import gzip
import io
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any


class Store:
    """A folder that tables are written into, scoped to one source."""

    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def scope(self, folder: str) -> Store:
        return Store(self.root / folder)

    def path(self, rel: str) -> Path:
        return self.root / rel

    def exists(self, rel: str) -> bool:
        return self.path(rel).exists()

    def write_csv(
        self, rel: str, rows: Iterable[Mapping[str, Any]], fields: list[str]
    ) -> tuple[Path, int]:
        """Write rows as CSV (gzipped when ``rel`` ends in .gz). Returns path, count."""
        path = self.path(rel)
        count = 0
        with _atomic(path) as fh:
            writer = csv.DictWriter(
                fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
            )
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
                count += 1
        return path, count

    def read_csv(self, rel: str) -> list[dict[str, str]]:
        path = self.path(rel)
        if not path.exists():
            return []
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))

    def append_csv(
        self, rel: str, rows: Iterable[Mapping[str, Any]], fields: list[str]
    ) -> int:
        """Append rows to a plain CSV, writing the header if the file is new.

        Used for progress files that a later run picks up from, so it is not
        atomic: each call adds whole rows and flushes.
        """
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        count = 0
        with open(path, "a", encoding="utf-8", newline="") as fh:
            writer = csv.DictWriter(
                fh, fieldnames=fields, extrasaction="ignore", lineterminator="\n"
            )
            if new:
                writer.writeheader()
            for row in rows:
                writer.writerow(row)
                count += 1
        return count

    def write_json(self, rel: str, payload: Any) -> Path:
        """Save a response untouched (gzipped when ``rel`` ends in .gz)."""
        path = self.path(rel)
        with _atomic(path) as fh:
            json.dump(payload, fh, ensure_ascii=False)
        return path


class _atomic:
    """Open a text file for writing that only appears once it is complete."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.tmp = path.with_name(f".{path.name}.tmp")
        self.file: io.BufferedWriter | None = None
        self.fh: io.TextIOWrapper | None = None

    def __enter__(self) -> io.TextIOWrapper:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = open(self.tmp, "wb")
        stream: Any = self.file  # a plain or gzip binary stream
        if self.path.suffix == ".gz":
            # mtime=0 keeps the bytes identical for identical content, so
            # re-running a day does not create a spurious git change.
            stream = gzip.GzipFile(filename="", mode="wb", fileobj=self.file, mtime=0)
        self.fh = io.TextIOWrapper(stream, encoding="utf-8", newline="")
        return self.fh

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.fh is None or self.file is None:
            return
        self.fh.close()  # also finishes the gzip stream, if any
        self.file.close()
        if exc_type is None:
            os.replace(self.tmp, self.path)
        else:
            self.tmp.unlink(missing_ok=True)
