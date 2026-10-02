"""Compare equivalent HTML escaping implementations.

Each implementation escapes the same strings,
which vary in length (short and long)
and in how many characters need escaping (none, little, or a lot).
Besides ``html.escape``, ``str.replace`` and ``str.translate``
this includes the strategies that first look for characters to escape,
because most strings in real documents contain none:
chained ``in`` checks and a compiled regular expression
that decide whether to call ``html.escape`` at all,
and a regular expression substitution that escapes in a single pass.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable

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
TEXT_NEEDLE = re.compile(r"[&<>]")
ATTRIBUTE_NEEDLE = re.compile(r"""[&<>"']""")
TEXT_REPLACEMENTS = {"&": "&amp;", "<": "&lt;", ">": "&gt;"}
ATTRIBUTE_REPLACEMENTS = {**TEXT_REPLACEMENTS, '"': "&quot;", "'": "&#x27;"}


def escape_text(value: str) -> str:
    return html.escape(value, quote=False)


def escape_attribute(value: str) -> str:
    return html.escape(value, quote=True)


def replace_text(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def replace_attribute(value: str) -> str:
    return (
        value.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def translate_text(value: str) -> str:
    return value.translate(TEXT_TABLE)


def translate_attribute(value: str) -> str:
    return value.translate(ATTRIBUTE_TABLE)


def in_checks_text(value: str) -> str:
    if "&" in value or "<" in value or ">" in value:
        return html.escape(value, quote=False)
    return value


def in_checks_attribute(value: str) -> str:
    if "&" in value or "<" in value or ">" in value or '"' in value or "'" in value:
        return html.escape(value, quote=True)
    return value


def regex_check_text(value: str) -> str:
    if TEXT_NEEDLE.search(value):
        return html.escape(value, quote=False)
    return value


def regex_check_attribute(value: str) -> str:
    if ATTRIBUTE_NEEDLE.search(value):
        return html.escape(value, quote=True)
    return value


def regex_sub_text(value: str) -> str:
    return TEXT_NEEDLE.sub(lambda match: TEXT_REPLACEMENTS[match.group()], value)


def regex_sub_attribute(value: str) -> str:
    return ATTRIBUTE_NEEDLE.sub(
        lambda match: ATTRIBUTE_REPLACEMENTS[match.group()], value
    )


IMPLEMENTATIONS: dict[str, dict[str, Callable[[str], str]]] = {
    "text": {
        "html.escape": escape_text,
        "replace": replace_text,
        "translate": translate_text,
        "in-checks": in_checks_text,
        "regex-check": regex_check_text,
        "regex-sub": regex_sub_text,
    },
    "attribute": {
        "html.escape": escape_attribute,
        "replace": replace_attribute,
        "translate": translate_attribute,
        "in-checks": in_checks_attribute,
        "regex-check": regex_check_attribute,
        "regex-sub": regex_sub_attribute,
    },
}

CLEAN = "A short summary for an article about templates and their readers. "
SPECIAL = "&<>\"'"
SIZES = {"short": 48, "long": 4096}
# The number of characters between escapable ones, or None for no such characters.
DENSITIES = {"none": None, "little": 400, "lot": 4}


def make_text(size: int, spacing: int | None) -> str:
    """Return text of the given length with an escapable character every few."""
    text = (CLEAN * (size // len(CLEAN) + 1))[:size]
    if spacing is None:
        return text
    characters = list(text)
    # Strings shorter than the spacing still get one, in the middle.
    positions = [size // 2] if size < spacing else range(spacing - 1, size, spacing)
    for count, position in enumerate(positions):
        characters[position] = SPECIAL[count % len(SPECIAL)]
    return "".join(characters)


CASES = [
    pytest.param(kind, make_text(size, spacing), id=f"{kind}-{size_name}-{density}")
    for kind in IMPLEMENTATIONS
    for size_name, size in SIZES.items()
    for density, spacing in DENSITIES.items()
]


def test_texts_have_the_intended_density() -> None:
    assert not any(c in make_text(SIZES["long"], None) for c in SPECIAL)
    short_little = make_text(SIZES["short"], DENSITIES["little"])
    assert sum(c in SPECIAL for c in short_little) == 1
    long_little = make_text(SIZES["long"], DENSITIES["little"])
    assert sum(c in SPECIAL for c in long_little) == SIZES["long"] // 400
    long_lot = make_text(SIZES["long"], DENSITIES["lot"])
    assert sum(c in SPECIAL for c in long_lot) == SIZES["long"] // 4
    assert all(len(make_text(size, None)) == size for size in SIZES.values())


@pytest.mark.parametrize("method", IMPLEMENTATIONS["text"])
@pytest.mark.parametrize(("kind", "value"), CASES)
def test_escape(benchmark, kind: str, value: str, method: str) -> None:
    escape = IMPLEMENTATIONS[kind][method]
    expected = IMPLEMENTATIONS[kind]["html.escape"](value)
    benchmark.group = f"escape {kind} {len(value)} B, " + (
        f"{sum(c in SPECIAL for c in value)} special"
    )
    assert benchmark(escape, value) == expected
