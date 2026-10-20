"""End-to-end tests: write a template, shadow it, run mypy, read the errors."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from tplcheck.runner import check
from tplcheck.shadow import Config, UnsupportedError, translate

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
    assert 'Argument 1 to "show" of "Macros"' in output.output


def test_unsupported_feature_is_reported_with_line() -> None:
    source = "{# tplcheck\n#}\n\n{% import 'x.html' as x %}\n"
    with pytest.raises(UnsupportedError) as raised:
        translate(source, "t.html")
    assert raised.value.lineno == 4


def run_many(
    tmp_path: Path,
    files: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
    config: Config | None = None,
) -> str:
    (tmp_path / "ctxmod.py").write_text(
        textwrap.dedent(CONTEXT)
        + "\nclass TitleOnly(TypedDict):\n    title: str\n"
        + "\nclass RowCtx(TypedDict):\n    user: User\n"
        + "\nclass BaseCtx(TypedDict):\n    active: str\n"
    )
    templates = tmp_path / "templates"
    templates.mkdir(exist_ok=True)
    for name, body in files.items():
        (templates / name).write_text(body)
    monkeypatch.setenv("MYPYPATH", str(tmp_path))
    return check(
        templates, tmp_path / "shadow", None, ["--config-file", str(CONFIG)], config
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


HEAD = "{# tplcheck\n   context: ctxmod.Ctx\n#}\n"
LIB = "{# tplcheck\n   context: ctxmod.TitleOnly\n#}\n"


def test_import_with_context_exposes_typed_macros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = (
        LIB
        + "{% macro heading(level) %}<h{{ level }}>{{ title }}</h{{ level }}>{% endmacro %}\n"
    )
    page = (
        HEAD
        + "{% import 'lib.html' as lib with context %}"
        + "{{ lib.heading(1) }}{{ lib.heading(level=2) }}{{ lib.nope() }}"
    )
    output = run_many(tmp_path, {"lib.html": lib, "page.html": page}, monkeypatch)
    assert "page.html:4:" in output
    assert '"Macros" has no attribute "nope"' in output
    assert output.count("error:") == 1


def test_import_with_context_checks_importers_context(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = LIB + "{% macro heading() %}{{ title }}{% endmacro %}\n"
    page = (
        "{# tplcheck\n   context: ctxmod.RowCtx\n#}\n"
        "{% import 'lib.html' as lib with context %}{{ lib.heading() }}"
    )
    output = run_many(tmp_path, {"lib.html": lib, "page.html": page}, monkeypatch)
    assert "page.html:4: error" in output
    assert "TitleOnly" in output


def test_call_block_passes_caller(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = (
        LIB
        + "{% macro panel(heading, aclass='x') %}<div class='{{ aclass }}'>{{ heading }}"
        + "{{ caller() }}</div>{% endmacro %}\n"
        + "{% macro maybe() %}{% if caller %}{{ caller() }}{% endif %}{% endmacro %}\n"
    )
    page = (
        HEAD
        + "{% import 'lib.html' as lib with context %}"
        + "{% call lib.panel(heading=title) %}{% for u in users %}{{ u.name }}{% endfor %}"
        + "{% endcall %}{{ lib.maybe() }}"
        + "{{ lib.panel('x') }}"
    )
    output = run_many(tmp_path, {"lib.html": lib, "page.html": page}, monkeypatch)
    # panel() without a call block: `caller` is required there
    assert 'Missing named argument "caller" for "panel"' in output
    assert output.count("error:") == 1


def test_call_block_with_arguments_and_body_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    lib = LIB + "{% macro rows() %}{{ caller(1) }}{% endmacro %}\n"
    page = (
        HEAD
        + "{% import 'lib.html' as lib with context %}"
        + "{% call(n) lib.rows() %}{{ n }}{{ users.nope }}{% endcall %}"
    )
    output = run_many(tmp_path, {"lib.html": lib, "page.html": page}, monkeypatch)
    assert "page.html:4" in output
    assert "nope" in output


def test_top_level_set_reaches_parent_and_macros(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    base = (
        "{# tplcheck\n   context: ctxmod.BaseCtx\n#}\n"
        "{{ active.upper() }}{% block b %}{% endblock %}"
    )
    child = (
        HEAD
        + "{% set active = 'home' %}{% extends 'base.html' %}"
        + "{% block b %}{{ super() }}{{ self.b() }}{% endblock %}"
    )
    output = run_many(tmp_path, {"base.html": base, "child.html": child}, monkeypatch)
    assert output.startswith("Success"), output
    bad = child.replace("'home'", "3")
    output = run_many(tmp_path, {"base.html": base, "child.html": bad}, monkeypatch)
    assert "child.html:4: error" in output
    assert "active" in output


def test_with_do_loopcontrols_and_keyword_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = (
        HEAD
        + "{% with n = users|length, label = title %}{{ n + 1 }}{{ label.upper() }}{% endwith %}"
        + "{% for u in users %}{% if u.age > 3 %}{% continue %}{% endif %}{% break %}{% endfor %}"
        + "{% set seen = [] %}{% do seen.append(title) %}"
        + "{{ dict(class='a', id=1)|xmlattr }}"
    )
    config = Config(extensions=("jinja2.ext.do", "jinja2.ext.loopcontrols"))
    output = run_many(tmp_path, {"page.html": page}, monkeypatch, config)
    assert output.startswith("Success"), output


def test_trans_blocks_and_translation_functions(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = (
        HEAD
        + "{% trans %}Hello{% endtrans %}"
        + "{% trans name=title %}Hello {{ name }}{% endtrans %}"
        + "{% trans count=users|length %}{{ count }} user{% pluralize %}{{ count }} users{% endtrans %}"
        + "{{ gettext('x') }}{{ _('y') }}{{ ngettext('a', 'b', 2) }}"
        + "{% trans %}{{ nope }}{% endtrans %}"
    )
    config = Config(extensions=("jinja2.ext.i18n",))
    output = run_many(tmp_path, {"page.html": page}, monkeypatch, config)
    assert output.count("error:") == 1, output
    assert 'has no key "nope"' in output


def test_set_in_if_branches_is_scoped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    page = (
        HEAD
        + "{% if title %}{% set a = 1 %}{% set b = 1 %}"
        + "{% else %}{% set a = 'text' %}{{ b }}{% endif %}{{ a }}"
    )
    output = run_many(tmp_path, {"page.html": page}, monkeypatch)
    # `a` is set in every branch, so it is defined afterwards (with either type);
    # `b` is only set in one branch, so the read in the other one is the context's
    assert 'has no key "b"' in output
    assert output.count("error:") == 1


def test_project_filters_and_tests_modules(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "myfilters.py").write_text(
        "def shout(value: str, times: int = 1) -> str:\n    raise NotImplementedError\n"
    )
    page = HEAD + "{{ title|shout(2) }}{{ users|shout }}"
    config = Config(filters_module="myfilters")
    output = run_many(tmp_path, {"page.html": page}, monkeypatch, config)
    assert "page.html:4: error" in output
    assert output.count("error:") == 1


def test_is_tests_narrow_types(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "ctxmod.py").write_text("")  # replaced by run_many
    page = HEAD + "{% if title is string %}{{ title.upper() }}{% endif %}"
    output = run_many(tmp_path, {"page.html": page}, monkeypatch)
    assert output.startswith("Success"), output
