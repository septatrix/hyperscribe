import pytest

import hyperscribe
from hyperscribe import DocWriter, markup
from hyperscribe.markup import escape, tokenlist


def render_div(**attrs: hyperscribe.AttributeValue) -> str:
    parts: list[str] = []
    DocWriter(parts.append).tags.div("", **attrs)
    return "".join(parts)


def test_helpers_are_also_available_from_the_package() -> None:
    for name in markup.__all__:
        assert getattr(hyperscribe, name) is getattr(markup, name)


def test_tokenlist_joins_names_and_included_mapping_keys() -> None:
    is_active, is_hidden = True, False
    result = tokenlist(
        "btn",
        {"btn-primary": True, "disabled": False, "hidden": is_hidden},
        is_active and "active",
        is_hidden and "gone",
        None,
        "",
        "large wide",
    )
    assert result == "btn btn-primary active large wide"


def test_tokenlist_includes_mapping_keys_by_truthiness() -> None:
    assert tokenlist({"has-items": [1], "empty": [], "named": "x", "zero": 0}) == (
        "has-items named"
    )


def test_tokenlist_escapes_the_names() -> None:
    assert tokenlist('a"b', {"<c>": True}) == "a&quot;b &lt;c&gt;"


def test_tokenlist_without_names_leaves_the_attribute_out() -> None:
    assert tokenlist() is None
    assert tokenlist({"a": False}, None, False) is None
    assert render_div(class_=tokenlist({"a": False})) == "<div></div>\n"


def test_tokenlist_as_an_attribute() -> None:
    assert render_div(class_=tokenlist("card", {"open": True})) == (
        '<div class="card open"></div>\n'
    )


def test_tokenlist_suits_other_attributes() -> None:
    parts: list[str] = []
    external = True
    DocWriter(parts.append).tags.a(
        "Docs", href="/docs", rel=tokenlist("noopener", {"noreferrer": external})
    )
    assert "".join(parts) == '<a href="/docs" rel="noopener noreferrer">Docs</a>\n'


def test_tokenlist_rejects_other_values() -> None:
    with pytest.raises(TypeError, match="not int"):
        tokenlist(3)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="not bool"):
        tokenlist(True)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "hint"),
    [("class_", "tokenlist()"), ("style", "as a string")],
)
def test_class_and_style_cannot_be_dictionaries(name: str, hint: str) -> None:
    value: dict[str, hyperscribe.AttributeValue] = {"a": True}
    with pytest.raises(TypeError, match=rf"cannot be a dictionary; .*{hint}"):
        render_div(**{name: value})


def test_class_and_style_inside_a_prefix_are_still_flattened() -> None:
    assert render_div(data={"class": "x", "style": "y"}) == (
        '<div data-class="x" data-style="y"></div>\n'
    )


def test_escape_still_works_from_the_package() -> None:
    assert hyperscribe.escape is escape
    assert escape("<b>") == "&lt;b&gt;"
