"""Cheetah base page template class with replaceable page sections."""

from pathlib import Path

from Cheetah.Template import Template

_template_path = Path(__file__).parent / "templates" / "base.cheetah"
BasePage = Template.compile(file=str(_template_path))
