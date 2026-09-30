# Benchmarks

The repository includes a benchmark comparing hyperscribe with
Jinja, Mako, Cheetah3, Airium, Yattag, dominate, Ludic, Hyperscript, Tagflow,
and `xml.etree.ElementTree`.
Each library renders the same article list
with conditional badges, optional authors, tag loops and a reusable component.

```sh
uv sync --group benchmarks
uv run --group benchmarks pytest benchmarks
uv run --group benchmarks pytest benchmarks -k "Jinja or Hyperscribe" --items 1000
```

The benchmarks use [pytest-benchmark](https://pytest-benchmark.readthedocs.io/),
so its options for sorting, comparing, and saving results all apply.
The dependencies are in the optional `benchmarks` dependency group
and require Python 3.14.

Every renderer is first checked to produce the same document.
The report then shows the timing statistics for each library,
followed by a table of the peak traced Python memory and output size of one render.
See `benchmarks/README.md` in the repository for the methodology.
