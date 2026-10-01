"""Article-list renderer implemented with xml.etree.ElementTree."""

from xml.etree import ElementTree

from ..models import Item


def render_topic_list(parent: ElementTree.Element, topics: list[str]) -> None:
    """Append a topic-list element to its active ElementTree parent."""
    topic_list = ElementTree.SubElement(parent, "div")
    for index, topic in enumerate(topics):
        if index:
            topic_list[-1].tail = ", "
        ElementTree.SubElement(topic_list, "span").text = topic


def render(items: list[Item]) -> str:
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    root = ElementTree.Element("html", lang="en")
    head = ElementTree.SubElement(root, "head")
    ElementTree.SubElement(head, "title").text = "Articles"
    ElementTree.SubElement(head, "meta", charset="utf-8")
    ElementTree.SubElement(
        head, "meta", name="viewport", content="width=device-width, initial-scale=1"
    )
    ElementTree.SubElement(head, "link", rel="stylesheet", href="/static/site.css")
    ElementTree.SubElement(head, "script", src="/static/app.js", defer="").text = ""
    body = ElementTree.SubElement(root, "body")
    main = ElementTree.SubElement(body, "main")
    navigation = ElementTree.SubElement(main, "nav")
    ElementTree.SubElement(navigation, "h2").text = "Browse topics"
    render_topic_list(navigation, topic_index)
    listing = ElementTree.SubElement(main, "ul")
    if not items:
        listing.text = "\n"
    for item in items:
        item_attributes = {"data-category": item["category"]}
        if item["featured"]:
            item_attributes["class"] = "featured"
        if item["draft"]:
            item_attributes["hidden"] = ""
        entry = ElementTree.SubElement(listing, "li", item_attributes)
        entry.append(ElementTree.Comment(f" article {item['id']} "))
        ElementTree.SubElement(
            entry,
            "img",
            src=item["thumbnail"],
            alt=item["title"],
            width="64",
            height="64",
            loading="lazy",
        )
        link = ElementTree.SubElement(entry, "a", href=item["url"])
        if item["external"]:
            link.set("target", "_blank")
            link.set("rel", "noopener")
        link.text = item["title"]
        ElementTree.SubElement(entry, "p").text = item["summary"]
        if item["featured"]:
            ElementTree.SubElement(entry, "strong").text = "Featured"
        ElementTree.SubElement(entry, "span").text = item["category"]
        ElementTree.SubElement(entry, "span", {"class": "rating"}).text = str(
            item["rating"]
        )
        if item["author"]:
            ElementTree.SubElement(
                ElementTree.SubElement(entry, "small"), "span"
            ).text = f"By {item['author']}"
        if item["tags"]:
            render_topic_list(entry, item["tags"])
        if item["comments"]:
            ElementTree.SubElement(entry, "span").text = f"{item['comments']} comments"
    ElementTree.indent(root, space="  ")
    return "<!DOCTYPE html>\n" + ElementTree.tostring(
        root, encoding="unicode", method="html"
    )
