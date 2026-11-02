"""Stream documents in chunks, for example to an async web server.

Templates still write synchronously.
:class:`BufferedDocWriter` collects what they write,
and the document is sent on in chunks at the few places where it is worth it,
usually right before the template waits for something slow:

- :class:`AsyncDocWriter` sends the buffer when the template calls
  ``await doc.drain()``.
- :func:`stream` turns a template into an async iterator of chunks,
  which most async web frameworks accept as a streaming response body.
  A template written as an async generator is flushed at each bare ``yield``,
  and one written as a plain ``async def`` function
  is flushed whenever it waits for something.

:class:`OutOfOrder` works with all three.
It writes placeholders for slow content,
so the rest of the page can be sent first,
and fills them in as the content becomes available.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import string
import types
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Coroutine,
    Generator,
)
from types import TracebackType
from typing import TYPE_CHECKING, Any, Concatenate, ParamSpec, TypeVar, overload

from . import AttributeValue, DocWriter, TrustedContent, _TagBuilder, escape, trust

__all__ = ["AsyncDocWriter", "BufferedDocWriter", "OutOfOrder", "Placeholder", "stream"]

_P = ParamSpec("_P")
_T = TypeVar("_T")


class _Parts(list[str]):
    """A list that is its own ``write`` target.

    ``write`` is ``list.append`` itself,
    so writing costs no Python-level call on top of the append.
    """

    if TYPE_CHECKING:
        # What io.Writer asks for; list.append returns None instead,
        # which DocWriter never looks at.
        def write(self, data: str, /) -> int: ...
    else:
        write = list.append


class BufferedDocWriter(DocWriter):
    """A :class:`~hyperscribe.DocWriter` that keeps what is written until it is taken.

    The buffer only holds references to the strings written so far,
    so taking it is the only time the text is copied.
    """

    def __init__(self) -> None:
        self._parts = _Parts()
        super().__init__(self._parts)

    def take(self) -> str:
        """Return everything written since the last call and empty the buffer."""
        parts = self._parts
        text = "".join(parts)
        # Cleared in place: the writer holds on to this list's append method.
        parts.clear()
        return text


class AsyncDocWriter(BufferedDocWriter):
    """A buffered writer that sends its buffer when ``await doc.drain()`` is called.

    Like :meth:`asyncio.StreamWriter.drain`,
    :meth:`drain` waits until the data written so far has been passed on:
    ``send`` is awaited with each chunk,
    so a slow client holds the template up instead of letting the buffer grow.
    It can be a wrapper around an ASGI ``send`` callable,
    or around :meth:`asyncio.StreamWriter.write` and
    :meth:`~asyncio.StreamWriter.drain`.
    Call :meth:`drain` once more when the template is done,
    to send whatever it wrote after the last time.
    """

    def __init__(self, send: Callable[[str], Awaitable[object]]) -> None:
        super().__init__()
        self._send = send

    async def drain(self) -> None:
        """Send what has been written since the last drain, if anything."""
        if chunk := self.take():
            await self._send(chunk)


@types.coroutine
def _suspend(signal: Any) -> Generator[Any, Any, Any]:
    """Pass what a coroutine suspended with on to the event loop, and back."""
    return (yield signal)


async def _stream_generator(
    doc: BufferedDocWriter, template: AsyncIterator[None]
) -> AsyncGenerator[str, None]:
    try:
        async for _ in template:
            if chunk := doc.take():
                yield chunk
    finally:
        aclose = getattr(template, "aclose", None)
        if aclose is not None:
            await aclose()
    if chunk := doc.take():
        yield chunk


async def _stream_coroutine(
    doc: BufferedDocWriter, template: Coroutine[Any, Any, object]
) -> AsyncGenerator[str, None]:
    # The coroutine is stepped by hand, like an event loop's task would,
    # and whatever it suspends with is passed on to the real task unchanged.
    # This works with any event loop, and the template keeps running in the
    # caller's task, so context variables and cancellation behave as usual.
    # Writes are synchronous, so the template can only have written something
    # new when it suspends, which is exactly when sending it is worthwhile.
    value: Any = None
    error: BaseException | None = None
    try:
        while True:
            try:
                if error is None:
                    signal = template.send(value)
                else:
                    signal = template.throw(error)
            except StopIteration:
                break
            finally:
                # Break the cycle between the error and this frame.
                error = None
            if chunk := doc.take():
                yield chunk
            try:
                value = await _suspend(signal)
            except BaseException as caught:  # noqa: B036 - forwarded to the template
                value = None
                error = caught
    finally:
        template.close()
    if chunk := doc.take():
        yield chunk


@overload
def stream(
    template: Callable[Concatenate[BufferedDocWriter, _P], AsyncIterator[None]],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> AsyncGenerator[str, None]: ...


@overload
def stream(
    template: Callable[Concatenate[BufferedDocWriter, _P], Coroutine[Any, Any, object]],
    /,
    *args: _P.args,
    **kwargs: _P.kwargs,
) -> AsyncGenerator[str, None]: ...


def stream(
    template: Callable[..., Any], /, *args: Any, **kwargs: Any
) -> AsyncGenerator[str, None]:
    """Render a template in chunks, as an async iterator of strings.

    The template is called with a new :class:`BufferedDocWriter`,
    followed by ``args`` and ``kwargs``.
    Where the document is split into chunks depends on what the template is:

    - An async generator is flushed each time it yields,
      so a bare ``yield`` sends everything written up to that point.
      What it yields is ignored.
    - A coroutine, from a plain ``async def`` function,
      is flushed each time it is suspended,
      which is when it waits for something that is not ready yet.
      Nothing has to be added to the template for this.

    Either way, the rest of the document is sent when the template returns.
    Stopping the iterator early, as servers do when a client disconnects,
    closes the template, so its ``finally`` blocks and ``with`` exits run.
    """
    doc = BufferedDocWriter()
    rendering = template(doc, *args, **kwargs)
    if inspect.iscoroutine(rendering):
        return _stream_coroutine(doc, rendering)
    if hasattr(rendering, "__aiter__"):
        return _stream_generator(doc, rendering)
    raise TypeError(
        "a template for stream() must be an async generator or async function, "
        f"not one that returns {type(rendering).__name__}"
    )


# The script runs as the parser reaches it, right after its <template>,
# and moves the template's content into the target.
# It is written on one line, so the indentation here is stripped.
_SWAP_SCRIPT = """
    {
      let script = document.currentScript;
      let template = script.previousElementSibling;
      document.getElementById($target).$method(template.content);
      template.remove();
      script.remove();
    }
"""
_SWAP = string.Template("".join(line.strip() for line in _SWAP_SCRIPT.splitlines()))


def _script_string(value: str) -> str:
    """Return ``value`` as a JavaScript string literal that is safe in ``<script>``.

    JSON escapes quotes, backslashes and line terminators,
    and escaping ``<`` as well rules out ``</script>`` and ``<!--``.
    """
    return json.dumps(value).replace("<", "\\u003c")


class Placeholder:
    """The element a deferred part takes the place of, from :meth:`OutOfOrder.defer`.

    It is written like a tag, exactly once:
    call it with content, such as a loading message,
    or use it as a context manager and write the content in the block.
    """

    __slots__ = ("_element", "_written")

    def __init__(self, element: _TagBuilder) -> None:
        self._element = element
        self._written = False

    def _write(self) -> None:
        if self._written:
            raise RuntimeError("a placeholder can only be written once")
        self._written = True

    def __call__(self, content: TrustedContent = "", /) -> None:
        """Write the element with ``content``, or empty if it is left out."""
        self._write()
        self._element(content)

    def __enter__(self) -> None:
        self._write()
        self._element.__enter__()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self._element.__exit__(exc_type, exc_value, traceback)


class OutOfOrder:
    """Send the rest of the page while slow parts of it are still loading.

    :meth:`defer` writes a placeholder in place of the slow content
    and starts waiting for its data in the background.
    Once the rest of the page has been written,
    :meth:`resolve` renders each part as soon as its data arrives,
    in whatever order that is,
    inside a ``<template>`` followed by a small script
    that moves it into place in the browser.

    It is meant for templates rendered with :func:`stream`
    or :class:`AsyncDocWriter`;
    see :meth:`resolve` for how to send each part as it is written.
    Waiting in the background uses :mod:`asyncio` tasks,
    so unlike the rest of this module it needs asyncio.
    """

    def __init__(
        self,
        doc: DocWriter,
        *,
        prefix: str = "hyperscribe-slot",
        nonce: str | None = None,
    ) -> None:
        """Write the placeholders and parts of ``doc``.

        Placeholders without an ``id`` of their own
        get the IDs ``prefix-1``, ``prefix-2`` and so on,
        so ``prefix`` has to be unique within the page.
        ``nonce`` is added to each script,
        for pages with a content security policy that requires one.
        """
        self._doc = doc
        self._prefix = prefix
        self._nonce = None if nonce is None else escape(nonce)
        self._count = 0
        self._pending: dict[
            asyncio.Future[Any],
            tuple[Placeholder, str, Callable[[DocWriter, Any], None]],
        ] = {}

    def defer(
        self,
        awaitable: Awaitable[_T],
        render: Callable[[DocWriter, _T], None],
        /,
        *,
        tag: str = "div",
        id: str | None = None,
        keep: bool = False,
        **attrs: AttributeValue,
    ) -> Placeholder:
        """Return a placeholder to write now, to be filled in by ``render`` later.

        The placeholder is a ``tag`` element with the given attributes.
        Write it like a tag, with a loading message for example::

            slots.defer(fetch_articles(), article_list)("Loading…")

            with slots.defer(fetch_articles(), article_list, tag="section"):
                t.h2("Articles")
                t.p("Loading…")

        Once the data has arrived, :meth:`resolve` calls ``render(doc, data)``,
        and by default the placeholder is replaced as a whole by what it writes.
        With ``keep``, the element stays and only its content is replaced,
        so the element becomes the parent of what ``render`` writes.

        The element gets ``id`` as its ID if given,
        which is then up to the caller to keep unique,
        and an ID made from the prefix otherwise.
        ``awaitable`` starts running right away,
        so several deferred parts load concurrently.
        """
        if id is None:
            self._count += 1
            target = f"{self._prefix}-{self._count}"
        else:
            target = id
        placeholder = Placeholder(self._doc.tags[tag](id=escape(target), **attrs))
        script = _SWAP.substitute(
            target=_script_string(target),
            method="replaceChildren" if keep else "replaceWith",
        )
        self._pending[asyncio.ensure_future(awaitable)] = (placeholder, script, render)
        return placeholder

    async def resolve(self) -> AsyncIterator[None]:
        """Render the deferred parts in the order their data arrives.

        This yields after writing each part,
        so the caller can send it on right away:

        - In an async generator template rendered by :func:`stream`,
          write ``async for _ in slots.resolve(): yield``.
        - With :class:`AsyncDocWriter`,
          write ``async for _ in slots.resolve(): await doc.drain()``.
        - In an ``async def`` template rendered by :func:`stream`,
          ``async for _ in slots.resolve(): pass`` is enough,
          because waiting for the next part sends the previous one.

        Call it where the parts should be written, usually right before ``</body>``,
        once every placeholder has been written.
        If rendering a part fails, the parts still loading are cancelled.
        """
        doc = self._doc
        t = doc.tags
        nonce = self._nonce
        pending = self._pending
        try:
            if any(not placeholder._written for placeholder, _, _ in pending.values()):
                raise RuntimeError(
                    "every placeholder from defer() has to be written before "
                    "resolve(), by calling it or using it in a with statement"
                )
            while pending:
                done, _ = await asyncio.wait(
                    pending.keys(), return_when=asyncio.FIRST_COMPLETED
                )
                for task in done:
                    _, script, render = pending.pop(task)
                    value = task.result()
                    with t.template:
                        render(doc, value)
                    # The target ID is encoded by _script_string.
                    t.script(trust(script), nonce=nonce)
                    yield
        finally:
            for task in pending:
                task.cancel()
            pending.clear()
