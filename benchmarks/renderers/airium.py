"""Article-list renderer implemented with Airium."""

import html

from airium import Airium

from ..models import Item


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
            doc.meta(charset="utf-8")
            doc.meta(name="viewport", content="width=device-width, initial-scale=1")
            doc.link(rel="stylesheet", href="/static/site.css")
            with doc.script(src="/static/app.js", defer=True):
                pass
        with doc.body():
            with doc.main():
                with doc.nav():
                    with doc.h2():
                        doc("Browse topics")
                    render_topic_list(doc, topic_index)
                with doc.ul():
                    for item in items:
                        item_attributes = {"data-category": item["category"]}
                        if item["featured"]:
                            item_attributes["class"] = "featured"
                        if item["draft"]:
                            item_attributes["hidden"] = True
                        link_attributes = {"href": item["url"]}
                        if item["external"]:
                            link_attributes["target"] = "_blank"
                            link_attributes["rel"] = "noopener"
                        with doc.li(**item_attributes):
                            doc(f"<!-- article {item['id']} -->")
                            doc.img(
                                src=item["thumbnail"],
                                alt=html.escape(item["title"], quote=False),
                                width=64,
                                height=64,
                                loading="lazy",
                            )
                            with doc.a(**link_attributes):
                                doc(html.escape(item["title"], quote=False))
                            with doc.p():
                                doc(html.escape(item["summary"], quote=False))
                            if item["featured"]:
                                with doc.strong():
                                    doc("Featured")
                            with doc.span():
                                doc(item["category"])
                            with doc.span(klass="rating"):
                                doc(item["rating"])
                            if item["author"]:
                                with doc.small(), doc.span():
                                    doc(
                                        f"By {html.escape(item['author'], quote=False)}"
                                    )
                            if item["tags"]:
                                render_topic_list(doc, item["tags"])
                            if item["comments"]:
                                with doc.span():
                                    doc(f"{item['comments']} comments")
    return str(doc)
