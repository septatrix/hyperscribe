"""``python -m tplcheck TEMPLATE_DIR`` -- type-check annotated Jinja templates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .runner import check, coverage
from .shadow import Config


def main() -> int:
    parser = argparse.ArgumentParser(prog="tplcheck", description=__doc__)
    parser.add_argument("templates", type=Path, help="directory of templates")
    parser.add_argument("--shadow-dir", type=Path, default=Path("build/tplcheck"))
    parser.add_argument(
        "--stub", type=Path, help="write a typed get_template stub here"
    )
    parser.add_argument("--config-file", help="mypy config to use")
    parser.add_argument(
        "--extension",
        action="append",
        default=[],
        help="Jinja extension the templates need, e.g. jinja2.ext.i18n",
    )
    parser.add_argument(
        "--environment-factory",
        help="module:function returning the Environment to parse with",
    )
    parser.add_argument("--filters-module", help="typed stand-ins for custom filters")
    parser.add_argument("--tests-module", help="typed stand-ins for custom tests")
    parser.add_argument("--globals-module", help="typed stand-ins for custom globals")
    parser.add_argument(
        "--coverage",
        action="store_true",
        help="only report which templates can be translated, annotated or not",
    )
    args, mypy_args = parser.parse_known_args()
    config = Config(
        extensions=tuple(args.extension),
        environment_factory=args.environment_factory,
        filters_module=args.filters_module,
        tests_module=args.tests_module,
        globals_module=args.globals_module,
    )
    if args.coverage:
        result = coverage(args.templates, config)
    else:
        if args.config_file:
            mypy_args = ["--config-file", args.config_file, *mypy_args]
        result = check(args.templates, args.shadow_dir, args.stub, mypy_args, config)
    print(result.output)
    return result.status


if __name__ == "__main__":
    sys.exit(main())
