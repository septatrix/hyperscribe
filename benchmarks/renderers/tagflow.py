"""Article-list renderer implemented with the Tagflow package from PyPI."""

from xml.etree import ElementTree

from tagflow import document, tag, text
from tagflow.tagflow import node

from ..models import Item


def render_topic_list(topics: list[str]) -> None:
    """Append a topic list to the element that is currently open."""
    with tag.div():
        for index, topic in enumerate(topics):
            if index:
                text(", ")
            with tag.span():
                text(topic)


def render(items: list[Item]) -> str:
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    with document() as root:
        with tag.html(lang="en"):
            with tag.head():
                with tag.title():
                    text("Articles")
                tag.meta(charset="utf-8")
                tag.meta(name="viewport", content="width=device-width, initial-scale=1")
                tag.link(rel="stylesheet", href="/static/site.css")
                with tag.script(src="/static/app.js", defer=True):
                    pass
            with tag.body(), tag.main():
                with tag.nav():
                    with tag.h2():
                        text("Browse topics")
                    render_topic_list(topic_index)
                with tag.ul():
                    for item in items:
                        with tag.li(
                            class_="featured" if item["featured"] else None,
                            data_category=item["category"],
                            hidden=item["draft"],
                        ):
                            node.get().append(
                                ElementTree.Comment(f" article {item['id']} ")
                            )
                            tag.img(
                                src=item["thumbnail"],
                                alt=item["title"],
                                width=64,
                                height=64,
                                loading="lazy",
                            )
                            with tag.a(
                                href=item["url"],
                                target="_blank" if item["external"] else None,
                                rel="noopener" if item["external"] else None,
                            ):
                                text(item["title"])
                            with tag.p():
                                text(item["summary"])
                            if item["featured"]:
                                with tag.strong():
                                    text("Featured")
                            with tag.span():
                                text(item["category"])
                            with tag.span(class_="rating"):
                                text(str(item["rating"]))
                            if item["author"]:
                                with tag.small(), tag.span():
                                    text(f"By {item['author']}")
                            if item["tags"]:
                                render_topic_list(item["tags"])
                            if item["comments"]:
                                with tag.span():
                                    text(f"{item['comments']} comments")
    return "<!DOCTYPE html>" + root.to_html()
