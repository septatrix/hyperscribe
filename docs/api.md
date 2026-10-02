# API reference

```{eval-rst}
.. module:: hyperscribe

.. autoclass:: hyperscribe.DocWriter
   :members: tags, voids, parts, comment, inline, text, write_raw, tag, void_tag
   :special-members: __call__

.. autofunction:: hyperscribe.escape

.. autofunction:: hyperscribe.escape_silent

.. autofunction:: hyperscribe.trust

.. autodata:: hyperscribe.SafeStr
   :annotation:

.. autodata:: hyperscribe.TrustedContent
   :annotation:

.. autodata:: hyperscribe.AttributeValue
   :annotation:
```

## Tag objects

{attr}`~hyperscribe.DocWriter.tags` is a tag builder,
and {attr}`~hyperscribe.DocWriter.voids` looks up void element builders.
They are documented here because they appear in the signatures above,
but you normally do not create them yourself.

```{eval-rst}
.. autoclass:: hyperscribe._TagBuilder
   :members:
   :special-members: __call__, __getattr__, __getitem__

.. autoclass:: hyperscribe._Voids
   :special-members: __getattr__, __getitem__

.. autoclass:: hyperscribe._VoidBuilder
   :special-members: __call__
```
