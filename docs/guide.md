# User guide

## Writing a document

Everything starts with a {class}`~hyperscribe.DocWriter`,
which wraps any object with a `write(str)` method:
a {class}`io.StringIO`, an open file, or a socket wrapper.

```python
from io import StringIO

from hyperscribe import DocWriter

output = StringIO()
doc, t, v = DocWriter(output).parts
```

The writer keeps tags and void elements apart from its own methods,
in two namespaces:
{attr}`~hyperscribe.DocWriter.tags` and {attr}`~hyperscribe.DocWriter.voids`.
{attr}`~hyperscribe.DocWriter.parts` returns the writer together with both,
so they can be unpacked into short names,
which the examples below call `doc`, `t` and `v`.
A function that receives the writer can unpack only what it needs,
as in `t = doc.tags`.

Accessing an attribute on `t`, such as `t.div`, gives you a tag.
Any name works, including those of the writer's methods,
so `t.text` is SVG's `<text>` element.
For names that are not valid Python identifiers, subscript instead,
as in `t["my-element"]`.
Tags are used in one of two ways.

### Leaf tags

Calling a tag with content writes the complete element on one line.
The content is handled like that of `doc(...)`, described under
[Trusted content](#trusted-content): it is written as it is,
so dynamic strings go through {func}`~hyperscribe.escape` first.

```{testcode}
t.p(escape("Fish & chips"))
```

```{testoutput}
<p>Fish &amp; chips</p>
```

Numbers are converted with {class}`str`,
so `t.td(3)` writes `<td>3</td>`.
`None` is rejected with a {class}`TypeError`:
it almost always means a value is missing,
and passing it on silently would hide that.
Pass an empty string for an empty element,
or use a [void element](#void-elements) for one that cannot have content.

### Container tags

Using a tag as a context manager writes the opening tag,
indents everything inside the block,
and writes the closing tag when the block ends.

```{testcode}
with t.ul:
    t.li("one")
    t.li("two")
```

```{testoutput}
<ul>
  <li>one</li>
  <li>two</li>
</ul>
```

Because the closing tag is written by the context manager,
it is emitted even if you leave the block early with `break` or `return`.

## Attributes

Pass attributes as keyword arguments, both to leaf and to container tags.
Like tag content, string values are written as they are
between double quotes, so dynamic strings go through
{func}`~hyperscribe.escape` first, which also escapes quotes.

```{testcode}
t.a("Home", href="/")
with t.div(id="main"):
    ...
```

```{testoutput}
<a href="/">Home</a>
<div id="main">
</div>
```

### Attribute names

Python keywords such as `class` and `for` cannot be keyword names,
so a trailing underscore is dropped:

```{testcode}
with t.div(class_="card"):
    t.label("Name", for_="name")
```

```{testoutput}
<div class="card">
  <label for="name">Name</label>
</div>
```

Names with a hyphen, such as `data-*` and `aria-*`,
are written as a dictionary under the prefix,
which is flattened into one attribute per entry:

```{testcode}
t.button("Close", data={"id": 7, "action": "close"}, aria={"label": "Close dialog"})
```

```{testoutput}
<button data-id="7" data-action="close" aria-label="Close dialog">Close</button>
```

The entries follow the same rules as other values, described below,
and dictionaries may be nested.
The exception is `aria`, whose attributes take strings, not HTML boolean semantics:
`aria={"hidden": True, "expanded": False}` gives `aria-hidden="true" aria-expanded="false"`.
For any other name, such as `xml:lang`, unpack a dictionary:
`t.p("hi", **{"xml:lang": "en"})`.

Names are written as given,
so only pass names you control.

### Attribute values

| Value | Result |
| --- | --- |
| a literal string, or one from {func}`~hyperscribe.escape` or {func}`~hyperscribe.trust` | written as it is |
| an `int` or `float` | `str(value)` |
| an object with `__html__` | its `__html__()` |
| a template string | like [tag content](#template-strings), with its values escaped |
| `True` | the bare attribute, as in `<script defer>` |
| a dictionary | flattened with the name as a prefix |
| `False` or `None` | the attribute is left out |

This makes optional attributes a matter of passing the value or `None`:

```{testcode}
t.a("Docs", href=escape(url), target="_blank" if external else None)
t.script("", src="app.js", defer=True)
```

As with content, a type checker that supports `LiteralString`, such as pyright,
rejects a plain `str` variable as an attribute value,
and the writer does not escape anything itself:
a string that comes from user input and is not passed through
{func}`~hyperscribe.escape` can break out of the attribute.

```{testoutput}
<a href="/docs">Docs</a>
<script src="app.js" defer></script>
```

## Nested tags

Chaining attributes opens several tags at once,
which avoids deeply nested `with` statements.

```{testcode}
with t.body.main:
    t.h1("Title")
```

```{testoutput}
<body>
  <main>
    <h1>Title</h1>
  </main>
</body>
```

Chained tags work for leaves, too.
`t.small.span("hi", title="t")` produces `<small><span title="t">hi</span></small>`,
with the attributes applied to the innermost tag.

Calling a tag with attributes but no content gives a new tag,
so attributes can also be set partway along a chain:

```{testcode}
with t.div.div(class_="x").div:
    doc("t")
```

```{testoutput}
<div>
  <div class="x">
    <div>
      t
    </div>
  </div>
</div>
```

Subscripting works anywhere in a chain, as in `t.div["my-element"]`.
Tags never change once created, so they can be stored and reused:
`body = t.body` followed by `with body.main:` leaves `body` itself as it was.

## Text

Text is written as it is, so a string that is not a literal
has to be escaped first, whether it is the content of a tag or written with `doc(...)`:

```{testcode}
t.span(escape(user.name))
```

```{testoutput}
<span>Ada &amp; co</span>
```

### Trusted content

Tag content and calling the writer directly write trusted content verbatim,
with the current indentation and line ending.
Its type annotation accepts {class}`typing.LiteralString`,
{data}`~hyperscribe.SafeStr`,
values implementing ``__html__`` (such as MarkupSafe's {class}`~markupsafe.Markup`),
and ``int`` or ``float`` values:

```{testcode}
doc("<!DOCTYPE html>")
with doc.inline(), t.p:
    doc("Some ")  # LiteralString: written verbatim
    t.strong("important")
    doc(" text")  # LiteralString: written verbatim
```

```{testoutput}
<!DOCTYPE html>
<p>Some <strong>important</strong> text</p>
```

These types are trust declarations;
only use them for content that is safe to include as HTML.
A type checker rejects other strings,
such as those built with an f-string from user input.
To write such a string without a tag around it,
pass it through {func}`~hyperscribe.escape` first:

```{testcode}
from hyperscribe import escape

with doc.inline(), t.p:
    doc("Hello, ")
    doc(escape(user.name))
```

```{testoutput}
<p>Hello, Ada &amp; co</p>
```

Optional values, which may be `None`,
go through {func}`~hyperscribe.escape_silent`,
which is like {func}`~hyperscribe.escape` but writes `None` as an empty string
instead of raising a {class}`TypeError`:

```{testcode}
from hyperscribe import escape_silent

with doc.inline(), t.td:
    doc(escape_silent(device.get("label")))
```

```{testoutput}
<td></td>
```

For a dynamic string that is already valid HTML,
such as markup read from a trusted file,
{func}`~hyperscribe.trust` marks it as safe without escaping it:

```{testcode}
from hyperscribe import trust

# For example markup that was read from a trusted file
doc(trust(rendered))
```

```{testoutput}
<b>trusted</b>
```

Both return a {data}`~hyperscribe.SafeStr`.
It only exists for type checkers and is a plain {class}`str` at runtime,
so type checkers can tell trusted strings from the rest,
in attribute values as well as in content.
They are a minimal alternative to [MarkupSafe](https://markupsafe.palletsprojects.com/),
which works the same way with `doc(...)` and in tag content.

### Template strings

On Python 3.14 and newer, tag content and `doc(...)` also accept
template strings (`t"..."`, {pep}`750`),
which mix markup and values without any `escape` calls.
The literal parts are trusted and written as they are,
and the interpolated values are escaped unless they are trusted themselves:

```{testcode}
:skipif: sys.version_info < (3, 14)

with doc.inline(), t.p:
    doc(t"Hello, <b>{user.name}</b>! You have {count} messages.")
```

```{testoutput}
:skipif: sys.version_info < (3, 14)

<p>Hello, <b>Ada &amp; co</b>! You have 3 messages.</p>
```

| Interpolated value | Written as |
| --- | --- |
| a string | escaped |
| an `int` or `float` | `str(value)` |
| an object with `__html__` (such as MarkupSafe's {class}`~markupsafe.Markup`) | its `__html__()` |
| anything else, such as a {class}`~pathlib.Path` | `str(value)`, escaped |
| `None` | a {class}`TypeError` |

A conversion or format specifier, as in `{n:.2f}` or `{name!r}`,
is applied first and its result is escaped like a string.
Values such as dates have their own format specifiers:

```{testcode}
:skipif: sys.version_info < (3, 14)

import datetime

doc(t"{datetime.date(2026, 10, 2):%d.%m.%Y}")
```

```{testoutput}
:skipif: sys.version_info < (3, 14)

02.10.2026
```

Template strings are also accepted as attribute values:
in `t.a("x", href=t"/users/{user.id}?q={query}")`,
the literal parts are trusted and the interpolated values are escaped as above.

{func}`~hyperscribe.SafeStr` only exists for type checkers
and is a plain {class}`str` at run time,
so a string from {func}`~hyperscribe.escape` or {func}`~hyperscribe.trust`
is escaped again when it is interpolated:

```{testcode}
:skipif: sys.version_info < (3, 14)

doc(t"<p>{trust(rendered)}</p>")
```

```{testoutput}
:skipif: sys.version_info < (3, 14)

<p>&lt;b&gt;trusted&lt;/b&gt;</p>
```

To put markup that is safe already into a template string,
interpolate an object with `__html__`, such as MarkupSafe's {class}`~markupsafe.Markup`:

```{testcode}
:skipif: sys.version_info < (3, 14)

from markupsafe import Markup

doc(t"<p>{Markup(rendered)}</p>")
```

```{testoutput}
:skipif: sys.version_info < (3, 14)

<p><b>trusted</b></p>
```

Escaping is for HTML text and attribute values only:
template strings do not make it safe to interpolate into a `<script>` or `<style>` element,
an event handler attribute or a URL scheme.

```{note}
{meth}`~hyperscribe.DocWriter.text` and {meth}`~hyperscribe.DocWriter.write_raw`
are deprecated.
Use `doc(...)` for trusted content, including a doctype,
and `doc(escape(value))` for anything else.
```

### Inline formatting

By default every tag gets its own line.
That is what you want for structure, but it inserts whitespace into running text.
Wrap content in {meth}`~hyperscribe.DocWriter.inline` to keep it on one line:

```{testcode}
with doc.inline(), t.li:
    doc("hi, ")
    t.b("there")
```

```{testoutput}
<li>hi, <b>there</b></li>
```

The block is indented and ends its line like any other tag.
Inline blocks may be nested;
normal formatting resumes once the outermost one exits.

## Escaping

{func}`~hyperscribe.escape` escapes `&`, `<`, `>` and both kinds of quotes,
so its result is safe in text and in double-quoted attribute values.
The writer does not escape anything itself,
so every dynamic string, in tag content and in attribute values alike,
has to go through it.
Nothing else is escaped,
so do not use hyperscribe to write into `<script>` or `<style>` elements
with untrusted data.

## Void elements

Void elements such as `<br>`, `<img>`, `<meta>` and `<input>` have no content and no closing tag.
hyperscribe does not know which elements are void,
so they have their own namespace, {attr}`~hyperscribe.DocWriter.voids`.
Calling one writes it, indented like any other tag and with the same attributes;
it takes no content and cannot be used as a context manager:

```{testcode}
v.meta(charset="utf-8")
v.img(src="logo.png", alt="Logo")
```

```{testoutput}
<meta charset="utf-8">
<img src="logo.png" alt="Logo">
```

Inside {meth}`~hyperscribe.DocWriter.inline` blocks it stays on the line,
so `v.br()` between two pieces of text gives `a<br>b`.

## Comments

{meth}`~hyperscribe.DocWriter.comment` writes an HTML comment on its own line.

```{testcode}
doc.comment("navigation")
```

```{testoutput}
<!-- navigation -->
```

Text containing `--` raises a {class}`ValueError`,
because it could end the comment early.

## Loops, conditions and filters

Templates are plain Python,
so what other engines provide as special syntax is ordinary code.
These are the idioms that come up most often.

Filtering the items of a loop is a comprehension or an early `continue`.
Jinja's `{% for x in xs if cond %}` becomes:

```{testcode}
for item in items:
    if not item.visible:
        continue
    t.li(escape(item.name))
```

```{testoutput}
<li>One</li>
<li>Two</li>
```

The `loop` variable is `enumerate`.
`loop.first`, `loop.index0` and `loop.length` become:

```{testcode}
visible = [item for item in items if item.visible]
for index, item in enumerate(visible):
    t.li(escape(("+ " if index else "") + item.name))
t.p(f"{len(visible)} items")
```

```{testoutput}
<li>One</li>
<li>+ Two</li>
<p>2 items</p>
```

When something must be known before the loop starts,
such as a `rowspan` that counts the rows of a group,
build the list first and then write it,
as above.

Optional attributes take `None`, so no branching is needed:

```{testcode}
item = items[0]
t.li(escape(item.name), class_="done" if item.done else None)
```

```{testoutput}
<li class="done">One</li>
```

Text next to markup needs {meth}`~hyperscribe.DocWriter.inline`,
which is described above,
so that no whitespace appears between them.

Whitespace-sensitive elements such as `<pre>` and `<textarea>`
already stay on one line when given their content directly, as in `t.pre(escape(code))`.
When they contain further markup, they need an inline block,
or the indentation becomes part of their content:

```{testcode}
with doc.inline(), t.pre:
    doc(escape(code))
```

```{testoutput}
<pre>a &lt; b</pre>
```

## Layouts and components

Since templates are Python, components are functions
and layouts can be generators or `@contextmanager` functions.
The layout below yields once per replaceable section:

```{testcode}
from collections.abc import Iterator
from typing import Literal

from hyperscribe import DocWriter, escape


def topic_list(doc: DocWriter, topics: list[str]) -> None:
    t = doc.tags
    with doc.inline(), t.div:
        for index, topic in enumerate(topics):
            if index:
                doc(", ")
            t.span(escape(topic))


def page(doc: DocWriter) -> Iterator[Literal["head", "content"]]:
    t = doc.tags
    with t.html(lang="en"):
        with t.head:
            yield "head"
        with t.body:
            yield "content"


doc("<!DOCTYPE html>")
for section in page(doc):
    match section:
        case "head":
            t.title("Topics")
        case "content":
            topic_list(doc, ["python", "html"])
```

```{testoutput}
<!DOCTYPE html>
<html lang="en">
  <head>
    <title>Topics</title>
  </head>
  <body>
    <div><span>python</span>, <span>html</span></div>
  </body>
</html>
```

The `benchmarks/renderers/hyperscribe.py` module in the repository
shows a larger example.

## Streaming

Because output goes straight to the object you provide,
nothing is buffered by hyperscribe itself.
Pass a file or a socket wrapper to send the document as it is generated,
or a `StringIO` to get the result as a string.
