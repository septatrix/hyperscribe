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

intersphinx_mapping = {"python": ("https://docs.python.org/3", None)}

html_theme = "furo"
html_title = f"hyperscribe {release}"
html_theme_options = {
    "source_repository": "https://github.com/septatrix/hyperscribe/",
    "source_branch": "main",
    "source_directory": "docs/",
}
