"""Article-list renderer implemented with the Python Hyperscript library."""

from typing import Any

from hyperscript import h, safe

from ..models import Item


def render_topic_list(topics: list[str]):
    """Create a topic list that can be inserted in multiple places."""
    children = []
    for index, topic in enumerate(topics):
        if index:
            children.append(", ")
        children.append(h("span", topic))
    return h("div", *children)


def render(items: list[Item]) -> str:
    """Render articles using Hyperscript element construction."""
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    navigation = h("nav", h("h2", "Browse topics"), render_topic_list(topic_index))
    entries = []
    for item in items:
        link_attributes: dict[str, Any] = {"href": item["url"]}
        if item["external"]:
            link_attributes["target"] = "_blank"
            link_attributes["rel"] = "noopener"
        item_attributes: dict[str, Any] = {"data-category": item["category"]}
        if item["featured"]:
            item_attributes["class"] = "featured"
        if item["draft"]:
            item_attributes["hidden"] = True
        children = [
            safe(f"<!-- article {item['id']} -->"),
            h(
                "img",
                {
                    "src": item["thumbnail"],
                    "alt": item["title"],
                    "width": 64,
                    "height": 64,
                    "loading": "lazy",
                },
            ),
            h("a", link_attributes, item["title"]),
            h("p", item["summary"]),
        ]
        if item["featured"]:
            children.append(h("strong", "Featured"))
        children.append(h("span", item["category"]))
        children.append(h("span", {"class": "rating"}, str(item["rating"])))
        if item["author"]:
            children.append(h("small", h("span", f"By {item['author']}")))
        if item["tags"]:
            children.append(render_topic_list(item["tags"]))
        if item["comments"]:
            children.append(h("span", f"{item['comments']} comments"))
        entries.append(h("li", item_attributes, *children))
    document = h(
        "html",
        {"lang": "en"},
        h(
            "head",
            h("title", "Articles"),
            h("meta", {"charset": "utf-8"}),
            h(
                "meta",
                {
                    "name": "viewport",
                    "content": "width=device-width, initial-scale=1",
                },
            ),
            h("link", {"rel": "stylesheet", "href": "/static/site.css"}),
            h("script", {"src": "/static/app.js", "defer": True}),
        ),
        h("body", h("main", navigation, h("ul", *entries))),
    )
    return "<!DOCTYPE html>\n" + str(document)
