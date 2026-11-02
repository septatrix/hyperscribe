"""Stream documents in chunks, for example to an async web server.

Templates still write synchronously to a :class:`~hyperscribe.DocWriter`.
What they write is collected in a list,
and the document is sent on in chunks at the few places where it is worth it,
usually right before the template waits for something slow:

- :class:`AsyncDocWriter` sends the buffer when the template calls
  ``await doc.drain()``.
- :func:`aiter_chunks` turns a template written as an async generator
  into an async iterator of chunks,
  which most async web frameworks accept as a streaming response body.
  The document is split at each bare ``yield``.
- :func:`iter_chunks` does the same for synchronous servers, such as WSGI ones,
  with a template written as a generator.
"""

from __future__ import annotations

import inspect
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Iterator,
)
from typing import Any, Concatenate, ParamSpec, overload

from . import DocWriter, Ignored

__all__ = ["AsyncDocWriter", "aiter_chunks", "iter_chunks"]

_P = ParamSpec("_P")


def _take(parts: list[str]) -> str:
    """Return the text collected in ``parts`` and empty the list.

    The list only holds references to the strings written so far,
    so this is the only time the text is copied.
    It is cleared in place,
    because the writer holds on to the list's ``append`` method.
    """
    text = "".join(parts)
    parts.clear()
    return text


class AsyncDocWriter(DocWriter):
    """A writer that keeps what is written until ``await doc.drain()`` sends it.

    Like :meth:`asyncio.StreamWriter.drain`,
    :meth:`drain` waits until the data written so far has been passed on:
    ``send`` is awaited with each chunk,
    so a slow client holds the template up instead of letting the buffer grow.
    It can be a wrapper around an ASGI ``send`` callable,
    or around :meth:`asyncio.StreamWriter.write` and
    :meth:`~asyncio.StreamWriter.drain`.
    Call :meth:`drain` once more when the template is done,
    to send whatever it wrote after the last time.

    The template sends the chunks itself,
    so timeouts and cancel scopes in it cover the sending as well,
    and can be used anywhere, unlike with :func:`aiter_chunks`.
    """

    def __init__(self, send: Callable[[str], Awaitable[Ignored]]) -> None:
        self._parts: list[str] = []
        # Writing is list.append itself, without a Python-level call around it.
        super().__init__(self._parts.append)
        self._send = send

    async def drain(self) -> None:
        """Send what has been written since the last drain, if anything."""
        if chunk := _take(self._parts):
            await self._send(chunk)


def _iter_generator(
    parts: list[str], template: Iterator[None]
) -> Generator[str, None, None]:
    try:
        for _ in template:
            if chunk := _take(parts):
                yield chunk
    finally:
        close = getattr(template, "close", None)
        if close is not None:
            close()
    if chunk := _take(parts):
        yield chunk


async def _aiter_sync_generator(
    parts: list[str], template: Iterator[None]
) -> AsyncGenerator[str, None]:
    chunks = _iter_generator(parts, template)
    try:
        for chunk in chunks:
            yield chunk
    finally:
        chunks.close()


async def _aiter_generator(
    parts: list[str], template: AsyncIterator[None]
) -> AsyncGenerator[str, None]:
    try:
        async for _ in template:
            if chunk := _take(parts):
                yield chunk
    finally:
        aclose = getattr(template, "aclose", None)
        if aclose is not None:
            await aclose()
    if chunk := _take(parts):
        yield chunk


def _render(
    template: Callable[..., Any], args: Any, kwargs: Any
) -> tuple[list[str], Any]:
    parts: list[str] = []
    # Writing is list.append itself, without a Python-level call around it.
    return parts, template(DocWriter(parts.append), *args, **kwargs)


def _wrong_template(name: str, kinds: str, rendering: object) -> TypeError:
    hint = ""
    if inspect.iscoroutine(rendering):
        rendering.close()  # It will never run, so do not warn that it was not awaited.
        hint = "; render async functions with AsyncDocWriter instead"
    return TypeError(
        f"a template for {name}() must be {kinds}, "
        f"not one that returns {type(rendering).__name__}{hint}"
    )


def iter_chunks(
    template: Callable[Concatenate[DocWriter, _P], Iterator[None]],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> Generator[str, None, None]:
    """Render a generator template in chunks, as an iterator of strings.

    The template is called with a new :class:`~hyperscribe.DocWriter`,
    followed by ``args`` and ``kwargs``,
    and the document is split each time it yields,
    so a bare ``yield`` sends everything written up to that point.
    What it yields is ignored,
    and the rest of the document is sent when it returns.
    This suits synchronous servers that accept an iterator as a response body,
    such as WSGI ones,
    which want the chunks encoded as bytes.

    Closing the iterator early closes the template,
    so its ``finally`` blocks and ``with`` exits run.
    """
    parts, rendering = _render(template, args, kwargs)
    if not hasattr(rendering, "__next__"):
        raise _wrong_template("iter_chunks", "a generator", rendering)
    return _iter_generator(parts, rendering)


@overload
def aiter_chunks(
    template: Callable[Concatenate[DocWriter, _P], AsyncIterator[None]],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> AsyncGenerator[str, None]: ...


@overload
def aiter_chunks(
    template: Callable[Concatenate[DocWriter, _P], Iterator[None]],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> AsyncGenerator[str, None]: ...


def aiter_chunks(
    template: Callable[..., Any], /, *args: Any, **kwargs: Any
) -> AsyncGenerator[str, None]:
    """Render a generator template in chunks, as an async iterator of strings.

    The template is called with a new :class:`~hyperscribe.DocWriter`,
    followed by ``args`` and ``kwargs``.
    It is an async generator,
    and the document is split each time it yields,
    so a bare ``yield`` sends everything written up to that point.
    What it yields is ignored,
    and the rest of the document is sent when it returns.
    A synchronous generator is accepted as well, as for :func:`iter_chunks`,
    so the same template can be served by synchronous and async servers.

    Stopping the iterator early, as servers do when a client disconnects,
    closes the template, so its ``finally`` blocks and ``with`` exits run.

    The template is paused at each ``yield`` while its chunk is sent,
    in the same task, as with any async generator.
    So it must not yield inside a block that limits its task,
    such as ``asyncio.timeout()``, an :class:`asyncio.TaskGroup`
    or a Trio cancel scope,
    which would otherwise limit sending the chunk as well.
    Use :class:`AsyncDocWriter` for templates that need such blocks around output.
    """
    parts, rendering = _render(template, args, kwargs)
    if hasattr(rendering, "__aiter__"):
        return _aiter_generator(parts, rendering)
    if hasattr(rendering, "__next__"):
        return _aiter_sync_generator(parts, rendering)
    raise _wrong_template("aiter_chunks", "an async generator or generator", rendering)
