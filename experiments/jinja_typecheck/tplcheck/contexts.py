"""Find out which variables a declared context TypedDict provides."""

from __future__ import annotations

import importlib


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
