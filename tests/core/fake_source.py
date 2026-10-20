"""A tiny source for the registry tests."""

from __future__ import annotations

from apographe.core.source import Options, Report, Source
from apographe.core.storage import Store


class FakeSource(Source):
    id = "xx.test"
    title = "Fake"
    country = "XX"
    homepage = "https://example.invalid"
    jobs = {"rows": "one row"}
    default_jobs = ("rows",)

    def run(self, job: str, out: Store, options: Options) -> Report:
        report = Report()
        path, count = out.write_csv("rows.csv", [{"a": 1}], ["a"])
        report.add("rows", count, path)
        return report


class NotASource:
    pass
