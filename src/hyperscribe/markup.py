"""Helpers that turn values into text that is safe to write as HTML.

They are also available from :mod:`hyperscribe` itself.
"""

from __future__ import annotations

import html
from collections.abc import Mapping
from typing import Literal, NewType

__all__ = ["SafeStr", "classes", "escape", "escape_silent", "trust"]

SafeStr = NewType("SafeStr", str)
"""A string that is safe to write as HTML, returned by :func:`escape` and :func:`trust`.

It only exists for type checkers; at runtime it is a plain :class:`str`.
Attribute values are escaped as usual, whatever their type.
"""


def escape(value: str) -> SafeStr:
    """Escape ``&``, ``<``, ``>`` and quotes so the text can be written as HTML.

    Quotes are escaped as well,
    so the result is safe in text and in attribute values.
    """
    # Looking for characters to escape is much cheaper than escaping,
    # and most strings have none.
    if (
        "&" not in value
        and "<" not in value
        and ">" not in value
        and '"' not in value
        and "'" not in value
    ):
        return SafeStr(value)
    return SafeStr(html.escape(value))


def escape_silent(value: str | None) -> SafeStr:
    """Like :func:`escape`, but write ``None`` as an empty string.

    Use it for optional values, such as a field that may be missing in some data,
    where an empty result is what the page should show.
    """
    return SafeStr("") if value is None else escape(value)


def trust(value: str) -> SafeStr:
    """Mark a string as safe to write as HTML, without escaping it.

    Only use it for content that cannot contain untrusted input.
    """
    return SafeStr(value)


def classes(
    *names: str | Mapping[str, object] | Literal[False] | None,
) -> SafeStr | None:
    """Join class names into a value for the ``class`` attribute.

    Each argument is a class name, or several separated by spaces,
    or a mapping from class names to whether to include them,
    so conditional classes can be written next to fixed ones::

        t.button("Save", class_=classes("btn", {"active": is_active}, extra))

    ``None`` and ``False`` are skipped,
    so ``is_active and "active"`` works as an argument too.
    The names are escaped.
    If no names are left, ``None`` is returned,
    which leaves the attribute out altogether.
    """
    parts: list[str] = []
    for name in names:
        if isinstance(name, str):
            if name:
                parts.append(name)
        elif isinstance(name, Mapping):
            parts.extend(key for key, include in name.items() if include)
        elif name is not None and name is not False:
            raise TypeError(
                "classes() takes class names, mappings of class names to booleans, "
                f"None and False, not {type(name).__name__}"
            )
    return escape(" ".join(parts)) if parts else None
