"""Article-list renderer implemented with dominate."""

from typing import Any

from dominate import tags
from dominate.util import text as dominate_text

from ..models import Item


def render_topic_list(topics: list[str]):
    """Build a reusable topic list element for insertion into a document."""
    result = tags.div()
    with result:
        for index, topic in enumerate(topics):
            if index:
                dominate_text(", ")
            tags.span(topic)
    return result


def render(items: list[Item]) -> str:
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    root = tags.html(lang="en")
    with root:
        with tags.head():
            tags.title("Articles")
            tags.meta(charset="utf-8")
            tags.meta(name="viewport", content="width=device-width, initial-scale=1")
            tags.link(rel="stylesheet", href="/static/site.css")
            tags.script(src="/static/app.js", defer=True)
        with tags.body():
            with tags.main():
                with tags.nav():
                    tags.h2("Browse topics")
                    render_topic_list(topic_index)
                with tags.ul():
                    for item in items:
                        item_attributes: dict[str, Any] = {
                            "data_category": item["category"]
                        }
                        if item["featured"]:
                            item_attributes["cls"] = "featured"
                        if item["draft"]:
                            item_attributes["hidden"] = True
                        link_attributes: dict[str, Any] = {"href": item["url"]}
                        if item["external"]:
                            link_attributes["target"] = "_blank"
                            link_attributes["rel"] = "noopener"
                        with tags.li(**item_attributes):
                            tags.comment(f"article {item['id']}")
                            tags.img(
                                src=item["thumbnail"],
                                alt=item["title"],
                                width=64,
                                height=64,
                                loading="lazy",
                            )
                            tags.a(item["title"], **link_attributes)
                            tags.p(item["summary"])
                            if item["featured"]:
                                tags.strong("Featured")
                            tags.span(item["category"])
                            tags.span(str(item["rating"]), cls="rating")
                            if item["author"]:
                                with tags.small():
                                    tags.span(f"By {item['author']}")
                            if item["tags"]:
                                render_topic_list(item["tags"])
                            if item["comments"]:
                                tags.span(f"{item['comments']} comments")
    return "<!DOCTYPE html>\n" + root.render(pretty=True)
