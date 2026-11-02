import asyncio
import contextvars
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import TypeVar

import pytest

from hyperscribe import DocWriter, escape
from hyperscribe.streaming import AsyncDocWriter, aiter_chunks, iter_chunks

T = TypeVar("T")


def run(main: Callable[[], Awaitable[T]]) -> T:
    async def wrapper() -> T:
        return await main()

    return asyncio.run(wrapper())


async def collect(chunks: AsyncIterator[str]) -> list[str]:
    return [chunk async for chunk in chunks]


async def ready(value: T) -> T:
    """Return without suspending, like an await on a cached value."""
    return value


async def later(value: T, delay: float = 0.01) -> T:
    await asyncio.sleep(delay)
    return value


def test_drain_sends_the_buffer_and_skips_empty_chunks() -> None:
    sent: list[str] = []

    async def send(chunk: str) -> None:
        sent.append(chunk)

    async def main() -> None:
        doc = AsyncDocWriter(send)
        await doc.drain()
        with doc.tags.ul:
            doc.tags.li("a")
            await doc.drain()
            doc.tags.li("b")
        await doc.drain()

    run(main)
    assert sent == ["<ul>\n  <li>a</li>\n", "  <li>b</li>\n</ul>\n"]


def test_generator_template_is_flushed_at_each_yield() -> None:
    async def page(doc: DocWriter, title: str) -> AsyncIterator[None]:
        t = doc.tags
        with t.main:
            t.h1(escape(title))
            yield
            yield  # nothing new: no empty chunk
            t.p(await later("slow"))

    chunks = run(lambda: collect(aiter_chunks(page, "Hi")))
    assert chunks == ["<main>\n  <h1>Hi</h1>\n", "  <p>slow</p>\n</main>\n"]


def test_generator_template_does_not_flush_while_waiting() -> None:
    async def page(doc: DocWriter) -> AsyncIterator[None]:
        doc.tags.p("a")
        await later(None)
        doc.tags.p("b")
        yield

    assert run(lambda: collect(aiter_chunks(page))) == ["<p>a</p>\n<p>b</p>\n"]


def test_template_runs_in_the_callers_task_and_context() -> None:
    var: contextvars.ContextVar[str] = contextvars.ContextVar("var", default="unset")

    async def page(
        doc: DocWriter, outer: asyncio.Task[object] | None
    ) -> AsyncIterator[None]:
        assert asyncio.current_task() is outer
        yield
        var.set("set by template")

    async def main() -> str:
        await collect(aiter_chunks(page, asyncio.current_task()))
        return var.get()

    assert run(main) == "set by template"


def test_template_errors_propagate_after_earlier_chunks() -> None:
    async def page(doc: DocWriter) -> AsyncIterator[None]:
        doc.tags.p("before")
        yield
        raise ValueError("broken")

    async def main() -> list[str]:
        chunks: list[str] = []
        with pytest.raises(ValueError, match="broken"):
            async for chunk in aiter_chunks(page):
                chunks.append(chunk)
        return chunks

    assert run(main) == ["<p>before</p>\n"]


@pytest.mark.parametrize("kind", ["generator", "sync generator"])
def test_closing_the_stream_closes_the_template(kind: str) -> None:
    events: list[str] = []

    async def generator(doc: DocWriter) -> AsyncIterator[None]:
        try:
            doc.tags.p("first")
            yield
            doc.tags.p("never sent")
            yield
        finally:
            events.append("closed")

    def sync_generator(doc: DocWriter) -> Iterator[None]:
        try:
            doc.tags.p("first")
            yield
            doc.tags.p("never sent")
            yield
        finally:
            events.append("closed")

    async def main() -> str:
        if kind == "generator":
            chunks = aiter_chunks(generator)
        else:
            chunks = aiter_chunks(sync_generator)
        first = await anext(chunks)
        await chunks.aclose()
        return first

    assert run(main) == "<p>first</p>\n"
    assert events == ["closed"]


def test_cancellation_reaches_the_template() -> None:
    events: list[str] = []

    async def page(doc: DocWriter) -> AsyncIterator[None]:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            events.append("cancelled")
            raise
        yield

    async def main() -> None:
        task = asyncio.ensure_future(collect(aiter_chunks(page)))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(main)
    assert events == ["cancelled"]


@pytest.mark.filterwarnings("error::RuntimeWarning")
def test_aiter_chunks_rejects_functions() -> None:
    def function(doc: DocWriter) -> None:
        doc.tags.p("sync")

    async def coroutine(doc: DocWriter) -> None:
        doc.tags.p("async")

    with pytest.raises(TypeError, match="must be an async generator or generator"):
        aiter_chunks(function)  # type: ignore[call-overload]
    with pytest.raises(TypeError, match="render async functions with AsyncDocWriter"):
        aiter_chunks(coroutine)  # type: ignore[call-overload]


def test_aiter_chunks_flushes_sync_generators_at_each_yield() -> None:
    def page(doc: DocWriter, title: str) -> Iterator[None]:
        doc.tags.h1(escape(title))
        yield
        doc.tags.p("rest")

    chunks = run(lambda: collect(aiter_chunks(page, "Hi")))
    assert chunks == ["<h1>Hi</h1>\n", "<p>rest</p>\n"]


def test_iter_chunks_flushes_at_each_yield() -> None:
    def page(doc: DocWriter, title: str) -> Iterator[None]:
        t = doc.tags
        with t.main:
            t.h1(escape(title))
            yield
            yield  # nothing new: no empty chunk
            t.p("rest")

    assert list(iter_chunks(page, title="Hi")) == [
        "<main>\n  <h1>Hi</h1>\n",
        "  <p>rest</p>\n</main>\n",
    ]


def test_closing_iter_chunks_closes_the_template() -> None:
    events: list[str] = []

    def page(doc: DocWriter) -> Iterator[None]:
        try:
            doc.tags.p("first")
            yield
            doc.tags.p("never sent")
        finally:
            events.append("closed")

    chunks = iter_chunks(page)
    assert next(chunks) == "<p>first</p>\n"
    chunks.close()
    assert events == ["closed"]


def test_iter_chunks_errors_propagate_after_earlier_chunks() -> None:
    def page(doc: DocWriter) -> Iterator[None]:
        doc.tags.p("before")
        yield
        raise ValueError("broken")

    chunks = iter_chunks(page)
    assert next(chunks) == "<p>before</p>\n"
    with pytest.raises(ValueError, match="broken"):
        next(chunks)


@pytest.mark.filterwarnings("error::RuntimeWarning")
def test_iter_chunks_rejects_async_templates_without_warnings() -> None:
    async def function(doc: DocWriter) -> None:
        pass

    async def generator(doc: DocWriter) -> AsyncIterator[None]:
        yield

    with pytest.raises(TypeError, match="must be a generator"):
        iter_chunks(function)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="must be a generator"):
        iter_chunks(generator)  # type: ignore[arg-type]


if sys.version_info >= (3, 11):  # asyncio.timeout is new in 3.11

    def test_timeouts_around_output_work_with_async_doc_writer() -> None:
        sent: list[str] = []

        async def send(chunk: str) -> None:
            await asyncio.sleep(0.05)  # a client slower than the timeout
            sent.append(chunk)

        async def main() -> None:
            doc = AsyncDocWriter(send)
            try:
                async with asyncio.timeout(0.02):
                    doc.tags.p("before")
                    await doc.drain()
                    doc.tags.p("never written")
            except TimeoutError:
                doc.tags.p("timed out")
            await doc.drain()

        run(main)
        assert sent == ["<p>timed out</p>\n"]
