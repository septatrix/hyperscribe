"""Pytest options and fixtures for the benchmarks."""

from __future__ import annotations

import pytest

from benchmarks.models import Item
from benchmarks.support import MEMORY_RESULTS, make_items


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--items", type=int, default=500, help="number of list entries to render"
    )


@pytest.fixture(scope="session")
def items(request: pytest.FixtureRequest) -> list[Item]:
    return make_items(request.config.getoption("--items"))


def pytest_terminal_summary(terminalreporter: pytest.TerminalReporter) -> None:
    if not MEMORY_RESULTS:
        return
    terminalreporter.section("peak memory per render")
    rows = sorted(MEMORY_RESULTS.items(), key=lambda row: row[1][0])
    name_width = max(len("Renderer"), *(len(name) for name, _ in rows))
    terminalreporter.write_line(
        f"{'Renderer':<{name_width}}  {'Peak memory (B)':>16}  {'Output (B)':>12}"
    )
    for name, (peak, output_size) in rows:
        terminalreporter.write_line(
            f"{name:<{name_width}}  {peak:>16,d}  {output_size:>12,d}"
        )
    terminalreporter.write_line(
        "Peak memory is traced Python allocations only; native allocations are excluded."
    )
