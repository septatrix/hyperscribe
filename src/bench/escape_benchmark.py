"""Microbenchmark equivalent HTML escaping implementations with ``timeit``."""

from __future__ import annotations

import argparse
import html
import statistics
import timeit
from collections.abc import Callable

TEXT_TABLE = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;"})
ATTRIBUTE_TABLE = str.maketrans(
    {
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&apos;",
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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--number", type=int, default=20_000, help="calls per sample")
    parser.add_argument("--repeat", type=int, default=5, help="samples per method")
    args = parser.parse_args()
    if args.number < 1 or args.repeat < 1:
        parser.error("number and repeat must be positive")

    short = "A short summary for an article & its readers."
    long = (short + ' <tag attr="value">O\'Reilly & friends</tag> ') * 64
    cases: tuple[tuple[str, str, bool], ...] = (
        ("text short", short, False),
        ("text long", long, False),
        ("attribute short", short, True),
        ("attribute long", long, True),
    )

    print(f"Median time per call ({args.number:,} calls/sample, {args.repeat} samples)")
    print(f"{'case':18} {'html.escape':>13} {'replace':>13} {'translate':>13}  units")
    for label, value, quote in cases:
        escape = lambda text: html.escape(text, quote=quote)
        replace: Callable[[str], str] = replace_attribute if quote else replace_text
        translate: Callable[[str], str] = (
            translate_attribute if quote else translate_text
        )
        expected = escape(value)
        if replace(value) != expected or translate(value) != expected:
            raise RuntimeError(f"Escapers produced different output for {label}")

        timings = []
        for function in (escape, replace, translate):
            call = lambda function=function, value=value: function(value)
            samples = timeit.repeat(call, number=args.number, repeat=args.repeat)
            timings.append(statistics.median(samples) / args.number * 1_000_000_000)
        print(
            f"{label:18} {timings[0]:13.1f} {timings[1]:13.1f} "
            f"{timings[2]:13.1f}  ns/call"
        )


if __name__ == "__main__":
    main()
