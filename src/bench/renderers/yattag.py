"""Article-list renderer implemented with Yattag."""

from yattag import FIRST_LINE, SimpleDoc, indent

from bench.models import Item


def render_topic_list(tag, text, topics: list[str]) -> None:
    """Render topic markup with the active Yattag tag/text functions."""
    with tag("div"):
        for index, topic in enumerate(topics):
            if index:
                text(", ")
            with tag("span"):
                text(topic)


def render(items: list[Item]) -> str:
    simpledoc, tag, text = SimpleDoc().tagtext()
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    with tag("main"):
        with tag("nav"):
            with tag("h2"):
                text("Browse topics")
            render_topic_list(tag, text, topic_index)
        with tag("ul"):
            for item in items:
                with tag("li"):
                    with tag("a", href=item["url"]):
                        text(item["title"])
                    with tag("p"):
                        text(item["summary"])
                    if item["featured"]:
                        with tag("strong"):
                            text("Featured")
                    with tag("span"):
                        text(item["category"])
                    if item["author"]:
                        with tag("small"), tag("span"):
                            text(f"By {item['author']}")
                    if item["tags"]:
                        render_topic_list(tag, text, item["tags"])
                    if item["comments"]:
                        with tag("span"):
                            text(f"{item['comments']} comments")
    return indent(simpledoc.getvalue(), indent_text=FIRST_LINE)
