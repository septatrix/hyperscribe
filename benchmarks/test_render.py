"""Render the same article list with each library.

``test_output`` checks that every renderer produces the same document.
``test_render`` times it, and ``test_memory`` measures its peak traced memory;
the memory results are printed as a table at the end of the run.
"""

from __future__ import annotations

import pytest

from benchmarks.models import Item
from benchmarks.renderers import RENDERERS, load_renderer
from benchmarks.support import (
    MEMORY_RESULTS,
    check_document,
    html_shape,
    peak_memory,
)

NAMES = list(RENDERERS)


@pytest.fixture(scope="module")
def expected_shape(items: list[Item]) -> list[tuple[object, ...]]:
    return html_shape(load_renderer(NAMES[0])(items))


@pytest.mark.parametrize("name", NAMES)
def test_output(
    name: str, items: list[Item], expected_shape: list[tuple[object, ...]]
) -> None:
    shape = check_document(name, load_renderer(name)(items), len(items))
    assert shape == expected_shape, f"{name} differs from {NAMES[0]}"


@pytest.mark.parametrize("name", NAMES)
def test_memory(name: str, items: list[Item]) -> None:
    renderer = load_renderer(name)
    renderer(items)  # Warm up caches and lazy imports outside the measurement.
    MEMORY_RESULTS[name] = (
        peak_memory(renderer, items),
        len(renderer(items).encode("utf-8")),
    )


@pytest.mark.benchmark(group="render")
@pytest.mark.parametrize("name", NAMES)
def test_render(benchmark, name: str, items: list[Item]) -> None:
    benchmark(load_renderer(name), items)
