"""Article-list renderer using the stream-backed Hyperscribe package."""

from collections.abc import Iterator
from io import StringIO
from typing import Literal

from hyperscribe import DocWriter

from ..models import Item


def page(doc: DocWriter) -> Iterator[Literal["head", "navigation", "content"]]:
    """Provide the document shell and yield its replaceable content sections."""
    t = doc.tags
    with t.html(lang="en"):
        with t.head:
            yield "head"
        with t.body.main:
            with t.nav:
                yield "navigation"
            with t.ul:
                yield "content"


def render_topic_list(doc: DocWriter, topics: list[str]) -> None:
    """Append topic markup to the active writer-backed document on a single line."""
    t = doc.tags
    with doc.inline(), t.div:
        for index, topic in enumerate(topics):
            if index:
                doc(", ")
            t.span(topic)


def render(items: list[Item]) -> str:
    output = StringIO()
    doc, t, v = DocWriter(output).parts
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    doc("<!DOCTYPE html>\n")
    for block in page(doc):
        match block:
            case "head":
                t.title("Articles")
                v.meta(charset="utf-8")
                v.meta(
                    name="viewport",
                    content="width=device-width, initial-scale=1",
                )
                v.link(rel="stylesheet", href="/static/site.css")
                t.script("", src="/static/app.js", defer=True)
            case "navigation":
                t.h2("Browse topics")
                render_topic_list(doc, topic_index)
            case "content":
                for item in items:
                    with t.li(
                        class_="featured" if item["featured"] else None,
                        data={"category": item["category"]},
                        hidden=item["draft"],
                    ):
                        doc.comment(f"article {item['id']}")
                        v.img(
                            src=item["thumbnail"],
                            alt=item["title"],
                            width=64,
                            height=64,
                            loading="lazy",
                        )
                        t.a(
                            item["title"],
                            href=item["url"],
                            target="_blank" if item["external"] else None,
                            rel="noopener" if item["external"] else None,
                        )
                        t.p(item["summary"])
                        if item["featured"]:
                            t.strong("Featured")
                        t.span(item["category"])
                        t.span(item["rating"], class_="rating")
                        if item["author"]:
                            t.small.span(f"By {item['author']}")
                        if item["tags"]:
                            render_topic_list(doc, item["tags"])
                        if item["comments"]:
                            t.span(f"{item['comments']} comments")
    return output.getvalue()
