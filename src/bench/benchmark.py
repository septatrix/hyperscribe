"""Compare the steady-state cost of rendering the same HTML with each implementation.

Run with ``python -m bench.benchmark`` or ``benchmark-templates``.
The benchmark measures rendering only: Jinja template compilation and input data
creation happen before timed iterations.
"""

from __future__ import annotations

import argparse
import statistics
import time
import tracemalloc
from collections.abc import Callable
from html.parser import HTMLParser

from bench.models import Item
from bench.renderers import RENDERERS

Renderer = Callable[[list[Item]], str]


class _HTMLShape(HTMLParser):
    """Collect rendered tags, attributes, and text without indentation whitespace."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[tuple[object, ...]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(("start", tag, tuple(attrs)))

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.parts.append(("start", tag, tuple(attrs)))
        self.parts.append(("end", tag))

    def handle_endtag(self, tag: str) -> None:
        self.parts.append(("end", tag))

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
    categories = ("engineering", "research", "releases", "community")
    topics = ("python", "templates", "performance", "html", "tooling")
    return [
        {
            "title": f"Article {index}: <Python> & templates",
            "url": f"/articles/{index}",
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
        }
        for index in range(count)
    ]


def measure(renderer: Renderer, items: list[Item], warmup: int, rounds: int) -> float:
    for _ in range(warmup):
        renderer(items)
    samples = []
    for _ in range(rounds):
        start = time.perf_counter_ns()
        renderer(items)
        samples.append(time.perf_counter_ns() - start)
    return statistics.median(samples) / 1_000_000


def measure_peak_memory(
    renderer: Renderer, items: list[Item], warmup: int, rounds: int
) -> int:
    """Return median peak traced Python memory allocated by one render."""
    for _ in range(warmup):
        renderer(items)

    samples = []
    for _ in range(rounds):
        tracemalloc.start()
        baseline, _ = tracemalloc.get_traced_memory()
        output = renderer(items)
        _, peak = tracemalloc.get_traced_memory()
        samples.append(max(0, peak - baseline))
        # Keep the rendered document alive through the peak measurement.
        del output
        tracemalloc.stop()
    return round(statistics.median(samples))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=int, default=500, help="number of list entries")
    parser.add_argument(
        "--rounds", type=int, default=25, help="timed renders per library"
    )
    parser.add_argument(
        "--warmup", type=int, default=3, help="untimed renders per library"
    )
    parser.add_argument(
        "--show-output",
        action="store_true",
        help="print each renderer's generated HTML before the timing results",
    )
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument(
        "--include",
        "--include-renderers",
        nargs="+",
        choices=tuple(RENDERERS),
        help="run only these renderers (space-separated names)",
    )
    selection.add_argument(
        "--exclude",
        "--exclude-renderers",
        nargs="+",
        choices=tuple(RENDERERS),
        help="skip these renderers (space-separated names)",
    )
    args = parser.parse_args()
    if args.items < 0 or args.rounds < 1 or args.warmup < 0:
        parser.error("items and warmup must be non-negative; rounds must be positive")

    items = make_items(args.items)
    if args.include:
        renderers = {name: RENDERERS[name] for name in args.include}
    elif args.exclude:
        renderers = {
            name: renderer
            for name, renderer in RENDERERS.items()
            if name not in args.exclude
        }
    else:
        renderers = RENDERERS
    if not renderers:
        parser.error("renderer selection is empty")

    # Fail early if an implementation does not produce the expected output.
    outputs = {name: renderer(items) for name, renderer in renderers.items()}

    if args.show_output:
        for name, output in outputs.items():
            print(f"--- {name} ---")
            print(output)

    baseline_name, baseline_output = next(iter(outputs.items()))
    expected_shape = html_shape(baseline_output)
    for name, output in outputs.items():
        shape = html_shape(output)
        list_item_count = sum(1 for part in shape if part[:2] == ("start", "li"))
        if (
            not shape
            or not output.lstrip().lower().startswith("<!doctype html>")
            or shape[0] != ("start", "html", (("lang", "en"),))
            or shape[:4]
            != [
                ("start", "html", (("lang", "en"),)),
                ("start", "head", ()),
                ("start", "title", ()),
                ("text", "Articles"),
            ]
            or not any(part[:2] == ("start", "body") for part in shape)
            or not any(part[:2] == ("start", "main") for part in shape)
            or list_item_count != args.items
        ):
            raise RuntimeError(f"{name} produced an unexpected HTML document")
        if shape != expected_shape:
            raise RuntimeError(
                f"{name} produced HTML structure or text that differs from "
                f"{baseline_name}:\n"
                f"expected: {expected_shape!r}\nactual:   {shape!r}"
            )

    output_sizes = {
        name: len(output.encode("utf-8")) for name, output in outputs.items()
    }
    results = [
        (
            name,
            measure(renderer, items, args.warmup, args.rounds),
            measure_peak_memory(renderer, items, args.warmup, args.rounds),
            output_sizes[name],
        )
        for name, renderer in renderers.items()
    ]
    print(
        f"Median render time and peak traced memory, "
        f"{args.items} items ({args.rounds} rounds):"
    )
    results.sort(key=lambda result: result[1])
    name_width = max(len("Renderer"), *(len(name) for name in renderers))
    time_width = max(
        len("Time (ms)"),
        *(len(f"{milliseconds:.3f}") for _, milliseconds, _, _ in results),
    )
    peak_width = max(
        len("Peak memory (B)"), *(len(f"{peak:,d}") for _, _, peak, _ in results)
    )
    output_width = max(
        len("Output (B)"), *(len(f"{size:,d}") for _, _, _, size in results)
    )
    print(
        f"{'Renderer':<{name_width}}  {'Time (ms)':>{time_width}}  "
        f"{'Peak memory (B)':>{peak_width}}  {'Output (B)':>{output_width}}"
    )
    for name, milliseconds, peak_bytes, output_bytes in results:
        print(
            f"{name:<{name_width}}  {milliseconds:>{time_width}.3f}  "
            f"{peak_bytes:>{peak_width},d}  {output_bytes:>{output_width},d}"
        )


if __name__ == "__main__":
    main()
