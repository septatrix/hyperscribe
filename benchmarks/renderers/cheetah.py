"""Renderer using a precompiled Cheetah3 template."""

import html
from pathlib import Path

from Cheetah.Template import Template

from benchmarks.cheetah_base import BasePage  # noqa: F401  # Precompile before the child.
from benchmarks.models import Item

_template_path = Path(__file__).parents[1] / "templates" / "articles.cheetah"
_template_class = Template.compile(file=str(_template_path))


def render(items: list[Item]) -> str:
    """Render the article list with the compiled Cheetah3 template."""
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    template = _template_class(
        searchList=[
            {
                # Cheetah's Template class exposes an ``items()`` method, so
                # use a distinct namespace key to avoid shadowing the input.
                "articles": items,
                "topic_index": topic_index,
                "escape_text": lambda value: html.escape(value, quote=False),
                "escape_attr": lambda value: html.escape(value, quote=True),
            }
        ]
    )
    return str(template)
