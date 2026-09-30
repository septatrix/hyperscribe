"""Article-list renderer implemented with dominate."""

from dominate import tags
from dominate.util import text as dominate_text

from ..models import Item


def render_topic_list(topics: list[str]):
    """Build a reusable topic list element for insertion into a document."""
    result = tags.div()
    with result:
        for index, topic in enumerate(topics):
            if index:
                dominate_text(", ")
            tags.span(topic)
    return result


def render(items: list[Item]) -> str:
    topic_index = sorted({topic for item in items for topic in item["tags"]})
    root = tags.html(lang="en")
    with root:
        with tags.head():
            tags.title("Articles")
        with tags.body():
            with tags.main():
                with tags.nav():
                    tags.h2("Browse topics")
                    render_topic_list(topic_index)
                with tags.ul():
                    for item in items:
                        with tags.li():
                            tags.a(item["title"], href=item["url"])
                            tags.p(item["summary"])
                            if item["featured"]:
                                tags.strong("Featured")
                            tags.span(item["category"])
                            if item["author"]:
                                with tags.small():
                                    tags.span(f"By {item['author']}")
                            if item["tags"]:
                                render_topic_list(item["tags"])
                            if item["comments"]:
                                tags.span(f"{item['comments']} comments")
    return "<!DOCTYPE html>\n" + root.render(pretty=True)
