import asyncio
import contextvars
import sys
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import TypeVar

import pytest

from hyperscribe import DocWriter, escape, trust
from hyperscribe.streaming import AsyncDocWriter, OutOfOrder, aiter_chunks, iter_chunks

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


def articles(doc: DocWriter, titles: list[str]) -> None:
    with doc.tags.ul:
        for title in titles:
            doc.tags.li(escape(title))


def swap(target: str, method: str = "replaceWith") -> str:
    return (
        "{let script = document.currentScript;"
        "let template = script.previousElementSibling;"
        f"document.getElementById({target}).{method}(template.content);"
        "template.remove();script.remove();}"
    )


def test_out_of_order_parts_are_written_as_they_arrive() -> None:
    async def page(doc: DocWriter) -> AsyncIterator[None]:
        t = doc.tags
        slots = OutOfOrder(doc, nonce="n<1")
        with t.body:
            t.div("Loading…", id=slots.defer(later(["slow"], 0.05), articles))
            t.section("", id=slots.defer(later(["fast"], 0.01), articles))
            t.footer("end")
            yield
            async for _ in slots.resolve():
                yield

    chunks = run(lambda: collect(aiter_chunks(page)))
    assert chunks == [
        "<body>\n"
        '  <div id="hyperscribe-slot-1">Loading…</div>\n'
        '  <section id="hyperscribe-slot-2"></section>\n'
        "  <footer>end</footer>\n",
        "  <template>\n"
        "    <ul>\n"
        "      <li>fast</li>\n"
        "    </ul>\n"
        "  </template>\n"
        '  <script nonce="n&lt;1">' + swap('"hyperscribe-slot-2"') + "</script>\n",
        "  <template>\n"
        "    <ul>\n"
        "      <li>slow</li>\n"
        "    </ul>\n"
        "  </template>\n"
        '  <script nonce="n&lt;1">' + swap('"hyperscribe-slot-1"') + "</script>\n",
        "</body>\n",
    ]


def test_out_of_order_with_explicit_drains() -> None:
    sent: list[str] = []

    async def send(chunk: str) -> None:
        sent.append(chunk)

    async def main() -> None:
        doc = AsyncDocWriter(send)
        slots = OutOfOrder(doc)
        doc.tags.div("", id=slots.defer(later(["a"]), articles))
        await doc.drain()
        async for _ in slots.resolve():
            await doc.drain()

    run(main)
    assert sent[0] == '<div id="hyperscribe-slot-1"></div>\n'
    assert len(sent) == 2
    assert sent[1].endswith("</script>\n")


def test_out_of_order_cancels_the_rest_when_a_part_fails() -> None:
    cancelled: list[bool] = []

    async def fail() -> list[str]:
        await asyncio.sleep(0)
        raise LookupError("gone")

    async def slow() -> list[str]:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise
        return []

    async def main() -> None:
        parts: list[str] = []
        doc = DocWriter(parts.append)
        slots = OutOfOrder(doc)
        doc.tags.div("", id=slots.defer(slow(), articles))
        doc.tags.div("", id=slots.defer(fail(), articles))
        with pytest.raises(LookupError):
            async for _ in slots.resolve():
                pass
        await asyncio.sleep(0)

    run(main)
    assert cancelled == [True]


def test_out_of_order_can_keep_the_placeholder_element() -> None:
    def items(doc: DocWriter, titles: list[str]) -> None:
        for title in titles:
            doc.tags.li(escape(title))

    async def main() -> str:
        parts: list[str] = []
        doc = DocWriter(parts.append)
        slots = OutOfOrder(doc)
        slot = slots.defer(ready(["a"]), items, keep=True, id="articles")
        with doc.tags.ul(id=slot, class_="list"):
            doc.tags.li(trust("…"))
        async for _ in slots.resolve():
            pass
        return "".join(parts)

    assert run(main) == (
        '<ul id="articles" class="list">\n'
        "  <li>…</li>\n"
        "</ul>\n"
        "<template>\n"
        "  <li>a</li>\n"
        "</template>\n"
        + "<script>"
        + swap('"articles"', "replaceChildren")
        + "</script>\n"
    )


@pytest.mark.parametrize(
    ("given", "attribute", "literal"),
    [
        ("plain", "plain", '"plain"'),
        ('a"b', "a&quot;b", '"a\\"b"'),
        ("a</script><!--", "a&lt;/script&gt;&lt;!--", '"a\\u003c/script>\\u003c!--"'),
        ("zürich\u2028", "zürich\u2028", '"z\\u00fcrich\\u2028"'),
    ],
)
def test_out_of_order_ids_are_encoded_for_attributes_and_scripts(
    given: str, attribute: str, literal: str
) -> None:
    async def main() -> str:
        parts: list[str] = []
        doc = DocWriter(parts.append)
        slots = OutOfOrder(doc)
        doc.tags.div("", id=slots.defer(ready([]), articles, id=given))
        async for _ in slots.resolve():
            pass
        return "".join(parts)

    output = run(main)
    assert output.startswith(f'<div id="{attribute}"></div>\n')
    assert f"getElementById({literal})" in output
    assert output.count("</script>") == 1


def test_slot_ids_must_be_written_exactly_once() -> None:
    async def main() -> None:
        parts: list[str] = []
        doc = DocWriter(parts.append)
        slots = OutOfOrder(doc)
        slot = slots.defer(ready([]), articles)
        assert repr(slot) == "SlotId('hyperscribe-slot-1')"
        doc.tags.div("", id=slot)
        with pytest.raises(RuntimeError, match="only be written once"):
            doc.tags.div("", id=slot)
        slots.defer(ready([]), articles)
        with pytest.raises(RuntimeError, match="has to be written as the id"):
            async for _ in slots.resolve():
                pass

    run(main)


def test_placeholder_can_be_any_element_with_any_content() -> None:
    async def main() -> str:
        parts: list[str] = []
        doc = DocWriter(parts.append)
        t = doc.tags
        slots = OutOfOrder(doc, prefix="p")
        with t.main, t.section(class_="box", id=slots.defer(ready(["a"]), articles)):
            t.h2("Articles")
            t.p("Loading…")
        return "".join(parts)

    assert run(main) == (
        "<main>\n"
        '  <section class="box" id="p-1">\n'
        "    <h2>Articles</h2>\n"
        "    <p>Loading…</p>\n"
        "  </section>\n"
        "</main>\n"
    )


def test_slots_can_share_a_future() -> None:
    def labelled(label: str) -> Callable[[DocWriter, list[str]], None]:
        return lambda doc, titles: doc.tags.p(escape(f"{label}: {', '.join(titles)}"))

    async def main() -> str:
        parts: list[str] = []
        doc = DocWriter(parts.append)
        with OutOfOrder(doc, prefix="s") as slots:
            shared = asyncio.ensure_future(later(["a"]))
            doc.tags.div("", id=slots.defer(shared, labelled("first")))
            doc.tags.div("", id=slots.defer(shared, labelled("second")))
            async for _ in slots.resolve():
                pass
        return "".join(parts)

    output = run(main)
    assert output.index("<p>first: a</p>") < output.index("<p>second: a</p>")
    assert 'getElementById("s-1")' in output
    assert 'getElementById("s-2")' in output


def test_closing_the_stream_before_resolve_cancels_deferred_parts() -> None:
    tasks: list[asyncio.Future[list[str]]] = []

    def defer_slow(doc: DocWriter, slots: OutOfOrder) -> None:
        task: asyncio.Future[list[str]] = asyncio.ensure_future(later([], 10))
        tasks.append(task)
        doc.tags.div("", id=slots.defer(task, articles))

    async def page(doc: DocWriter) -> AsyncIterator[None]:
        with OutOfOrder(doc) as slots:
            defer_slow(doc, slots)
            yield
            async for _ in slots.resolve():
                yield

    async def main() -> bool:
        chunks = aiter_chunks(page)
        await anext(chunks)
        await chunks.aclose()
        await asyncio.sleep(0)
        return tasks[0].cancelled()

    assert run(main)


def test_cancel_stops_the_deferred_parts() -> None:
    async def main() -> bool:
        parts: list[str] = []
        slots = OutOfOrder(DocWriter(parts.append))
        future: asyncio.Future[list[str]] = asyncio.ensure_future(later([]))
        slots.defer(future, articles)
        slots.cancel()
        await asyncio.sleep(0)
        return future.cancelled()

    assert run(main)


def visible(chunk: str) -> list[str]:
    """Return the lines of a chunk, without the swap scripts."""
    return [
        line.strip()
        for line in chunk.splitlines()
        if not line.strip().startswith(("<script", "<template", "</template"))
    ]


def p(doc: DocWriter, text: str) -> None:
    doc.tags.p(escape(text))


def test_resolve_with_an_async_doc_writer_drains_after_each_part() -> None:
    sent: list[list[str]] = []

    async def send(chunk: str) -> None:
        sent.append(visible(chunk))

    async def main() -> None:
        doc = AsyncDocWriter(send)
        with OutOfOrder(doc) as slots:
            doc.tags.div("…", id=slots.defer(later("slow", 0.05), p))
            doc.tags.div("…", id=slots.defer(later("fast", 0.01), p))
            await doc.drain()
            async for _ in slots.resolve():
                await doc.drain()

    run(main)
    assert sent == [
        [
            '<div id="hyperscribe-slot-1">…</div>',
            '<div id="hyperscribe-slot-2">…</div>',
        ],
        ["<p>fast</p>"],
        ["<p>slow</p>"],
    ]


def test_with_cancels_the_parts_when_the_block_raises() -> None:
    tasks: list[asyncio.Future[str]] = []

    async def main() -> None:
        parts: list[str] = []
        doc = DocWriter(parts.append)
        with pytest.raises(LookupError), OutOfOrder(doc) as slots:
            task: asyncio.Future[str] = asyncio.ensure_future(later("x", 10))
            tasks.append(task)
            doc.tags.div("", id=slots.defer(task, p))
            raise LookupError
        await asyncio.sleep(0)
        assert "<template>" not in "".join(parts)

    run(main)
    assert tasks[0].cancelled()


def test_with_raises_and_cancels_when_parts_were_not_resolved() -> None:
    tasks: list[asyncio.Future[str]] = []

    async def main() -> None:
        parts: list[str] = []
        doc = DocWriter(parts.append)
        with (
            pytest.raises(RuntimeError, match="call resolve"),
            OutOfOrder(doc) as slots,
        ):
            task: asyncio.Future[str] = asyncio.ensure_future(later("x", 10))
            tasks.append(task)
            doc.tags.div("", id=slots.defer(task, p))
        await asyncio.sleep(0)

    run(main)
    assert tasks[0].cancelled()


def test_with_after_resolve_has_nothing_left() -> None:
    async def page(doc: DocWriter) -> AsyncIterator[None]:
        with OutOfOrder(doc) as slots:
            doc.tags.div("…", id=slots.defer(later("a"), p))
            yield
            async for _ in slots.resolve():
                yield
        doc.tags.footer("end")

    chunks = [visible(chunk) for chunk in run(lambda: collect(aiter_chunks(page)))]
    assert chunks == [
        ['<div id="hyperscribe-slot-1">…</div>'],
        ["<p>a</p>"],
        ["<footer>end</footer>"],
    ]


def test_write_completed_writes_only_the_parts_that_have_arrived() -> None:
    async def page(doc: DocWriter) -> AsyncIterator[None]:
        with OutOfOrder(doc) as slots:
            doc.tags.div("…", id=slots.defer(later("slow", 0.1), p))
            doc.tags.div("…", id=slots.defer(later("fast", 0.01), p))
            assert slots.write_completed() == 0
            yield
            await asyncio.sleep(0.03)
            if slots.write_completed():
                yield
            assert slots.write_completed() == 0
            # Something slow that is not deferred, after "fast" has been sent.
            await later(None, 0.03)
            doc.tags.footer("end")
            yield
            async for _ in slots.resolve():
                yield

    chunks = [visible(chunk) for chunk in run(lambda: collect(aiter_chunks(page)))]
    assert chunks == [
        [
            '<div id="hyperscribe-slot-1">…</div>',
            '<div id="hyperscribe-slot-2">…</div>',
        ],
        ["<p>fast</p>"],
        ["<footer>end</footer>"],
        ["<p>slow</p>"],
    ]


def test_write_completed_checks_that_the_placeholder_was_written() -> None:
    async def main() -> None:
        parts: list[str] = []
        slots = OutOfOrder(DocWriter(parts.append))
        slots.defer(ready("a"), p)
        await asyncio.sleep(0)
        with pytest.raises(RuntimeError, match="has to be written"):
            slots.write_completed()
        slots.cancel()

    run(main)


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
