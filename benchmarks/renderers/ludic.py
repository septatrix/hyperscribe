"""Article-list renderer implemented with Ludic."""

import html

from ludic.html import (
    a,
    body,
    div,
    h2,
    head,
    img,
    li,
    link,
    main,
    meta,
    nav,
    p,
    script,
    small,
    span,
    strong,
    title,
    ul,
)
from ludic.html import (
    html as html_element,
)

from ..models import Item


def render_topic_list(topics: list[str]):
    """Create a topic-list element that can be inserted in multiple places."""
    topic_children: list[str | span] = []
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
        link_attributes = {"href": item["url"]}
        if item["external"]:
            link_attributes["target"] = "_blank"
            link_attributes["rel"] = "noopener"
        children = [
            f"<!-- article {item['id']} -->",
            img(
                src=item["thumbnail"],
                alt=html.escape(item["title"], quote=False),
                width=64,
                height=64,
                loading="lazy",
            ),
            a(html.escape(item["title"], quote=False), **link_attributes),
            p(html.escape(item["summary"], quote=False)),
        ]
        if item["featured"]:
            children.append(strong("Featured"))
        children.append(span(item["category"]))
        children.append(span(str(item["rating"]), class_="rating"))
        if item["author"]:
            children.append(
                small(span(f"By {html.escape(item['author'], quote=False)}"))
            )
        if item["tags"]:
            children.append(render_topic_list(item["tags"]))
        if item["comments"]:
            children.append(span(f"{item['comments']} comments"))
        item_attributes = {"data-category": item["category"]}
        if item["featured"]:
            item_attributes["class_"] = "featured"
        if item["draft"]:
            item_attributes["hidden"] = True
        entries.append(li(*children, **item_attributes))
    document = html_element(
        head(
            title("Articles"),
            meta(charset="utf-8"),
            meta(name="viewport", content="width=device-width, initial-scale=1"),
            link(rel="stylesheet", href="/static/site.css"),
            script("", src="/static/app.js", defer=True),
        ),
        body(main(topic_nav, ul(*entries))),
        lang="en",
    )
    return "<!DOCTYPE html>\n" + document.to_string(pretty=True)
