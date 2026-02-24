"""Automolt CLI - A command-line client for the Moltbook social network."""

import sys

sys.dont_write_bytecode = True

from importlib.metadata import PackageNotFoundError, version  # noqa: E402

try:
    __version__ = version("automolt")
except PackageNotFoundError:
    __version__ = "0.0.0-dev"
