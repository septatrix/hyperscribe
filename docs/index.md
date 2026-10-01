# hyperscribe

hyperscribe is a small, dependency-free HTML templating engine for Python.
Instead of a separate template language,
you write markup as Python code with context managers
and hyperscribe streams escaped, indented HTML to any file-like object.

```python
from io import StringIO

from hyperscribe import DocWriter

output = StringIO()
doc, t, v = DocWriter(output).parts

with t.html(lang="en"):
    with t.body.main:
        t.h1("Hello & welcome")

print(output.getvalue())
```

```html
<html lang="en">
  <body>
    <main>
      <h1>Hello &amp; welcome</h1>
    </main>
  </body>
</html>
```

```{toctree}
:maxdepth: 2
:caption: Contents

installation
guide
api
benchmarks
```
