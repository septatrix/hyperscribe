"""Article-list renderer implemented with Yattag."""

from yattag import FIRST_LINE, SimpleDoc, indent

from ..models import Item


def render_topic_list(tag, text, topics: list[str]) -> None:
    """Render topic markup with the active Yattag tag/text functions."""
    with tag("div"):
        for index, topic in enumerate(topics):
            if index:
                text(", ")
            with tag("span"):
                text(topic)


def render(items: list[Item]) -> str:
    doc = SimpleDoc()
    tag, text = doc.tag, doc.text
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    with tag("html", lang="en"):
        with tag("head"):
            with tag("title"):
                text("Articles")
            doc.stag("meta", charset="utf-8")
            doc.stag(
                "meta", name="viewport", content="width=device-width, initial-scale=1"
            )
            doc.stag("link", rel="stylesheet", href="/static/site.css")
            with tag("script", src="/static/app.js", defer=""):
                pass
        with tag("body"):
            with tag("main"):
                with tag("nav"):
                    with tag("h2"):
                        text("Browse topics")
                    render_topic_list(tag, text, topic_index)
                with tag("ul"):
                    for item in items:
                        item_attributes = [("data-category", item["category"])]
                        if item["featured"]:
                            item_attributes.append(("class", "featured"))
                        if item["draft"]:
                            item_attributes.append(("hidden", ""))
                        link_attributes = [("href", item["url"])]
                        if item["external"]:
                            link_attributes += [
                                ("target", "_blank"),
                                ("rel", "noopener"),
                            ]
                        with tag("li", *item_attributes):
                            doc.asis(f"<!-- article {item['id']} -->")
                            doc.stag(
                                "img",
                                src=item["thumbnail"],
                                alt=item["title"],
                                width=64,
                                height=64,
                                loading="lazy",
                            )
                            with tag("a", *link_attributes):
                                text(item["title"])
                            with tag("p"):
                                text(item["summary"])
                            if item["featured"]:
                                with tag("strong"):
                                    text("Featured")
                            with tag("span"):
                                text(item["category"])
                            with tag("span", klass="rating"):
                                text(str(item["rating"]))
                            if item["author"]:
                                with tag("small"), tag("span"):
                                    text(f"By {item['author']}")
                            if item["tags"]:
                                render_topic_list(tag, text, item["tags"])
                            if item["comments"]:
                                with tag("span"):
                                    text(f"{item['comments']} comments")
    return "<!DOCTYPE html>\n" + indent(doc.getvalue(), indent_text=FIRST_LINE)
