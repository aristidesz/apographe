"""Command line: ``apographe list`` and ``apographe run <source>``.

Exit codes: 0 done, 2 the source now needs a login (nothing collected),
1 anything else.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from apographe._version import __version__
from apographe.core import registry
from apographe.core.source import LoginWall, Report, SourceError
from apographe.runner import run


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
    current = args.source

    def progress(job: str, day: date, report: Report | None) -> None:
        nonlocal current
        current = f"{args.source} {job}"
        if report is None:
            print(f"{current}: started for {day}", flush=True)
            return
        for table, count in report.rows.items():
            print(f"{current}: {count} rows -> {table}", flush=True)

    try:
        run(
            args.source,
            out=args.out,
            jobs=args.jobs,
            day=args.date,
            limit=args.limit,
            only=[x.strip() for x in args.only.split(",")] if args.only else None,
            delay=args.delay,
            inputs=args.inputs,
            force=args.force,
            progress=progress,
        )
    except LoginWall as exc:
        print(f"::warning::{args.source} needs a login now, skipping: {exc}")
        return 2
    except SourceError as exc:
        print(f"{current}: stopped: {exc}", file=sys.stderr)
        return 1
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
