# API reference

```{eval-rst}
.. module:: hyperscribe

.. autoclass:: hyperscribe.DocWriter
   :members: tag, inline, text, write_raw
   :special-members: __call__, __getattr__
```

## Tag objects

Accessing an attribute on a {class}`~hyperscribe.DocWriter` returns a tag builder.
Calling {meth}`~hyperscribe.DocWriter.tag` returns a tag context.
Both are documented here because they appear in the signatures above,
but you normally do not create them yourself.

```{eval-rst}
.. autoclass:: hyperscribe._TagBuilder
   :members:
   :special-members: __call__, __getattr__

.. autoclass:: hyperscribe._TagContext
```
