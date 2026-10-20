"""What every source provides, and what a run hands back."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import ClassVar

from apographe.core.storage import Store


@dataclass
class Options:
    """Settings for one run, shared by every source.

    A source reads the ones that make sense for it and ignores the rest.
    """

    day: date
    limit: int | None = None  # only the first N items, for a quick trial run
    only: list[str] = field(default_factory=list)  # only these item ids
    delay: float | None = None  # seconds between requests; None = source default
    inputs: list[Path] = field(default_factory=list)  # files a job imports
    force: bool = False  # redo work that already exists


@dataclass
class Report:
    """Rows written per table. Counts only, so it is safe to print in public logs."""

    rows: dict[str, int] = field(default_factory=dict)
    files: list[Path] = field(default_factory=list)

    def add(self, table: str, count: int, path: Path | None = None) -> None:
        """Record ``count`` rows written to ``table`` (and the file, if given)."""
        self.rows[table] = self.rows.get(table, 0) + count
        if path is not None:
            self.files.append(path)

    def merge(self, other: Report) -> None:
        """Add another report's rows and files to this one."""
        for table, count in other.rows.items():
            self.add(table, count)
        self.files.extend(other.files)


class SourceError(RuntimeError):
    """The source answered, but not with what we expected."""


class LoginWall(SourceError):
    """The source now asks for a login, so there is nothing to collect."""


class Source(ABC):
    """One place data comes from, such as a country's fuel price observatory.

    Subclasses set the class attributes and implement :meth:`run`. Everything a
    source writes goes through ``out``, under the source's own folder.
    """

    id: ClassVar[str]  # "cy.ekalathi": country code, then a short name
    title: ClassVar[str]
    country: ClassVar[str]  # ISO 3166-1 alpha-2, e.g. "CY"
    homepage: ClassVar[str]
    timezone: ClassVar[str] = "UTC"  # the day a run belongs to is taken here
    jobs: ClassVar[dict[str, str]]  # job name -> one-line description
    default_jobs: ClassVar[tuple[str, ...]]  # what `apographe run <id>` does

    @property
    def folder(self) -> str:
        """Where the source writes inside a store: "cy.ekalathi" -> "cy/ekalathi"."""
        return self.id.replace(".", "/")

    @abstractmethod
    def run(self, job: str, out: Store, options: Options) -> Report:
        """Run one job, write its tables to ``out`` and report what was written."""
