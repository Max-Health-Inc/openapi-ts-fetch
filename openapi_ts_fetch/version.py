"""Single source of truth for the package version, read from installed metadata."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("openapi-ts-fetch")
except PackageNotFoundError:  # running from a source tree without an install
    __version__ = "0.0.0.dev0"
