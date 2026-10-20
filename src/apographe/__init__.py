"""Apographe: collect public data, source by source and day by day, into plain files.

Quick start::

    from apographe import run

    report = run("cy.ekalathi", out="data", limit=5)
    print(report.rows)  # rows written per table

``help(run)`` shows every option and how to write your own source.
"""

from apographe._version import __version__
from apographe.core.http import PoliteClient
from apographe.core.oauth import ClientCredentials
from apographe.core.source import (
    LoginWall,
    Options,
    Report,
    Source,
    SourceError,
)
from apographe.core.storage import Store
from apographe.runner import run

__all__ = [
    "ClientCredentials",
    "LoginWall",
    "Options",
    "PoliteClient",
    "Report",
    "Source",
    "SourceError",
    "Store",
    "__version__",
    "run",
]
