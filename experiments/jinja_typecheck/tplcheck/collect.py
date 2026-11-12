"""Generate context TypedDicts from a project's ``render(...)`` call sites.

Where templates are rendered through one function or method,
the call sites already say what each template gets::

    self.render(rs, "index", {"meta_info": meta_info, "dashboard": dashboard})

A mypy plugin records, for every such call with a literal template name and a
dict literal, the keys and the types mypy infers for the values.
Calls that render the same template are merged: keys passed at every site are
required, the others ``NotRequired``, and value types become unions.
The result is a module of TypedDicts plus ``TEMPLATE_CONTEXTS``, which
``python -m tplcheck --contexts-module`` uses for templates without a
``context:`` header line.

::

    python -m tplcheck.collect --render pkg.mod.Class.render \\
        --module pkg.contexts --out pkg/contexts.py [--base-context pkg.ctx.Base] \\
        -- --config-file mypy.ini pkg/
"""

from __future__ import annotations

import argparse
import importlib
import keyword
import os
import re
import sys
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from mypy import build
from mypy.errors import CompileError
from mypy.main import process_options
from mypy.nodes import ARG_POS, DictExpr, Expression, StrExpr
from mypy.options import Options
from mypy.plugin import FunctionContext, MethodContext, Plugin
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    LiteralType,
    NoneType,
    TupleType,
    Type,
    TypedDictType,
    TypeType,
    UnionType,
    get_proper_type,
)

from .contexts import add_import_paths

Mapper = Callable[[str, str | None, str], str | None]


@dataclass
class Site:
    """One ``render`` call with a literal template name."""

    template: str
    location: str
    complete: bool = True  # False if the params are not a plain dict literal
    keys: dict[str, str] = field(default_factory=dict)  # key -> annotation
    imports: set[str] = field(default_factory=set)


@dataclass
class Spec:
    function: str  # fullname, e.g. "pkg.mod.Class.render"
    name_arg: str = "templatename"
    params_arg: str = "params"
    mapper: Mapper | None = None


# -- mypy types -> annotation source ----------------------------------------


def to_source(typ: Type, imports: set[str]) -> str:
    """Python source for a mypy type; collects the modules it needs."""
    typ = get_proper_type(typ)
    if isinstance(typ, AnyType):
        imports.add("typing")
        return "typing.Any"
    if isinstance(typ, NoneType):
        return "None"
    if isinstance(typ, LiteralType):
        return to_source(typ.fallback, imports)
    if isinstance(typ, Instance):
        info = typ.type
        if "<locals>" in info.fullname:
            imports.add("typing")
            return "typing.Any"
        if info.fullname == "builtins.function":
            imports.add("typing")
            return "typing.Callable[..., typing.Any]"
        if info.module_name == "builtins":
            name = info.fullname.removeprefix("builtins.")
        else:
            imports.add(info.module_name)
            name = info.fullname
        if typ.args:
            args = ", ".join(to_source(a, imports) for a in typ.args)
            return f"{name}[{args}]"
        return name
    if isinstance(typ, UnionType):
        parts: list[str] = []
        for item in typ.items:
            source = to_source(item, imports)
            if source not in parts:
                parts.append(source)
        parts.sort(key=lambda p: p == "None")  # None last, as is customary
        return " | ".join(parts)
    if isinstance(typ, TupleType):
        if typ.partial_fallback.type.fullname != "builtins.tuple":
            return to_source(typ.partial_fallback, imports)
        if not typ.items:
            return "tuple[()]"
        return f"tuple[{', '.join(to_source(i, imports) for i in typ.items)}]"
    if isinstance(typ, TypedDictType):
        info = typ.fallback.type
        if info.fullname != "typing._TypedDict":
            imports.add(info.module_name)
            return info.fullname
        imports.add("typing")
        return "dict[str, typing.Any]"
    if isinstance(typ, TypeType):
        return f"type[{to_source(typ.item, imports)}]"
    if isinstance(typ, CallableType):
        if typ.is_type_obj():  # a class passed as a value
            return f"type[{to_source(typ.ret_type, imports)}]"
        imports.add("typing")
        ret = to_source(typ.ret_type, imports)
        if all(kind == ARG_POS for kind in typ.arg_kinds):
            args = ", ".join(to_source(a, imports) for a in typ.arg_types)
            return f"typing.Callable[[{args}], {ret}]"
        return f"typing.Callable[..., {ret}]"
    imports.add("typing")
    return "typing.Any"  # type variables, partial types, errors, ...


# -- the mypy plugin ----------------------------------------------------------


class CollectPlugin(Plugin):
    def __init__(self, options: Options, spec: Spec, sites: list[Site]) -> None:
        super().__init__(options)
        self.spec = spec
        self.sites = sites
        self.seen: set[tuple[str, int, int]] = set()

    def get_method_hook(self, fullname: str) -> Callable[[MethodContext], Type] | None:
        # mypy asks with the receiver's class, which may be a subclass of the one
        # that defines the method; _hook checks the MRO.
        method = self.spec.function.rpartition(".")[2]
        return self._method_hook if fullname.endswith(f".{method}") else None

    def _method_hook(self, ctx: MethodContext) -> Type:
        owner = self.spec.function.rpartition(".")[0]
        receiver = get_proper_type(ctx.type)
        if isinstance(receiver, Instance) and any(
            base.fullname == owner for base in receiver.type.mro
        ):
            return self._hook(ctx)
        return ctx.default_return_type

    def get_function_hook(
        self, fullname: str
    ) -> Callable[[FunctionContext], Type] | None:
        return self._hook if fullname == self.spec.function else None

    def value_type(
        self, ctx: MethodContext | FunctionContext, value: Expression
    ) -> Type | None:
        """The type of a dict value as if it stood on its own.

        mypy checks a dict literal argument against ``dict[str, Any]``, which
        makes ``[Row()]`` a ``list[Any]``; inferred without that context
        it is a ``list[Row]``.
        """
        checker = ctx.api
        try:
            with checker.msg.filter_errors():  # type: ignore[attr-defined]
                return checker.expr_checker.accept(value)  # type: ignore[attr-defined]
        except Exception:
            return checker.lookup_type_or_none(value)  # type: ignore[attr-defined]

    def _hook(self, ctx: MethodContext | FunctionContext) -> Type:
        names = ctx.callee_arg_names
        if self.spec.name_arg not in names:
            return ctx.default_return_type
        name_exprs = ctx.args[names.index(self.spec.name_arg)]
        if not (name_exprs and isinstance(name_exprs[0], StrExpr)):
            return ctx.default_return_type  # dynamic template name
        where = ctx.context
        mark = (str(getattr(ctx.api, "path", "")), where.line, where.column)
        if mark in self.seen:
            return ctx.default_return_type
        self.seen.add(mark)

        scope = getattr(ctx.api, "tscope", None)
        module = scope.current_module_id() if scope else ""
        active = scope.classes[-1] if scope and scope.classes else None
        template = name_exprs[0].value
        if self.spec.mapper is not None:
            mapped = self.spec.mapper(module, active.name if active else None, template)
            if mapped is None:
                return ctx.default_return_type
            template = mapped
        path = os.path.relpath(str(getattr(ctx.api, "path", module)))
        site = Site(template, f"{path}:{where.line}")

        params = (
            names.index(self.spec.params_arg) if self.spec.params_arg in names else -1
        )
        exprs = ctx.args[params] if params >= 0 else []
        if exprs and isinstance(exprs[0], DictExpr):
            for key, value in exprs[0].items:
                if not isinstance(key, StrExpr):  # `**other` or a computed key
                    site.complete = False
                    continue
                typ = self.value_type(ctx, value)
                site.keys[key.value] = (
                    to_source(typ, site.imports) if typ is not None else "typing.Any"
                )
        elif exprs:
            site.complete = False  # a variable, a call, ... we cannot see inside
        self.sites.append(site)
        return ctx.default_return_type


def collect(spec: Spec, mypy_args: list[str]) -> tuple[list[Site], list[str]]:
    """Run mypy over the project and return the render sites it saw."""
    sources, options = process_options(mypy_args)
    options.incremental = False
    sites: list[Site] = []
    messages: list[str] = []

    def flush(filename: str | None, new_messages: list[str], serious: bool) -> None:
        messages.extend(new_messages)

    try:
        build.build(
            sources,
            options,
            flush_errors=flush,
            extra_plugins=[CollectPlugin(options, spec, sites)],
        )
    except CompileError:
        pass  # type errors elsewhere do not matter, the hooks already ran
    return sites, messages


# -- merging and writing ------------------------------------------------------


@dataclass
class Context:
    template: str
    class_name: str
    keys: dict[str, tuple[str, bool]]  # key -> (annotation, required)
    sites: list[Site]
    imports: set[str]

    @property
    def complete(self) -> bool:
        return all(site.complete for site in self.sites)


def class_name(template: str, keep_suffix: bool = False) -> str:
    stem = template if keep_suffix else re.sub(r"\.[A-Za-z0-9]+$", "", template)
    parts = [p for p in re.split(r"[^A-Za-z0-9]+", stem) if p]
    return "".join(p[:1].upper() + p[1:] for p in parts) + "Context"


def split_union(annotation: str) -> list[str]:
    """Split ``A | B[C | D] | None`` at the top-level bars."""
    parts, depth, start = [], 0, 0
    for index, char in enumerate(annotation):
        if char in "[(":
            depth += 1
        elif char in "])":
            depth -= 1
        elif char == "|" and depth == 0:
            parts.append(annotation[start:index].strip())
            start = index + 1
    parts.append(annotation[start:].strip())
    return parts


def merge(sites: list[Site]) -> list[Context]:
    by_template: dict[str, list[Site]] = {}
    for site in sites:
        by_template.setdefault(site.template, []).append(site)
    contexts = []
    used: set[str] = set()
    for template, group in sorted(by_template.items()):
        keys: dict[str, tuple[str, bool]] = {}
        for key in dict.fromkeys(k for s in group for k in s.keys):
            having = [s for s in group if key in s.keys]
            members = dict.fromkeys(m for s in having for m in split_union(s.keys[key]))
            ordered = sorted(members, key=lambda m: m == "None")  # None last
            keys[key] = (" | ".join(ordered), len(having) == len(group))
        name = class_name(template)
        if name in used:  # index.html vs index.txt
            name = class_name(template, keep_suffix=True)
        used.add(name)
        contexts.append(
            Context(
                template,
                name,
                keys,
                group,
                set().union(*(s.imports for s in group)),
            )
        )
    return contexts


def render_module(
    contexts: list[Context], module: str, base: str | None, include_incomplete: bool
) -> str:
    imports = sorted(set().union(*(c.imports for c in contexts)) - {"builtins"})
    lines = [
        "# Generated by `python -m tplcheck.collect`; do not edit.",
        "from __future__ import annotations",
        "",
        "from typing import TYPE_CHECKING",
        "",
        "from typing_extensions import NotRequired, TypedDict",
    ]
    if base:
        base_module, _, base_name = base.rpartition(".")
        lines.append(f"from {base_module} import {base_name}")
    lines += ["", "if TYPE_CHECKING:"]
    lines += [f"    import {name}" for name in imports] or ["    pass"]
    mapping: list[str] = []
    for context in contexts:
        usable = context.complete or include_incomplete
        lines += ["", ""]
        parent = base.rpartition(".")[2] if base else "TypedDict"
        lines.append(f"class {context.class_name}({parent}):")
        lines.append('    """' + context.template)
        lines.append("")
        for site in context.sites:
            flag = "" if site.complete else "  (not a dict literal: keys unknown)"
            lines.append(f"    {site.location}{flag}")
        lines.append('    """')
        lines.append("")
        body = 0
        for key, (annotation, required) in context.keys.items():
            if not key.isidentifier() or keyword.iskeyword(key):
                lines.append(f"    # skipped key {key!r}: not usable as a field name")
                continue
            wrapped = annotation if required else f"NotRequired[{annotation}]"
            lines.append(f"    {key}: {wrapped}")
            body += 1
        if not body and not any(line.startswith("    #") for line in lines[-3:]):
            lines.append("    pass")
        if usable:
            mapping.append(
                f"    {context.template!r}: {module + '.' + context.class_name!r},"
            )
    lines += ["", "", "TEMPLATE_CONTEXTS: dict[str, str] = {", *mapping, "}", ""]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tplcheck.collect", description=__doc__)
    parser.add_argument(
        "--render", required=True, help="fullname of the render function"
    )
    parser.add_argument("--template-arg", default="templatename")
    parser.add_argument("--params-arg", default="params")
    parser.add_argument(
        "--module", required=True, help="dotted name the output will have"
    )
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--base-context", help="TypedDict every context extends")
    parser.add_argument(
        "--mapper",
        help="module:function(module, class, template) -> template path or None",
    )
    parser.add_argument(
        "--include-incomplete",
        action="store_true",
        help="also map templates rendered with a non-literal dict somewhere",
    )
    args, mypy_args = parser.parse_known_args(argv)
    add_import_paths()
    mypy_args = [a for a in mypy_args if a != "--"]
    mapper = None
    if args.mapper:
        module, _, function = args.mapper.partition(":")
        mapper = getattr(importlib.import_module(module), function)
    spec = Spec(args.render, args.template_arg, args.params_arg, mapper)
    sites, _ = collect(spec, mypy_args)
    contexts = merge(sites)
    args.out.write_text(
        render_module(
            contexts, args.module, args.base_context, args.include_incomplete
        ),
        encoding="utf-8",
    )
    complete = sum(c.complete for c in contexts)
    print(
        f"{len(sites)} render calls, {len(contexts)} templates, "
        f"{complete} with complete contexts -> {args.out}"
    )
    for context in contexts:
        if not context.complete:
            where = next(s.location for s in context.sites if not s.complete)
            print(f"  incomplete: {context.template} (e.g. {where})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
