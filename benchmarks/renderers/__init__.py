"""Renderer implementations used by the benchmark."""

from collections.abc import Callable
from importlib import import_module

from benchmarks.models import Item

# Modules are imported on demand so that running one renderer does not require
# every other library to be importable.
RENDERERS = {
    "Jinja": "jinja",
    "Airium": "airium",
    "Yattag": "yattag",
    "Hyperscribe": "hyperscribe",
    "Tagflow": "tagflow",
    "dominate": "dominate",
    "Ludic": "ludic",
    "ElementTree": "element_tree",
    "Hyperscript": "hyperscript",
    "Mako": "mako",
    "Cheetah3": "cheetah",
}


def load_renderer(name: str) -> Callable[[list[Item]], str]:
    """Import and return the ``render`` function of the named renderer."""
    return import_module(f"benchmarks.renderers.{RENDERERS[name]}").render
