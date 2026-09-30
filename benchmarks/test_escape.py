"""Compare equivalent HTML escaping implementations."""

from __future__ import annotations

import html

import pytest

TEXT_TABLE = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})
ATTRIBUTE_TABLE = str.maketrans(
    {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#x27;",
    }
)


def translate_text(value: str) -> str:
    return value.translate(TEXT_TABLE)


def replace_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def translate_attribute(value: str) -> str:
    return value.translate(ATTRIBUTE_TABLE)


def replace_attribute(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


SHORT = "A short summary for an article & its readers."
LONG = (SHORT + ' <tag attr="value">O\'Reilly & friends</tag> ') * 64

IMPLEMENTATIONS = {
    "text": {
        "html.escape": lambda value: html.escape(value, quote=False),
        "replace": replace_text,
        "translate": translate_text,
    },
    "attribute": {
        "html.escape": lambda value: html.escape(value, quote=True),
        "replace": replace_attribute,
        "translate": translate_attribute,
    },
}

CASES = [
    pytest.param(kind, size, value, id=f"{kind}-{size}")
    for kind in IMPLEMENTATIONS
    for size, value in (("short", SHORT), ("long", LONG))
]


@pytest.mark.parametrize("method", ["html.escape", "replace", "translate"])
@pytest.mark.parametrize(("kind", "size", "value"), CASES)
def test_escape(benchmark, kind: str, size: str, value: str, method: str) -> None:
    escape = IMPLEMENTATIONS[kind][method]
    expected = IMPLEMENTATIONS[kind]["html.escape"](value)
    benchmark.group = f"escape {kind} {size}"
    assert benchmark(escape, value) == expected
