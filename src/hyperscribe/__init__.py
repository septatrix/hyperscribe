"""A minimal tag/text writer with Airium-style dynamic tag access."""

from __future__ import annotations

import html
from contextlib import AbstractContextManager
from dataclasses import dataclass, field
from types import TracebackType
from typing import TextIO, overload


def _escape_text(value: str) -> str:
    """Skip the replacement work for the common case with no HTML metacharacters."""
    if "&" not in value and "<" not in value and ">" not in value:
        return value
    return html.escape(value, quote=False)


@dataclass(slots=True)
class _TagContext:
    """Write a tag while the document tracks its nesting for indentation."""

    doc: DocWriter
    openings: tuple[str, ...]
    closings: tuple[str, ...]

    def __enter__(self) -> None:
        for opening in self.openings:
            self.doc._open_tag(opening)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        for closing in reversed(self.closings):
            self.doc._close_tag(closing)


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
    """Represent a tag, usable directly or with attributes supplied by a call."""

    _doc: DocWriter
    _path: tuple[str, ...]
    _context: _TagContext = field(init=False)

    def __post_init__(self) -> None:
        self._context = self._doc._context_for(self._path)

    def __getattr__(self, name: str) -> _TagBuilder:
        """Return a builder for a nested tag, such as ``body`` in ``doc.body.main``."""
        if name.startswith("_"):
            raise AttributeError(name)
        return _TagBuilder(self._doc, (*self._path, name))

    @overload
    def __call__(self, /, **attrs: str) -> AbstractContextManager[None]: ...

    @overload
    def __call__(self, content: str, /, **attrs: str) -> None: ...

    def __call__(
        self, content: str | None = None, /, **attrs: str
    ) -> AbstractContextManager[None] | None:
        """Write a leaf element when given content, else return a context manager."""
        if content is not None:
            context = (
                self._doc._context_for(self._path, **attrs) if attrs else self._context
            )
            self._doc._render_leaf(context, content)
            return None
        return self._doc._context_for(self._path, **attrs)

    def __enter__(self) -> None:
        return self._context.__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._context.__exit__(exc_type, exc_value, traceback)


class DocWriter:
    """Write escaped HTML fragments to any object with a ``write(str)`` method."""

    def __init__(self, writer: TextIO) -> None:
        self._write = writer.write
        self._tags: dict[str, _TagContext] = {}
        self._tag_builders: dict[str, _TagBuilder] = {}
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

        tag_builders = self._tag_builders
        if name not in tag_builders:
            tag_builders[name] = _TagBuilder(self, (name,))
        return tag_builders[name]

    def __call__(self, value: str) -> None:
        """Write escaped text to the document."""
        self.text(value)

    def inline(self) -> AbstractContextManager[None]:
        """Suppress line breaks and indentation for the markup written in the block.

        The block is indented and ends its line like any other tag,
        so ``with doc.inline(), doc.div:`` renders the whole ``div`` on one line.
        Blocks may be nested; formatting resumes once the outermost one exits.
        """
        return _InlineContext(self)

    def tag(self, name: str, **attrs: str) -> _TagContext:
        """Return a context manager for a tag with any name and attributes.

        Use it for names or attributes that are not valid Python identifiers,
        such as ``doc.tag("div", **{"class": "card"})``.
        """
        if attrs:
            attributes = "".join(
                f' {key}="{html.escape(value, quote=True)}"'
                for key, value in attrs.items()
            )
            return _TagContext(self, (f"<{name}{attributes}>",), (f"</{name}>",))

        if context := self._tags.get(name):
            return context

        context = _TagContext(self, (f"<{name}>",), (f"</{name}>",))
        self._tags[name] = context
        return context

    def _context_for(self, path: tuple[str, ...], **attrs: str) -> _TagContext:
        """Make a context manager for a tag chain, adding attributes to its leaf."""
        if len(path) == 1:
            return self.tag(path[0], **attrs)

        contexts = [self.tag(name) for name in path[:-1]]
        contexts.append(self.tag(path[-1], **attrs))
        return _TagContext(
            self,
            tuple(context.openings[0] for context in contexts),
            tuple(context.closings[0] for context in contexts),
        )

    def _generate_prefix(self, depth: int) -> str:
        """Return the prefix for a depth, extending the per-depth caches as needed."""
        for missing in range(len(self._line_prefixes), depth + 1):
            self._line_prefixes.append(self._indentation * missing)
            self._inline_prefixes.append("")
        return self._line_prefixes[depth]

    def _prefix(self, depth: int) -> str:
        """Return what to write before a tag at this depth, honoring inline blocks."""
        try:
            return self._prefixes[depth]
        except IndexError:
            self._generate_prefix(depth)
            return self._prefixes[depth]

    def _render_leaf(self, context: _TagContext, text: str) -> None:
        """Write shorthand leaf markup inline, without context manager allocation."""
        prefix = self._prefix(self._depth)
        openings = "".join(context.openings)
        closings = "".join(reversed(context.closings))
        self._write(f"{prefix}{openings}{_escape_text(text)}{closings}{self._end}")

    def _open_tag(self, opening: str) -> None:
        self._write(f"{self._prefix(self._depth)}{opening}{self._end}")
        self._depth += 1

    def _close_tag(self, closing: str) -> None:
        self._depth -= 1
        self._write(f"{self._prefix(self._depth)}{closing}{self._end}")

    def write_raw(self, value: str) -> None:
        """Write unescaped text to the document, bypassing the escaping logic."""
        self._write(value)

    def text(self, value: str) -> None:
        """Write escaped text to the document on its own line."""
        self._write(f"{self._prefix(self._depth)}{_escape_text(value)}{self._end}")
