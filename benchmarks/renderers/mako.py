"""Renderer using a preloaded Mako template."""

from pathlib import Path

from mako.lookup import TemplateLookup

from ..models import Item

_template_directory = Path(__file__).parents[1] / "templates"
_lookup = TemplateLookup(
    directories=[str(_template_directory)],
    default_filters=["str", "h"],
)
_template = _lookup.get_template("articles.mako")


def render(items: list[Item]) -> str:
    """Render the article list with Mako."""
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    return _template.render(items=items, topic_index=topic_index)
