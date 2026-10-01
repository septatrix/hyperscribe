"""Article-list renderer using the stream-backed Hyperscribe package."""

from collections.abc import Iterator
from io import StringIO
from typing import Literal

from hyperscribe import DocWriter

from ..models import Item


def page(doc: DocWriter) -> Iterator[Literal["head", "navigation", "content"]]:
    """Provide the document shell and yield its replaceable content sections."""
    with doc.html(lang="en"):
        with doc.head:
            yield "head"
        with doc.body.main:
            with doc.nav:
                yield "navigation"
            with doc.ul:
                yield "content"


def render_topic_list(doc: DocWriter, topics: list[str]) -> None:
    """Append topic markup to the active writer-backed document on a single line."""
    with doc.inline(), doc.div:
        for index, topic in enumerate(topics):
            if index:
                doc(", ")
            doc.span(topic)


def render(items: list[Item]) -> str:
    output = StringIO()
    doc = DocWriter(output)
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    doc.write_raw("<!DOCTYPE html>\n")
    for block in page(doc):
        match block:
            case "head":
                doc.title("Articles")
                doc.void_tag("meta", charset="utf-8")
                doc.void_tag(
                    "meta",
                    name="viewport",
                    content="width=device-width, initial-scale=1",
                )
                doc.void_tag("link", rel="stylesheet", href="/static/site.css")
                doc.script("", src="/static/app.js", defer=True)
            case "navigation":
                doc.h2("Browse topics")
                render_topic_list(doc, topic_index)
            case "content":
                for item in items:
                    with doc.li(
                        class_="featured" if item["featured"] else None,
                        data={"category": item["category"]},
                        hidden=item["draft"],
                    ):
                        doc.comment(f"article {item['id']}")
                        doc.void_tag(
                            "img",
                            src=item["thumbnail"],
                            alt=item["title"],
                            width=64,
                            height=64,
                            loading="lazy",
                        )
                        doc.a(
                            item["title"],
                            href=item["url"],
                            target="_blank" if item["external"] else None,
                            rel="noopener" if item["external"] else None,
                        )
                        doc.p(item["summary"])
                        if item["featured"]:
                            doc.strong("Featured")
                        doc.span(item["category"])
                        doc.span(item["rating"], class_="rating")
                        if item["author"]:
                            doc.small.span(f"By {item['author']}")
                        if item["tags"]:
                            render_topic_list(doc, item["tags"])
                        if item["comments"]:
                            doc.span(f"{item['comments']} comments")
    return output.getvalue()
