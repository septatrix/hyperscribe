"""Sphinx configuration for the hyperscribe documentation."""

from importlib.metadata import version as _version

project = "hyperscribe"
author = "Septatrix"
copyright = "Septatrix"
release = _version("hyperscribe")
version = release

extensions = [
    "myst_parser",
    "sphinx.ext.autodoc",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
    "sphinx_copybutton",
]

myst_enable_extensions = ["colon_fence"]
myst_heading_anchors = 3

autodoc_member_order = "bysource"
autodoc_typehints = "signature"
autodoc_typehints_format = "short"
python_use_unqualified_type_names = True

# The examples in the guide are run by ``make doctest``.
# They write to stdout, which the builder compares with the expected output.
doctest_global_setup = """
import sys
from types import SimpleNamespace

from hyperscribe import DocWriter, escape, escape_silent, trust


class Stdout:
    # Look the stream up on every write, because the builder replaces it per block.
    def write(self, value):
        return sys.stdout.write(value)


doc, t, v = DocWriter(Stdout()).parts

user = SimpleNamespace(name="Ada & co", id=7)
count = 3
url = "/docs"
external = False
device = {}
rendered = "<b>trusted</b>"
code = "a < b"
items = [
    SimpleNamespace(name="One", visible=True, done=True),
    SimpleNamespace(name="Hidden", visible=False, done=False),
    SimpleNamespace(name="Two", visible=True, done=False),
]
item = items[0]
"""

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "markupsafe": ("https://markupsafe.palletsprojects.com/en/stable/", None),
}

html_theme = "furo"
html_title = f"hyperscribe {release}"
html_theme_options = {
    "source_repository": "https://github.com/septatrix/hyperscribe/",
    "source_branch": "main",
    "source_directory": "docs/",
}
