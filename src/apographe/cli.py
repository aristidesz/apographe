"""Command line: ``apographe list`` and ``apographe run <source>``.

Exit codes: 0 done, 2 the source now needs a login (nothing collected),
1 anything else.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from apographe import __version__
from apographe.core import registry
from apographe.core.source import LoginWall, Options, Report, SourceError
from apographe.core.storage import Store


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="apographe",
        description=(
            "Collect public data, source by source and day by day, into plain files."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show the sources and their jobs")

    run = sub.add_parser("run", help="run a source's jobs")
    run.add_argument("source", help="source id, e.g. cy.ekalathi")
    run.add_argument(
        "--job",
        action="append",
        dest="jobs",
        help="job to run (repeatable); default: the source's usual daily jobs",
    )
    run.add_argument(
        "--out", type=Path, default=Path("data"), help="folder to write into"
    )
    run.add_argument(
        "--date",
        type=date.fromisoformat,
        help="the day to file the data under (default: today where the source is)",
    )
    run.add_argument("--limit", type=int, help="only the first N items")
    run.add_argument(
        "--only", help="only these item ids, comma separated (e.g. 2074,1906)"
    )
    run.add_argument("--delay", type=float, help="seconds between requests")
    run.add_argument(
        "--input",
        type=Path,
        action="append",
        dest="inputs",
        default=[],
        help="file or folder for a job that imports (repeatable)",
    )
    run.add_argument("--force", action="store_true", help="redo existing work")

    args = parser.parse_args(argv)
    if args.command == "list":
        return _list()
    return _run(args)


def _list() -> int:
    for source_id in sorted(registry.available()):
        source = registry.load(source_id)
        print(f"{source.id}  {source.title} ({source.country})")
        for job, about in source.jobs.items():
            mark = "*" if job in source.default_jobs else " "
            print(f"   {mark} {job:<14} {about}")
    print("\n* runs by default")
    return 0


def _run(args: argparse.Namespace) -> int:
    try:
        source = registry.load(args.source)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    jobs = args.jobs or list(source.default_jobs)
    unknown = [job for job in jobs if job not in source.jobs]
    if unknown:
        print(
            f"{source.id} has no job {', '.join(unknown)}; "
            f"its jobs: {', '.join(source.jobs)}",
            file=sys.stderr,
        )
        return 1
    options = Options(
        day=args.date or datetime.now(ZoneInfo(source.timezone)).date(),
        limit=args.limit,
        only=[x.strip() for x in args.only.split(",")] if args.only else [],
        delay=args.delay,
        inputs=args.inputs,
        force=args.force,
    )
    out = Store(args.out).scope(source.folder)
    total = Report()
    for job in jobs:
        print(f"{source.id} {job}: started for {options.day}", flush=True)
        try:
            report = source.run(job, out, options)
        except LoginWall as exc:
            print(f"::warning::{source.id} needs a login now, skipping: {exc}")
            return 2
        except SourceError as exc:
            print(f"{source.id} {job}: stopped: {exc}", file=sys.stderr)
            return 1
        for table, count in report.rows.items():
            print(f"{source.id} {job}: {count} rows -> {table}", flush=True)
        total.merge(report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
