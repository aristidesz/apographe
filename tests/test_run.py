import pytest

import apographe
from apographe import Report, Source, run
from apographe.core import registry


class Fake(Source):
    id = "xx.test"
    title = "Fake"
    country = "XX"
    homepage = "https://example.invalid"
    jobs = {"rows": "one row"}
    default_jobs = ("rows",)

    def run(self, job, out, options):
        path, count = out.write_csv(f"{options.day}.csv", [{"a": 1}], ["a"])
        report = Report()
        report.add("rows", count, path)
        return report


def test_run_instance_and_class(tmp_path):
    for source in (Fake(), Fake):
        report = run(source, out=tmp_path, day="2026-10-01")
        assert report.rows == {"rows": 1}
    assert (tmp_path / "xx/test/2026-10-01.csv").exists()


def test_run_by_id(tmp_path, monkeypatch):
    monkeypatch.setitem(registry.BUILT_IN, "xx.test", f"{__name__}:Fake")
    assert run("xx.test", out=tmp_path).rows == {"rows": 1}
    with pytest.raises(KeyError):
        run("xx.nothing", out=tmp_path)


def test_unknown_job(tmp_path):
    with pytest.raises(ValueError, match="rows"):
        run(Fake(), out=tmp_path, jobs=["nope"])


def test_progress(tmp_path):
    seen = []
    run(Fake(), out=tmp_path, progress=lambda job, day, report: seen.append(report))
    assert seen[0] is None and seen[1].rows == {"rows": 1}


def test_public_api_and_help():
    assert "run" in apographe.__all__ and apographe.Source is Source
    assert "Source" in run.__doc__ and "write_csv" in run.__doc__
