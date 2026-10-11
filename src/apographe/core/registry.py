"""Find sources: the ones shipped with apographe, plus any installed package
that registers more under the ``apographe.sources`` entry point group:

    [project.entry-points."apographe.sources"]
    gr.ekatanalotis = "apographe_gr.ekatanalotis:EkatanalotisSource"
"""

from __future__ import annotations

from importlib import import_module
from importlib.metadata import entry_points

from apographe.core.source import Source

BUILT_IN = {
    "cy.ekalathi": "apographe.sources.cy.ekalathi:EkalathiSource",
    "cy.fuel": "apographe.sources.cy.fuel.source:FuelSource",
}


def available() -> dict[str, str]:
    """Source id -> "module:Class", built-in sources first."""
    found = dict(BUILT_IN)
    for ep in entry_points(group="apographe.sources"):
        found.setdefault(ep.name, ep.value)
    return found


def load(source_id: str) -> Source:
    target = available().get(source_id)
    if target is None:
        known = ", ".join(sorted(available()))
        raise KeyError(f"unknown source {source_id!r}; known sources: {known}")
    module, _, name = target.partition(":")
    cls = getattr(import_module(module), name)
    return cls()
