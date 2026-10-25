import os

import pytest

from apographe import SourceError, cli, run
from apographe.core import registry
from apographe.core.source import Report, Source


class NeedsKey(Source):
    id = "xx.key"
    title = "Needs a key"
    country = "XX"
    homepage = "https://example.invalid"
    jobs = {"go": "needs a key"}
    default_jobs = ("go",)
    env = {"XX_KEY": "an API key"}
    job_env = {"go": ("XX_KEY",)}

    def run(self, job, out, options):
        return Report()


def test_missing_variable_is_named_but_not_its_value(tmp_path, monkeypatch):
    monkeypatch.delenv("XX_KEY", raising=False)
    with pytest.raises(SourceError, match="XX_KEY") as exc:
        run(NeedsKey(), out=tmp_path)
    assert "apographe info xx.key" in str(exc.value)
    monkeypatch.setenv("XX_KEY", "s3cret")
    run(NeedsKey(), out=tmp_path)  # set: runs
    monkeypatch.setenv("XX_KEY", "")
    with pytest.raises(SourceError) as exc:
        run(NeedsKey(), out=tmp_path)
    assert "s3cret" not in str(exc.value)


def test_env_file_is_read_for_one_run_only(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CYCONNECT_CLIENT_ID", raising=False)
    monkeypatch.delenv("CYCONNECT_CLIENT_SECRET", raising=False)
    monkeypatch.setenv("CYCONNECT_ENV", "from-shell")
    env = tmp_path / ".env"
    env.write_text(
        "# comment\n\nCYCONNECT_CLIENT_ID='abc'\n"
        'CYCONNECT_CLIENT_SECRET="top-secret"\nCYCONNECT_ENV=production\n'
    )
    seen = {}

    def spy(*args, **kwargs):
        seen.update(os.environ)
        raise SourceError("stop here")

    monkeypatch.setattr(cli, "run", spy)
    assert cli.main(["run", "cy.fuel", "--job", "api", "--env-file", str(env)]) == 1
    assert seen["CYCONNECT_CLIENT_ID"] == "abc"
    assert seen["CYCONNECT_CLIENT_SECRET"] == "top-secret"
    assert seen["CYCONNECT_ENV"] == "from-shell"  # already set: kept
    assert "CYCONNECT_CLIENT_ID" not in os.environ  # removed after the run
    assert "top-secret" not in capsys.readouterr().err


def test_missing_env_file(tmp_path, capsys):
    assert cli.main(["run", "cy.fuel", "--env-file", str(tmp_path / "nope")]) == 1
    assert "cannot read" in capsys.readouterr().err


def test_cy_fuel_api_needs_its_variables(tmp_path, monkeypatch):
    monkeypatch.delenv("CYCONNECT_CLIENT_ID", raising=False)
    with pytest.raises(SourceError, match="CYCONNECT_CLIENT_ID"):
        run("cy.fuel", jobs=["api"], out=tmp_path)


def test_info_lists_variables_and_docs_link(capsys, monkeypatch):
    monkeypatch.setitem(registry.BUILT_IN, "xx.key", f"{__name__}:NeedsKey")
    assert cli.main(["info", "xx.key"]) == 0
    out = capsys.readouterr().out
    assert "needs XX_KEY: an API key" in out
    assert "docs/sources/xx-key.md" in out
    assert cli.main(["info", "xx.nothing"]) == 1
    cli.main(["info", "cy.fuel"])
    assert "apographe[cy-fuel]" in capsys.readouterr().out


def test_list_marks_jobs_that_need_env(capsys, monkeypatch):
    monkeypatch.setitem(registry.BUILT_IN, "xx.key", f"{__name__}:NeedsKey")
    cli.main(["list"])
    out = capsys.readouterr().out
    assert "[needs env]" in out and "[needs extra cy-fuel]" in out


def test_hidden_job_is_not_shown_but_still_runs(capsys, tmp_path, monkeypatch):
    cli.main(["list"])
    cli.main(["info", "cy.fuel"])
    cli.main(["run", "cy.fuel", "--job", "nope"])
    shown = capsys.readouterr()
    assert "api" not in (shown.out + shown.err).replace("apographe", "")
    for name in ("CYCONNECT_CLIENT_ID", "CYCONNECT_TOKEN_URL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SourceError, match="CYCONNECT_CLIENT_ID"):
        run("cy.fuel", jobs=["api"], out=tmp_path)


def test_help_has_examples_and_docs_link(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert "apographe info cy.fuel" in out and "docs/usage.md" in out
