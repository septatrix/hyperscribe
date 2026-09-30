"""Article-list renderer implemented with Airium."""

import html

from airium import Airium

from benchmarks.models import Item


def render_topic_list(doc: Airium, topics: list[str]) -> None:
    """Append a reusable topic list to the active Airium document."""
    with doc.div():
        for index, topic in enumerate(topics):
            with doc.span():
                doc(topic)
            if index < len(topics) - 1:
                doc(", ")


def render(items: list[Item]) -> str:
    doc = Airium()
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    doc("<!DOCTYPE html>\n")
    with doc.html(lang="en"):
        with doc.head():
            with doc.title():
                doc("Articles")
        with doc.body():
            with doc.main():
                with doc.nav():
                    with doc.h2():
                        doc("Browse topics")
                    render_topic_list(doc, topic_index)
                with doc.ul():
                    for item in items:
                        with doc.li():
                            with doc.a(href=item["url"]):
                                doc(html.escape(item["title"], quote=False))
                            with doc.p():
                                doc(html.escape(item["summary"], quote=False))
                            if item["featured"]:
                                with doc.strong():
                                    doc("Featured")
                            with doc.span():
                                doc(item["category"])
                            if item["author"]:
                                with doc.small(), doc.span():
                                    doc(f"By {html.escape(item['author'], quote=False)}")
                            if item["tags"]:
                                render_topic_list(doc, item["tags"])
                            if item["comments"]:
                                with doc.span():
                                    doc(f"{item['comments']} comments")
    return str(doc)
