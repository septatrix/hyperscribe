"""Signatures of cdedb2's custom Jinja filters (cdedb/filter.py).

In cdedb2 itself one would not copy these: ``--filters-registry
cdedb.filter:JINJA_FILTERS`` uses the real functions and their annotations.
They are copied here (bodies dropped, project types replaced by ``Any``)
because the case study does not install cdedb2's dependencies.
"""

from __future__ import annotations

import datetime
import decimal
import enum
from collections import Counter
from collections.abc import (
    Callable,
    Collection,
    Container,
    ItemsView,
    Iterable,
    Mapping,
)
from typing import Any, Literal, TypeVar, overload

import jinja2
import markupsafe

T = TypeVar("T")
S = TypeVar("S")


@overload
def safe_filter(val: None) -> None: ...
@overload
def safe_filter(val: str) -> markupsafe.Markup: ...
def safe_filter(val: str | None) -> markupsafe.Markup | None:
    raise NotImplementedError


def date_filter(
    val: datetime.date | str | None,
    formatstr: str = "%Y-%m-%d",
    lang: str | None = None,
    verbosity: str = "medium",
    passthrough: bool = False,
) -> str | None:
    raise NotImplementedError


def datetime_filter(
    val: datetime.datetime | str | None,
    formatstr: str = "%Y-%m-%d %H:%M (%Z)",
    lang: str | None = None,
    passthrough: bool = False,
) -> str | None:
    raise NotImplementedError


def timedelta_filter(delta: datetime.timedelta, gettext: Callable[[str], str]) -> str:
    raise NotImplementedError


@overload
def money_filter(val: None, currency: str = "EUR", lang: str = "de") -> None: ...
@overload
def money_filter(
    val: decimal.Decimal | int, currency: str = "EUR", lang: str = "de"
) -> str: ...
def money_filter(
    val: decimal.Decimal | int | None, currency: str = "EUR", lang: str = "de"
) -> str | None:
    raise NotImplementedError


@overload
def decimal_filter(val: None, lang: str) -> None: ...
@overload
def decimal_filter(val: float, lang: str) -> str: ...
def decimal_filter(val: float | None, lang: str) -> str | None:
    raise NotImplementedError


@overload
def cdedbid_filter(val: None) -> None: ...
@overload
def cdedbid_filter(val: int) -> str: ...
def cdedbid_filter(val: int | None) -> str | None:
    raise NotImplementedError


@overload
def iban_filter(val: None) -> None: ...
@overload
def iban_filter(val: str) -> str: ...
def iban_filter(val: str | None) -> str | None:
    raise NotImplementedError


@overload
def hidden_iban_filter(val: None) -> None: ...
@overload
def hidden_iban_filter(val: str) -> str: ...
def hidden_iban_filter(val: str | None) -> str | None:
    raise NotImplementedError


@overload
def phone_filter(val: None) -> None: ...
@overload
def phone_filter(val: str) -> str: ...
def phone_filter(val: str | None) -> str | None:
    raise NotImplementedError


def hasattr_filter(entity: object, attr: Any) -> bool:
    raise NotImplementedError


def persona_name_filter(val: Any, *args: bool, **kwargs: bool) -> str:
    raise NotImplementedError


@overload
def escape_filter(val: None) -> None: ...
@overload
def escape_filter(val: str) -> markupsafe.Markup: ...
def escape_filter(val: str | None) -> markupsafe.Markup | None:
    raise NotImplementedError


@overload
def tex_escape_filter(val: None) -> None: ...
@overload
def tex_escape_filter(val: Any) -> str: ...
def tex_escape_filter(val: Any | None) -> str | None:
    raise NotImplementedError


@overload
def enum_filter(val: None, enum_: type[enum.Enum]) -> None: ...
@overload
def enum_filter(val: int, enum_: type[enum.Enum]) -> str: ...
def enum_filter(val: int | None, enum_: type[enum.Enum]) -> str | None:
    raise NotImplementedError


def stringIn_filter(val: Any, alist: Collection[Any]) -> bool:
    raise NotImplementedError


@overload
def linebreaks_filter(val: None, replacement: str) -> None: ...
@overload
def linebreaks_filter(
    val: str | markupsafe.Markup, replacement: str
) -> markupsafe.Markup: ...
def linebreaks_filter(
    val: None | str | markupsafe.Markup, replacement: str = "<br>"
) -> markupsafe.Markup | None:
    raise NotImplementedError


@overload
def md_filter(val: None) -> None: ...
@overload
def md_filter(val: str) -> markupsafe.Markup: ...
def md_filter(val: str | None) -> markupsafe.Markup | None:
    raise NotImplementedError


def dict_count_filter(value: Mapping[T, S]) -> Counter[S]:
    raise NotImplementedError


@jinja2.pass_environment
def sort_filter(
    env: jinja2.Environment,
    value: Iterable[T],
    reverse: bool = False,
    attribute: Any | None = None,
) -> list[T]:
    raise NotImplementedError


def dictsort_filter(
    value: Mapping[T, S], by: Literal["key", "value"] = "key", reverse: bool = False
) -> list[tuple[T, S]]:
    raise NotImplementedError


def xdictsort_filter(
    value: Mapping[T, S], attribute: str, reverse: bool = False
) -> list[tuple[T, S]]:
    raise NotImplementedError


def keydictsort_filter(
    value: Mapping[T, S], sortkey: Callable[[Any], Any], reverse: bool = False
) -> list[tuple[T, S]]:
    raise NotImplementedError


def keysort_filter(
    value: Iterable[T], sortkey: Callable[[Any], Any], reverse: bool = False
) -> list[T]:
    raise NotImplementedError


def map_dict_filter(
    d: dict[str, str], processing: Callable[[Any], str]
) -> ItemsView[str, str]:
    raise NotImplementedError


def set_filter(value: Iterable[T]) -> set[T]:
    raise NotImplementedError


def enum_entries_filter(
    enum: Iterable[enum.IntEnum],
    processing: Callable[[Any], str] | None = None,
    raw: bool = False,
    prefix: str = "",
    exempt: Collection[enum.Enum] = frozenset(),
    intval: bool = False,
) -> list[tuple[enum.IntEnum | int, str]]:
    raise NotImplementedError


def multiselect_selectize_filter(
    entries: Iterable[tuple[int | enum.IntEnum, str]],
) -> list[dict[str, Any]]:
    raise NotImplementedError


def dict_entries_filter(
    items: list[tuple[Any, Mapping[str, S] | Any]], *args: str
) -> list[tuple[S, ...]]:
    raise NotImplementedError


def entries_filter(
    entities: Mapping[Any, Any] | Iterable[Any],
    *args: str,
    group: str = "",
    default_group: str = "",
    include: Container[int] | None = None,
) -> list[tuple[Any, ...]] | dict[Any, list[tuple[Any, ...]]]:
    raise NotImplementedError


JINJA_FILTERS = {
    "date": date_filter,
    "datetime": datetime_filter,
    "timedelta": timedelta_filter,
    "money": money_filter,
    "decimal": decimal_filter,
    "cdedbid": cdedbid_filter,
    "iban": iban_filter,
    "hasattr": hasattr_filter,
    "hidden_iban": hidden_iban_filter,
    "phone": phone_filter,
    "persona_name": persona_name_filter,
    "escape": escape_filter,
    "e": escape_filter,
    "stringIn": stringIn_filter,
    "linebreaks": linebreaks_filter,
    "map_dict": map_dict_filter,
    "md": md_filter,
    "dictcount": dict_count_filter,
    "enum": enum_filter,
    "sort": sort_filter,
    "keysort": keysort_filter,
    "dictsort": dictsort_filter,
    "xdictsort": xdictsort_filter,
    "keydictsort": keydictsort_filter,
    "s": safe_filter,
    "set": set_filter,
    "tex_escape": tex_escape_filter,
    "te": tex_escape_filter,
    "enum_entries": enum_entries_filter,
    "multiselect_selectize": multiselect_selectize_filter,
    "dict_entries": dict_entries_filter,
    "entries": entries_filter,
}
