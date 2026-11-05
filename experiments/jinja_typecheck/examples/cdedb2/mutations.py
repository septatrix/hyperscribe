"""Do realistic mistakes in the cdedb2 index page get caught?

Applies one small edit at a time to the prepared templates and reports whether
the checker finds something it did not find in the unmodified templates::

    python mutations.py PATH/TO/cdedb2
"""

from __future__ import annotations

import re
import shutil
import sys
import tempfile
from pathlib import Path

from prepare import main as prepare
from tplcheck.runner import check
from tplcheck.shadow import Config

HERE = Path(__file__).parent
CONFIG = Config(
    extensions=("jinja2.ext.i18n", "jinja2.ext.do", "jinja2.ext.loopcontrols"),
    tests_module="cdedb_tests",
    filters_registry="cdedb_filters:JINJA_FILTERS",
    globals_module="cdedb_globals",
)

# (description, template, old, new) -- only the first occurrence is replaced
MUTATIONS = [
    ("attribute typo on an Event", "web/core/index.tmpl", "event.id", "event.idd"),
    (
        "key typo on the dashboard",
        "web/core/index.tmpl",
        "dashboard['genesis_cases'] > 0",
        "dashboard['genesis_case'] > 0",
    ),
    (
        "optional dashboard key read without its `in` guard",
        "web/core/index.tmpl",
        "{% if 'genesis_cases' in dashboard and dashboard['genesis_cases'] > 0 or",
        "{% if dashboard['genesis_cases'] > 0 or",
    ),
    (
        "wrong key type",
        "web/core/index.tmpl",
        "dashboard['orga_registrations'][event.id]",
        "dashboard['orga_registrations'][event.title]",
    ),
    (
        "unknown keyword for a macro",
        "web/core/index.tmpl",
        'util.input_text(type="search", name="phrase"',
        'util.input_text(type="search", nam="phrase"',
    ),
    (
        "typo in a context variable",
        "web/core/index.tmpl",
        "cdedblink('core/admin_show_user')",
        "cdedblnk('core/admin_show_user')",
    ),
    (
        "typo on the user",
        "web/core/index.tmpl",
        "user.admin_views.has(",
        "user.admin_viewz.has(",
    ),
    (
        "optional datetime compared without a check",
        "web/core/index.tmpl",
        "{% if event.registration_start and event.is_registration_approved %}",
        "{% if event.is_registration_approved %}",
    ),
    (
        "arithmetic on a datetime",
        "web/core/index.tmpl",
        "event['registration_start'] <= dashboard['present']",
        "event['registration_start'] <= dashboard['present'] + 1",
    ),
    (
        "wrong keyword for a filter",
        "web/core/index.tmpl",
        "|date(lang=lang)",
        "|date(lan=lang)",
    ),
    (
        "unknown filter",
        "web/core/index.tmpl",
        "|xdictsort('title')",
        "|xdictsrt('title')",
    ),
    (
        "macro in the library renamed (call site breaks)",
        "web/util.tmpl",
        "{% macro breadcrumb_link(",
        "{% macro breadcrumb_lnk(",
    ),
]


def errors(templates: Path, shadow: Path) -> set[str]:
    result = check(
        templates,
        shadow,
        None,
        ["--config-file", str(HERE.parent.parent / "mypy.ini"), "--no-incremental"],
        CONFIG,
    )
    return {
        re.sub(r"^.*?/(web/)", r"\1", line)
        for line in result.output.splitlines()
        if "error:" in line
    }


def main(checkout: Path) -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        prepare(checkout, root / "pristine")
        baseline = errors(root / "pristine", root / "shadow")
        print(f"baseline: {len(baseline)} findings in the unmodified templates")
        caught = 0
        for description, name, old, new in MUTATIONS:
            work = root / "work"
            shutil.rmtree(work, ignore_errors=True)
            shutil.copytree(root / "pristine", work)
            path = work / name
            text = path.read_text(encoding="utf-8")
            if old not in text:
                print(f"  SKIPPED  {description}: pattern not found")
                continue
            path.write_text(text.replace(old, new, 1), encoding="utf-8")
            new_errors = errors(work, root / "shadow") - baseline
            caught += bool(new_errors)
            status = "caught" if new_errors else "MISSED"
            print(f"  {status:7}  {description}")
            for line in sorted(new_errors)[:1]:
                print(f"           {line}")
        print(f"{caught} of {len(MUTATIONS)} caught")
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
