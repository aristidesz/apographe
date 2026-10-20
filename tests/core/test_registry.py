from importlib.metadata import EntryPoint

import pytest

from apographe import cli
from apographe.core import registry

FAKE = "tests.core.fake_source:FakeSource"


def plug(monkeypatch, *eps):
    monkeypatch.setattr(
        registry,
        "entry_points",
        lambda group: [EntryPoint(n, v, group) for n, v in eps],
    )


def test_entry_point_is_discovered(monkeypatch):
    plug(monkeypatch, ("xx.test", FAKE))
    assert registry.available()["xx.test"] == FAKE
    assert registry.load("xx.test").id == "xx.test"


def test_plugin_cannot_replace_built_in(monkeypatch):
    plug(monkeypatch, ("cy.fuel", FAKE))
    with pytest.warns(UserWarning, match="cy.fuel"):
        found = registry.available()
    assert found["cy.fuel"] == registry.BUILT_IN["cy.fuel"]


def test_load_dotted_path_and_reject_non_source():
    assert registry.load(FAKE).id == "xx.test"
    with pytest.raises(TypeError, match="Source"):
        registry.load("tests.core.fake_source:NotASource")


def test_list_survives_broken_plugin(monkeypatch, capsys):
    plug(monkeypatch, ("xx.broken", "no_such_module:Nope"))
    assert cli.main(["list"]) == 0
    out = capsys.readouterr().out
    assert "could not load: ModuleNotFoundError" in out
    assert "cy.ekalathi" in out
