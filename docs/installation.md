# Installation

hyperscribe requires Python 3.10 or newer and has no dependencies.

```sh
pip install hyperscribe
```

or, with [uv](https://docs.astral.sh/uv/):

```sh
uv add hyperscribe
```

## Development setup

```sh
git clone https://github.com/septatrix/hyperscribe
cd hyperscribe
make sync     # install dependencies
make check    # lint, type-check, check formatting, and test
make format   # format the code with ruff
make docs     # build the documentation
make doctest  # run the examples in the documentation
```

Run `make help` to list all targets.
Use `uv run sphinx-autobuild docs docs/_build/html` to preview the docs while editing.
