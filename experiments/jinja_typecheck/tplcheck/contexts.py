"""Find out which variables a declared context TypedDict provides."""

from __future__ import annotations

import importlib
import os
import sys


def context_keys(dotted: str | None) -> frozenset[str]:
    """Keys of the TypedDict named by ``dotted`` (empty for no context)."""
    if dotted is None:
        return frozenset()
    module_name, _, class_name = dotted.rpartition(".")
    try:
        cls = getattr(importlib.import_module(module_name), class_name)
        return frozenset(cls.__required_keys__ | cls.__optional_keys__)
    except (ImportError, AttributeError) as error:
        raise ValueError(f"cannot load context {dotted}: {error}") from error


def add_import_paths() -> None:
    """Make the project importable: the working directory and ``MYPYPATH``.

    Context TypedDicts, filter modules and mappers are project code that is
    imported while generating; explicit ``MYPYPATH`` entries win over what is
    already on ``sys.path``.
    """
    mypypath = [p for p in os.environ.get("MYPYPATH", "").split(":") if p]
    for entry in reversed([os.getcwd(), *mypypath]):
        if entry in sys.path:
            sys.path.remove(entry)
        sys.path.insert(0, entry)
    importlib.invalidate_caches()
