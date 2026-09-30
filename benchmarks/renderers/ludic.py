"""Article-list renderer implemented with Ludic."""

import html

from ludic.html import (
    a,
    body,
    div,
    h2,
    head,
    html as html_element,
    li,
    main,
    nav,
    p,
    small,
    span,
    strong,
    title,
    ul,
)

from benchmarks.models import Item


def render_topic_list(topics: list[str]):
    """Create a topic-list element that can be inserted in multiple places."""
    topic_children = []
    for index, topic in enumerate(topics):
        if index:
            topic_children.append(", ")
        topic_children.append(span(topic))
    return div(*topic_children)


def render(items: list[Item]) -> str:
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    topic_nav = nav(h2("Browse topics"), render_topic_list(topic_index))
    entries = []
    for item in items:
        children = [
            a(html.escape(item["title"], quote=False), href=item["url"]),
            p(html.escape(item["summary"], quote=False)),
        ]
        if item["featured"]:
            children.append(strong("Featured"))
        children.append(span(item["category"]))
        if item["author"]:
            children.append(
                small(span(f"By {html.escape(item['author'], quote=False)}"))
            )
        if item["tags"]:
            children.append(render_topic_list(item["tags"]))
        if item["comments"]:
            children.append(span(f"{item['comments']} comments"))
        entries.append(li(*children))
    document = html_element(
        head(title("Articles")),
        body(main(topic_nav, ul(*entries))),
        lang="en",
    )
    return "<!DOCTYPE html>\n" + document.to_string(pretty=True)
