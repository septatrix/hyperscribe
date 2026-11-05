"""Copy a few cdedb2 templates and give them tplcheck headers.

The headers live here, not in cdedb2, so that its checkout stays untouched
and none of its templates are vendored into this repository::

    python prepare.py PATH/TO/cdedb2 build/templates
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

PREFIX = "cdedb/frontend/templates/"

# template -> header body (see tplcheck.shadow for the format)
HEADERS: dict[str, str] = {
    "web/util.tmpl": """
        context: cdedb_ctx.OptionalPageContext
        self-name: util
        from collections.abc import Callable
        from typing import Any
    """,
    "web/base.tmpl": """
        context: cdedb_ctx.OptionalPageContext
    """,
    "web/core/base.tmpl": """
        context: cdedb_ctx.OptionalPageContext
    """,
    "web/core/index.tmpl": """
        context: cdedb_ctx.CoreIndexContext
    """,
}


def main(checkout: Path, target: Path) -> None:
    for name, body in HEADERS.items():
        source = (checkout / PREFIX / name).read_text(encoding="utf-8")
        header = "{# tplcheck\n" + "\n".join(
            "   " + line.strip() for line in body.strip().splitlines()
        )
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(header + "\n-#}\n" + source, encoding="utf-8")
    shutil.rmtree(target / "__pycache__", ignore_errors=True)
    print(f"prepared {len(HEADERS)} templates in {target}")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
