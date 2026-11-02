import asyncio
import contextvars
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import TypeVar

import pytest

from hyperscribe import DocWriter, escape, trust
from hyperscribe.streaming import AsyncDocWriter, BufferedDocWriter, OutOfOrder, stream

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


def test_take_returns_what_was_written_since_the_last_take() -> None:
    doc = BufferedDocWriter()
    doc.tags.p("one")
    assert doc.take() == "<p>one</p>\n"
    assert doc.take() == ""
    with doc.tags.div:
        doc.tags.p("two")
        assert doc.take() == "<div>\n  <p>two</p>\n"
    assert doc.take() == "</div>\n"


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
    async def page(doc: BufferedDocWriter, title: str) -> AsyncIterator[None]:
        t = doc.tags
        with t.main:
            t.h1(escape(title))
            yield
            yield  # nothing new: no empty chunk
            t.p(await later("slow"))

    chunks = run(lambda: collect(stream(page, "Hi")))
    assert chunks == ["<main>\n  <h1>Hi</h1>\n", "  <p>slow</p>\n</main>\n"]


def test_generator_template_does_not_flush_while_waiting() -> None:
    async def page(doc: BufferedDocWriter) -> AsyncIterator[None]:
        doc.tags.p("a")
        await later(None)
        doc.tags.p("b")
        yield

    assert run(lambda: collect(stream(page))) == ["<p>a</p>\n<p>b</p>\n"]


def test_async_function_is_flushed_whenever_it_suspends() -> None:
    async def page(doc: BufferedDocWriter, title: str) -> None:
        t = doc.tags
        with t.main:
            t.h1(escape(title))
            t.p(await ready("cached"))  # completes at once: no flush
            t.p(await later("slow"))
            await asyncio.sleep(0)
        t.footer("done")

    chunks = run(lambda: collect(stream(page, title="Hi")))
    assert chunks == [
        "<main>\n  <h1>Hi</h1>\n  <p>cached</p>\n",
        "  <p>slow</p>\n",
        "</main>\n<footer>done</footer>\n",
    ]


def test_async_function_runs_in_the_callers_task_and_context() -> None:
    var: contextvars.ContextVar[str] = contextvars.ContextVar("var", default="unset")

    async def page(doc: BufferedDocWriter, outer: asyncio.Task[object] | None) -> None:
        assert asyncio.current_task() is outer
        await asyncio.sleep(0)
        var.set("set by template")

    async def main() -> str:
        await collect(stream(page, asyncio.current_task()))
        return var.get()

    assert run(main) == "set by template"


def test_errors_reach_the_awaiting_template() -> None:
    async def fail() -> None:
        await asyncio.sleep(0)
        raise KeyError("missing")

    async def page(doc: BufferedDocWriter) -> None:
        try:
            await fail()
        except KeyError:
            doc.tags.p("handled")

    assert run(lambda: collect(stream(page))) == ["<p>handled</p>\n"]


def test_template_errors_propagate_after_earlier_chunks() -> None:
    async def page(doc: BufferedDocWriter) -> None:
        doc.tags.p("before")
        await asyncio.sleep(0)
        raise ValueError("broken")

    async def main() -> list[str]:
        chunks: list[str] = []
        with pytest.raises(ValueError, match="broken"):
            async for chunk in stream(page):
                chunks.append(chunk)
        return chunks

    assert run(main) == ["<p>before</p>\n"]


@pytest.mark.parametrize("kind", ["function", "generator"])
def test_closing_the_stream_closes_the_template(kind: str) -> None:
    events: list[str] = []

    async def function(doc: BufferedDocWriter) -> None:
        try:
            doc.tags.p("first")
            await asyncio.sleep(0)
            doc.tags.p("never sent")
            await asyncio.sleep(0)
        finally:
            events.append("closed")

    async def generator(doc: BufferedDocWriter) -> AsyncIterator[None]:
        try:
            doc.tags.p("first")
            yield
            doc.tags.p("never sent")
            yield
        finally:
            events.append("closed")

    async def main() -> str:
        chunks = stream(function if kind == "function" else generator)
        first = await anext(chunks)
        await chunks.aclose()
        return first

    assert run(main) == "<p>first</p>\n"
    assert events == ["closed"]


def test_cancellation_reaches_the_template() -> None:
    events: list[str] = []

    async def page(doc: BufferedDocWriter) -> None:
        try:
            await asyncio.sleep(10)
        except asyncio.CancelledError:
            events.append("cancelled")
            raise

    async def main() -> None:
        task = asyncio.ensure_future(collect(stream(page)))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    run(main)
    assert events == ["cancelled"]


def test_stream_rejects_synchronous_templates() -> None:
    def page(doc: BufferedDocWriter) -> None:
        doc.tags.p("sync")

    with pytest.raises(TypeError, match="async generator or async function"):
        stream(page)  # type: ignore[call-overload]


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
    async def page(doc: BufferedDocWriter) -> AsyncIterator[None]:
        t = doc.tags
        slots = OutOfOrder(doc, nonce="n<1")
        with t.body:
            slots.defer(later(["slow"], 0.05), articles)("Loading…")
            slots.defer(later(["fast"], 0.01), articles, tag="section")()
            t.footer("end")
            yield
            async for _ in slots.resolve():
                yield

    chunks = run(lambda: collect(stream(page)))
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


def test_out_of_order_flushes_implicitly_in_async_functions() -> None:
    async def page(doc: BufferedDocWriter) -> None:
        slots = OutOfOrder(doc, prefix="s")
        slots.defer(later(["a"]), articles)()
        async for _ in slots.resolve():
            pass

    chunks = run(lambda: collect(stream(page)))
    assert chunks[0] == '<div id="s-1"></div>\n'
    assert chunks[1].startswith("<template>")
    assert 'getElementById("s-1")' in chunks[1]


def test_out_of_order_with_explicit_drains() -> None:
    sent: list[str] = []

    async def send(chunk: str) -> None:
        sent.append(chunk)

    async def main() -> None:
        doc = AsyncDocWriter(send)
        slots = OutOfOrder(doc)
        slots.defer(later(["a"]), articles)()
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
        doc = BufferedDocWriter()
        slots = OutOfOrder(doc)
        slots.defer(slow(), articles)()
        slots.defer(fail(), articles)()
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
        doc = BufferedDocWriter()
        slots = OutOfOrder(doc)
        with slots.defer(
            ready(["a"]), items, tag="ul", keep=True, id="articles", class_="list"
        ):
            doc.tags.li(trust("…"))
        async for _ in slots.resolve():
            pass
        return doc.take()

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
        doc = BufferedDocWriter()
        slots = OutOfOrder(doc)
        slots.defer(ready([]), articles, id=given)()
        async for _ in slots.resolve():
            pass
        return doc.take()

    output = run(main)
    assert output.startswith(f'<div id="{attribute}"></div>\n')
    assert f"getElementById({literal})" in output
    assert output.count("</script>") == 1


def test_placeholders_must_be_written_exactly_once() -> None:
    async def main() -> None:
        doc = BufferedDocWriter()
        slots = OutOfOrder(doc)
        placeholder = slots.defer(ready([]), articles)
        placeholder()
        with pytest.raises(RuntimeError, match="only be written once"), placeholder:
            pass
        slots.defer(ready([]), articles)
        with pytest.raises(RuntimeError, match="has to be written before"):
            async for _ in slots.resolve():
                pass

    run(main)


def test_placeholder_block_wraps_the_written_content() -> None:
    async def main() -> str:
        doc = BufferedDocWriter()
        t = doc.tags
        slots = OutOfOrder(doc, prefix="p")
        with t.main, slots.defer(ready(["a"]), articles, tag="section"):
            t.h2("Articles")
            t.p("Loading…")
        return doc.take()

    assert run(main) == (
        "<main>\n"
        '  <section id="p-1">\n'
        "    <h2>Articles</h2>\n"
        "    <p>Loading…</p>\n"
        "  </section>\n"
        "</main>\n"
    )
