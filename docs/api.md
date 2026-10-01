# API reference

```{eval-rst}
.. module:: hyperscribe

.. autoclass:: hyperscribe.DocWriter
   :members: tag, void_tag, comment, inline, text, write_raw
   :special-members: __call__, __getattr__, __getitem__
```

## Tag objects

Accessing an attribute on a {class}`~hyperscribe.DocWriter`,
or subscripting it, returns a tag builder.
It is documented here because it appears in the signatures above,
but you normally do not create one yourself.

```{eval-rst}
.. autoclass:: hyperscribe._TagBuilder
   :members:
   :special-members: __call__, __getattr__, __getitem__
```
