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
Values must be strings and are escaped for use inside double quotes.

```python
doc.a("Home", href="/")
with doc.div(id="main"):
    ...
```

Keyword names are written exactly as given.
For names that are not valid Python identifiers or are reserved words,
such as `class` or `data-id`, use {meth}`~hyperscribe.DocWriter.tag`
with dictionary unpacking:

```python
with doc.tag("div", **{"class": "card", "data-id": "7"}):
    doc.p("content")
# <div class="card" data-id="7">
#   <p>content</p>
# </div>
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

hyperscribe does not know which HTML elements are void.
A tag is only written when it is called with content or used as a context manager,
so `doc.br` on its own does nothing.
Write void elements with {meth}`~hyperscribe.DocWriter.write_raw`:

```python
doc.write_raw("<br>\n")
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
