"""Pluggable output format discovery.

Drop a module with a ``write(rows, file)`` function into this package
and it becomes available as ``--format <module_name>``.
"""

import importlib
import pkgutil
from collections.abc import Callable
from pathlib import Path

_registry: dict[str, Callable] | None = None


def _discover() -> dict[str, Callable]:
    global _registry
    if _registry is not None:
        return _registry
    _registry = {}
    pkg_path = Path(__file__).parent
    for info in pkgutil.iter_modules([str(pkg_path)]):
        mod = importlib.import_module(f".{info.name}", __package__)
        if hasattr(mod, "write"):
            _registry[info.name] = mod.write
    return _registry


def available_formats() -> list[str]:
    """Return sorted list of discovered format names."""
    return sorted(_discover().keys())


def get_writer(name: str):
    """Return the write function for a format, or None."""
    return _discover().get(name)
