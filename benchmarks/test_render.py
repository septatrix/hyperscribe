"""Render the same article list with each library.

``test_output`` checks that every renderer produces the same document.
``test_render`` times it and records peak memory and output size
in the benchmark's ``extra_info``.
"""

from __future__ import annotations

import pytest

from benchmarks.models import Item
from benchmarks.renderers import RENDERERS, load_renderer
from benchmarks.support import check_document, html_shape, make_items, peak_memory

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


@pytest.mark.benchmark(group="render")
@pytest.mark.parametrize("name", NAMES)
def test_render(benchmark, name: str, items: list[Item]) -> None:
    renderer = load_renderer(name)
    output = benchmark(renderer, items)
    benchmark.extra_info["items"] = len(items)
    benchmark.extra_info["output_bytes"] = len(output.encode("utf-8"))
    benchmark.extra_info["peak_memory_bytes"] = peak_memory(renderer, items)
