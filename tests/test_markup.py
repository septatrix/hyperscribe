import pytest

import hyperscribe
from hyperscribe import DocWriter, markup
from hyperscribe.markup import classes, escape


def render_div(**attrs: hyperscribe.AttributeValue) -> str:
    parts: list[str] = []
    DocWriter(parts.append).tags.div("", **attrs)
    return "".join(parts)


def test_helpers_are_also_available_from_the_package() -> None:
    for name in markup.__all__:
        assert getattr(hyperscribe, name) is getattr(markup, name)


def test_classes_joins_names_and_included_mapping_keys() -> None:
    is_active, is_hidden = True, False
    result = classes(
        "btn",
        {"btn-primary": True, "disabled": False, "hidden": is_hidden},
        is_active and "active",
        is_hidden and "gone",
        None,
        "",
        "large wide",
    )
    assert result == "btn btn-primary active large wide"


def test_classes_includes_mapping_keys_by_truthiness() -> None:
    assert classes({"has-items": [1], "empty": [], "named": "x", "zero": 0}) == (
        "has-items named"
    )


def test_classes_escapes_the_names() -> None:
    assert classes('a"b', {"<c>": True}) == "a&quot;b &lt;c&gt;"


def test_classes_without_names_leaves_the_attribute_out() -> None:
    assert classes() is None
    assert classes({"a": False}, None, False) is None
    assert render_div(class_=classes({"a": False})) == "<div></div>\n"


def test_classes_as_an_attribute() -> None:
    assert render_div(class_=classes("card", {"open": True})) == (
        '<div class="card open"></div>\n'
    )


def test_classes_rejects_other_values() -> None:
    with pytest.raises(TypeError, match="not int"):
        classes(3)  # type: ignore[arg-type]
    with pytest.raises(TypeError, match="not bool"):
        classes(True)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("name", "hint"),
    [("class_", "classes()"), ("style", "as a string")],
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
