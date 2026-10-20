"""Find a source by its id.

Sources are listed by "module:Class" text rather than imported up front, so
running one source never imports another's dependencies (e-kalathi works
without the browser that the fuel source needs).

Other packages add sources through the ``apographe.sources`` entry point group.
"""

from __future__ import annotations

import os
import sys
import warnings
from importlib import import_module
from importlib.metadata import entry_points

from apographe.core.source import Source

BUILT_IN = {
    "cy.ekalathi": "apographe.sources.cy.ekalathi:EkalathiSource",
    "cy.fuel": "apographe.sources.cy.fuel.source:FuelSource",
}


ENTRY_POINT_GROUP = "apographe.sources"


def available() -> dict[str, str]:
    """Source id -> "module:Class": the built-in sources plus installed plug-ins."""
    found = dict(BUILT_IN)
    for ep in entry_points(group=ENTRY_POINT_GROUP):
        if ep.name in BUILT_IN:
            warnings.warn(
                f"plug-in {ep.value!r} cannot replace the built-in source {ep.name!r}",
                stacklevel=2,
            )
        else:
            found[ep.name] = ep.value
    return found


def load(spec: str) -> Source:
    """Make a source from its id (``"cy.ekalathi"``) or a ``"module:Class"`` path.

    Raises KeyError for an unknown id and TypeError if the class is not a Source.
    """
    target = spec
    if ":" in spec:
        if os.getcwd() not in sys.path:  # the command does not put it there itself
            sys.path.insert(0, os.getcwd())
    else:
        found = available().get(spec)
        if found is None:
            known = ", ".join(sorted(available()))
            raise KeyError(f"unknown source {spec!r}; known sources: {known}")
        target = found
    module, _, name = target.partition(":")
    cls = getattr(import_module(module), name)
    if not (isinstance(cls, type) and issubclass(cls, Source)):
        raise TypeError(f"{target} is not a Source subclass")
    return cls()
