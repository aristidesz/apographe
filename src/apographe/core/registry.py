"""Find a source by its id.

Sources are listed by "module:Class" text rather than imported up front, so
running one source never imports another's dependencies (e-kalathi works
without the browser that the fuel source needs).
"""

from __future__ import annotations

from importlib import import_module

from apographe.core.source import Source

BUILT_IN = {
    "cy.ekalathi": "apographe.sources.cy.ekalathi:EkalathiSource",
    "cy.fuel": "apographe.sources.cy.fuel.source:FuelSource",
}


def available() -> dict[str, str]:
    """Source id -> "module:Class"."""
    return dict(BUILT_IN)


def load(source_id: str) -> Source:
    target = available().get(source_id)
    if target is None:
        known = ", ".join(sorted(available()))
        raise KeyError(f"unknown source {source_id!r}; known sources: {known}")
    module, _, name = target.partition(":")
    cls = getattr(import_module(module), name)
    return cls()
