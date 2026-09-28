"""Jinja renderer and template initialization."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from bench.models import Item

_template_directory = Path(__file__).parents[1] / "templates"
_environment = Environment(
    loader=FileSystemLoader(_template_directory),
    autoescape=select_autoescape(default=True),
)
_template = _environment.get_template("articles.jinja2")


def render(items: list[Item]) -> str:
    """Render the articles template with the supplied items."""
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    return _template.render(items=items, topic_index=topic_index)
