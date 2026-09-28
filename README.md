# Python HTML templating benchmark

This project compares rendering the same article list with Jinja, Mako,
Cheetah3, Airium, Yattag, dominate, Ludic, Hyperscript, and
`xml.etree.ElementTree`. The template includes
conditional featured badges, optional authors, tag loops, and comment counts.
It also renders a reusable topic-list component in the page navigation and for
each article with tags. Jinja defines the component as a macro; each Python
renderer exposes and calls a matching helper function.
The default workload contains 500 articles and varies the data to exercise each
branch. The Jinja template lives in `src/bench/templates/articles.jinja2`; each
Python renderer has its own module under `src/bench/renderers/`. The
stream-backed Tagflow renderer uses the standalone package in `src/tagflow/`.

Install the project and run the benchmark:

```sh
uv sync
uv run benchmark-templates
```

You can adjust the workload and sample count:

```sh
uv run benchmark-templates --items 1000 --rounds 50 --warmup 5
```

Select renderers with `--include` or skip some with `--exclude`:

```sh
uv run benchmark-templates --include Jinja Hyperscript
uv run benchmark-templates --exclude "Tagflow StringIO" Ludic
```

The report shows median wall-clock time and peak traced Python memory per
document. Input construction and Jinja template compilation are excluded; each
library is warmed up before samples are collected. Formatters may lay out
whitespace differently, so output validation compares tags, attributes, and
visible text while ignoring indentation-only whitespace. `tracemalloc` does
not include native allocations.

To regenerate Jinja's generated Python source for inspection, run:

```sh
uv run compile-jinja-template
```

The generated source is saved in `src/bench/generated_jinja.py`. It shows the
Python function Jinja compiles for `articles.jinja2`; the benchmark still uses
Jinja's normal `Template.render()` path.

To compare text and attribute escaping independently of document rendering,
run:

```sh
uv run benchmark-escaping
```

This uses `timeit` to compare `html.escape`, chained `str.replace`, and a
precomputed `str.maketrans` table with `str.translate`. Use `--number` and
`--repeat` to adjust the measurement length and sample count.
