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
uv sync
uv run pytest
uv run sphinx-autobuild docs docs/_build/html
```
