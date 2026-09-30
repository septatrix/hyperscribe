"""Article-list renderer implemented with the Python Hyperscript library."""

from hyperscript import h

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
        children = [
            h("a", {"href": item["url"]}, item["title"]),
            h("p", item["summary"]),
        ]
        if item["featured"]:
            children.append(h("strong", "Featured"))
        children.append(h("span", item["category"]))
        if item["author"]:
            children.append(h("small", h("span", f"By {item['author']}")))
        if item["tags"]:
            children.append(render_topic_list(item["tags"]))
        if item["comments"]:
            children.append(h("span", f"{item['comments']} comments"))
        entries.append(h("li", *children))
    document = h(
        "html",
        {"lang": "en"},
        h("head", h("title", "Articles")),
        h("body", h("main", navigation, h("ul", *entries))),
    )
    return "<!DOCTYPE html>\n" + str(document)
