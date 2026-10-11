"""Typed stand-ins for Jinja's default globals."""

from __future__ import annotations

import builtins
from collections.abc import Iterator
from typing import Any, Generic, TypeVar

T = TypeVar("T")


def range(*args: int) -> Iterator[int]: ...
def dict(*args: Any, **kwargs: Any) -> builtins.dict[str, Any]: ...


class cycler(Generic[T]):  # noqa: N801
    current: T

    def __init__(self, *items: T) -> None: ...
    def next(self) -> T: ...
    def reset(self) -> None: ...


class joiner:  # noqa: N801
    def __init__(self, sep: str = ", ") -> None: ...
    def __call__(self) -> str: ...


def lipsum(n: int = 5, html: bool = True, min: int = 20, max: int = 100) -> str: ...
def namespace(**kwargs: Any) -> Any: ...
