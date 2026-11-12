"""mypy plugin that gives ``getattr_(obj, "name")`` the type of Jinja's ``obj.name``.

Jinja tries attribute access first and falls back to item access.
Which one applies depends on the static type of ``obj``,
so the shadow modules defer the decision to this plugin:

* TypedDict: the value type of the key
  (``UndefinedValue`` is added for optional keys unless a test narrowed it),
* any other class: the type of the attribute,
  or of ``__getitem__``'s result for mappings that lack such an attribute,
* unions: the union of the member types,
* ``Any``: ``Any``.
"""

from __future__ import annotations

from collections.abc import Callable

from mypy.checkmember import analyze_member_access
from mypy.expandtype import expand_type_by_instance
from mypy.nodes import IndexExpr, StrExpr
from mypy.plugin import FunctionContext, Plugin
from mypy.typeops import make_simplified_union
from mypy.types import (
    AnyType,
    CallableType,
    Instance,
    LiteralType,
    NoneType,
    TupleType,
    Type,
    TypedDictType,
    TypeOfAny,
    UnionType,
    get_proper_type,
)


def _member(ctx: FunctionContext, typ: Type, name: str, narrowed: str) -> Type:
    proper = get_proper_type(typ)
    if isinstance(proper, AnyType):
        return proper
    if isinstance(proper, UnionType):
        return make_simplified_union(
            [_member(ctx, item, name, narrowed) for item in proper.items]
        )
    if isinstance(proper, NoneType):
        ctx.api.fail(f'"None" has no attribute "{name}"', ctx.context)
        return AnyType(TypeOfAny.from_error)
    if isinstance(proper, TypedDictType):
        if name in proper.items:
            value = proper.items[name]
            if name in proper.required_keys or narrowed in ("defined", "truthy"):
                return _narrow(value, narrowed)
            # An optional key reads as Jinja's Undefined when it is missing.
            undefined = ctx.api.named_generic_type("tplcheck.UndefinedValue", [])
            return make_simplified_union([_narrow(value, narrowed), undefined])
        if proper.fallback.type.has_readable_member(name):
            return _member(ctx, proper.fallback, name, narrowed)  # .items / .keys
        ctx.api.fail(
            f'TypedDict "{proper.fallback.type.name}" has no key "{name}"', ctx.context
        )
        return AnyType(TypeOfAny.from_error)
    if isinstance(proper, Instance):
        if not proper.type.has_readable_member(name):
            getitem = proper.type.get_method("__getitem__")
            signature = getitem.type if getitem is not None else None
            if isinstance(signature, CallableType):
                return _narrow(
                    expand_type_by_instance(signature, proper).ret_type, narrowed
                )
    return _narrow(
        analyze_member_access(
            name,
            proper,
            ctx.context,
            is_lvalue=False,
            is_super=False,
            is_operator=False,
            original_type=proper,
            chk=ctx.api,  # type: ignore[arg-type]
        ),
        narrowed,
    )


def _narrow(typ: Type, narrowed: str) -> Type:
    """Drop ``None`` where a test established the value is not ``None``."""
    if narrowed not in ("notnone", "truthy"):
        return typ
    proper = get_proper_type(typ)
    if isinstance(proper, UnionType):
        kept = [i for i in proper.items if not isinstance(get_proper_type(i), NoneType)]
        return make_simplified_union(kept) if kept else typ
    return typ


def _getattr_hook(ctx: FunctionContext) -> Type:
    name_expr = ctx.args[1][0]
    if not isinstance(name_expr, StrExpr):
        return ctx.default_return_type
    flag = ctx.args[2][0] if len(ctx.args) > 2 and ctx.args[2] else None
    narrowed = flag.value if isinstance(flag, StrExpr) else ""
    return _member(ctx, ctx.arg_types[0][0], name_expr.value, narrowed)


def _index(ctx: FunctionContext, node: IndexExpr, typ: Type, arg: Type) -> Type:
    proper = get_proper_type(typ)
    if isinstance(proper, AnyType):
        return proper
    if isinstance(proper, UnionType):
        return make_simplified_union(
            [_index(ctx, node, item, arg) for item in proper.items]
        )
    subscriptable = (
        isinstance(proper, TupleType | TypedDictType)
        or (
            isinstance(proper, Instance)
            and proper.type.has_readable_member("__getitem__")
        )
        or (isinstance(proper, Instance) and proper.type.fullname == "builtins.type")
    )
    if not subscriptable and isinstance(proper, Instance):
        # Jinja: `obj[name]` is `getattr(obj, name)` if `obj` cannot be indexed.
        if may_be_str(arg):
            return AnyType(TypeOfAny.special_form)
    checker = ctx.api.expr_checker  # type: ignore[attr-defined]
    return checker.visit_index_with_type(proper, node)  # type: ignore[no-any-return]


def may_be_str(typ: Type) -> bool:
    proper = get_proper_type(typ)
    if isinstance(proper, AnyType):
        return True
    if isinstance(proper, UnionType):
        return any(may_be_str(item) for item in proper.items)
    if isinstance(proper, LiteralType):
        proper = proper.fallback
    return isinstance(proper, Instance) and proper.type.fullname == "builtins.str"


def _getitem_hook(ctx: FunctionContext) -> Type:
    base, index = ctx.args[0][0], ctx.args[1][0]
    node = IndexExpr(base, index)
    node.set_line(ctx.context)
    return _index(ctx, node, ctx.arg_types[0][0], ctx.arg_types[1][0])


class TplCheckPlugin(Plugin):
    def get_function_hook(
        self, fullname: str
    ) -> Callable[[FunctionContext], Type] | None:
        if fullname == "tplcheck.getattr_":
            return _getattr_hook
        if fullname == "tplcheck.getitem_":
            return _getitem_hook
        return None


def plugin(version: str) -> type[Plugin]:
    return TplCheckPlugin
