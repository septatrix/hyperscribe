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

:class:`OutOfOrder` works with the async ones.
It writes placeholders for slow content,
so the rest of the page can be sent first,
and fills them in as the content becomes available.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import string
from collections.abc import (
    AsyncGenerator,
    AsyncIterator,
    Awaitable,
    Callable,
    Generator,
    Iterator,
)
from types import TracebackType
from typing import Any, Concatenate, ParamSpec, TypeVar, overload

from . import DocWriter, Ignored, escape, trust

__all__ = ["AsyncDocWriter", "OutOfOrder", "SlotId", "aiter_chunks", "iter_chunks"]

_P = ParamSpec("_P")
_T = TypeVar("_T")


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
_UNWRITTEN = (
    "a slot ID from defer() has to be written as the id of its placeholder "
    "before its part is written"
)

_SWAP = string.Template("".join(line.strip() for line in _SWAP_SCRIPT.splitlines()))


def _script_string(value: str) -> str:
    """Return ``value`` as a JavaScript string literal that is safe in ``<script>``.

    JSON escapes quotes, backslashes and line terminators,
    and escaping ``<`` as well rules out ``</script>`` and ``<!--``.
    """
    return json.dumps(value).replace("<", "\\u003c")


class SlotId:
    """The ID of a deferred part's placeholder, from :meth:`OutOfOrder.defer`.

    Write it as the ``id`` of the element that the part should take the place of,
    as in ``t.div("Loading…", id=slot)``.
    It is written escaped, and only once,
    so that :meth:`OutOfOrder.resolve` can tell
    whether every placeholder is in the page.
    """

    __slots__ = ("_html", "_written")

    def __init__(self, target: str) -> None:
        self._html = escape(target)
        self._written = False

    def __html__(self) -> str:
        """Return the escaped ID, and note that it has been written."""
        if self._written:
            raise RuntimeError(f"the slot ID {self._html} can only be written once")
        self._written = True
        return self._html

    def __repr__(self) -> str:
        return f"SlotId({self._html!r})"


class OutOfOrder:
    """Send the rest of the page while slow parts of it are still loading.

    It is used in a ``with`` statement
    around the part of the page that contains the placeholders::

        with OutOfOrder(doc) as slots:
            t.div("Loading…", id=slots.defer(fetch_articles(), article_list))
            t.footer("Thanks for reading")
            yield
            async for _ in slots.resolve():
                yield

    :meth:`defer` starts waiting for the data of slow content in the background
    and returns the ID of a placeholder to write in its place.
    :meth:`resolve` then renders each part as soon as its data arrives,
    in whatever order that is,
    inside a ``<template>`` followed by a small script
    that moves it into place in the browser.
    It yields after each part, so the template can send it on:
    with a ``yield`` in an async generator template rendered by :func:`aiter_chunks`,
    or with ``await doc.drain()`` for an :class:`AsyncDocWriter`.

    If the block ends with an exception,
    including when the response is stopped because the client disconnected,
    the parts still loading are cancelled.
    If it ends without one while parts are still waiting to be resolved,
    they are cancelled as well and :exc:`RuntimeError` is raised.

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
        # Several slots can wait for the same future, so each has a list.
        self._pending: dict[
            asyncio.Future[Any],
            list[tuple[SlotId, str, Callable[[DocWriter, Any], None]]],
        ] = {}

    def defer(
        self,
        awaitable: Awaitable[_T],
        render: Callable[[DocWriter, _T], None],
        /,
        *,
        id: str | None = None,
        keep: bool = False,
    ) -> SlotId:
        """Return the ID of a placeholder to write now, filled in by ``render`` later.

        The placeholder is any element with this ID,
        written like any other, with a loading message for example::

            t.div("Loading…", id=slots.defer(fetch_articles(), article_list))

            with t.section(id=slots.defer(fetch_articles(), article_list)):
                t.h2("Articles")
                t.p("Loading…")

        Once the data has arrived, ``render(doc, data)`` is called,
        and by default the placeholder is replaced as a whole by what it writes.
        With ``keep``, the element stays and only its content is replaced,
        so the element becomes the parent of what ``render`` writes.

        The ID is ``id`` if given,
        which is then up to the caller to keep unique,
        and made from the prefix otherwise.
        ``awaitable`` starts running right away,
        so several deferred parts load concurrently.
        """
        if id is None:
            self._count += 1
            target = f"{self._prefix}-{self._count}"
        else:
            target = id
        slot = SlotId(target)
        script = _SWAP.substitute(
            target=_script_string(target),
            method="replaceChildren" if keep else "replaceWith",
        )
        future = asyncio.ensure_future(awaitable)
        self._pending.setdefault(future, []).append((slot, script, render))
        return slot

    def write_completed(self) -> int:
        """Write the deferred parts whose data has already arrived, without waiting.

        Call it before waiting for something slow that is not deferred,
        and send them on with a ``yield``,
        or ``await doc.drain()`` for an :class:`AsyncDocWriter`,
        so the parts that are done are sent first.
        Returns how many parts were written.
        """
        written = 0
        for future in [future for future in self._pending if future.done()]:
            written += self._write(future)
        return written

    async def resolve(self) -> AsyncIterator[None]:
        """Render the deferred parts in the order their data arrives.

        This yields after writing each part, so the caller can send it on::

            async for _ in slots.resolve():
                yield  # or: await doc.drain()

        Call it inside the ``with`` block,
        where the parts should be written, usually right before ``</body>``.
        Parts whose data arrives together are written in the order they were deferred.
        If rendering a part fails, the parts still loading are cancelled.
        """
        pending = self._pending
        try:
            if any(
                not slot._written for slots in pending.values() for slot, _, _ in slots
            ):
                raise RuntimeError(_UNWRITTEN)
            while pending:
                done, _ = await asyncio.wait(
                    pending.keys(), return_when=asyncio.FIRST_COMPLETED
                )
                # Parts that are ready together are written in the order deferred.
                for future in [future for future in pending if future in done]:
                    self._write(future)
                    yield
        finally:
            self.cancel()

    def _write(self, future: asyncio.Future[Any]) -> int:
        """Write the parts waiting for a finished future, and return how many."""
        doc = self._doc
        t = doc.tags
        value = future.result()
        parts = self._pending.pop(future)
        for slot, script, render in parts:
            if not slot._written:
                raise RuntimeError(_UNWRITTEN)
            with t.template:
                render(doc, value)
            # The target ID is encoded by _script_string.
            t.script(trust(script), nonce=self._nonce)
        return len(parts)

    def cancel(self) -> None:
        """Stop waiting for the deferred parts that have not been written yet.

        Their awaitables are cancelled,
        including tasks and futures that were passed to :meth:`defer` as they are.
        """
        for future in self._pending:
            future.cancel()
        self._pending.clear()

    def __enter__(self) -> OutOfOrder:
        """Return the slots to defer parts with."""
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        """Cancel the parts that have not been written.

        If the block ends without an exception while parts are left,
        :meth:`resolve` was not called for them,
        and :exc:`RuntimeError` is raised.
        """
        unresolved = bool(self._pending)
        self.cancel()
        if unresolved and exc_type is None:
            raise RuntimeError(
                "the parts deferred with OutOfOrder were not written; "
                "call resolve() before the end of the with block"
            )
