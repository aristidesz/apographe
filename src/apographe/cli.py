"""Command line: ``apographe list`` and ``apographe run <source>``.

Exit codes: 0 done, 2 the source now needs a login (nothing collected),
1 anything else.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

from apographe._version import __version__
from apographe.core import registry
from apographe.core.source import LoginWall, Report, SourceError
from apographe.runner import run

DOCS = "https://github.com/aristidesz/apographe/blob/main/docs"
EPILOG = f"""examples:
  apographe list                                   what you can collect
  apographe info cy.fuel                           a source's jobs and what they need
  apographe run cy.ekalathi --limit 5 --out data   try a source

docs: {DOCS}/usage.md"""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="apographe",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=EPILOG,
        description=(
            "Collect public data, source by source and day by day, into plain files."
        ),
    )
    parser.add_argument("--version", action="version", version=__version__)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="show the sources and their jobs")

    info = sub.add_parser("info", help="show a source's jobs and what they need")
    info.add_argument("source", help="source id, e.g. cy.fuel")

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
    run.add_argument(
        "--env-file",
        type=Path,
        help="file of KEY=VALUE lines to use as environment variables for this run",
    )

    args = parser.parse_args(argv)
    if args.command == "list":
        return _list()
    if args.command == "info":
        return _info(args.source)
    return _run(args)


def _list() -> int:
    for source_id in sorted(registry.available()):
        source = registry.load(source_id)
        print(f"{source.id}  {source.title} ({source.country})")
        for job, about in source.jobs.items():
            mark = "*" if job in source.default_jobs else " "
            needs = []
            if source.job_env.get(job):
                needs.append("[needs env]")
            if job in source.extras:
                needs.append(f"[needs extra {source.extras[job]}]")
            print(f"   {mark} {job:<14} {about} {' '.join(needs)}".rstrip())
    print("\n* runs by default")
    return 0


def _info(source_id: str) -> int:
    try:
        source = registry.load(source_id)
    except KeyError as exc:
        print(exc.args[0], file=sys.stderr)
        return 1
    print(f"{source.id}: {source.title}")
    print(f"homepage:  {source.homepage}")
    print(f"time zone: {source.timezone}")
    print(f"output:    <out>/{source.folder}/")
    print("jobs:")
    for job, about in source.jobs.items():
        default = " (default)" if job in source.default_jobs else ""
        print(f"  {job}{default}: {about}")
        if job in source.extras:
            print(f"    install: pip install 'apographe[{source.extras[job]}]'")
        for name in source.job_env.get(job, ()):
            print(f"    needs {name}: {source.env.get(name, '')}")
    optional = [
        n for n in source.env if not any(n in v for v in source.job_env.values())
    ]
    for name in optional:
        print(f"optional {name}: {source.env[name]}")
    print(f"docs: {DOCS}/sources/{source.id.replace('.', '-')}.md")
    return 0


def _read_env_file(path: Path) -> dict[str, str]:
    """KEY=VALUE lines; blank lines and # comments skipped, quotes stripped."""
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _run(args: argparse.Namespace) -> int:
    added: list[str] = []
    if args.env_file:
        try:
            values = _read_env_file(args.env_file)
        except OSError as exc:
            print(f"cannot read {args.env_file}: {exc.strerror}", file=sys.stderr)
            return 1
        for key, value in values.items():
            if key not in os.environ:  # a variable already set wins
                os.environ[key] = value
                added.append(key)
    try:
        return _run_source(args)
    finally:
        for key in added:  # the file only applies to this run
            del os.environ[key]


def _run_source(args: argparse.Namespace) -> int:
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
