"""A minimal tag/text writer with Airium-style dynamic tag access."""

from __future__ import annotations

import html
import sys
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from types import TracebackType
from typing import Protocol, TextIO, TypeAlias, overload, runtime_checkable

if sys.version_info >= (3, 13):
    from warnings import deprecated
else:
    from typing_extensions import deprecated

if sys.version_info >= (3, 11):
    from typing import LiteralString
else:
    from typing_extensions import LiteralString


@runtime_checkable
class SupportsHTML(Protocol):
    """An object whose ``__html__`` method returns trusted HTML."""

    def __html__(self) -> str: ...


TrustedContent: TypeAlias = LiteralString | SupportsHTML | int | float
"""Content accepted by :class:`DocWriter` without explicitly calling ``text``."""

AttributeValue = object
"""What an attribute may be set to.

``None`` and ``False`` omit the attribute,
``True`` writes it without a value (``<script defer>``),
a dictionary is flattened into one attribute per entry
with the name as a prefix (``data={"id": 7}`` gives ``data-id="7"``),
and anything else is converted with :class:`str` and escaped.
Inside ``aria``, booleans are written as ``"true"`` and ``"false"`` instead,
because ARIA attributes take strings rather than being HTML boolean attributes.
"""

_MISSING: object = object()


def _escape_text(value: str) -> str:
    """Skip the replacement work for the common case with no HTML metacharacters."""
    if "&" not in value and "<" not in value and ">" not in value:
        return value
    return html.escape(value, quote=False)


def _to_text(value: object) -> str:
    """Convert content to a string, refusing ``None``, which is almost always a bug."""
    if type(value) is str:
        return value
    if value is None:
        raise TypeError("content must not be None; pass a string or omit it")
    return str(value)


def _format_attributes(attrs: dict[str, AttributeValue], prefix: str = "") -> str:
    """Write attributes in the order given, escaped for use in double quotes.

    A trailing underscore is dropped from names, so ``class_`` is written ``class``.
    """
    aria = prefix == "aria"
    parts: list[str] = []
    for key, value in attrs.items():
        if value is None:
            continue
        name = key[:-1] if key.endswith("_") else key
        if prefix:
            name = f"{prefix}-{name}"
        if value is True:
            parts.append(f' {name}="true"' if aria else f" {name}")
        elif value is False:
            if aria:
                parts.append(f' {name}="false"')
        elif type(value) is str:
            parts.append(f' {name}="{html.escape(value, quote=True)}"')
        elif isinstance(value, dict):
            parts.append(_format_attributes(value, name))
        else:
            parts.append(f' {name}="{html.escape(str(value), quote=True)}"')
    return "".join(parts)


@dataclass(slots=True)
class _InlineContext:
    """Write everything in the block on one line, indented once and ended once."""

    doc: DocWriter
    previous_prefixes: list[str] = field(init=False)
    previous_end: str = field(init=False)

    def __enter__(self) -> None:
        doc = self.doc
        doc._write(doc._prefix(doc._depth))
        self.previous_prefixes = doc._prefixes
        self.previous_end = doc._end
        doc._prefixes = doc._inline_prefixes
        doc._end = ""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        doc = self.doc
        doc._prefixes = self.previous_prefixes
        doc._end = self.previous_end
        doc._write(doc._end)


@dataclass(slots=True)
class _TagBuilder:
    """Represent a chain of tags, usable directly or with attributes supplied by a call.

    Builders are immutable, so they can be cached and nested inside themselves.
    """

    _doc: DocWriter
    _openings: tuple[str, ...]
    _closings: tuple[str, ...]
    _children: dict[str, _TagBuilder] | None = field(default=None, repr=False)

    def __getattr__(self, name: str) -> _TagBuilder:
        """Return a builder for a nested tag, such as ``main`` in ``doc.body.main``."""
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    def __getitem__(self, name: str) -> _TagBuilder:
        """Return a builder for a nested tag, as in ``doc.div["x-y"]``."""
        children = self._children
        if children is None:
            children = self._children = {}
        elif child := children.get(name):
            return child
        child = children[name] = _TagBuilder(
            self._doc,
            (*self._openings, f"<{name}>"),
            (*self._closings, f"</{name}>"),
        )
        return child

    @overload
    def __call__(self, /, **attrs: AttributeValue) -> _TagBuilder: ...

    @overload
    def __call__(self, content: object, /, **attrs: AttributeValue) -> None: ...

    def __call__(
        self, content: object = _MISSING, /, **attrs: AttributeValue
    ) -> _TagBuilder | None:
        """Write a leaf element when given content, else return a builder.

        Attributes are added to the innermost tag,
        after any it was given by an earlier call.
        Content that is not a string is converted with :class:`str`.
        ``None`` is rejected with a :class:`TypeError`
        instead of being mistaken for missing content.
        """
        openings = self._openings
        if attrs:
            openings = (
                *openings[:-1],
                f"{openings[-1][:-1]}{_format_attributes(attrs)}>",
            )
        if content is _MISSING:
            return _TagBuilder(self._doc, openings, self._closings) if attrs else self
        self._doc._render_leaf(
            openings,
            self._closings,
            content if type(content) is str else _to_text(content),
        )
        return None

    def __enter__(self) -> None:
        open_tag = self._doc._open_tag
        for opening in self._openings:
            open_tag(opening)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        close_tag = self._doc._close_tag
        for closing in reversed(self._closings):
            close_tag(closing)


class DocWriter:
    """Write escaped HTML fragments to any object with a ``write(str)`` method."""

    def __init__(self, writer: TextIO) -> None:
        self._write = writer.write
        # An empty chain that is never written itself; its children are the
        # top-level tags, so it doubles as their cache.
        self._root = _TagBuilder(self, (), ())
        self._indentation = "  "
        self._depth: int = 0
        # Indentation by depth and the line ending written after each tag, like
        # print(); inline blocks swap in empty strings for both.
        self._end = "\n"
        self._line_prefixes: list[str] = []
        self._inline_prefixes: list[str] = []
        self._prefixes = self._line_prefixes

    def __getattr__(self, name: str) -> _TagBuilder:
        """Return a cached tag object usable directly or with attributes."""
        if name.startswith("_"):
            raise AttributeError(name)
        return self[name]

    def __getitem__(self, name: str) -> _TagBuilder:
        """Return a cached tag object for any name, such as ``doc["my-element"]``.

        Use it for names that are not valid Python identifiers.
        """
        return self._root[name]

    def __call__(self, value: TrustedContent) -> None:
        """Write trusted content verbatim, preserving the current indentation.

        Strings with non-literal provenance must be passed to :meth:`text`.
        Objects implementing ``__html__`` contribute their trusted HTML string;
        literal strings and primitive numeric values are also written verbatim.
        """
        if isinstance(value, str):
            content = value
        elif isinstance(value, SupportsHTML):
            content = value.__html__()
        else:
            content = str(value)
        self._write(f"{self._prefix(self._depth)}{content}{self._end}")

    def inline(self) -> AbstractContextManager[None]:
        """Suppress line breaks and indentation for the markup written in the block.

        The block is indented and ends its line like any other tag,
        so ``with doc.inline(), doc.div:`` renders the whole ``div`` on one line.
        Blocks may be nested; formatting resumes once the outermost one exits.
        """
        return _InlineContext(self)

    @deprecated("Use doc[name](...) instead")
    def tag(self, name: str, /, **attrs: AttributeValue) -> _TagBuilder:
        """Return a tag with any name and attributes.

        Equivalent to ``doc[name](**attrs)``, which should be used instead.
        """
        return self[name](**attrs)

    def void_tag(self, name: str, /, **attrs: AttributeValue) -> None:
        """Write a void element such as ``<br>`` or ``<img>`` on its own line.

        Void elements have no content and no closing tag,
        so there is nothing to enter as a context manager.
        Attributes work as in :meth:`tag`.
        """
        self._write(
            f"{self._prefix(self._depth)}<{name}{_format_attributes(attrs)}>{self._end}"
        )

    def comment(self, text: str) -> None:
        """Write an HTML comment on its own line.

        The text is written as given,
        so it must not be able to end the comment early.
        A :class:`ValueError` is raised if it contains ``--``.
        """
        if "--" in text:
            raise ValueError(f"text cannot be written in a comment: {text!r}")
        self._write(f"{self._prefix(self._depth)}<!-- {text} -->{self._end}")

    def _generate_prefix(self, depth: int) -> str:
        """Return the prefix for a depth, extending the per-depth caches as needed."""
        self._line_prefixes.append(self._indentation * depth)
        self._inline_prefixes.append("")
        return self._line_prefixes[depth]

    def _prefix(self, depth: int) -> str:
        """Return what to write before a tag at this depth, honoring inline blocks."""
        try:
            return self._prefixes[depth]
        except IndexError:
            self._generate_prefix(depth)
            return self._prefixes[depth]

    def _render_leaf(
        self, openings: tuple[str, ...], closings: tuple[str, ...], text: str
    ) -> None:
        """Write shorthand leaf markup on one line, escaping the text."""
        prefix = self._prefix(self._depth)
        opening = "".join(openings)
        closing = "".join(reversed(closings))
        self._write(f"{prefix}{opening}{_escape_text(text)}{closing}{self._end}")

    def _open_tag(self, opening: str) -> None:
        self._write(f"{self._prefix(self._depth)}{opening}{self._end}")
        self._depth += 1

    def _close_tag(self, closing: str) -> None:
        self._depth -= 1
        self._write(f"{self._prefix(self._depth)}{closing}{self._end}")

    @deprecated("Use doc(...) instead")
    def write_raw(self, value: str) -> None:
        """Write unescaped text to the document, bypassing the escaping logic."""
        self._write(value)

    @deprecated("Use doc(...) instead")
    def text(self, value: object) -> None:
        """Write escaped text to the document on its own line.

        Values that are not strings are converted with :class:`str`,
        but ``None`` raises a :class:`TypeError`.
        """
        self._write(
            f"{self._prefix(self._depth)}"
            f"{_escape_text(value if type(value) is str else _to_text(value))}"
            f"{self._end}"
        )
