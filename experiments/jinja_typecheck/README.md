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

The feature list follows what the
[cdedb2](https://github.com/cde-ev/cdedb2) templates use
(282 templates, ~1800 `{% trans %}` blocks, 280 `import … with context`,
227 `{% call %}`, 193 `extends`, 236 `super()`).
`python -m tplcheck --coverage` translates every template, annotated or not,
and reports what it cannot handle:
all 282 cdedb2 templates translate and compile,
and with typed stand-ins for the project's own filters
mypy reports one error in them (a project `gettext` that returns a non-`str`).

- **Control flow:** `if`/`elif`/`else`, `for` (incl. `loop`, `else`, inline `if`,
  `break`/`continue`), `with`, `do`, `set` (also block form and `ns.attr = …`).
  A `set` inside an `if` branch is visible in that branch only,
  unless every branch sets it (then it is `Any` afterwards).
  Container literals assigned with `set` are `list[Any]`/`dict[Any, Any]`,
  because templates mutate them (`do x.update(…)`).
- **Macros** are methods of a generated `Macros` class,
  so that `{% import "x" as m with context %}` and `{% from "x" import a %}`
  hand them the importer's context:
  the importer's context must satisfy the imported template's declared one.
  Parameters keep their names (callers pass them by keyword),
  defaults are checked in the template's context,
  and a macro that uses `caller`, `varargs` or `kwargs` gets matching parameters.
  `caller` is optional if the macro tests it (`{% if caller %}`), else required.
  Top-level `set` and `import` are attributes of that class too.
- **`self-name: util`** in the header makes `util` refer to the template's own
  macros inside it.
  Libraries such as cdedb2's `util.tmpl` call `util.other_macro()` on themselves,
  which works in Jinja only because the importer happened to import them as `util`.
- **`call` blocks** become a nested function passed as `caller=`;
  its parameters are `Any`.
- **`extends`:** the parent's declared context is filled from the child's context
  and the child's top-level `set` variables, as Jinja does.
  `super()` is a `Markup`, `self.block()` is a call returning `Markup`.
- **`include`:** filled from the context and the local variables in scope.
  `without context` passes nothing, `ignore missing` skips unknown templates.
- **i18n:** `{% trans %}`, `gettext`, `ngettext`, `_`, … with the extension enabled.
- **Narrowing** follows the template's own checks, because mypy cannot narrow
  the member accesses the shadow code is made of:
  `is defined` / `'k' in d` (optional TypedDict keys are `UndefinedValue`
  until then), `is not none`, plain truthiness and `d.get('k')` (drop `None`),
  in `if`/`elif`/`else`, conditional expressions and `and`/`or`.
  Bare context variables narrow natively.
- **Tests narrow types** (`is none`, `is string`, `is mapping`, …) through `TypeIs`.
- Filters (~50), tests (~30) and globals have typed stand-ins in `tplcheck/`.
  A project's own come from modules given with
  `--filters-module`, `--tests-module` and `--globals-module`,
  or, if it already has typed filter functions, from its registry dict with
  `--filters-registry module:NAME` (functions are used as they are,
  `@pass_environment` & co. included);
  those win over the builtin ones, like `Environment.filters.update()`.
- Extensions and a custom Environment (delimiters, policies, …) are configured with
  `--extension` and `--environment-factory module:function`.
  The factory is how the cdedb2 TeX templates, which use `<<%`, are parsed.

Not yet: `filter` blocks, recursive loops, dynamic template names
(`{% include name %}`, `{% extends name %}`),
`{% include %}` of a list of templates, namespace attribute types,
narrowing through `is defined`,
Templates that are extended, included or imported must carry a `tplcheck` header too.
A feature that is not supported is reported with its template line
rather than silently skipped.
Context TypedDicts are imported while generating, so they must be importable.

Run the tests with
`PYTHONPATH=experiments/jinja_typecheck pytest experiments/jinja_typecheck/tests`.

## Case study: cdedb2's index page

`examples/cdedb2/` type-checks four real templates of
[cdedb2](https://github.com/cde-ev/cdedb2) --
`web/core/index.tmpl`, the two base templates it extends and the 1200-line
`web/util.tmpl` macro library it imports --
without vendoring them: `prepare.py` copies them from a checkout and adds the
headers, which live in `prepare.py`.
`make check-cdedb2 CDEDB2=/path/to/cdedb2` runs it.

The contexts in `cdedb_ctx.py` follow `AbstractFrontend.fill_template`
(what every template gets), `render` and `CoreFrontend.index`;
`cdedb_filters.py` mirrors the signatures in `cdedb/filter.py`
(cdedb2 itself would point `--filters-registry` at `cdedb.filter:JINJA_FILTERS`)
and `cdedb_globals.py` what the constructor puts into `Environment.globals`.

It reports four things in the unmodified templates:

- `util.tmpl` passes `defaultvalue` to a macro in `form_input_file`,
  but that macro has no such parameter or variable --
  it passes Jinja's `Undefined`, which is probably harmless but looks unintended.
- `util.tmpl:709` reads `value` in `input_select`, which is nowhere defined
  (the line above computes `former_value`), so the sanity check
  `{% if value in ("", none) and defaultvalue %}` can never fire.
- `base.tmpl:227` calls `mls_with_defect_explicits.items()` inside
  `{% if defect_username or mls_with_defect_explicits %}`.
  This is correct only because `transform_defect_addresses` returns either
  two `None`s or two values; the checker cannot know and the context would
  have to say so (a pair, or a single optional object).

(The first two are what I read them as; I have not run them against a
database or asked the maintainers.)
Typing the index page's `dashboard` needed one assumption.
`CoreFrontend.index` adds `orga`, `orga_registrations` and `present`
(likewise `moderator`, `events`, …) only when there is something to show,
and the template relies on them coming together.
A type checker cannot see that, so the case study types the dashboard as if
`index` started from empty defaults; the `{% if dashboard.get('orga') %}` guards
in the template then keep working unchanged.

`mutations.py` applies twelve realistic mistakes one at a time
(attribute and key typos, an optional value used without its guard,
a wrong keyword for a macro or a filter, a renamed library macro, ...)
and checks that each produces a new finding: all twelve do.
