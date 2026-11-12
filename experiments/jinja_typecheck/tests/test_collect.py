"""Context TypedDicts generated from render() call sites."""

from __future__ import annotations

import sys
import textwrap
from pathlib import Path

import pytest
from tplcheck.collect import Spec, collect, main, merge, split_union
from tplcheck.runner import check
from tplcheck.shadow import Config

CONFIG = Path(__file__).parents[1] / "mypy.ini"

FILES = {
    "app/__init__.py": "",
    "app/base.py": """
        from typing import Any

        class Frontend:
            def render(
                self, rs: str, templatename: str, params: dict[str, Any] | None = None
            ) -> str:
                return ""
    """,
    "app/models.py": """
        import datetime

        class Event:
            id: int
            title: str
            start: datetime.datetime | None

        class User:
            name: str
    """,
    "app/views.py": """
        import datetime
        from app.base import Frontend
        from app.models import Event, User

        class CoreFrontend(Frontend):
            def index(self, rs: str, event: Event, flag: bool) -> str:
                if flag:
                    return self.render(rs, "index.html", {"event": event, "n": 1})
                return self.render(
                    rs, "index.html", {"event": event, "n": "x", "extra": [User()]}
                )

            def others(self, rs: str, name: str) -> str:
                params = {"a": 1}
                self.render(rs, name, {"x": 1})  # dynamic name
                self.render(rs, "dynamic.html", params)  # not a dict literal
                return self.render(rs, "login.html")  # no params at all
    """,
}


@pytest.fixture
def project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name, body in FILES.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(body))
    monkeypatch.setenv("MYPYPATH", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    sys.modules.pop("genctx", None)
    return tmp_path


def generate(project: Path, *extra: str) -> str:
    argv = [
        "--render",
        "app.base.Frontend.render",
        "--module",
        "genctx",
        "--out",
        str(project / "genctx.py"),
        *extra,
        "--",
        "--explicit-package-bases",
        str(project / "app"),
    ]
    assert main(argv) == 0
    return (project / "genctx.py").read_text()


def test_sites_are_collected_through_a_subclass(project: Path) -> None:
    sites, _ = collect(
        Spec("app.base.Frontend.render"),
        ["--explicit-package-bases", str(project / "app")],
    )
    templates = sorted(site.template for site in sites)
    # the dynamic name is skipped, everything else is seen
    assert templates == ["dynamic.html", "index.html", "index.html", "login.html"]


def test_calls_are_merged_into_one_typeddict(project: Path) -> None:
    sites, _ = collect(
        Spec("app.base.Frontend.render"),
        ["--explicit-package-bases", str(project / "app")],
    )
    index = next(c for c in merge(sites) if c.template == "index.html")
    assert index.class_name == "IndexContext"
    assert index.keys == {
        "event": ("app.models.Event", True),
        "n": ("int | str", True),  # both calls pass it, with different types
        "extra": ("list[app.models.User]", False),  # only one does
    }


def test_generated_module(project: Path) -> None:
    text = generate(project)
    assert "class IndexContext(TypedDict):" in text
    assert "    event: app.models.Event" in text
    assert "    extra: NotRequired[list[app.models.User]]" in text
    # a template rendered with something we cannot look into is not mapped
    assert "'dynamic.html'" not in text.split("TEMPLATE_CONTEXTS")[1]
    assert "'index.html': 'genctx.IndexContext'" in text
    assert "'login.html': 'genctx.LoginContext'" in text


def test_base_context_and_mapper(project: Path) -> None:
    (project / "basectx.py").write_text(
        "from typing import TypedDict\n\nclass Base(TypedDict):\n    rs: str\n"
    )
    (project / "mapper.py").write_text(
        textwrap.dedent(
            """
            def mapper(module, cls, template):
                return None if template == "login.html" else f"web/{cls}/{template}"
            """
        )
    )
    text = generate(
        project, "--base-context", "basectx.Base", "--mapper", "mapper:mapper"
    )
    assert "from basectx import Base" in text
    assert "class WebCoreFrontendIndexContext(Base):" in text
    assert "login" not in text


def test_split_union_respects_brackets() -> None:
    assert split_union("A | dict[str, B | None] | None") == [
        "A",
        "dict[str, B | None]",
        "None",
    ]


def test_templates_are_checked_against_the_generated_contexts(
    project: Path,
) -> None:
    generate(project)
    templates = project / "templates"
    templates.mkdir()
    # no header at all: the context comes from the render() calls
    (templates / "index.html").write_text(
        "{{ event.title }}{{ n }}{% if extra %}{{ extra[0].name }}{% endif %}\n"
    )
    config = Config(contexts_module="genctx")
    args = ["--config-file", str(CONFIG)]
    ok = check(templates, project / "shadow", None, args, config)
    assert ok.output.startswith("Success"), ok.output

    (templates / "index.html").write_text(
        "{{ event.titel }}{{ extra[0].nme }}{{ nope }}\n"
    )
    bad = check(templates, project / "shadow", None, args, config)
    assert (
        'has no key "titel"' in bad.output or '"Event" has no attribute' in bad.output
    )
    assert "nme" in bad.output
    assert 'has no key "nope"' in bad.output
