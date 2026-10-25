"""Run a source from Python: the same thing ``apographe run`` does."""

from __future__ import annotations

import os
from collections.abc import Callable, Sequence
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apographe.core import registry
from apographe.core.source import Options, Report, Source, SourceError
from apographe.core.storage import Store


def run(
    source: str | Source | type[Source],
    *,
    out: str | Path = "data",
    jobs: Sequence[str] | None = None,
    day: date | str | None = None,
    limit: int | None = None,
    only: Sequence[str] | None = None,
    delay: float | None = None,
    inputs: Sequence[str | Path] = (),
    force: bool = False,
    progress: Callable[[str, date, Report | None], None] | None = None,
) -> Report:
    """Collect data from a source into dated files.

    Args:
        source: a source id such as ``"cy.ekalathi"``, or your own ``Source``
            (an instance or the class).
        out: folder to write into; the source writes under
            ``out/<country>/<name>/``.
        jobs: names of the jobs to run; default: the source's usual daily jobs.
        day: the day to file the data under, a ``date`` or ``"YYYY-MM-DD"``;
            default: today in the source's time zone.
        limit: only the first N items, for a quick trial.
        only: only these item ids.
        delay: seconds between requests; default: the source's own.
        inputs: files or folders for jobs that import.
        force: redo work that already exists.
        progress: called as ``progress(job, day, None)`` when a job starts
            and ``progress(job, day, report)`` when it ends.

    Returns:
        A ``Report`` with the rows written per table and the files written.

    Raises:
        ValueError: a job the source does not have.
        SourceError: an environment variable a job needs is not set (the
            message names the variables, never their values), or the site
            did not answer as expected.
        KeyError: an unknown source id.
        LoginWall: the site now asks for a login, so nothing was collected.

    Run a built-in source::

        from apographe import run

        report = run("cy.ekalathi", out="data", limit=5)
        print(report.rows)

    Collect from somewhere else by writing your own source: a class with one
    job that fetches data and writes a table with ``out.write_csv``::

        from apographe import PoliteClient, Report, Source, run

        class Stations(Source):
            id = "xx.fuel"  # country code, then a short name
            title = "Example fuel prices"
            country = "XX"
            homepage = "https://fuel.example.gov"
            jobs = {"prices": "every station's prices, now"}
            default_jobs = ("prices",)

            def run(self, job, out, options):
                http = PoliteClient("https://fuel.example.gov/api")
                rows = http.get_json("/stations")
                path, count = out.write_csv(
                    f"prices/{options.day}.csv", rows, ["id", "fuel", "price"]
                )
                report = Report()
                report.add("prices", count, path)
                return report

        run(Stations(), out="data")

    More in docs/adding-a-source.md.
    """
    if isinstance(source, str):
        source = registry.load(source)
    elif isinstance(source, type):
        source = source()
    jobs = list(jobs) if jobs else list(source.default_jobs)
    unknown = [job for job in jobs if job not in source.jobs]
    if unknown:
        raise ValueError(
            f"{source.id} has no job {', '.join(unknown)}; "
            f"its jobs: {', '.join(source.listed_jobs)}"
        )
    for job in jobs:
        missing = [v for v in source.job_env.get(job, ()) if not os.environ.get(v)]
        if missing:
            raise SourceError(
                f"{source.id} {job} needs {', '.join(missing)} "
                f"(see `apographe info {source.id}`)"
            )
    if day is None:
        day = datetime.now(ZoneInfo(source.timezone)).date()
    elif isinstance(day, str):
        day = date.fromisoformat(day)
    options = Options(
        day=day,
        limit=limit,
        only=list(only or []),
        delay=delay,
        inputs=[Path(p) for p in inputs],
        force=force,
    )
    store = Store(out).scope(source.folder)
    total = Report()
    for job in jobs:
        if progress:
            progress(job, day, None)
        report = source.run(job, store, options)
        if progress:
            progress(job, day, report)
        total.merge(report)
    return total
