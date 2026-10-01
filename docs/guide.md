# User guide

## Writing a document

Everything starts with a {class}`~hyperscribe.DocWriter`,
which wraps any object with a `write(str)` method:
a {class}`io.StringIO`, an open file, or a socket wrapper.

```python
from io import StringIO

from hyperscribe import DocWriter

output = StringIO()
doc = DocWriter(output)
```

Accessing an attribute on the writer, such as `doc.div`, gives you a tag.
Tags are used in one of two ways.

### Leaf tags

Calling a tag with a string writes the complete element on one line.
The content is escaped.

```python
doc.p("Fish & chips")
# <p>Fish &amp; chips</p>
```

Content that is not a string is converted with {class}`str`,
so `doc.td(3)` writes `<td>3</td>`.
`None` is rejected with a {class}`TypeError`:
it almost always means a value is missing,
and passing it on silently would hide that.
Pass an empty string for an empty element,
or use {meth}`~hyperscribe.DocWriter.void_tag` for one that cannot have content.

### Container tags

Using a tag as a context manager writes the opening tag,
indents everything inside the block,
and writes the closing tag when the block ends.

```python
with doc.ul:
    doc.li("one")
    doc.li("two")
# <ul>
#   <li>one</li>
#   <li>two</li>
# </ul>
```

Because the closing tag is written by the context manager,
it is emitted even if you leave the block early with `break` or `return`.

## Attributes

Pass attributes as keyword arguments, both to leaf and to container tags.
Values are escaped for use inside double quotes.

```python
doc.a("Home", href="/")
with doc.div(id="main"):
    ...
```

### Attribute names

Python keywords such as `class` and `for` cannot be keyword names,
so a trailing underscore is dropped:

```python
with doc.div(class_="card"):
    doc.label("Name", for_="name")
# <div class="card">
#   <label for="name">Name</label>
# </div>
```

Names with a hyphen, such as `data-*` and `aria-*`,
are written as a dictionary under the prefix,
which is flattened into one attribute per entry:

```python
doc.button("Close", data={"id": 7, "action": "close"}, aria={"label": "Close dialog"})
# <button data-id="7" data-action="close" aria-label="Close dialog">Close</button>
```

The entries follow the same rules as other values, described below,
and dictionaries may be nested.
For any other name, such as `xml:lang`, unpack a dictionary:
`doc.p("hi", **{"xml:lang": "en"})`.

Names are written as given,
so only pass names you control.

### Attribute values

| Value | Result |
| --- | --- |
| a string | written, escaped |
| a number | converted with {class}`str` and written |
| `True` | the bare attribute, as in `<script defer>` |
| a dictionary | flattened with the name as a prefix |
| `False` or `None` | the attribute is left out |

This makes optional attributes a matter of passing the value or `None`:

```python
doc.a("Docs", href=url, target="_blank" if external else None)
doc.script("", src="app.js", defer=True)
# <a href="/docs">Docs</a>  or  <a href="/docs" target="_blank">Docs</a>
# <script src="app.js" defer></script>
```

## Nested tags

Chaining attributes opens several tags at once,
which avoids deeply nested `with` statements.

```python
with doc.body.main:
    doc.h1("Title")
# <body>
#   <main>
#     <h1>Title</h1>
#   </main>
# </body>
```

Chained tags work for leaves, too.
`doc.small.span("hi", title="t")` produces `<small><span title="t">hi</span></small>`,
with the attributes applied to the innermost tag.

## Text

Use {meth}`~hyperscribe.DocWriter.text`, or call the writer directly,
to write escaped text on its own line.

```python
with doc.p:
    doc("Some ")
    doc.strong("important")
    doc(" text")
```

### Inline formatting

By default every tag gets its own line.
That is what you want for structure, but it inserts whitespace into running text.
Wrap content in {meth}`~hyperscribe.DocWriter.inline` to keep it on one line:

```python
with doc.inline(), doc.li:
    doc("hi, ")
    doc.b("there")
# <li>hi, <b>there</b></li>
```

The block is indented and ends its line like any other tag.
Inline blocks may be nested;
normal formatting resumes once the outermost one exits.

### Raw output

{meth}`~hyperscribe.DocWriter.write_raw` writes a string exactly as given,
without escaping or indentation.
Use it for a doctype or for markup you have already made safe.

```python
doc.write_raw("<!DOCTYPE html>\n")
```

```{warning}
`write_raw` bypasses escaping.
Never pass it untrusted input.
```

## Escaping

Text content escapes `&`, `<` and `>`.
Attribute values additionally escape quotes.
Nothing else is escaped,
so do not use hyperscribe to write into `<script>` or `<style>` elements
with untrusted data.

## Void elements

Void elements such as `<br>`, `<img>`, `<meta>` and `<input>` have no content and no closing tag.
hyperscribe does not know which elements are void,
so a tag that is only accessed, such as `doc.br`, writes nothing.
Write them with {meth}`~hyperscribe.DocWriter.void_tag`,
which indents like any other tag and accepts the same attributes:

```python
doc.void_tag("meta", charset="utf-8")
doc.void_tag("img", src="logo.png", alt="Logo")
# <meta charset="utf-8">
# <img src="logo.png" alt="Logo">
```

Inside {meth}`~hyperscribe.DocWriter.inline` blocks it stays on the line,
so `doc.void_tag("br")` between two pieces of text gives `a<br>b`.

## Comments

{meth}`~hyperscribe.DocWriter.comment` writes an HTML comment on its own line.

```python
doc.comment("navigation")
# <!-- navigation -->
```

Text containing `--` raises a {class}`ValueError`,
because it could end the comment early.

## Loops, conditions and filters

Templates are plain Python,
so what other engines provide as special syntax is ordinary code.
These are the idioms that come up most often.

Filtering the items of a loop is a comprehension or an early `continue`.
Jinja's `{% for x in xs if cond %}` becomes:

```python
for item in items:
    if not item.visible:
        continue
    doc.li(item.name)
```

The `loop` variable is `enumerate`.
`loop.first`, `loop.index0` and `loop.length` become:

```python
visible = [item for item in items if item.visible]
for index, item in enumerate(visible):
    doc.li(("+ " if index else "") + item.name)
doc.p(f"{len(visible)} items")
```

When something must be known before the loop starts,
such as a `rowspan` that counts the rows of a group,
build the list first and then write it,
as above.

Optional attributes take `None`, so no branching is needed:

```python
doc.li(item.name, class_="done" if item.done else None)
```

Text next to markup needs {meth}`~hyperscribe.DocWriter.inline`,
which is described above,
so that no whitespace appears between them.

Whitespace-sensitive elements such as `<pre>` and `<textarea>` need the same,
or the indentation becomes part of their content:

```python
with doc.inline(), doc.pre:
    doc(code)
```

## Layouts and components

Since templates are Python, components are functions
and layouts can be generators or `@contextmanager` functions.
The layout below yields once per replaceable section:

```python
from collections.abc import Iterator
from typing import Literal

from hyperscribe import DocWriter


def topic_list(doc: DocWriter, topics: list[str]) -> None:
    with doc.inline(), doc.div:
        for index, topic in enumerate(topics):
            if index:
                doc(", ")
            doc.span(topic)


def page(doc: DocWriter) -> Iterator[Literal["head", "content"]]:
    with doc.html(lang="en"):
        with doc.head:
            yield "head"
        with doc.body:
            yield "content"


doc.write_raw("<!DOCTYPE html>\n")
for section in page(doc):
    match section:
        case "head":
            doc.title("Topics")
        case "content":
            topic_list(doc, ["python", "html"])
```

The `benchmarks/renderers/hyperscribe.py` module in the repository
shows a larger example.

## Streaming

Because output goes straight to the object you provide,
nothing is buffered by hyperscribe itself.
Pass a file or a socket wrapper to send the document as it is generated,
or a `StringIO` to get the result as a string.
