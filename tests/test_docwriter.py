from io import StringIO

from hyperscribe import DocWriter


def render(build) -> str:
    output = StringIO()
    build(DocWriter(output))
    return output.getvalue()


def test_leaf_tag_is_written_on_one_line() -> None:
    assert render(lambda doc: doc.p("hello")) == "<p>hello</p>\n"


def test_text_is_escaped() -> None:
    assert render(lambda doc: doc.p("a & <b>")) == "<p>a &amp; &lt;b&gt;</p>\n"


def test_attributes_are_escaped() -> None:
    result = render(lambda doc: doc.a("x", href='a"b&c'))
    assert result == '<a href="a&quot;b&amp;c">x</a>\n'


def test_nested_tags_are_indented() -> None:
    def build(doc: DocWriter) -> None:
        with doc.ul:
            doc.li("one")

    assert render(build) == "<ul>\n  <li>one</li>\n</ul>\n"


def test_chained_tags_open_together() -> None:
    def build(doc: DocWriter) -> None:
        with doc.body.main:
            doc.p("x")

    assert render(build) == "<body>\n  <main>\n    <p>x</p>\n  </main>\n</body>\n"


def test_chained_leaf_with_attributes() -> None:
    result = render(lambda doc: doc.small.span("hi", title="t"))
    assert result == '<small><span title="t">hi</span></small>\n'


def test_tag_method_supports_arbitrary_names() -> None:
    def build(doc: DocWriter) -> None:
        with doc.tag("my-element", id="1"):
            doc.text("t")

    assert render(build) == '<my-element id="1">\n  t\n</my-element>\n'


def test_call_writes_escaped_text() -> None:
    assert render(lambda doc: doc("1 < 2")) == "1 &lt; 2\n"


def test_write_raw_is_not_escaped_or_indented() -> None:
    def build(doc: DocWriter) -> None:
        with doc.div:
            doc.write_raw("<hr>\n")

    assert render(build) == "<div>\n<hr>\n</div>\n"


def test_inline_suppresses_whitespace() -> None:
    def build(doc: DocWriter) -> None:
        with doc.ul:
            with doc.inline(), doc.li:
                doc("hi, ")
                doc.b("there")

    assert render(build) == "<ul>\n  <li>hi, <b>there</b></li>\n</ul>\n"


def test_nested_inline_resumes_formatting_after_outermost_exit() -> None:
    def build(doc: DocWriter) -> None:
        with doc.inline():
            with doc.inline(), doc.span:
                doc("a")
        doc.p("b")

    assert render(build) == "<span>a</span>\n<p>b</p>\n"


def test_writes_to_any_object_with_write() -> None:
    chunks: list[str] = []

    class Sink:
        def write(self, value: str) -> int:
            chunks.append(value)
            return len(value)

    DocWriter(Sink()).p("x")  # type: ignore[arg-type]
    assert "".join(chunks) == "<p>x</p>\n"
