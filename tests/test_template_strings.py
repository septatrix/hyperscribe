"""Template strings (``t"..."``), which need Python 3.14.

The templates are compiled from source at run time
so that this module can still be imported on older versions, where it is skipped.
"""

import datetime
import sys
from collections.abc import Callable
from io import StringIO
from pathlib import Path
from typing import Any

import pytest

from hyperscribe import DocWriter, escape, trust

pytestmark = pytest.mark.skipif(
    sys.version_info < (3, 14), reason="template strings need Python 3.14"
)


class TrustedHTML:
    def __init__(self, value: str) -> None:
        self.value = value

    def __html__(self) -> str:
        return self.value


def template(source: str, **values: Any) -> Any:
    return eval(f't"""{source}"""', {}, values)


def render(build: Callable[[DocWriter], object]) -> str:
    output = StringIO()
    build(DocWriter(output))
    return output.getvalue()


def test_literal_parts_are_trusted() -> None:
    assert render(lambda doc: doc(template("<b>1 < 2</b>"))) == "<b>1 < 2</b>\n"


def test_strings_are_escaped() -> None:
    result = render(lambda doc: doc(template("<b>{name}</b>", name="a & <i>")))
    assert result == "<b>a &amp; &lt;i&gt;</b>\n"


def test_numbers_are_trusted() -> None:
    result = render(lambda doc: doc(template("{n} and {x}", n=3, x=1.5)))
    assert result == "3 and 1.5\n"


def test_html_objects_are_trusted() -> None:
    markup = TrustedHTML("<i>x</i>")
    result = render(lambda doc: doc(template("<b>{m}</b>", m=markup)))
    assert result == "<b><i>x</i></b>\n"


def test_html_protocol_wins_over_numeric_subclasses() -> None:
    class HTMLInt(int):
        def __html__(self) -> str:
            return "<b>int</b>"

    result = render(lambda doc: doc(template("{n}", n=HTMLInt(3))))
    assert result == "<b>int</b>\n"


def test_other_objects_are_converted_and_escaped() -> None:
    result = render(lambda doc: doc(template("{p}", p=Path("a<b"))))
    assert result == "a&lt;b\n"


def test_safe_strings_are_escaped_again() -> None:
    # SafeStr is a plain str at run time, so an interpolated one cannot be told
    # from any other string. Interpolate the raw value, or an object with __html__.
    result = render(lambda doc: doc(template("{s}", s=escape("a<b"))))
    assert result == "a&amp;lt;b\n"
    result = render(lambda doc: doc(template("{s}", s=trust("<b>"))))
    assert result == "&lt;b&gt;\n"


def test_format_spec_is_applied_and_the_result_escaped() -> None:
    result = render(lambda doc: doc(template("{n:.2f}|{s:>6}", n=3.14159, s="<")))
    assert result == "3.14|     &lt;\n"


def test_dates_are_formatted_with_a_format_spec() -> None:
    day = datetime.date(2026, 10, 2)
    moment = datetime.datetime(2026, 10, 2, 13, 5, 9)
    clock = datetime.time(13, 5)
    result = render(
        lambda doc: doc(
            template(
                "{d:%d.%m.%Y}|{m:%Y-%m-%d %H:%M:%S}|{c:%H:%M}", d=day, m=moment, c=clock
            )
        )
    )
    assert result == "02.10.2026|2026-10-02 13:05:09|13:05\n"


def test_the_result_of_a_date_format_spec_is_escaped() -> None:
    day = datetime.date(2026, 10, 2)
    result = render(lambda doc: doc(template("{d:<%Y>}", d=day)))
    assert result == "&lt;2026&gt;\n"


def test_conversion_is_applied_and_the_result_escaped() -> None:
    result = render(lambda doc: doc(template("{s!r}", s="<")))
    assert result == "'&lt;'\n"


def test_converted_html_objects_are_escaped() -> None:
    class Both:
        def __str__(self) -> str:
            return "<plain>"

        def __html__(self) -> str:
            return "<safe>"

    assert render(lambda doc: doc(template("{b}", b=Both()))) == "<safe>\n"
    assert render(lambda doc: doc(template("{b!s}", b=Both()))) == "&lt;plain&gt;\n"


def test_none_is_rejected() -> None:
    with pytest.raises(TypeError, match="x"):
        render(lambda doc: doc(template("{x}", x=None)))


def test_escaped_braces_are_literal() -> None:
    assert render(lambda doc: doc(template("{{x}}"))) == "{x}\n"


def test_tag_content_handles_templates_like_call() -> None:
    result = render(
        lambda doc: doc.tags.p(template("Hello, <b>{name}</b>!", name="<Ada>"))
    )
    assert result == "<p>Hello, <b>&lt;Ada&gt;</b>!</p>\n"


def test_templates_work_in_inline_blocks() -> None:
    def build(doc: DocWriter) -> None:
        with doc.inline(), doc.tags.li:
            doc(template("{a} &mdash; ", a="<x>"))
            doc.tags.b("y")

    assert render(build) == "<li>&lt;x&gt; &mdash; <b>y</b></li>\n"


def test_attribute_values_may_be_templates() -> None:
    result = render(
        lambda doc: doc.tags.a("x", href=template("/u/{id}?q={q}", id=7, q='a"b&c'))
    )
    assert result == '<a href="/u/7?q=a&quot;b&amp;c">x</a>\n'
