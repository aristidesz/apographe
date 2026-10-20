"""The installed version, in its own module so core code can import it early."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("apographe")
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "0.0.0"
