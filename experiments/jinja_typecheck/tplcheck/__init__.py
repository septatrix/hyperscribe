"""Typing-only runtime for shadow modules generated from Jinja templates.

Nothing in here is ever executed.
The generated modules only exist so that mypy can check them,
so the bodies are stubs and the signatures are what matters.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from typing import Any, Generic, TypeVar

from jinja2 import Undefined

T = TypeVar("T")
U = TypeVar("U")


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


def getattr_(obj: object, name: str) -> Any:
    """Jinja's ``obj.name``: attribute access, falling back to item access.

    The mypy plugin (``tplcheck.mypy_plugin``) replaces this return type
    with the precise type of the member.
    Without the plugin every attribute access is ``Any``.
    """
    raise NotImplementedError


def emit(value: object) -> None:
    """Stands for ``{{ value }}``: evaluates the expression so it gets checked."""


def concat_(*parts: object) -> str:
    raise NotImplementedError


def undefined_() -> Undefined:
    raise NotImplementedError
