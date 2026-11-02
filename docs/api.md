# API reference

```{eval-rst}
.. module:: hyperscribe

.. autoclass:: hyperscribe.DocWriter
   :members: tags, voids, parts, comment, inline
   :special-members: __call__

.. autodata:: hyperscribe.Ignored
   :annotation:

.. autodata:: hyperscribe.TrustedContent
   :annotation:

.. autodata:: hyperscribe.AttributeValue
   :annotation:
```

## Markup

```{eval-rst}
.. automodule:: hyperscribe.markup
   :no-members:

.. autofunction:: hyperscribe.markup.escape

.. autofunction:: hyperscribe.markup.escape_silent

.. autofunction:: hyperscribe.markup.trust

.. autofunction:: hyperscribe.markup.classes

.. autodata:: hyperscribe.markup.SafeStr
   :annotation:
```

## Streaming

```{eval-rst}
.. automodule:: hyperscribe.streaming
   :no-members:

.. autoclass:: hyperscribe.streaming.AsyncDocWriter
   :members: drain

.. autofunction:: hyperscribe.streaming.aiter_chunks

.. autofunction:: hyperscribe.streaming.iter_chunks

.. autoclass:: hyperscribe.streaming.OutOfOrder
   :members: defer, write_completed, resolve, cancel
   :special-members: __init__, __exit__

.. autoclass:: hyperscribe.streaming.SlotId
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
