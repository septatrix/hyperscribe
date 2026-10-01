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
- Text written with `doc.text(...)` and attribute values are escaped.
- `doc(...)` writes trusted `LiteralString`, `__html__` objects, and numeric values
  verbatim while preserving indentation.
- Output is streamed to anything with a `write(str)` method.
- Fully typed, and supports Python 3.10 and newer.

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
Attribute handling, content conversion, comments,
`doc.void_tag` for void elements, and the guide's loop idioms
have been dealt with since.
Two larger items remain.

- **Element registry.**
  hyperscribe does not know anything about individual elements.
  A registry with metadata per element
  should cover the following:
  - Void elements such as `<br>` and `<img>` should be written
    without calling `doc.void_tag` explicitly.
  - Whitespace-sensitive elements such as `<pre>` and `<textarea>`
    should switch to inline mode automatically.
    Today the caller has to know to use `doc.inline()`.
  - The contents of `<style>` and `<script>` should be written verbatim.
  - The set of permitted attributes could be checked.
- **Trusted content.**
  `DocWriter.__call__` has preliminary support for trusted content:
  `LiteralString`, objects implementing `__html__` (such as MarkupSafe's `Markup`),
  and numeric values are written verbatim with indentation.
  Broader safe string support for CSS, JavaScript, or prepared markup,
  perhaps built on template strings, remains future work.

## Status

hyperscribe is in early development
and its API may change between minor releases.
