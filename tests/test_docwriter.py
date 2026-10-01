from collections.abc import Callable
from decimal import Decimal
from io import StringIO

import pytest

from hyperscribe import DocWriter


class TrustedHTML:
    def __init__(self, value: str) -> None:
        self.value = value

    def __html__(self) -> str:
        return self.value


def render(build: Callable[[DocWriter], object]) -> str:
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


@pytest.mark.filterwarnings("ignore:Use doc.* instead:DeprecationWarning")
def test_tag_method_supports_arbitrary_names() -> None:
    def build(doc: DocWriter) -> None:
        with doc.tag("my-element", id="1"):
            doc.text("t")

    assert render(build) == '<my-element id="1">\n  t\n</my-element>\n'


def test_call_writes_trusted_text_verbatim() -> None:
    assert render(lambda doc: doc("1 < 2")) == "1 < 2\n"


def test_call_writes_html_protocol_content_verbatim() -> None:
    assert render(lambda doc: doc(TrustedHTML("<b>trusted & safe</b>"))) == (
        "<b>trusted & safe</b>\n"
    )


def test_call_indents_html_protocol_content() -> None:
    def build(doc: DocWriter) -> None:
        with doc.div:
            doc(TrustedHTML("<b>trusted</b>"))

    assert render(build) == "<div>\n  <b>trusted</b>\n</div>\n"


@pytest.mark.filterwarnings("ignore:Use doc.* instead:DeprecationWarning")
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


def test_none_attribute_is_omitted() -> None:
    assert render(lambda doc: doc.a("x", href=None)) == "<a>x</a>\n"


def test_false_attribute_is_omitted() -> None:
    assert render(lambda doc: doc.a("x", hidden=False)) == "<a>x</a>\n"


def test_true_attribute_is_written_without_a_value() -> None:
    result = render(lambda doc: doc.script("", src="a.js", defer=True))
    assert result == '<script src="a.js" defer></script>\n'


def test_numeric_attribute_is_converted() -> None:
    assert render(lambda doc: doc.td("x", colspan=3)) == '<td colspan="3">x</td>\n'


def test_trailing_underscore_is_dropped_from_attribute_names() -> None:
    result = render(lambda doc: doc.label("x", for_="a", class_="b"))
    assert result == '<label for="a" class="b">x</label>\n'


def test_only_the_trailing_underscore_is_dropped() -> None:
    result = render(lambda doc: doc.div("x", data_id="7"))
    assert result == '<div data_id="7">x</div>\n'


def test_dictionary_attribute_is_flattened_with_a_prefix() -> None:
    result = render(lambda doc: doc.div("x", data={"id": 7, "user-name": "a&b"}))
    assert result == '<div data-id="7" data-user-name="a&amp;b">x</div>\n'


def test_dictionary_attribute_follows_the_value_rules() -> None:
    result = render(
        lambda doc: doc.div("x", data={"flag": True, "label": None, "busy": False})
    )
    assert result == "<div data-flag>x</div>\n"


def test_aria_booleans_are_written_as_strings() -> None:
    result = render(
        lambda doc: doc.div(
            "x", aria={"hidden": True, "expanded": False, "label": None}
        )
    )
    assert result == '<div aria-hidden="true" aria-expanded="false">x</div>\n'


def test_arbitrary_objects_are_converted_with_str() -> None:
    result = render(lambda doc: doc.void_tag("input", value=Decimal("1.25")))
    assert result == '<input value="1.25">\n'


def test_dictionaries_nest() -> None:
    result = render(lambda doc: doc.div("x", data={"a": {"b": "1"}}))
    assert result == '<div data-a-b="1">x</div>\n'


def test_dictionary_prefix_drops_a_trailing_underscore() -> None:
    result = render(lambda doc: doc.div("x", data_={"id": "7"}))
    assert result == '<div data-id="7">x</div>\n'


def test_attribute_names_apply_to_context_managers() -> None:
    def build(doc: DocWriter) -> None:
        with doc.div(class_="card", data={"id": "7"}):
            doc.p("x")

    assert render(build) == '<div class="card" data-id="7">\n  <p>x</p>\n</div>\n'


def test_attribute_names_apply_to_tag_method() -> None:
    def build(doc: DocWriter) -> None:
        with doc.tag("my-element", class_="x"):
            pass

    assert render(build) == '<my-element class="x">\n</my-element>\n'


def test_unpacked_attribute_names_are_still_possible() -> None:
    result = render(lambda doc: doc.p("x", **{"xml:lang": "en"}))
    assert result == '<p xml:lang="en">x</p>\n'


@pytest.mark.filterwarnings("ignore:Use doc.* instead:DeprecationWarning")
def test_number_content_is_converted() -> None:
    assert render(lambda doc: doc.p(3)) == "<p>3</p>\n"
    assert render(lambda doc: doc(1.5)) == "1.5\n"
    assert render(lambda doc: doc.text(True)) == "True\n"


def test_none_content_is_rejected() -> None:
    with pytest.raises(TypeError, match="None"):
        render(lambda doc: doc.p(None))


def test_call_converts_non_string_values_without_escaping() -> None:
    assert render(lambda doc: doc(1.5)) == "1.5\n"


def test_empty_string_content_writes_an_empty_element() -> None:
    assert render(lambda doc: doc.div("")) == "<div></div>\n"


def test_tag_method_accepts_a_name_attribute() -> None:
    def build(doc: DocWriter) -> None:
        with doc.tag("label", name="viewport"):
            pass

    assert render(build) == '<label name="viewport">\n</label>\n'


def test_attributes_may_be_called_content_or_path() -> None:
    assert render(lambda doc: doc.a("x", content="c")) == '<a content="c">x</a>\n'

    def build(doc: DocWriter) -> None:
        with doc.a(path="p"):
            pass

    assert render(build) == '<a path="p">\n</a>\n'


def test_void_tag_writes_an_opening_tag_only() -> None:
    assert render(lambda doc: doc.void_tag("br")) == "<br>\n"


def test_void_tag_has_attributes_that_are_escaped() -> None:
    result = render(
        lambda doc: doc.void_tag("meta", name="a&b", content='x"y', defer=True)
    )
    assert result == '<meta name="a&amp;b" content="x&quot;y" defer>\n'


def test_void_tag_is_indented_and_does_not_nest() -> None:
    def build(doc: DocWriter) -> None:
        with doc.p:
            doc.void_tag("br")
            doc("x")

    assert render(build) == "<p>\n  <br>\n  x\n</p>\n"


def test_void_tag_honors_inline_blocks() -> None:
    def build(doc: DocWriter) -> None:
        with doc.inline(), doc.p:
            doc("a")
            doc.void_tag("br")
            doc("b")

    assert render(build) == "<p>a<br>b</p>\n"


def test_comment_is_indented() -> None:
    def build(doc: DocWriter) -> None:
        with doc.div:
            doc.comment("note")

    assert render(build) == "<div>\n  <!-- note -->\n</div>\n"


def test_comment_cannot_end_early() -> None:
    with pytest.raises(ValueError, match="comment"):
        render(lambda doc: doc.comment("a --> <script>"))
