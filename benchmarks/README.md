# Python HTML templating benchmark

This directory compares rendering the same article list with Jinja, Mako,
Cheetah3, Airium, Yattag, dominate, Ludic, Hyperscript, Tagflow, Hyperscribe,
and `xml.etree.ElementTree`. The template includes
conditional featured badges, optional authors, tag loops, and comment counts.
It also renders a reusable topic-list component in the page navigation and for
each article with tags.
Each article further exercises what a real page needs besides nested elements:
an HTML comment, a void `<img>` element with numeric attributes,
attributes that are only present for some articles
(`class="featured"`, `target` and `rel` on external links),
a boolean `hidden` attribute for drafts,
a hyphenated `data-category` attribute,
and a numeric rating written as content.
The head has void `<meta>` and `<link>` elements
and a `<script defer>`. Jinja defines the component as a macro; each Python
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
It also uses the attribute and content handling of the package:
`None` omits an optional attribute,
`True` writes a boolean attribute,
`class_` becomes `class`, `data={"category": ...}` becomes `data-category`,
numbers are written as content and attributes without `str()`,
and `doc.void_tag` and `doc.comment` write the void elements and the comments.
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
it compares tags, attributes, comments, and visible text
while ignoring indentation-only whitespace,
because formatters lay out whitespace differently.
Libraries also write void elements as `<img>` or `<img />`,
order attributes differently,
and write boolean attributes as `hidden`, `hidden=""`, `hidden="hidden"` or `hidden="true"`,
so the comparison treats those as equal.
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
a precomputed `str.maketrans` table with `str.translate`,
two strategies that look for characters to escape before calling `html.escape`
(chained `in` checks and a compiled regular expression),
and a single-pass `re.sub`.
Every implementation runs on short (48 characters) and long (4,096 characters) strings
with no, little (one in 400 characters),
or a lot of (one in four) characters that need escaping,
and its result is checked against `html.escape`.
