"""A dashboard page with deeper nesting, chained tags, forms, tables and components.

Unlike the article list, it is only rendered with Hyperscribe.
It exercises attribute-heavy markup, the components built from context managers,
void elements, inline blocks and the ``aria`` and ``data`` attribute groups.
"""

from __future__ import annotations

import random
from contextlib import contextmanager
from io import StringIO
from typing import Any

from hyperscribe import DocWriter, escape, trust


def make_data(
    n_products: int = 60, n_orders: int = 200, n_options: int = 120, seed: int = 1
) -> dict[str, Any]:
    r = random.Random(seed)
    words = (
        "alpha beta <gamma> delta & epsilon zeta eta theta iota kappa lambda mu".split()
    )

    def sentence(n):
        return " ".join(r.choice(words) for _ in range(n))

    return {
        "user": {"name": "Ada <Admin>", "avatar": "/img/ada.png", "unread": 3},
        "menu": [
            (
                f"Item {i}",
                f"/m/{i}",
                i == 2,
                [(f"Sub {j}", f"/m/{i}/{j}") for j in range(r.randint(0, 4))],
            )
            for i in range(8)
        ],
        "crumbs": [("Home", "/"), ("Shop", "/shop"), ("Gadgets & Gizmos", None)],
        "filters": [
            (f"f{i}", sentence(2), r.random() < 0.3, r.random() < 0.1)
            for i in range(12)
        ],
        "options": [(i, sentence(2)) for i in range(n_options)],
        "products": [
            {
                "id": i,
                "name": sentence(3),
                "url": f"/p/{i}?a=1&b=2",
                "img": f"/img/{i}.jpg",
                "price": round(r.random() * 100, 2),
                "rating": r.randint(0, 5),
                "reviews": r.randint(0, 900),
                "badges": [sentence(1) for _ in range(r.randint(0, 3))],
                "stock": r.choice([0, 3, 50]),
                "desc": sentence(r.randint(8, 25)),
                "sale": r.random() < 0.25,
            }
            for i in range(n_products)
        ],
        "orders": [
            {
                "id": 1000 + i,
                "customer": sentence(2),
                "email": f"u{i}@example.com",
                "status": r.choice(["paid", "pending", "failed"]),
                "total": round(r.random() * 500, 2),
                "items": r.randint(1, 9),
                "date": f"2026-0{r.randint(1, 9)}-1{r.randint(0, 9)}",
            }
            for i in range(n_orders)
        ],
        "footer": [
            (f"Col {c}", [(sentence(1), f"/f/{c}/{j}") for j in range(5)])
            for c in range(4)
        ],
        "pages": 12,
        "page": 5,
    }


def render(data: dict[str, Any]) -> str:
    out = StringIO()
    doc, t, v = DocWriter(out).parts

    @contextmanager
    def card(cls, **attrs):
        with t.article(class_=escape(f"card {cls}"), **attrs):
            with t.div(class_="card-body"):
                yield

    def badge(text, kind="info"):
        t.span(escape(text), class_=escape(f"badge badge-{kind}"))

    def stars(n):
        with doc.inline(), t.div(class_="stars", aria={"label": escape(f"{n} of 5")}):
            for i in range(5):
                t.i(class_="star filled" if i < n else "star")

    def menu_item(label, href, active, subs):
        with t.li(class_="active" if active else None, aria={"haspopup": bool(subs)}):
            t.a(
                escape(label),
                href=escape(href),
                aria={"current": "page" if active else None},
            )
            if subs:
                with t.ul(class_="submenu"):
                    for sl, sh in subs:
                        t.li.a(escape(sl), href=escape(sh))

    doc("<!DOCTYPE html>")
    with t.html(lang="en", data={"theme": "dark"}):
        with t.head:
            v.meta(charset="utf-8")
            v.meta(name="viewport", content="width=device-width, initial-scale=1")
            t.title("Shop dashboard")
            v.link(rel="stylesheet", href="/static/site.css")
            v.link(rel="icon", href="/favicon.ico", type="image/x-icon")
            t.script("", src="/static/app.js", defer=True)
        with t.body(class_="dashboard"):
            with t.header(class_="top"):
                with t.div(class_="container"):
                    t.a(href="/", class_="logo").strong(escape("Shop"))
                    with t.nav(class_="main", aria={"label": "Main"}):
                        with t.ul(class_="menu"):
                            for m in data["menu"]:
                                menu_item(*m)
                    with t.div(class_="user"):
                        v.img(
                            src=escape(data["user"]["avatar"]),
                            alt="",
                            width=32,
                            height=32,
                        )
                        t.span(escape(data["user"]["name"]))
                        if data["user"]["unread"]:
                            badge(str(data["user"]["unread"]), "alert")
            with t.main(class_="container"):
                with t.nav(aria={"label": "Breadcrumb"}), t.ol(class_="crumbs"):
                    for label, href in data["crumbs"]:
                        with t.li:
                            if href:
                                t.a(escape(label), href=escape(href))
                            else:
                                t.span(escape(label), aria={"current": "page"})
                with t.div(class_="layout"):
                    with (
                        t.aside(class_="filters"),
                        t.form(action="/search", method="get"),
                    ):
                        with t.fieldset:
                            t.legend("Filters")
                            for fid, label, checked, disabled in data["filters"]:
                                with t.div(class_="field"):
                                    v.input(
                                        type="checkbox",
                                        id=escape(fid),
                                        name=escape(fid),
                                        value="1",
                                        checked=checked,
                                        disabled=disabled,
                                    )
                                    t.label(escape(label), for_=escape(fid))
                        with t.div(class_="field"):
                            t.label("Category", for_="cat")
                            with t.select(id="cat", name="cat", required=True):
                                for val, label in data["options"]:
                                    t.option(escape(label), value=val)
                            t.textarea("", name="note", rows=3, placeholder="Notes")
                        t.button(
                            "Apply",
                            type="submit",
                            class_="btn btn-primary",
                            data={"action": "filter"},
                        )
                    with t.section(class_="products"):
                        t.h2("Products")
                        with t.div(class_="grid"):
                            for p in data["products"]:
                                with card(
                                    "product", data={"id": p["id"], "sale": p["sale"]}
                                ):
                                    with t.div.figure(class_="media"):
                                        with t.picture:
                                            v.source(
                                                srcset=escape(p["img"] + " 2x"),
                                                media="(min-width: 800px)",
                                            )
                                            v.img(
                                                src=escape(p["img"]),
                                                alt=escape(p["name"]),
                                                width=240,
                                                height=180,
                                                loading="lazy",
                                            )
                                        t.figcaption(escape(p["name"]))
                                    with t.div.div(class_="info"):
                                        t.h3.a(escape(p["name"]), href=escape(p["url"]))
                                        for b in p["badges"]:
                                            badge(b)
                                        if p["sale"]:
                                            badge("Sale", "sale")
                                        stars(p["rating"])
                                        t.small(f"{p['reviews']} reviews")
                                        t.p(escape(p["desc"]))
                                        with t.div(class_="buy"):
                                            t.span(f"${p['price']:.2f}", class_="price")
                                            t.button(
                                                "Add to cart",
                                                type="button",
                                                class_="btn",
                                                disabled=not p["stock"],
                                                data={
                                                    "id": p["id"],
                                                    "price": p["price"],
                                                },
                                                aria={
                                                    "label": escape(f"Add {p['name']}")
                                                },
                                            )
                        with t.table(class_="orders"):
                            t.caption("Recent orders")
                            with t.thead, t.tr:
                                for h in (
                                    "ID",
                                    "Customer",
                                    "Email",
                                    "Status",
                                    "Items",
                                    "Total",
                                    "Date",
                                ):
                                    t.th(h, scope="col")
                            with t.tbody:
                                for o in data["orders"]:
                                    with t.tr(
                                        class_=escape(o["status"]), data={"id": o["id"]}
                                    ):
                                        t.td.a(o["id"], href=escape(f"/o/{o['id']}"))
                                        t.td(escape(o["customer"]))
                                        t.td.a(
                                            escape(o["email"]),
                                            href=escape(f"mailto:{o['email']}"),
                                        )
                                        t.td.span(
                                            escape(o["status"]),
                                            class_=escape(f"status {o['status']}"),
                                        )
                                        t.td(o["items"], class_="num")
                                        t.td(f"${o['total']:.2f}", class_="num")
                                        t.td(o["date"])
                        with (
                            t.nav(aria={"label": "Pagination"}),
                            t.ul(class_="pagination"),
                        ):
                            for pg in range(1, data["pages"] + 1):
                                with t.li(
                                    class_="current" if pg == data["page"] else None
                                ):
                                    t.a(
                                        pg,
                                        href=escape(f"?page={pg}"),
                                        aria={
                                            "current": "page"
                                            if pg == data["page"]
                                            else None
                                        },
                                    )
            with t.footer(class_="site"):
                with t.div(class_="container cols"):
                    for title, links in data["footer"]:
                        with t.section:
                            t.h4(escape(title))
                            with t.ul:
                                for label, href in links:
                                    t.li.a(escape(label), href=href)
                doc.comment("generated")
                t.p(trust("&copy; 2026 Shop"))
    return out.getvalue()
