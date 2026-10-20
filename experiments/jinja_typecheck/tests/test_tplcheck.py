"""End-to-end tests: write a template, shadow it, run mypy, read the errors."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from tplcheck.runner import check
from tplcheck.shadow import UnsupportedError, translate

CONFIG = Path(__file__).parents[1] / "mypy.ini"

CONTEXT = """
from typing import TypedDict

class User(TypedDict):
    name: str
    age: int

class Ctx(TypedDict):
    users: list[User]
    title: str
"""


@pytest.fixture(autouse=True)
def fresh_context_module() -> None:
    sys.modules.pop("ctxmod", None)


def run(tmp_path: Path, template: str, monkeypatch: pytest.MonkeyPatch) -> str:
    (tmp_path / "ctxmod.py").write_text(textwrap.dedent(CONTEXT))
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "page.html").write_text(
        "{# tplcheck\n   context: ctxmod.Ctx\n#}\n" + textwrap.dedent(template)
    )
    monkeypatch.setenv("MYPYPATH", str(tmp_path))
    result = check(templates, tmp_path / "shadow", None, ["--config-file", str(CONFIG)])
    return result.output


def test_valid_template_passes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = run(
        tmp_path,
        """\
        <h1>{{ title|upper }}</h1>
        {% for user in users %}
          {{ loop.index }}: {{ user.name }} ({{ user.age + 1 }})
        {% endfor %}
        """,
        monkeypatch,
    )
    assert output.startswith("Success"), output


def test_unknown_attribute_reports_template_line(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = run(
        tmp_path,
        """\
        <h1>{{ title }}</h1>
        {% for user in users %}
          {{ user.nmae }}
        {% endfor %}
        """,
        monkeypatch,
    )
    assert 'page.html:6: error: TypedDict "User" has no key "nmae"' in output


def test_unknown_variable(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    output = run(tmp_path, "{{ titel }}\n", monkeypatch)
    assert 'has no key "titel"' in output


def test_wrong_type_in_filter_and_operator(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = run(
        tmp_path,
        """\
        {% for user in users %}{{ user.age|upper }}{{ user.name + 1 }}{% endfor %}
        """,
        monkeypatch,
    )
    assert "page.html:4" in output
    assert output.count("error:") >= 2


def test_macro_annotations_check_call_sites(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "ctxmod.py").write_text(textwrap.dedent(CONTEXT))
    templates = tmp_path / "templates"
    templates.mkdir()
    (templates / "page.html").write_text(
        "{# tplcheck\n   context: ctxmod.Ctx\n   macro show(n: int)\n#}\n"
        "{% macro show(n) %}{{ n }}{% endmacro %}\n"
        "{{ show(1) }}{{ show(title) }}\n"
    )
    monkeypatch.setenv("MYPYPATH", str(tmp_path))
    output = check(templates, tmp_path / "shadow", None, ["--config-file", str(CONFIG)])
    assert "page.html:6" in output.output
    assert 'Argument 1 to "l_macro_show' in output.output


def test_unsupported_feature_is_reported_with_line() -> None:
    source = "{# tplcheck\n#}\n\n{% import 'x.html' as x %}\n"
    with pytest.raises(UnsupportedError) as raised:
        translate(source, "t.html")
    assert raised.value.lineno == 4


def run_many(
    tmp_path: Path, files: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> str:
    (tmp_path / "ctxmod.py").write_text(
        textwrap.dedent(CONTEXT)
        + "\nclass TitleOnly(TypedDict):\n    title: str\n"
        + "\nclass RowCtx(TypedDict):\n    user: User\n"
    )
    templates = tmp_path / "templates"
    templates.mkdir()
    for name, body in files.items():
        (templates / name).write_text(body)
    monkeypatch.setenv("MYPYPATH", str(tmp_path))
    return check(
        templates, tmp_path / "shadow", None, ["--config-file", str(CONFIG)]
    ).output


BASE = (
    "{# tplcheck\n   context: ctxmod.TitleOnly\n#}\n"
    "<h1>{{ title }}</h1>{% block b %}{% endblock %}\n"
)


def test_extends_with_compatible_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child = (
        "{# tplcheck\n   context: ctxmod.Ctx\n#}\n"
        "{% extends 'base.html' %}{% block b %}{{ users }}{% endblock %}\n"
    )
    output = run_many(tmp_path, {"base.html": BASE, "child.html": child}, monkeypatch)
    assert output.startswith("Success"), output


def test_extends_with_missing_parent_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child = "{# tplcheck\n   context: ctxmod.RowCtx\n#}\n{% extends 'base.html' %}\n"
    output = run_many(tmp_path, {"base.html": BASE, "child.html": child}, monkeypatch)
    assert "child.html:4: error" in output
    assert "TitleOnly" in output


def test_include_passes_loop_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = "{# tplcheck\n   context: ctxmod.RowCtx\n#}\n{{ user.name }}\n"
    page = (
        "{# tplcheck\n   context: ctxmod.Ctx\n#}\n"
        "{% for user in users %}{% include 'row.html' %}{% endfor %}\n"
    )
    output = run_many(tmp_path, {"row.html": row, "page.html": page}, monkeypatch)
    assert output.startswith("Success"), output


def test_include_with_missing_variable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = "{# tplcheck\n   context: ctxmod.RowCtx\n#}\n{{ user.name }}\n"
    page = "{# tplcheck\n   context: ctxmod.Ctx\n#}\n{% include 'row.html' %}\n"
    output = run_many(tmp_path, {"row.html": row, "page.html": page}, monkeypatch)
    assert "page.html:4: error" in output
    assert 'Missing key "user"' in output


def test_include_without_context_gets_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = (
        "{# tplcheck\n   context: ctxmod.Ctx\n#}\n"
        "{% include 'base.html' without context %}\n"
    )
    output = run_many(tmp_path, {"base.html": BASE, "page.html": page}, monkeypatch)
    assert 'Missing key "title"' in output


def test_extends_unannotated_parent_is_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    child = "{# tplcheck\n   context: ctxmod.Ctx\n#}\n{% extends 'plain.html' %}\n"
    output = run_many(tmp_path, {"plain.html": "x", "child.html": child}, monkeypatch)
    assert (
        "child.html:4: error: extends of 'plain.html', which has no tplcheck header"
        in output
    )
