"""Pytest options and fixtures for the benchmarks."""

from __future__ import annotations

import pytest

from benchmarks.models import Item
from benchmarks.support import make_items


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--items", type=int, default=500, help="number of list entries to render"
    )


@pytest.fixture(scope="session")
def items(request: pytest.FixtureRequest) -> list[Item]:
    return make_items(request.config.getoption("--items"))
