"""``python -m tplcheck TEMPLATE_DIR`` -- type-check annotated Jinja templates."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .runner import check


def main() -> int:
    parser = argparse.ArgumentParser(prog="tplcheck", description=__doc__)
    parser.add_argument("templates", type=Path, help="directory of templates")
    parser.add_argument("--shadow-dir", type=Path, default=Path("build/tplcheck"))
    parser.add_argument(
        "--stub", type=Path, help="write a typed get_template stub here"
    )
    parser.add_argument("--config-file", help="mypy config to use")
    args, mypy_args = parser.parse_known_args()
    if args.config_file:
        mypy_args = ["--config-file", args.config_file, *mypy_args]
    result = check(args.templates, args.shadow_dir, args.stub, mypy_args)
    print(result.output)
    return result.status


if __name__ == "__main__":
    sys.exit(main())
