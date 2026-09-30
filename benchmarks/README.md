# Python HTML templating benchmark

This directory compares rendering the same article list with Jinja, Mako,
Cheetah3, Airium, Yattag, dominate, Ludic, Hyperscript, Tagflow, Hyperscribe,
and `xml.etree.ElementTree`. The template includes
conditional featured badges, optional authors, tag loops, and comment counts.
It also renders a reusable topic-list component in the page navigation and for
each article with tags. Jinja defines the component as a macro; each Python
renderer exposes and calls a matching helper function.
The default workload contains 500 articles and varies the data to exercise each
branch. Jinja, Mako, and Cheetah3 each use a base template with overridable
navigation and content sections. The Jinja template lives in
`benchmarks/templates/articles.jinja2`; each renderer has its own module under
`benchmarks/renderers/`. Hyperscribe wraps the shared page container in a
`@contextmanager` function and uses the standalone package in `src/hyperscribe/`.
It renders each topic list on a single line with `doc.inline()`,
which suppresses line breaks and indentation inside its block,
so its output stays close to Jinja's.
Tagflow is the unrelated [`tagflow`](https://pypi.org/project/tagflow/) package from PyPI,
which builds an ElementTree through context managers backed by context variables.

The benchmarks are a [pytest-benchmark](https://pytest-benchmark.readthedocs.io/) suite.
Their dependencies are in the optional `benchmarks` dependency group
and require Python 3.14.
Run everything with:

```sh
uv run --group benchmarks pytest benchmarks
```

Select renderers or escaping cases with `-k`,
and change the workload with `--items`
(the default is 500 articles):

```sh
uv run --group benchmarks pytest benchmarks -k "Jinja or Hyperscribe" --items 1000
```

Use pytest-benchmark's own options to control the measurement
and to sort, compare, or save results:

```sh
uv run --group benchmarks pytest benchmarks \
    --benchmark-sort=mean --benchmark-min-rounds=50 --benchmark-warmup=on \
    --benchmark-save=baseline
```

`--benchmark-skip` runs only the output and memory checks
and `--benchmark-only` runs only the timings.

## Rendering

`test_render.py` renders the same article list with each library.
`test_output` first checks that every renderer produces the same document:
it compares tags, attributes, and visible text
while ignoring indentation-only whitespace,
because formatters lay out whitespace differently.
`test_render` then times the render,
excluding input construction and Jinja template compilation.
`test_memory` measures the peak traced Python memory of one render
after a warm-up render
and, like the output size, prints it in a table after the timing results.
`tracemalloc` does not include native allocations.

To regenerate Jinja's generated Python source for inspection, run:

```sh
uv run --group benchmarks python -m benchmarks.compile_jinja
```

The generated source is saved in `benchmarks/generated_jinja.py`.
It shows the Python function Jinja compiles for `articles.jinja2`;
the benchmark still uses Jinja's normal `Template.render()` path.

## Escaping

`test_escape.py` compares text and attribute escaping independently of document rendering.
It benchmarks `html.escape`, chained `str.replace`,
and a precomputed `str.maketrans` table with `str.translate`
on short and long strings, and checks that they agree.
