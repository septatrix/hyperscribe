"""Typing-only runtime for shadow modules generated from Jinja templates.

Nothing in here is ever executed.
The generated modules only exist so that mypy can check them,
so the bodies are stubs and the signatures are what matters.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator
from typing import Any, Generic, Literal, TypedDict, TypeVar

from jinja2 import Undefined as Undefined
from markupsafe import Markup

T = TypeVar("T")
U = TypeVar("U")


class UndefinedValue:
    """What an optional context key reads as when it is missing.

    Unlike ``jinja2.Undefined`` it has no ``__getattr__``, so using the value
    without an ``is defined`` check (``user.email.upper()``) is an error.
    """


class NoContext(TypedDict):
    """Context of a template that declares no variables."""


class Loop(Generic[T]):
    """Type of Jinja's ``loop`` variable inside a ``{% for %}`` block."""

    index: int
    index0: int
    revindex: int
    revindex0: int
    first: bool
    last: bool
    length: int
    depth: int
    depth0: int
    previtem: T | Undefined
    nextitem: T | Undefined

    def cycle(self, *values: U) -> U: ...
    def changed(self, *values: object) -> bool: ...
    def __iter__(self) -> Iterator[T]: ...


def loop_(iterable: Iterable[T]) -> Loop[T]:
    raise NotImplementedError


def getattr_(
    obj: object,
    name: str,
    narrowed: Literal["defined", "notnone", "truthy"] | None = None,
) -> Any:
    """Jinja's ``obj.name``: attribute access, falling back to item access.

    The mypy plugin (``tplcheck.mypy_plugin``) replaces this return type
    with the precise type of the member.
    Without the plugin every attribute access is ``Any``.

    ``narrowed`` is emitted where a surrounding test vouches for the access
    (``is defined`` / ``'k' in d``: not ``UndefinedValue``;
    ``is not none``: not ``None``; a truthiness test or ``d.get('k')``: neither).
    mypy cannot narrow call expressions itself, so the plugin does it.
    """
    raise NotImplementedError


def emit(value: object) -> None:
    """Stands for ``{{ value }}``: evaluates the expression so it gets checked."""


def concat_(*parts: object) -> str:
    raise NotImplementedError


def undefined_() -> Undefined:
    raise NotImplementedError


anything_: Any
"""Stands for a value the checker knows nothing about (lenient mode)."""


def super_() -> Markup:
    """``{{ super() }}`` inside a block: the parent's rendering of it."""
    raise NotImplementedError


class _Self:
    """``self`` in a template: ``self.some_block()`` renders a block."""

    def __getattr__(self, block: str) -> Callable[[], Markup]: ...


self_ = _Self()
