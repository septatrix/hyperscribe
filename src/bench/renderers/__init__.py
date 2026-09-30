"""Renderer implementations used by the benchmark."""

# TODO use lazy import to not load those which are not run
from bench.renderers.airium import render as render_airium
from bench.renderers.cheetah import render as render_cheetah
from bench.renderers.dominate import render as render_dominate
from bench.renderers.element_tree import render as render_element_tree
from bench.renderers.hyperscribe import render as render_hyperscribe
from bench.renderers.hyperscript import render as render_hyperscript
from bench.renderers.jinja import render as render_jinja
from bench.renderers.ludic import render as render_ludic
from bench.renderers.mako import render as render_mako
from bench.renderers.tagflow import render as render_tagflow
from bench.renderers.yattag import render as render_yattag

RENDERERS = {
    "Jinja": render_jinja,
    "Airium": render_airium,
    "Yattag": render_yattag,
    "Hyperscribe": render_hyperscribe,
    "Tagflow": render_tagflow,
    "dominate": render_dominate,
    "Ludic": render_ludic,
    "ElementTree": render_element_tree,
    "Hyperscript": render_hyperscript,
    "Mako": render_mako,
    "Cheetah3": render_cheetah,
}
