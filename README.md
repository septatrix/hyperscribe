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
None of them is fixed yet.

- **Void elements.**
  hyperscribe does not know elements such as `<meta>`, `<link>`, `<br>`, `<img>` and `<input>`.
  They have to be written with `write_raw`,
  which skips indentation and does not escape attribute values.
- **Raw text elements.**
  Text is escaped,
  so the contents of `<style>` and `<script>` (`>` combinators, CSS nesting with `&`, JavaScript operators)
  have to go through `write_raw`.
  Support for these elements should write their content verbatim.
- **Whitespace-sensitive elements.**
  Indentation inside `<pre>` and `<textarea>` changes what the reader sees.
  The workaround is `doc.inline()`,
  which only works if the caller knows to use it.
- **Attribute names that are not Python identifiers.**
  `class`, `data-*`, `aria-*` and `http-equiv` need `**{"class": "card"}`.
  Mapping a trailing underscore (`class_`) and underscores to hyphens (`data_id`)
  would remove most of this.
- **Attribute values.**
  Values must be `str`.
  Optional attributes need a conditional `dict`,
  and `None` or `bool` values are not understood.
  Boolean attributes such as `defer` have to be written as `defer=""`.
- **Non-string content.**
  Passing `None` or a number as content raises `TypeError`,
  so every value has to be wrapped in `str()` first.
- **Name clashes.**
  `DocWriter.tag(name, **attrs)` cannot take a `name` attribute,
  which `<meta>` and `<input>` need,
  and tags named `tag`, `text` or `inline` are shadowed by the methods.
- **Mixed text and inline markup.**
  A cell such as `🔑 <code>x</code>` needs `with doc.inline(), doc.td(...)`.
  A shorter way to write it would help.
- **Conditionals and filtered loops.**
  Plain Python covers them,
  but what Jinja writes as `{% for x in xs if cond %}` with `loop.first` and `loop.length`
  turns into list comprehensions and `enumerate`.
  Helpers for repeated rows, or documentation of the idioms, would make this easier.
- **Comments.**
  There is no way to write an HTML comment except through `write_raw`.

## Status

hyperscribe is in early development
and its API may change between minor releases.
