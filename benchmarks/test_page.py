"""Render a larger dashboard page with Hyperscribe.

The article list of ``test_render`` is flat and every library renders it.
This page is deeper and heavier on attributes, to profile Hyperscribe itself.
"""

from __future__ import annotations

import tracemalloc
from typing import Any

import pytest

from .hyperscribe_page import make_data, render


@pytest.fixture(scope="module")
def data() -> dict[str, Any]:
    return make_data()


def test_page_output(data: dict[str, Any]) -> None:
    html = render(data)
    assert html.startswith("<!DOCTYPE html>\n<html")
    assert html.count("<article ") == len(data["products"])
    assert html.count("<tr ") == len(data["orders"])
    assert html.endswith("</html>\n")


def test_page_memory(data: dict[str, Any]) -> None:
    render(data)  # Warm up caches outside the measurement.
    tracemalloc.start()
    try:
        render(data)
        peak = tracemalloc.get_traced_memory()[1]
    finally:
        tracemalloc.stop()
    print(f"\npeak traced memory of the page: {peak:,d} B")


@pytest.mark.benchmark(group="page")
def test_page_render(benchmark, data: dict[str, Any]) -> None:
    benchmark(render, data)
