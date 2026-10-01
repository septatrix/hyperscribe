"""Input data and output checks shared by the benchmarks."""

from __future__ import annotations

import tracemalloc
from collections.abc import Callable
from html.parser import HTMLParser

from .models import Item

Renderer = Callable[[list[Item]], str]

# Filled by ``test_memory`` and printed by the terminal summary in ``conftest``:
# renderer name -> (peak traced memory of one render, output size), in bytes.
MEMORY_RESULTS: dict[str, tuple[int, int]] = {}


# Elements without an end tag. Libraries write them as ``<img>`` or ``<img />``,
# which is the same element, so neither form gets an end event in the shape.
VOID_ELEMENTS = frozenset({"br", "hr", "img", "input", "link", "meta"})

# Libraries write boolean attributes as ``hidden``, ``hidden=""``,
# ``hidden="hidden"`` or ``hidden="true"``, which all mean the same.
BOOLEAN_ATTRIBUTES = frozenset({"defer", "hidden"})


def _normalize_attributes(
    attrs: list[tuple[str, str | None]],
) -> tuple[tuple[str, str | None], ...]:
    # Libraries also order attributes differently, so the order is not compared.
    return tuple(
        sorted(
            (name, "")
            if name in BOOLEAN_ATTRIBUTES and value in (None, "", name, "true", "True")
            else (name, value)
            for name, value in attrs
        )
    )


class _HTMLShape(HTMLParser):
    """Collect rendered tags, attributes, and text without indentation whitespace."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[tuple[object, ...]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(("start", tag, _normalize_attributes(attrs)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(("start", tag, _normalize_attributes(attrs)))
        if tag not in VOID_ELEMENTS:
            self.parts.append(("end", tag))

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(("end", tag))

    def handle_comment(self, data: str) -> None:
        self.parts.append(("comment", data.strip()))

    def handle_data(self, data: str) -> None:
        self.parts.append(("text", data))


def html_shape(source: str) -> list[tuple[object, ...]]:
    parser = _HTMLShape()
    parser.feed(source)
    parser.close()
    normalized: list[tuple[object, ...]] = []
    text_parts: list[str] = []
    for part in parser.parts:
        if part[0] == "text":
            text_parts.append(str(part[1]))
            continue
        if text_parts:
            text = " ".join("".join(text_parts).split())
            if text:
                normalized.append(("text", text))
            text_parts.clear()
        normalized.append(part)
    if text_parts:
        text = " ".join("".join(text_parts).split())
        if text:
            normalized.append(("text", text))
    return normalized


def make_items(count: int) -> list[Item]:
    """Build articles that vary so that every branch of the template is exercised."""
    categories = ("engineering", "research", "releases", "community")
    topics = ("python", "templates", "performance", "html", "tooling")
    return [
        {
            "id": index,
            "title": f"Article {index}: <Python> & templates",
            "url": (
                f"https://example.org/articles/{index}"
                if index % 7 == 0
                else f"/articles/{index}"
            ),
            "summary": (
                f"A detailed summary for article {index}, covering HTML generation, "
                "safe escaping, and performance tradeoffs for readers."
            ),
            "category": categories[index % len(categories)],
            "featured": index % 4 == 0,
            "author": "" if index % 3 == 0 else f"Author {index % 17}",
            "tags": []
            if index % 5 == 0
            else [topics[index % len(topics)], topics[(index + 2) % len(topics)]],
            "comments": 0 if index % 6 == 0 else (index % 23) + 1,
            "thumbnail": f"/thumbnails/{index}.png",
            "external": index % 7 == 0,
            "draft": index % 11 == 0,
            "rating": (index % 5) + 1,
        }
        for index in range(count)
    ]


def check_document(name: str, output: str, item_count: int) -> list[tuple[object, ...]]:
    """Raise unless the output is the expected document, and return its shape."""
    shape = html_shape(output)
    list_item_count = sum(1 for part in shape if part[:2] == ("start", "li"))
    if (
        not shape
        or not output.lstrip().lower().startswith("<!doctype html>")
        or shape[:4]
        != [
            ("start", "html", (("lang", "en"),)),
            ("start", "head", ()),
            ("start", "title", ()),
            ("text", "Articles"),
        ]
        or not any(part[:2] == ("start", "body") for part in shape)
        or not any(part[:2] == ("start", "main") for part in shape)
        or list_item_count != item_count
    ):
        raise AssertionError(f"{name} produced an unexpected HTML document")
    return shape


def peak_memory(renderer: Renderer, items: list[Item]) -> int:
    """Return the peak traced Python memory allocated by one render, in bytes."""
    tracemalloc.start()
    try:
        baseline, _ = tracemalloc.get_traced_memory()
        output = renderer(items)
        _, peak = tracemalloc.get_traced_memory()
        # Keep the rendered document alive through the peak measurement.
        del output
    finally:
        tracemalloc.stop()
    return max(0, peak - baseline)
