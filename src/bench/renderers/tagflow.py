"""Article-list renderer using the stream-backed Tagflow package."""

from io import StringIO

from bench.models import Item
from tagflow import DocWriter


def render_topic_list(doc: DocWriter, topics: list[str]) -> None:
    """Append topic markup to the active writer-backed document."""
    with doc.div:
        for index, topic in enumerate(topics):
            if index:
                doc(", ")
            doc.span(topic)


def render(items: list[Item]) -> str:
    output = StringIO()
    doc = DocWriter(output)
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    with doc.main:
        with doc.nav:
            doc.h2("Browse topics")
            render_topic_list(doc, topic_index)
        with doc.ul:
            for item in items:
                with doc.li:
                    doc.a(item["title"], href=item["url"])
                    doc.p(item["summary"])
                    if item["featured"]:
                        doc.strong("Featured")
                    doc.span(item["category"])
                    if item["author"]:
                        doc.small.span(f"By {item['author']}")
                    if item["tags"]:
                        render_topic_list(doc, item["tags"])
                    if item["comments"]:
                        doc.span(f"{item['comments']} comments")
    return output.getvalue()
