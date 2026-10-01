# hyperscribe

A small, dependency-free HTML templating engine for Python.
You write markup as ordinary Python code with context managers,
and hyperscribe streams escaped, indented HTML to any file-like object.

```python
from io import StringIO

from hyperscribe import DocWriter

output = StringIO()
doc = DocWriter(output)

with doc.html(lang="en"):
    with doc.body.main:
        doc.h1("Hello & welcome")
        with doc.ul:
            for name in ("one", "two"):
                doc.li(name)

print(output.getvalue())
```

```html
<html lang="en">
  <body>
    <main>
      <h1>Hello &amp; welcome</h1>
      <ul>
        <li>one</li>
        <li>two</li>
      </ul>
    </main>
  </body>
</html>
```

## Features

- Templates are plain Python: use loops, functions, and `@contextmanager` layouts.
- Text and attribute values are escaped by default.
- Output is streamed to anything with a `write(str)` method.
- No dependencies, fully typed, and supports Python 3.10 and newer.

## Installation

```sh
pip install hyperscribe
```

## Documentation

Full documentation is available at
<https://septatrix.github.io/hyperscribe/>.

## Development

```sh
make sync     # install dependencies
make check    # lint, type-check, check formatting, and test
make format   # format the code with ruff
make docs     # build the documentation
```

Run `make help` to list all targets.
Use `uv run sphinx-autobuild docs docs/_build/html` to preview the docs while editing.

The [benchmarks](benchmarks/README.md) compare hyperscribe with other Python HTML templating libraries
using pytest-benchmark.
Their dependencies live in the optional `benchmarks` dependency group
and need Python 3.14:

```sh
uv run --group benchmarks pytest benchmarks
```

## Releasing

The version is derived from git tags by `hatch-vcs`.
To release, publish a GitHub release whose tag is `v` plus the version, such as `v0.2.0`.
The `Publish` workflow builds the package
and uploads it to PyPI through
[trusted publishing](https://docs.pypi.org/trusted-publishers/).
Copy the files in `contrib/workflows/` to `.github/workflows/` once,
using a credential that may edit workflows.

## Roadmap

These gaps showed up
when porting real Jinja and bottle templates to hyperscribe.
None of them are fixed yet.

- **Element registry.**
  hyperscribe does not know anything about individual elements.
  A registry with metadata per element
  should cover the following:
  - Void elements such as `<meta>`, `<link>`, `<br>`, `<img>` and `<input>`
    have to be written with `write_raw` for now,
    which skips indentation and does not escape attribute values.
  - Whitespace-sensitive elements such as `<pre>` and `<textarea>`
    should switch to inline mode automatically.
    Today the caller has to know to use `doc.inline()`.
  - The contents of `<style>` and `<script>` should be written verbatim.
  - The set of permitted attributes could be checked.
- **Trusted content.**
  Escaping text by default is intended.
  What is missing is a way to mark content as already safe
  other than `write_raw`,
  for example CSS, JavaScript or prepared markup.
  The idea is a safe string type,
  either MarkupSafe's `Markup` or a custom implementation,
  perhaps built on template strings (`t""`).
- **Attribute values.**
  Values must be `str`.
  They should behave like Jinja's `xmlattr` filter:
  `None` omits the attribute,
  and booleans write or omit a boolean attribute such as `defer`.
  Today optional attributes need a conditional `dict`
  and boolean attributes have to be written as `defer=""`.
- **Attribute names that are not Python identifiers.**
  `class`, `data-*`, `aria-*` and `http-equiv` need `**{"class": "card"}`.
  Mapping a trailing underscore (`class_`) and underscores to hyphens (`data_id`)
  would remove most of this.
- **Content that is not a string.**
  A number as content raises `TypeError`,
  so values have to be wrapped in `str()` first.
  `None` is treated as omitted content,
  so `doc.p(None)` silently writes nothing
  instead of raising or writing an empty element.
- **Name clash.**
  `DocWriter.tag(name, **attrs)` cannot take a `name` attribute,
  which `<meta>` and `<input>` need.
  The internal parameter should be renamed to `_name`.
- **Comments.**
  There is no way to write an HTML comment except through `write_raw`.
  A function such as `doc.comment` should be added.
- **Filtered loops.**
  What Jinja writes as `{% for x in xs if cond %}` with `loop.first` and `loop.length`
  turns into list comprehensions and `enumerate`.
  The idioms should be documented in the guide.

## Status

hyperscribe is in early development
and its API may change between minor releases.
