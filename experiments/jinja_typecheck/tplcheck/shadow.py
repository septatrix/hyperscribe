"""Translate a Jinja template into Python that mypy can check.

The output is never executed.
It keeps the *types* of the template's expressions and drops everything else:
literal text disappears, ``{{ expr }}`` becomes ``emit(expr)``,
``{% for %}`` becomes a ``for`` loop, macros and blocks become nested functions,
and the declared context is the type of a ``ctx`` parameter.

A template opts in with a leading comment::

    {# tplcheck
       context: myapp.views.ArticlesContext
       from collections.abc import Sequence
       macro topic_list(topics: Sequence[str])
    #}

``context:`` names the TypedDict of the variables passed to ``render()``.
``import``/``from`` lines are copied verbatim into the shadow module.
``macro`` lines annotate macro parameters (Jinja has no syntax for that).
"""

from __future__ import annotations

import ast
import importlib
import keyword
import re
from collections.abc import Mapping
from dataclasses import dataclass, field

from jinja2 import Environment, nodes

from .contexts import context_keys

HEADER = re.compile(r"\A\s*\{#-?\s*tplcheck\b(?P<body>.*?)-?#\}", re.DOTALL)

GLOBALS = frozenset(
    {
        "range",
        "dict",
        "lipsum",
        "cycler",
        "joiner",
        "namespace",
        "gettext",
        "ngettext",
        "pgettext",
        "npgettext",
        "_",
    }
)

# Jinja names that are Python builtins or keywords in the stub modules.
RENAMED = {
    "int": "int_",
    "float": "float_",
    "abs": "abs_",
    "round": "round_",
    "sum": "sum_",
    "list": "list_",
    "in": "in_",
    "min": "min_",
    "max": "max_",
    "map": "map_",
    "slice": "slice_",
    "callable": "callable_",
    "filter": "filter_",
    "test": "test_",
}

COMPARE = {
    "eq": "==",
    "ne": "!=",
    "gt": ">",
    "gteq": ">=",
    "lt": "<",
    "lteq": "<=",
    "in": "in",
    "notin": "not in",
}

BINARY = {
    nodes.Add: "+",
    nodes.Sub: "-",
    nodes.Mul: "*",
    nodes.Div: "/",
    nodes.FloorDiv: "//",
    nodes.Mod: "%",
    nodes.Pow: "**",
}


@dataclass(frozen=True)
class TemplateInfo:
    """What other templates need to know to extend or include a template."""

    module: str  # name of the shadow module
    context: str | None


# Names the generated code uses itself; a macro parameter must not shadow them.
RESERVED = frozenset(
    {
        "f", "g", "t", "cf", "cg", "ct", "ctx", "macros", "self", "caller",
        "Markup", "Any", "Callable", "emit", "getattr_", "loop_", "concat_",
        "undefined_", "anything_", "self_", "super_", "tplcheck", "list", "dict",
    }
)  # fmt: skip


class Scope(dict[str, str]):
    """Names visible in a scope; ``shared`` pre-assigns names set in all branches."""

    def __init__(self, shared: dict[str, str] | None = None) -> None:
        super().__init__()
        self.shared = shared or {}


class UnsupportedError(Exception):
    """A template feature the shadow translation does not model (yet)."""

    def __init__(self, what: str, lineno: int) -> None:
        super().__init__(what)
        self.what = what
        self.lineno = lineno


@dataclass(frozen=True)
class Config:
    """Project-specific pieces the generic translation cannot know."""

    #: Jinja extensions the templates need to parse, e.g. ``jinja2.ext.i18n``.
    extensions: tuple[str, ...] = ()
    #: ``module:function`` returning the Environment to parse with
    #: (for custom delimiters, policies, ...). Overrides ``extensions``.
    environment_factory: str | None = None
    #: Modules with typed stand-ins for the project's own filters/tests/globals.
    filters_module: str | None = None
    tests_module: str | None = None
    globals_module: str | None = None
    #: Translate templates without a header too, with an untyped (Any) context.
    lenient: bool = False


@dataclass
class Header:
    context: str | None = None
    imports: list[str] = field(default_factory=list)
    macros: dict[str, ast.arguments] = field(default_factory=dict)


def parse_header(source: str) -> Header | None:
    """Return the ``{# tplcheck ... #}`` header, or None if the template has none."""
    match = HEADER.match(source)
    if match is None:
        return None
    header = Header()
    for raw in match["body"].splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("context:"):
            header.context = line.removeprefix("context:").strip()
        elif line.startswith(("import ", "from ")):
            header.imports.append(line)
        elif line.startswith("macro "):
            module = ast.parse(f"def {line.removeprefix('macro ')}: ...")
            func = module.body[0]
            assert isinstance(func, ast.FunctionDef)
            header.macros[func.name] = func.args
        else:
            raise ValueError(f"unknown tplcheck header line: {line!r}")
    return header


class Emitter:
    """Builds one shadow module.

    Layout of the output::

        class Macros:            # everything other templates can import
            def __init__(self, tpl_ctx): ...   # top-level import/set
            def some_macro(self, ...): ...     # top-level macros
        def check(ctx):          # the rest: blocks, output, control flow
            macros = Macros(ctx)
            ...

    Macros live on a class because ``{% import "x" as m with context %}``
    gives them the *importer's* context: ``tpl_x.Macros(ctx)`` checks that
    the importer's context satisfies the imported template's declared one.
    """

    def __init__(
        self,
        source: str,
        source_name: str,
        environment: Environment,
        templates: Mapping[str, TemplateInfo],
        config: Config,
    ) -> None:
        self.source_name = source_name
        self.templates = templates
        self.config = config
        header = parse_header(source)
        self.untyped = header is None
        if header is None:
            if not config.lenient:
                raise ValueError(f"{source_name} has no tplcheck header")
            header = Header()
        self.header = header
        self.ctx_type = header.context or (
            "Any" if self.untyped else "tplcheck.NoContext"
        )
        self.tree = environment.parse(source, source_name)
        self.lines: list[str] = []
        self.depth = 1
        self.counter = 0
        # Template name -> Python name, innermost scope last.
        self.scopes: list[dict[str, str]] = [{}]
        # Top-level names other templates can import: macros, imports, `set`.
        self.exports: set[str] = set()
        self.ctx_expr = "ctx"
        self.exports_ref = "macros"
        self.imports: list[str] = []
        self.ctx_keys = context_keys(header.context)
        self.has_extends = any(isinstance(n, nodes.Extends) for n in self.tree.body)
        self.custom = {
            kind: importlib.import_module(module) if module else None
            for kind, module in (
                ("filters", config.filters_module),
                ("tests", config.tests_module),
                ("globals", config.globals_module),
            )
        }

    # -- output helpers -------------------------------------------------

    def line(self, text: str, lineno: int) -> None:
        self.lines.append(f"{'    ' * self.depth}{text}  # tpl:{lineno}")

    def suite(self, body: list[nodes.Node], lineno: int) -> None:
        """Emit an indented block, with ``pass`` if it ends up empty."""
        self.depth += 1
        before = len(self.lines)
        for node in body:
            self.statement(node)
        if len(self.lines) == before:
            self.line("pass", lineno)
        self.depth -= 1

    def param_name(self, name: str) -> str:
        """Macro parameters keep their name, since callers pass them by keyword."""
        if keyword.iskeyword(name) or name in RESERVED or not name.isidentifier():
            return self.fresh(name)
        return name

    def fresh(self, name: str) -> str:
        self.counter += 1
        return f"l_{name}_{self.counter}"

    def lookup(self, name: str) -> str | None:
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        if name in self.exports:
            return f"{self.exports_ref}.{name}"
        return None

    def visible_locals(self) -> dict[str, str]:
        visible: dict[str, str] = {}
        for scope in self.scopes:
            visible.update(scope)
        return visible

    # -- entry point ----------------------------------------------------

    def generate(self) -> str:
        body = self.tree.body
        toplevel = [n for n in body if self.is_export(n)]
        toplevel_ids = {id(n) for n in toplevel}
        for node in toplevel:
            self.exports.update(self.export_names(node))

        # Phase 1: what other templates can import.
        init_lines: list[str] = []
        method_lines: list[str] = []
        self.ctx_expr, self.exports_ref = "self.tpl_ctx", "self"
        self.lines, self.depth = init_lines, 2
        for node in toplevel:
            if not isinstance(node, nodes.Macro):
                self.statement(node)
        self.lines, self.depth = method_lines, 1
        for node in toplevel:
            if isinstance(node, nodes.Macro):
                self.macro_method(node)

        # Phase 2: the template body itself.
        self.ctx_expr, self.exports_ref = "ctx", "macros"
        self.lines, self.depth = [], 1
        for node in body:
            if id(node) not in toplevel_ids:
                self.statement(node)
        for node in body:
            if isinstance(node, nodes.Extends):
                self.extends_call(node)
        if not self.lines:
            self.line("pass", 1)

        context_module = self.ctx_type.rpartition(".")[0]
        head = [
            f"# tplcheck: {self.source_name}",
            "# Generated by tplcheck; never executed, only type-checked.",
            "from __future__ import annotations",
            "from collections.abc import Callable",
            "from typing import Any",
            "from markupsafe import Markup",
            "from tplcheck import anything_, concat_, emit, getattr_, loop_",
            "from tplcheck import self_, super_, undefined_",
            "from tplcheck import filters as f, globals_ as g, tests as t",
            *self.header.imports,
            "import tplcheck",
        ]
        if context_module and context_module != "tplcheck":
            head.append(f"import {context_module}")
        for alias, module in (
            ("cf", self.config.filters_module),
            ("ct", self.config.tests_module),
            ("cg", self.config.globals_module),
        ):
            if module:
                head.append(f"import {module} as {alias}")
        head += self.imports
        cls = [
            "",
            "class Macros:",
            f"    def __init__(self, tpl_ctx: {self.ctx_type}) -> None:",
            "        self.tpl_ctx = tpl_ctx",
            *init_lines,
            *method_lines,
            "",
            f"def check(ctx: {self.ctx_type}) -> None:",
            "    macros = Macros(ctx)",
        ]
        return "\n".join([*head, *cls, *self.lines, ""])

    def is_export(self, node: nodes.Node) -> bool:
        if isinstance(node, nodes.Assign):
            return isinstance(node.target, nodes.Name)
        return isinstance(
            node, nodes.Macro | nodes.Import | nodes.FromImport | nodes.AssignBlock
        ) and (
            not isinstance(node, nodes.AssignBlock)
            or isinstance(node.target, nodes.Name)
        )

    def export_names(self, node: nodes.Node) -> list[str]:
        if isinstance(node, nodes.Macro):
            return [node.name]
        if isinstance(node, nodes.Import):
            return [node.target]
        if isinstance(node, nodes.FromImport):
            return [n[1] if isinstance(n, tuple) else n for n in node.names]
        if isinstance(node, nodes.Assign | nodes.AssignBlock):
            assert isinstance(node.target, nodes.Name)
            return [node.target.name]
        return []

    # -- statements -----------------------------------------------------

    def statement(self, node: nodes.Node) -> None:
        handler = getattr(self, f"stmt_{type(node).__name__}", None)
        if handler is None:
            raise UnsupportedError(
                f"{type(node).__name__} is not supported", node.lineno
            )
        handler(node)

    def target(self, expr: nodes.Node, what: str) -> TemplateInfo | None:
        """Resolve the template named by an extends/include/import."""
        if not (isinstance(expr, nodes.Const) and isinstance(expr.value, str)):
            raise UnsupportedError(f"dynamic {what} names", expr.lineno)
        info = self.templates.get(expr.value)
        if info is None:
            if self.config.lenient:
                return None
            raise UnsupportedError(
                f"{what} of {expr.value!r}, which has no tplcheck header", expr.lineno
            )
        if (line := f"import {info.module} as tpl_{info.module}") not in self.imports:
            self.imports.append(line)
        return info

    def context_literal(self, info: TemplateInfo, locals_: bool, lineno: int) -> str:
        """A dict literal giving ``info``'s context its variables from here."""
        visible = self.visible_locals() if locals_ else {}
        entries = []
        for key in sorted(context_keys(info.context)):
            if key in visible:
                entries.append(f"{key!r}: {visible[key]}")
            elif key in self.exports:
                entries.append(f"{key!r}: {self.exports_ref}.{key}")
            elif key in self.ctx_keys:
                entries.append(f"{key!r}: {self.ctx_expr}[{key!r}]")
        return "{" + ", ".join(entries) + "}"

    def extends_call(self, node: nodes.Extends) -> None:
        info = self.target(node.template, "extends")
        if info is None:
            return
        literal = self.context_literal(info, locals_=False, lineno=node.lineno)
        self.line(f"tpl_{info.module}.check({literal})", node.lineno)

    def stmt_Extends(self, node: nodes.Extends) -> None:
        pass  # handled at the end of the template, see extends_call

    def stmt_Include(self, node: nodes.Include) -> None:
        try:
            info = self.target(node.template, "include")
        except UnsupportedError:
            if node.ignore_missing and isinstance(node.template, nodes.Const):
                return
            raise
        if info is None:
            return
        literal = "{}"
        if node.with_context:
            literal = self.context_literal(info, locals_=True, lineno=node.lineno)
        self.line(f"tpl_{info.module}.check({literal})", node.lineno)

    def import_value(self, node: nodes.Import | nodes.FromImport) -> str:
        info = self.target(node.template, "import")
        if info is None:
            return "anything_"
        argument = self.ctx_expr if node.with_context else "{}"
        return f"tpl_{info.module}.Macros({argument})"

    def stmt_Import(self, node: nodes.Import) -> None:
        value = self.import_value(node)
        if node.target in self.exports and self.at_export_level():
            self.line(f"self.{node.target} = {value}", node.lineno)
        else:
            py = self.bind(nodes.Name(node.target, "store"), self.scopes[-1])
            self.line(f"{py} = {value}", node.lineno)

    def stmt_FromImport(self, node: nodes.FromImport) -> None:
        module = self.fresh("module")
        self.line(f"{module} = {self.import_value(node)}", node.lineno)
        for entry in node.names:
            name, alias = entry if isinstance(entry, tuple) else (entry, entry)
            if alias in self.exports and self.at_export_level():
                self.line(f"self.{alias} = {module}.{name}", node.lineno)
            else:
                py = self.bind(nodes.Name(alias, "store"), self.scopes[-1])
                self.line(f"{py} = {module}.{name}", node.lineno)

    def at_export_level(self) -> bool:
        return self.exports_ref == "self" and len(self.scopes) == 1 and self.depth == 2

    def stmt_Output(self, node: nodes.Output) -> None:
        if self.depth == 1 and self.has_extends:
            return  # Jinja discards output outside blocks in a child template
        for child in node.nodes:
            if not isinstance(child, nodes.TemplateData):
                self.line(f"emit({self.expr(child)})", child.lineno)

    def stmt_ExprStmt(self, node: nodes.ExprStmt) -> None:
        self.line(f"emit({self.expr(node.node)})", node.lineno)

    def assigned_names(self, body: list[nodes.Node]) -> set[str]:
        """Names `set` directly in a body (not in nested loops and the like)."""
        names: set[str] = set()
        for child in body:
            if isinstance(child, nodes.Assign | nodes.AssignBlock):
                target = child.target
                targets = target.items if isinstance(target, nodes.Tuple) else [target]
                names.update(t.name for t in targets if isinstance(t, nodes.Name))
        return names

    def stmt_If(self, node: nodes.If) -> None:
        # A `set` inside a branch is only visible in that branch -- unless every
        # branch sets it, in which case the name is defined after the `if`.
        # (Python would otherwise flag a read in a sibling branch.)
        bodies = [node.body, *(branch.body for branch in node.elif_)]
        shared: dict[str, str] = {}
        if node.else_:
            common = set.intersection(
                *(self.assigned_names(b) for b in [*bodies, node.else_])
            )
            shared = {name: self.fresh(name) for name in sorted(common)}
            for py in shared.values():
                # The branches may assign different types, so don't pin one.
                self.line(f"{py}: Any", node.lineno)

        def branch(body: list[nodes.Node], lineno: int) -> None:
            self.scopes.append(Scope(shared))
            self.suite(body, lineno)
            self.scopes.pop()

        self.line(f"if {self.expr(node.test)}:", node.lineno)
        branch(node.body, node.lineno)
        for elif_ in node.elif_:
            self.line(f"elif {self.expr(elif_.test)}:", elif_.lineno)
            branch(elif_.body, elif_.lineno)
        if node.else_:
            self.line("else:", node.lineno)
            branch(node.else_, node.lineno)
        self.scopes[-1].update(shared)

    def stmt_For(self, node: nodes.For) -> None:
        if node.recursive:
            raise UnsupportedError("recursive loops are not supported", node.lineno)
        iterable = self.expr(node.iter)  # evaluated in the enclosing scope
        loop_name = self.fresh("loop")
        scope: dict[str, str] = {"loop": loop_name}
        target = self.bind(node.target, scope)
        self.line(f"{loop_name} = loop_({iterable})", node.lineno)
        self.line(f"for {target} in {loop_name}:", node.lineno)
        self.scopes.append(scope)
        if node.test is not None:
            self.depth += 1
            self.line(f"if not {self.expr(node.test)}: continue", node.lineno)
            self.depth -= 1
        self.suite(node.body, node.lineno)
        self.scopes.pop()
        if node.else_:
            self.line("else:", node.lineno)
            self.suite(node.else_, node.lineno)

    def stmt_Continue(self, node: nodes.Continue) -> None:
        self.line("continue", node.lineno)

    def stmt_Break(self, node: nodes.Break) -> None:
        self.line("break", node.lineno)

    def stmt_With(self, node: nodes.With) -> None:
        values = [self.expr(v) for v in node.values]  # outer scope
        scope: dict[str, str] = {}
        for target, value in zip(node.targets, values, strict=True):
            self.line(f"{self.bind(target, scope)} = {value}", node.lineno)
        self.scopes.append(scope)
        for child in node.body:
            self.statement(child)
        self.scopes.pop()

    def bind(self, target: nodes.Node, scope: dict[str, str]) -> str:
        """Allocate Python names for an assignment target and register them."""
        if isinstance(target, nodes.Name):
            shared = getattr(scope, "shared", {})
            scope[target.name] = py = shared.get(target.name) or self.fresh(target.name)
            return py
        if isinstance(target, nodes.Tuple):
            return f"({', '.join(self.bind(item, scope) for item in target.items)},)"
        raise UnsupportedError(f"{type(target).__name__} target", target.lineno)

    def stmt_Assign(self, node: nodes.Assign) -> None:
        if isinstance(node.target, nodes.NSRef):
            # `ns.attr = value`: namespace attributes are untyped
            self.line(f"emit({self.expr(node.node)})", node.lineno)
            return
        value = self.expr(node.node)  # before binding, so `set x = x + 1` works
        annotation = ""
        # Templates mutate containers (`do x.update(...)`), which mypy's narrow
        # inference for literals would reject, so literals are not inferred.
        if isinstance(node.node, nodes.List):
            annotation = ": list[Any]"
        elif isinstance(node.node, nodes.Dict):
            annotation = ": dict[Any, Any]"
        if (
            isinstance(node.target, nodes.Name)
            and node.target.name in self.exports
            and self.at_export_level()
        ):
            self.line(f"self.{node.target.name}{annotation} = {value}", node.lineno)
            return
        target = self.bind(node.target, self.scopes[-1])
        self.line(f"{target}{annotation} = {value}", node.lineno)

    def stmt_AssignBlock(self, node: nodes.AssignBlock) -> None:
        if node.filter is not None:
            raise UnsupportedError("filtered {% set %} blocks", node.lineno)
        self.scopes.append({})
        for child in node.body:
            self.statement(child)
        self.scopes.pop()
        if (
            isinstance(node.target, nodes.Name)
            and node.target.name in self.exports
            and self.at_export_level()
        ):
            self.line(f"self.{node.target.name} = Markup('')", node.lineno)
            return
        target = self.bind(node.target, self.scopes[-1])
        self.line(f"{target} = Markup('')", node.lineno)

    def signature(
        self, node: nodes.Macro
    ) -> tuple[list[str], dict[str, str], list[str]]:
        """Python parameters (after ``self``), name scope and default checks.

        Defaults are evaluated by the macro at call time, in the template's
        context, so the signature only says "has a default" (``anything_``)
        and the expressions are checked at the start of the body.
        """
        annotated = self.header.macros.get(node.name)
        names = [arg.name for arg in node.args]
        used = {n.name for n in node.find_all(nodes.Name)}
        called = {id(c.node) for c in node.find_all(nodes.Call)}
        caller_tested = any(
            n.name == "caller" and id(n) not in called
            for n in node.find_all(nodes.Name)
        )
        caller_annotation = (
            "Callable[..., Markup] | None" if caller_tested else "Callable[..., Markup]"
        )
        caller_default = "None" if caller_tested else None
        if annotated is not None:
            declared = [a.arg for a in annotated.args]
            if declared[: len(names)] != names or declared[len(names) :] not in (
                [],
                ["caller"],
            ):
                raise UnsupportedError(
                    f"macro {node.name}: header parameters {declared} "
                    f"do not match {names}",
                    node.lineno,
                )
            if "caller" in declared[len(names) :]:
                used.add("caller")
                last = annotated.args[-1]
                if last.annotation is not None:
                    caller_annotation = ast.unparse(last.annotation)
                if annotated.defaults:
                    caller_default = ast.unparse(annotated.defaults[-1])
        first_default = len(node.args) - len(node.defaults)
        params: list[str] = []
        scope: dict[str, str] = {}
        defaults: list[str] = []
        for index, arg in enumerate(node.args):
            annotation = "Any"
            if annotated is not None and annotated.args[index].annotation is not None:
                annotation = ast.unparse(annotated.args[index].annotation)  # type: ignore[arg-type]
            scope[arg.name] = py = self.param_name(arg.name)
            param = f"{py}: {annotation}"
            if index >= first_default:
                param += " = anything_"
                defaults.append(self.expr(node.defaults[index - first_default]))
            params.append(param)
        if "varargs" in used:
            scope["varargs"] = py = self.fresh("varargs")
            params.append(f"*{py}: Any")
        if "caller" in used:
            scope["caller"] = "caller"
            if "varargs" not in used:
                params.append("*")
            params.append(
                f"caller: {caller_annotation}"
                + (f" = {caller_default}" if caller_default else "")
            )
        if "kwargs" in used:
            scope["kwargs"] = py = self.fresh("kwargs")
            params.append(f"**{py}: Any")
        return params, scope, defaults

    def default_checks(self, defaults: list[str], lineno: int) -> None:
        self.depth += 1
        for default in defaults:
            self.line(f"emit({default})", lineno)
        self.depth -= 1

    def macro_method(self, node: nodes.Macro) -> None:
        if keyword.iskeyword(node.name):
            raise UnsupportedError(f"macro named {node.name!r}", node.lineno)
        params, scope, defaults = self.signature(node)
        self.line(
            f"def {node.name}({', '.join(['self', *params])}) -> Markup:", node.lineno
        )
        self.default_checks(defaults, node.lineno)
        saved, self.scopes = self.scopes, [{}, scope]
        self.suite(node.body, node.lineno)
        self.scopes = saved
        self.depth += 1
        self.line("return Markup('')", node.lineno)
        self.depth -= 1

    def stmt_Macro(self, node: nodes.Macro) -> None:
        """A macro that is not at the top level: a nested function."""
        params, scope, defaults = self.signature(node)
        py_name = self.fresh(f"macro_{node.name}")
        self.scopes[-1][node.name] = py_name
        self.line(f"def {py_name}({', '.join(params)}) -> Markup:", node.lineno)
        self.default_checks(defaults, node.lineno)
        self.scopes.append(scope)
        self.suite(node.body, node.lineno)
        self.scopes.pop()
        self.depth += 1
        self.line("return Markup('')", node.lineno)
        self.depth -= 1

    def stmt_CallBlock(self, node: nodes.CallBlock) -> None:
        caller = self.fresh("caller")
        first_default = len(node.args) - len(node.defaults)
        scope: dict[str, str] = {}
        params = []
        defaults: list[str] = []
        for index, arg in enumerate(node.args):
            scope[arg.name] = py = self.param_name(arg.name)
            param = f"{py}: Any"
            if index >= first_default:
                param += " = anything_"
                defaults.append(self.expr(node.defaults[index - first_default]))
            params.append(param)
        self.line(f"def {caller}({', '.join(params)}) -> Markup:", node.lineno)
        self.default_checks(defaults, node.lineno)
        self.scopes.append(scope)
        self.suite(node.body, node.lineno)
        self.scopes.pop()
        self.depth += 1
        self.line("return Markup('')", node.lineno)
        self.depth -= 1
        call = node.call
        arguments = self.arguments(call)
        arguments.insert(
            len(arguments) - (call.dyn_kwargs is not None), f"caller={caller}"
        )
        self.line(f"emit({self.expr(call.node)}({', '.join(arguments)}))", node.lineno)

    def stmt_Block(self, node: nodes.Block) -> None:
        py_name = self.fresh(f"block_{node.name}")
        self.line(f"def {py_name}() -> None:", node.lineno)
        saved = self.scopes
        # Blocks only see the template level unless declared `scoped`.
        self.scopes = [*saved] if node.scoped else [saved[0]]
        self.suite(node.body, node.lineno)
        self.scopes = saved

    # -- expressions ----------------------------------------------------

    def expr(self, node: nodes.Node) -> str:
        handler = getattr(self, f"expr_{type(node).__name__}", None)
        if handler is not None:
            return str(handler(node))
        for node_type, operator in BINARY.items():
            if type(node) is node_type:
                assert isinstance(node, nodes.BinExpr)
                return f"({self.expr(node.left)} {operator} {self.expr(node.right)})"
        raise UnsupportedError(f"{type(node).__name__} is not supported", node.lineno)

    def expr_Const(self, node: nodes.Const) -> str:
        return repr(node.value)

    def expr_Name(self, node: nodes.Name) -> str:
        py = self.lookup(node.name)
        if py is not None:
            return py
        custom_globals = self.custom["globals"]
        if node.name not in self.ctx_keys:
            if custom_globals is not None and hasattr(custom_globals, node.name):
                return f"cg.{node.name}"
            if node.name in GLOBALS:
                return f"g.{node.name}"
        if node.name == "super":
            return "super_"
        if node.name == "self":
            return "self_"
        return f"{self.ctx_expr}[{node.name!r}]"

    def expr_MarkSafeIfAutoescape(self, node: nodes.MarkSafeIfAutoescape) -> str:
        return self.expr(node.expr)

    def expr_MarkSafe(self, node: nodes.MarkSafe) -> str:
        return f"Markup({self.expr(node.expr)})"

    def expr_Getattr(self, node: nodes.Getattr) -> str:
        return f"getattr_({self.expr(node.node)}, {node.attr!r})"

    def expr_Getitem(self, node: nodes.Getitem) -> str:
        obj = self.expr(node.node)
        if isinstance(node.arg, nodes.Const) and isinstance(node.arg.value, str):
            return f"getattr_({obj}, {node.arg.value!r})"
        if isinstance(node.arg, nodes.Slice):
            parts = [
                self.expr(p) if p is not None else ""
                for p in (node.arg.start, node.arg.stop, node.arg.step)
            ]
            return f"{obj}[{':'.join(parts)}]"
        return f"{obj}[{self.expr(node.arg)}]"

    def arguments(self, node: nodes.Call | nodes.Filter | nodes.Test) -> list[str]:
        args = [self.expr(a) for a in node.args]
        if node.dyn_args is not None:
            args.append(f"*{self.expr(node.dyn_args)}")
        # Keywords such as `class` cannot be written as `class=...` in Python.
        plain = [kw for kw in node.kwargs if not keyword.iskeyword(kw.key)]
        odd = [kw for kw in node.kwargs if keyword.iskeyword(kw.key)]
        args += [f"{kw.key}={self.expr(kw.value)}" for kw in plain]
        if odd:
            args.append(
                "**{"
                + ", ".join(f"{kw.key!r}: {self.expr(kw.value)}" for kw in odd)
                + "}"
            )
        if node.dyn_kwargs is not None:
            args.append(f"**{self.expr(node.dyn_kwargs)}")
        return args

    def expr_Call(self, node: nodes.Call) -> str:
        return f"{self.expr(node.node)}({', '.join(self.arguments(node))})"

    def member(self, kind: str, alias: str, builtin: str, name: str) -> str:
        py = RENAMED.get(name, name)
        custom = self.custom[kind]
        if custom is not None and hasattr(custom, py):
            return f"c{alias}.{py}"
        return f"{builtin}.{py}"

    def expr_Filter(self, node: nodes.Filter) -> str:
        if node.node is None:
            raise UnsupportedError("filter blocks are not supported", node.lineno)
        args = [self.expr(node.node), *self.arguments(node)]
        return f"{self.member('filters', 'f', 'f', node.name)}({', '.join(args)})"

    def expr_Test(self, node: nodes.Test) -> str:
        args = [self.expr(node.node), *self.arguments(node)]
        return f"{self.member('tests', 't', 't', node.name)}({', '.join(args)})"

    def expr_CondExpr(self, node: nodes.CondExpr) -> str:
        otherwise = self.expr(node.expr2) if node.expr2 is not None else "undefined_()"
        return f"({self.expr(node.expr1)} if {self.expr(node.test)} else {otherwise})"

    def expr_Not(self, node: nodes.Not) -> str:
        return f"(not {self.expr(node.node)})"

    def expr_Neg(self, node: nodes.Neg) -> str:
        return f"(-{self.expr(node.node)})"

    def expr_Pos(self, node: nodes.Pos) -> str:
        return f"(+{self.expr(node.node)})"

    def expr_And(self, node: nodes.And) -> str:
        return f"({self.expr(node.left)} and {self.expr(node.right)})"

    def expr_Or(self, node: nodes.Or) -> str:
        return f"({self.expr(node.left)} or {self.expr(node.right)})"

    def expr_Compare(self, node: nodes.Compare) -> str:
        parts = [self.expr(node.expr)]
        for operand in node.ops:
            parts += [COMPARE[operand.op], self.expr(operand.expr)]
        return f"({' '.join(parts)})"

    def expr_Concat(self, node: nodes.Concat) -> str:
        return f"concat_({', '.join(self.expr(n) for n in node.nodes)})"

    def expr_List(self, node: nodes.List) -> str:
        return f"[{', '.join(self.expr(n) for n in node.items)}]"

    def expr_Tuple(self, node: nodes.Tuple) -> str:
        return f"({''.join(self.expr(n) + ', ' for n in node.items)})"

    def expr_Dict(self, node: nodes.Dict) -> str:
        pairs = (f"{self.expr(p.key)}: {self.expr(p.value)}" for p in node.items)
        return f"{{{', '.join(pairs)}}}"


def make_environment(config: Config) -> Environment:
    """The Environment templates are parsed with."""
    if config.environment_factory:
        module, _, function = config.environment_factory.partition(":")
        environment = getattr(importlib.import_module(module), function)()
        assert isinstance(environment, Environment)
        return environment
    return Environment(extensions=list(config.extensions))


def translate(
    source: str,
    source_name: str,
    environment: Environment | None = None,
    templates: Mapping[str, TemplateInfo] | None = None,
    config: Config | None = None,
) -> str:
    """Translate one template, or raise UnsupportedError with its line number.

    ``templates`` maps template names to the annotated templates
    that this one may extend, include or import.
    """
    config = config or Config()
    emitter = Emitter(
        source,
        source_name,
        environment or make_environment(config),
        templates or {},
        config,
    )
    return emitter.generate()
