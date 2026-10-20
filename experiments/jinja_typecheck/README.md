# Type-checking Jinja templates with mypy

An experiment in making Jinja templates checkable by mypy.

A template declares the context it is rendered with in a leading comment:

```jinja
{# tplcheck
   context: benchmarks.models.ArticlesContext
   from collections.abc import Sequence
   macro topic_list(topics: Sequence[str])
-#}
```

`python -m tplcheck` then

1. parses each annotated template with `Environment.parse()`
   (the public AST, not Jinja's generated code),
2. translates it into a *shadow module* that is never executed:
   `{{ expr }}` becomes `emit(expr)`,
   loops, conditionals, macros and blocks become their Python counterparts,
   and the context becomes the type of a `ctx` parameter,
3. runs mypy on the shadow modules
   and maps every error back to the line in the template,
4. writes a stub overloading `get_template(env, "name")`
   so that `render(**context)` is checked against the declared TypedDict
   (via `Unpack[TypedDict]` kwargs).

```console
$ make check-templates
$ python -m tplcheck templates/ --config-file experiments/jinja_typecheck/mypy.ini
templates/articles.jinja2:30: error: TypedDict "Item" has no key "titel"  [misc]
templates/articles.jinja2:22: error: TypedDict "ArticlesContext" has no key "topics"  [typeddict-item]
```

## Why not patch Jinja's compiled output?

It is all `Any`: `resolve('user')`, `environment.getattr(...)`,
`environment.filters['upper']`.
Typing it means overriding every `visit_*` of the code generator,
which is internal API, at which point it is a rewrite anyway.
The shadow translation only has to preserve expression *types*,
so it is far smaller.

## The mypy plugin

Jinja's `a.b` tries attribute access and falls back to item access,
and which one applies depends on the static type of `a`.
The shadow code emits `getattr_(a, "b")`
and `tplcheck/mypy_plugin.py` resolves it:
TypedDict key, attribute, or `__getitem__` for mappings.
This is the only thing that needs a plugin.
Everything else is plain, generated Python.

## Supported

`extends`: the child's context must satisfy the parent's declared context
(TypedDicts are structural, so extra keys are fine),
and blocks are checked in the child's context.
`include`: the included template's context is filled from the includer's context
and from the local variables in scope (loop variables, `set`),
so a missing or mistyped variable is reported at the `{% include %}` line.
`without context` passes nothing, `ignore missing` skips unknown templates.
A template with a bare `{# tplcheck #}` header declares that it uses no variables.

`if`/`elif`/`else`, `for` (incl. `loop`, `else`, inline `if`),
`set` (also block form), macros with annotated parameters and defaults,
expressions, ~25 filters, ~15 tests, default globals.

Not yet: `import`/`from import`, `with`, `call`/`caller`,
`self.block()`/`super()`, recursive loops, `namespace` attribute assignment,
narrowing via `is defined`,
top-level `set` in a child being visible to its parent,
and dynamic template names (`{% include name %}`).
Templates that are extended or included must carry a `tplcheck` header too.
Context TypedDicts are imported while generating, so they must be importable.
A feature that is not supported is reported with its template line
rather than silently skipped.
Filters and tests need typed stand-ins in `tplcheck/filters.py` and `tests.py`;
custom ones have to be added there.

Run the tests with
`PYTHONPATH=experiments/jinja_typecheck pytest experiments/jinja_typecheck/tests`.
